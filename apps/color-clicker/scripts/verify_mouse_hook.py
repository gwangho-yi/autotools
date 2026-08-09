#!/usr/bin/env python3
"""저수준 마우스 훅 이중 설치 안전성 검증 도구 (통합 전 사전 검증 전용).

`keyboard.GlobalHotKeys`(저수준 키보드 훅)가 이미 도는 프로세스에 저수준 마우스
훅을 하나 더 얹어도 안전한지만 확인한다. 이 프로젝트는 예전에 Windows에서 두 번째
pynput '키보드' 훅을 이중 설치했다가 네이티브 크래시를 겪은 적이 있다
(shared/src/autotools_shared/overlay/color_picker.py:174-178). 이번엔 키보드+마우스
조합이라 괜찮을 가능성이 높지만 추측으로 넘어갈 일이 아니라 실측한다.

★ 이 파일은 검증 도구다. 엔진/UI에 기능을 통합하지 않는다.

안전 요건(설계보다 우선):
  1. 억제 구간은 최대 10초. 워치독 스레드가 시간 초과 시 무조건 훅을 해제한다.
     메인 로직이 멈춰도 워치독은 살아 있어야 한다.
  2. 키보드는 절대 막지 않는다. Ctrl+F7 탈출구가 항상 살아 있어야 한다.
  3. 모든 예외 경로에서 finally로 훅을 해제한다.
  4. 억제 시작 전에 경고를 출력하고 Enter를 기다린다.

사용법:
    python scripts/verify_mouse_hook.py                  # 전체 검증
    python scripts/verify_mouse_hook.py --selftest-watchdog   # 워치독만 시험
"""
from __future__ import annotations

import argparse
import ctypes
import os
import platform
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

LOG_PATH = Path.home() / "verify-mouse-hook.log"

SUPPRESS_MAX_S = 10.0     # 안전 요건 1 — 타협 불가
PHASE1_WAIT_S = 10.0
PHASE2_WAIT_S = 30.0
PHASE3_OBSERVE_S = 8.0

# MSLLHOOKSTRUCT.flags (Win32 전용)
LLMHF_INJECTED = 0x01
LLMHF_LOWER_IL_INJECTED = 0x02
INJECTED_MASK = LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED

IS_WINDOWS = sys.platform == "win32"

PASS, FAIL, SKIP, UNKNOWN = "PASS", "FAIL", "SKIP", "판정불가"


class Logger:
    """콘솔과 ~/verify-mouse-hook.log에 동시 기록한다."""

    def __init__(self, path: Path = LOG_PATH):
        self.path = path
        try:
            self._fh = open(path, "a", encoding="utf-8")
        except OSError as exc:      # 로그 파일을 못 열어도 검증은 계속한다
            print(f"[경고] 로그 파일을 열 수 없습니다: {exc}")
            self._fh = None

    def __call__(self, message: str = "") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}" if message else ""
        print(line, flush=True)
        if self._fh is not None:
            self._fh.write(line + "\n")
            self._fh.flush()

    def rule(self, title: str = "") -> None:
        self("")
        self("=" * 68)
        if title:
            self(title)
            self("=" * 68)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


class HookWatchdog:
    """억제 훅을 timeout_s 뒤 무조건 해제하는 감시 스레드.

    메인 로직이 데드락이나 무한 루프에 빠져도 이 스레드는 계속 돌아야 하므로
    메인 쪽 상태를 일절 참조하지 않는다. release는 여러 경로(워치독/정상 종료/
    예외)에서 불릴 수 있어 락으로 1회만 실행되도록 보장한다.
    """

    def __init__(self, timeout_s: float, release, log: Logger, label: str = "억제"):
        self._timeout_s = timeout_s
        self._release = release
        self._log = log
        self._label = label
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._released = False
        self.fired = False              # 워치독이 강제 해제했는가
        self.released_by: str | None = None
        self._thread = threading.Thread(
            target=self._run, name="hook-watchdog", daemon=True
        )

    def start(self) -> "HookWatchdog":
        self._thread.start()
        return self

    def _run(self) -> None:
        if self._cancel.wait(self._timeout_s):
            return                      # 정상 종료 — 해제는 메인이 이미 했다
        self.fired = True
        self._log(f"★ 워치독 발동 — {self._timeout_s:.0f}초 초과, {self._label} 훅을 강제 해제합니다")
        self.release("watchdog")

    def release(self, who: str) -> bool:
        """훅을 해제한다. 이미 해제됐으면 아무것도 하지 않고 False를 반환."""
        with self._lock:
            if self._released:
                return False
            self._released = True
            self.released_by = who
        try:
            self._release()
        except Exception as exc:        # 해제 실패는 치명적이므로 크게 남긴다
            self._log(f"[!!] 훅 해제 중 예외({who}): {exc!r}")
            return False
        self._log(f"훅 해제 완료 (by {who})")
        return True

    def cancel(self) -> None:
        self._cancel.set()

    def join(self, timeout: float = 2.0) -> None:
        self._thread.join(timeout)


def _is_admin() -> str:
    if IS_WINDOWS:
        try:
            return "예" if ctypes.windll.shell32.IsUserAnAdmin() else "아니오"
        except Exception as exc:
            return f"확인 실패({exc!r})"
    try:
        return "예(root)" if os.geteuid() == 0 else "아니오"
    except AttributeError:
        return "확인 불가"


def _confirm_gate(log: Logger, seconds: float, what: str) -> bool:
    """안전 요건 4 — 억제 전 경고 + Enter 대기. 비대화형이면 건너뛴다."""
    log("")
    log(f"⚠  지금부터 최대 {seconds:.0f}초간 {what}")
    log(f"⚠  키보드는 막지 않습니다. Ctrl+F7과 Ctrl+C는 계속 살아 있습니다.")
    log(f"⚠  워치독이 {seconds:.0f}초 뒤 무조건 해제합니다.")
    if not sys.stdin or not sys.stdin.isatty():
        log("→ 비대화형 실행(stdin이 TTY가 아님). 안전을 위해 이 단계를 건너뜁니다.")
        return False
    log("→ 계속하려면 Enter, 중단하려면 Ctrl+C")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        log("→ 사용자가 중단했습니다. 이 단계를 건너뜁니다.")
        return False
    return True


def _screen_center() -> tuple[int, int]:
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0) // 2, user32.GetSystemMetrics(1) // 2
        except Exception:
            pass
    return 500, 500


# --------------------------------------------------------------------------
# Phase 0 — 환경
# --------------------------------------------------------------------------
def phase0_environment(log: Logger) -> dict:
    log.rule("Phase 0 — 환경")
    info: dict = {}

    log(f"OS            : {platform.platform()}")
    log(f"sys.platform  : {sys.platform}")
    log(f"Python        : {sys.version.split()[0]} ({sys.executable})")
    log(f"관리자 권한   : {_is_admin()}")

    try:
        import importlib.metadata as md
        version = md.version("pynput")
    except Exception as exc:
        version = f"확인 실패({exc!r})"
    log(f"pynput        : {version}")
    info["pynput"] = version

    # 보고 항목 — API가 문서대로 존재하는가 (없으면 ctypes로 SetWindowsHookEx 직접 호출 필요)
    from pynput import mouse

    has_suppress = hasattr(mouse.Listener, "suppress_event")
    log(f"mouse.Listener.suppress_event 존재 : {has_suppress}")
    info["has_suppress_event"] = has_suppress

    accepts_filter = False
    try:
        probe = mouse.Listener(win32_event_filter=lambda msg, data: True)
        accepts_filter = True
        if IS_WINDOWS:
            # 접두사가 벗겨져 _options['event_filter']로 들어갔는지까지 확인
            accepts_filter = "event_filter" in getattr(probe, "_options", {})
        del probe
    except Exception as exc:
        log(f"win32_event_filter kwarg 시험 중 예외: {exc!r}")
    log(f"win32_event_filter kwarg 수용     : {accepts_filter}"
        f"{'' if IS_WINDOWS else ' (macOS에선 무시되는 것이 정상)'}")
    info["accepts_win32_event_filter"] = accepts_filter

    if IS_WINDOWS and not (has_suppress and accepts_filter):
        log("[!!] pynput API가 기대와 다릅니다 — ctypes로 SetWindowsHookEx를 "
            "직접 호출해야 합니다. 즉시 보고할 것.")
    return info


# --------------------------------------------------------------------------
# Phase 1 — 기준선 (GlobalHotKeys 단독)
# --------------------------------------------------------------------------
def phase1_baseline(log: Logger, hotkey_fired: threading.Event):
    log.rule("Phase 1 — 기준선: GlobalHotKeys 단독 설치")
    from pynput import keyboard

    def on_hotkey() -> None:
        hotkey_fired.set()
        log("  ✓ Ctrl+F7 감지됨")

    try:
        hk = keyboard.GlobalHotKeys({"<ctrl>+<f7>": on_hotkey})
        hk.start()
        hk.wait()
    except Exception as exc:
        log(f"[!!] GlobalHotKeys 설치 실패: {exc!r}")
        return None, FAIL, f"설치 실패: {exc!r}"

    log(f"GlobalHotKeys 설치 성공. {PHASE1_WAIT_S:.0f}초 안에 Ctrl+F7을 눌러주세요.")
    deadline = time.monotonic() + PHASE1_WAIT_S
    while time.monotonic() < deadline and not hotkey_fired.is_set():
        remaining = deadline - time.monotonic()
        log(f"  대기 중... 남은 {remaining:4.1f}초")
        time.sleep(1.0)

    if not hk.running:
        log("[!!] 리스너가 죽었습니다.")
        return hk, FAIL, "리스너 비정상 종료"
    if hotkey_fired.is_set():
        return hk, PASS, "Ctrl+F7 감지 확인"
    # 설치는 됐지만 아무도 안 눌렀을 수 있다 — 실패로 단정하지 않는다
    log("입력이 관찰되지 않았습니다(설치 자체는 정상). 미확인으로 남깁니다.")
    return hk, UNKNOWN, "설치는 성공, 키 입력 미관찰"


# --------------------------------------------------------------------------
# Phase 2 — 이중 훅 생존 (★ 핵심)
# --------------------------------------------------------------------------
def phase2_dual_hook(log: Logger, hk, hotkey_fired: threading.Event):
    log.rule("Phase 2 — 이중 훅 생존 (★ 이 작업의 핵심)")
    from pynput import mouse

    if hk is None or not hk.running:
        log("[!!] 키보드 훅이 살아 있지 않아 이중 설치를 시험할 수 없습니다.")
        return FAIL, "키보드 훅 부재"

    counters = {"move": 0, "click": 0, "scroll": 0}

    def on_move(x, y, injected=False):
        counters["move"] += 1

    def on_click(x, y, button, pressed, injected=False):
        counters["click"] += 1

    def on_scroll(x, y, dx, dy, injected=False):
        counters["scroll"] += 1

    kwargs = {}
    if IS_WINDOWS:
        # 관찰만 한다 — 억제하지 않음(True 반환)
        kwargs["win32_event_filter"] = lambda msg, data: True

    log("키보드 훅을 살려둔 채 마우스 훅을 추가 설치합니다.")
    log("→ 이 단계에서 마우스를 실제로 움직이고 클릭해 주세요(훅 콜백이 도는 상태를 봐야 합니다).")
    listener = None
    try:
        listener = mouse.Listener(
            on_move=on_move, on_click=on_click, on_scroll=on_scroll, **kwargs
        )
        listener.start()
        listener.wait()
    except Exception as exc:
        log(f"[!!] 마우스 훅 설치 실패: {exc!r}")
        return FAIL, f"마우스 훅 설치 실패: {exc!r}"

    try:
        for elapsed in range(1, int(PHASE2_WAIT_S) + 1):
            time.sleep(1.0)
            alive_m = listener.running
            alive_k = hk.running
            log(f"  생존 {elapsed:2d}초 | 마우스훅={'O' if alive_m else 'X'} "
                f"키보드훅={'O' if alive_k else 'X'} | "
                f"이동 {counters['move']} 클릭 {counters['click']} 스크롤 {counters['scroll']} | "
                f"핫키 {'감지됨' if hotkey_fired.is_set() else '미감지'}")
            if not alive_m or not alive_k:
                log("[!!] 훅이 도중에 죽었습니다 — 이 방향은 닫힘.")
                return FAIL, f"{elapsed}초 시점에 훅 사망"
    finally:
        if listener is not None and listener.running:
            listener.stop()

    observed = counters["move"] + counters["click"] + counters["scroll"]
    log(f"{PHASE2_WAIT_S:.0f}초 생존. 관찰 이벤트 총 {observed}건.")
    if observed == 0:
        log("입력 이벤트가 한 건도 관찰되지 않았습니다 — 훅 콜백이 도는 상태를 "
            "확인하지 못했으므로 생존 판정을 보류합니다.")
        return UNKNOWN, "30초 생존했으나 콜백 미관찰(입력 없음 또는 권한 문제)"
    return PASS, f"30초 생존, 콜백 {observed}건 정상 수신"


# --------------------------------------------------------------------------
# Phase 3 — INJECTED 플래그 관찰 (억제 안 함, Win32 전용)
# --------------------------------------------------------------------------
def phase3_injected_flags(log: Logger):
    log.rule("Phase 3 — INJECTED 플래그 관찰 (억제 안 함)")
    if not IS_WINDOWS:
        log("Windows 전용 — 건너뜀 (win32_event_filter / LLMHF_INJECTED는 Win32 전용)")
        return SKIP, "Windows 전용"

    from pynput import mouse

    physical: list[int] = []
    injected: list[int] = []
    recording = {"bucket": physical}

    def _filter(msg, data):
        recording["bucket"].append(int(data.flags))
        return True                     # 억제하지 않는다

    listener = mouse.Listener(win32_event_filter=_filter)
    listener.start()
    listener.wait()
    try:
        log(f"[3a] {PHASE3_OBSERVE_S:.0f}초간 물리 마우스를 움직이고 클릭해 주세요.")
        time.sleep(PHASE3_OBSERVE_S)
        log(f"  물리 이벤트 {len(physical)}건 관찰, flags 예시: "
            f"{sorted(set(physical))[:8]}")

        log("[3b] 이제 Controller로 클릭을 주입합니다.")
        recording["bucket"] = injected
        controller = mouse.Controller()
        cx, cy = _screen_center()
        for _ in range(3):
            controller.position = (cx, cy)
            controller.click(mouse.Button.left)
            time.sleep(0.3)
        time.sleep(0.5)
        log(f"  주입 이벤트 {len(injected)}건 관찰, flags 예시: "
            f"{sorted(set(injected))[:8]}")
    finally:
        listener.stop()

    if not physical or not injected:
        log("[!!] 한쪽 표본이 비어 판정할 수 없습니다.")
        return UNKNOWN, f"표본 부족(물리 {len(physical)} / 주입 {len(injected)})"

    physical_clean = all((f & INJECTED_MASK) == 0 for f in physical)
    injected_marked = all((f & INJECTED_MASK) != 0 for f in injected)
    log(f"  물리 이벤트 전부 flags & 0x03 == 0 : {physical_clean}")
    log(f"  주입 이벤트 전부 flags & 0x03 != 0 : {injected_marked}")

    if physical_clean and injected_marked:
        return PASS, "물리/주입 구분 가능 — 선택 억제 가능"
    return FAIL, ("플래그로 물리/주입을 구분할 수 없음 — 선택 억제 불가"
                  f"(물리 clean={physical_clean}, 주입 marked={injected_marked})")


# --------------------------------------------------------------------------
# Phase 4 / 5 — 선택 억제 (Win32 전용, 워치독 필수)
# --------------------------------------------------------------------------
def _run_suppression(log: Logger, duration_s: float, on_tick):
    """물리 이벤트만 삼키고 주입 이벤트는 통과시킨다.

    억제 여부는 state['suppressing'] 플래그 하나로 제어한다. 워치독이 이 플래그를
    먼저 내리므로, 리스너 정지가 늦어져도 억제는 즉시 풀린다.
    """
    from pynput import mouse

    state = {"suppressing": True, "suppressed": 0, "passed": 0}
    listener_box: dict = {}

    def _filter(msg, data):
        is_injected = bool(int(data.flags) & INJECTED_MASK)
        if not is_injected and state["suppressing"]:
            state["suppressed"] += 1
            listener_box["listener"].suppress_event()   # ← 실제 억제는 이것뿐
        else:
            state["passed"] += 1
        return True

    listener = mouse.Listener(win32_event_filter=_filter)
    listener_box["listener"] = listener

    def release() -> None:
        state["suppressing"] = False        # 먼저 억제를 끄고
        if listener.running:
            listener.stop()                 # 그 다음 훅을 내린다

    listener.start()
    listener.wait()
    watchdog = HookWatchdog(SUPPRESS_MAX_S, release, log).start()
    try:
        deadline = time.monotonic() + duration_s
        tick = 0
        while time.monotonic() < deadline and state["suppressing"]:
            time.sleep(1.0)
            tick += 1
            on_tick(tick, state)
    finally:
        watchdog.cancel()
        watchdog.release("정상 종료")
        watchdog.join()
    return state, watchdog


def phase4_selective_suppression(log: Logger):
    log.rule("Phase 4 — 선택 억제 실전 (최대 10초, 워치독 필수)")
    if not IS_WINDOWS:
        log("Windows 전용 — 건너뜀 (suppress_event는 Win32 ListenerMixin에만 존재)")
        return SKIP, "Windows 전용"

    if not _confirm_gate(log, SUPPRESS_MAX_S,
                         "물리 마우스 입력이 차단됩니다(주입 클릭은 통과)."):
        return SKIP, "사용자가 건너뜀"

    from pynput import mouse

    controller = mouse.Controller()
    cx, cy = _screen_center()

    def on_tick(tick, state):
        controller.position = (cx, cy)       # 주입은 통과해야 하므로 커서가 중앙으로 튀어야 정상
        controller.click(mouse.Button.left)
        log(f"  억제 {tick:2d}초 | 삼킨 물리 {state['suppressed']} / "
            f"통과 주입 {state['passed']} | 화면 중앙({cx},{cy})에 클릭 주입")

    log("→ 마우스를 움직여 보세요. 커서가 움직이지 않아야 정상입니다.")
    state, watchdog = _run_suppression(log, SUPPRESS_MAX_S + 5.0, on_tick)

    log(f"억제 종료. 삼킨 물리 이벤트 {state['suppressed']}건, 통과 이벤트 {state['passed']}건.")
    log(f"해제 주체: {watchdog.released_by} (워치독 발동={watchdog.fired})")
    log("→ 지금 마우스가 정상으로 돌아왔는지 확인해 주세요.")

    if state["suppressed"] == 0:
        return UNKNOWN, "억제된 물리 이벤트가 0건(입력이 없었을 수 있음)"
    if state["passed"] == 0:
        return FAIL, "주입 이벤트까지 통과하지 못함"
    return PASS, (f"물리 {state['suppressed']}건 억제 / 주입 {state['passed']}건 통과, "
                  f"{'워치독' if watchdog.fired else '정상 경로'}로 해제")


def phase5_escape_hatch(log: Logger, hk, hotkey_fired: threading.Event):
    log.rule("Phase 5 — 억제 중 탈출구(Ctrl+F7)")
    if not IS_WINDOWS:
        log("Windows 전용 — 건너뜀 (Phase 4와 동일한 억제 상태가 전제)")
        return SKIP, "Windows 전용"
    if hk is None or not hk.running:
        return UNKNOWN, "키보드 훅이 살아 있지 않아 시험 불가"

    if not _confirm_gate(log, SUPPRESS_MAX_S,
                         "물리 마우스가 차단됩니다. 그 상태에서 Ctrl+F7을 눌러주세요."):
        return SKIP, "사용자가 건너뜀"

    hotkey_fired.clear()

    def on_tick(tick, state):
        log(f"  억제 {tick:2d}초 | Ctrl+F7을 눌러주세요 | "
            f"핫키 {'감지됨 ✓' if hotkey_fired.is_set() else '미감지'}")

    state, watchdog = _run_suppression(log, SUPPRESS_MAX_S + 5.0, on_tick)

    if hotkey_fired.is_set():
        return PASS, "억제 중에도 Ctrl+F7 콜백 발화 확인"
    return UNKNOWN, "억제 중 Ctrl+F7 발화가 관찰되지 않음(입력이 없었을 수 있음)"


# --------------------------------------------------------------------------
# 워치독 자체 시험
# --------------------------------------------------------------------------
def selftest_watchdog(log: Logger, hang_s: float = 16.0) -> bool:
    """메인 로직을 일부러 멈춰놓고도 워치독이 훅을 해제하는지 시험한다.

    실제 억제(Phase 4)와 같은 HookWatchdog 클래스를 그대로 쓰되, 해제 대상만
    가짜 훅으로 바꾼다. 클래스가 다르면 시험의 의미가 없다.
    """
    log.rule("워치독 자체 시험")
    ok = True

    # --- 시험 1: 메인이 멈춰도 timeout 뒤 강제 해제되는가 ---
    log(f"[시험 1] 메인 로직을 {hang_s:.0f}초간 멈춘 채로 둡니다 "
        f"(억제가 걸린 채 응답 없는 상황 재현). 워치독은 {SUPPRESS_MAX_S:.0f}초에 발동해야 합니다.")
    record: dict = {}
    start = time.monotonic()

    def fake_release() -> None:
        record["at"] = time.monotonic() - start
        record["thread"] = threading.current_thread().name

    watchdog = HookWatchdog(SUPPRESS_MAX_S, fake_release, log, label="가짜").start()

    frozen_until = start + hang_s
    while time.monotonic() < frozen_until:      # 취소도, 해제도 하지 않는다
        time.sleep(0.5)

    elapsed = record.get("at")
    log(f"  워치독 발동 여부 : {watchdog.fired}")
    log(f"  해제 시각        : {elapsed if elapsed is None else f'{elapsed:.2f}초'}")
    log(f"  해제 스레드      : {record.get('thread')}")
    if not (watchdog.fired and elapsed is not None
            and SUPPRESS_MAX_S <= elapsed <= SUPPRESS_MAX_S + 1.5):
        log("  → 실패: 10초 시점에 강제 해제되지 않았습니다.")
        ok = False
    elif record.get("thread") != "hook-watchdog":
        log("  → 실패: 워치독 스레드가 아닌 곳에서 해제됐습니다.")
        ok = False
    else:
        log("  → 통과: 메인이 멈춘 채로도 워치독 스레드가 훅을 해제했습니다.")

    # --- 시험 2: 이미 해제된 뒤 중복 해제되지 않는가 ---
    log("[시험 2] 해제 뒤 finally 경로가 다시 해제를 시도해도 1회만 실행되어야 합니다.")
    again = watchdog.release("finally")
    log(f"  두 번째 release() 반환값: {again} (False여야 정상)")
    if again is not False:
        log("  → 실패: 중복 해제가 일어났습니다.")
        ok = False
    else:
        log("  → 통과: 중복 해제 없음.")

    # --- 시험 3: 정상 종료 시 워치독이 발동하지 않는가 ---
    log("[시험 3] 작업이 제때 끝나면 워치독이 발동하지 않아야 합니다.")
    calls: list[str] = []
    quick = HookWatchdog(SUPPRESS_MAX_S, lambda: calls.append("release"), log).start()
    time.sleep(1.0)
    quick.cancel()
    quick.release("정상 종료")
    quick.join()
    time.sleep(0.3)
    log(f"  워치독 발동 여부: {quick.fired} (False여야 정상), 해제 주체: {quick.released_by}")
    if quick.fired or calls != ["release"]:
        log("  → 실패: 정상 종료 경로가 어긋났습니다.")
        ok = False
    else:
        log("  → 통과: 정상 종료 시 워치독 미발동, 해제는 1회.")

    log("")
    log(f"워치독 자체 시험 결과: {'전부 통과' if ok else '실패 있음'}")
    return ok


# --------------------------------------------------------------------------
# 요약
# --------------------------------------------------------------------------
def summarize(log: Logger, results: dict) -> None:
    log.rule("최종 요약")
    for name, (status, note) in results.items():
        log(f"  {name:<38} {status:<6} {note}")

    log("")
    p2 = results.get("Phase 2 이중 훅 생존", (UNKNOWN, ""))[0]
    p3 = results.get("Phase 3 INJECTED 플래그", (UNKNOWN, ""))[0]
    p5 = results.get("Phase 5 억제 중 탈출구", (UNKNOWN, ""))[0]

    if p2 == FAIL:
        log("결론: 통합 불가 — 키보드 훅과 마우스 훅을 동시에 걸면 프로세스가 살아남지 못한다.")
        return
    if FAIL in (p3, p5):
        log("결론: 통합 불가 — 이중 훅은 견디지만 선택 억제 또는 탈출구가 성립하지 않는다.")
        return
    if p2 == PASS and p3 == PASS and p5 == PASS:
        log("결론: 통합 가능 — 이중 훅 생존 + 물리/주입 구분 + 억제 중 탈출구가 모두 확인됐다.")
        return

    log("결론: 판정 불가 — 아래가 확인되지 않았다. 억지로 통과 판정하지 않는다.")
    for name, key in (("Phase 2 이중 훅 생존", p2),
                      ("Phase 3 INJECTED 플래그", p3),
                      ("Phase 5 억제 중 탈출구", p5)):
        if key != PASS:
            log(f"  - {name}: {key}")
    log("  필요한 추가 정보:")
    if not IS_WINDOWS:
        log("    · Windows 실기에서 재실행할 것. Phase 3/4/5는 Win32 전용이라 "
            "macOS에서는 원리상 검증할 수 없다.")
        log("    · 과거 네이티브 크래시도 Windows에서 발생했으므로 Phase 2 결과 역시 "
            "Windows 것이 있어야 결론이 선다.")
    else:
        log("    · 해당 단계에서 실제 마우스 입력/키 입력을 발생시킨 뒤 재실행할 것"
            "(입력이 없으면 표본이 비어 판정할 수 없다).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="저수준 마우스 훅 이중 설치 안전성 검증 도구(검증 전용, 기능 통합 아님)"
    )
    parser.add_argument("--selftest-watchdog", action="store_true",
                        help="워치독 강제 해제 동작만 시험하고 종료한다(마우스를 잠그지 않음)")
    args = parser.parse_args()

    log = Logger()
    log.rule(f"verify_mouse_hook.py — {datetime.now():%Y-%m-%d %H:%M:%S}")
    log(f"로그 파일: {log.path}")

    hk = None
    try:
        if args.selftest_watchdog:
            ok = selftest_watchdog(log)
            return 0 if ok else 1

        results: dict = {}
        phase0_environment(log)

        hotkey_fired = threading.Event()
        hk, status, note = phase1_baseline(log, hotkey_fired)
        results["Phase 1 기준선(GlobalHotKeys)"] = (status, note)
        if status == FAIL:
            log("[!!] 기준선이 무너졌으므로 이후 단계는 의미가 없습니다. 중단합니다.")
            summarize(log, results)
            return 1

        results["Phase 2 이중 훅 생존"] = phase2_dual_hook(log, hk, hotkey_fired)
        results["Phase 3 INJECTED 플래그"] = phase3_injected_flags(log)
        results["Phase 4 선택 억제"] = phase4_selective_suppression(log)
        results["Phase 5 억제 중 탈출구"] = phase5_escape_hatch(log, hk, hotkey_fired)

        selftest_ok = selftest_watchdog(log)
        results["워치독 자체 시험"] = (
            PASS if selftest_ok else FAIL,
            "10초 강제 해제/중복 방지/정상 종료",
        )

        summarize(log, results)
        return 0
    except KeyboardInterrupt:
        log("")
        log("사용자 중단(Ctrl+C).")
        return 130
    finally:
        # 안전 요건 3 — 어떤 경로로 빠져나가도 키보드 훅을 반드시 내린다
        if hk is not None and hk.running:
            hk.stop()
            log("GlobalHotKeys 해제 완료.")
        log(f"로그가 {log.path}에 기록됐습니다.")
        log.close()


if __name__ == "__main__":
    sys.exit(main())
