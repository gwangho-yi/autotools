"""color-capture 컬러 감지 실패 원인 진단 도구.

GPU 없는 Windows PC에서 "색은 정상 지정되는데 감지가 안 되는" 현상의 원인을
A/B/C 중 하나로 확정하기 위한 단독 실행 스크립트다. 이 도구는 아무것도 고치지
않는다. 관측값만 찍어서 보여준다.

  A. 지정 시점 ↔ 감지 시점의 픽셀 값이 미세하게 다름 (색 심도/디더링/렌더링 경로)
  B. DPI 배율 좌표계 불일치 (Qt 논리 좌표 vs mss 물리 픽셀)
  C. MIN_MATCHED 하드코딩으로 작은 대상이 발화 못 함

실행:
    python scripts/diagnose.py          # 대화형
    python scripts/diagnose.py --auto   # 입력 없이 기본값으로 (stdin 없어도 동작)

결과는 콘솔과 ~/color-capture-diagnose.log 에 동시 기록된다.
"""
import os
import sys
import time
import platform
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import mss

# 실제 감지 로직의 상수를 그대로 쓴다(값이 바뀌어도 진단이 따라가도록).
try:
    from core.color_monitor import MIN_MATCHED, INTERVAL
    _CONST_SOURCE = "core/color_monitor.py"
except Exception:  # exe/경로 문제로 임포트 실패 시 폴백
    MIN_MATCHED, INTERVAL = 15, 0.1
    _CONST_SOURCE = "폴백 상수(core.color_monitor 임포트 실패)"

IS_WINDOWS = sys.platform == "win32"
LOG_PATH = os.path.join(os.path.expanduser("~"), "color-capture-diagnose.log")
TOLERANCE_SWEEP = [10, 20, 30, 50]
SAMPLE_COUNT = 30
MONITOR_SECONDS = 5.0

_log_file = None


def log(msg: str = "") -> None:
    print(msg, flush=True)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()


def section(title: str) -> None:
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


def skip_windows_only(what: str) -> None:
    log(f"  [Windows 전용 — 건너뜀] {what} (현재 플랫폼: {sys.platform})")


def ask(prompt: str, default: str, auto: bool) -> str:
    """대화형 입력. --auto 이거나 stdin이 없으면 기본값을 그대로 쓴다."""
    if auto or not sys.stdin or not sys.stdin.isatty():
        log(f"{prompt}[자동 기본값: {default}]")
        return default
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        log(f"  (입력 없음 → 기본값 {default} 사용)")
        return default
    if _log_file:
        _log_file.write(f"{prompt}{raw or '(빈 입력 → ' + default + ')'}\n")
    return raw or default


# ---------------------------------------------------------------- 1. 좌표계/DPI

def win_metrics() -> dict:
    """Windows GDI/USER32 지표. 다른 OS에서는 빈 dict."""
    if not IS_WINDOWS:
        return {}
    import ctypes

    out: dict[str, object] = {}
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        caps = {
            "HORZRES": 8, "VERTRES": 10, "BITSPIXEL": 12, "PLANES": 14,
            "LOGPIXELSX": 88, "LOGPIXELSY": 90,
            "DESKTOPVERTRES": 117, "DESKTOPHORZRES": 118, "COLORRES": 108,
        }
        for name, idx in caps.items():
            try:
                out[name] = int(gdi32.GetDeviceCaps(hdc, idx))
            except Exception as e:
                out[name] = f"실패({e})"
        user32.ReleaseDC(0, hdc)
        for name, idx in (("SM_CXSCREEN", 0), ("SM_CYSCREEN", 1),
                          ("SM_CXVIRTUALSCREEN", 78), ("SM_CYVIRTUALSCREEN", 79)):
            out[name] = int(user32.GetSystemMetrics(idx))
        try:
            out["GetDpiForSystem"] = int(user32.GetDpiForSystem())
        except Exception as e:
            out["GetDpiForSystem"] = f"사용 불가({e}) — Windows 10 1607 미만"
    except Exception as e:
        out["오류"] = f"Windows API 접근 실패: {e}"
    return out


def qt_screens(app) -> list[dict]:
    from PySide6.QtGui import QGuiApplication

    infos = []
    for i, s in enumerate(QGuiApplication.screens()):
        g = s.geometry()
        infos.append({
            "index": i,
            "name": s.name(),
            "left": g.x(), "top": g.y(), "width": g.width(), "height": g.height(),
            "dpr": float(s.devicePixelRatio()),
            "logical_dpi": float(s.logicalDotsPerInch()),
            "physical_dpi": float(s.physicalDotsPerInch()),
            "primary": s is QGuiApplication.primaryScreen(),
        })
    return infos


def diagnose_coordinates(app, sct, pre_win: dict) -> dict:
    """가설 B 판정: Qt 논리 좌표계와 mss 캡처 좌표계가 같은 눈금인지."""
    section("1. 좌표계 / DPI 정합성  (가설 B 판정 — 가장 중요)")

    screens = qt_screens(app)
    log("[Qt] QGuiApplication.screens()")
    for s in screens:
        log(f"  #{s['index']} {s['name']}{' (primary)' if s['primary'] else ''}: "
            f"geometry=({s['left']},{s['top']}) {s['width']}x{s['height']}  "
            f"devicePixelRatio={s['dpr']:.4g}  "
            f"logicalDPI={s['logical_dpi']:.4g}  physicalDPI={s['physical_dpi']:.4g}")

    log("")
    log("[mss] MSS().monitors")
    monitors = sct.monitors
    for i, m in enumerate(monitors):
        tag = " (전체 가상 화면)" if i == 0 else ""
        log(f"  [{i}]{tag} left={m['left']} top={m['top']} "
            f"width={m['width']} height={m['height']}")

    log("")
    log("[Windows API] (ctypes)")
    if not IS_WINDOWS:
        skip_windows_only("GetDeviceCaps(HORZRES/VERTRES/LOGPIXELS), "
                          "GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN), GetDpiForSystem")
    else:
        post_win = win_metrics()
        log("  * mss 인스턴스 생성 전(Qt만 초기화된 상태):")
        for k, v in pre_win.items():
            log(f"      {k} = {v}")
        log("  * mss 인스턴스 생성 후(mss가 SetProcessDpiAwareness(2) 호출한 뒤):")
        for k, v in post_win.items():
            mark = "  <-- 변함!" if pre_win.get(k) != v else ""
            log(f"      {k} = {v}{mark}")
        try:
            hr, dhr = post_win.get("HORZRES"), post_win.get("DESKTOPHORZRES")
            if isinstance(hr, int) and isinstance(dhr, int) and hr and hr != dhr:
                log(f"  ! GetDeviceCaps: 논리 HORZRES={hr} vs 물리 DESKTOPHORZRES={dhr} "
                    f"→ 시스템 배율 {dhr / hr * 100:.0f}%")
        except Exception:
            pass

    # ---- 캡처 실측: 요청한 크기 그대로 돌아오는가
    log("")
    log("[실측] mss가 요청한 크기를 그대로 돌려주는지")
    probe_shape = None
    try:
        m = monitors[1] if len(monitors) > 1 else monitors[0]
        probe = {"left": m["left"] + 10, "top": m["top"] + 10, "width": 200, "height": 200}
        arr = np.array(sct.grab(probe))
        probe_shape = (arr.shape[1], arr.shape[0])  # (w, h)
        log(f"  요청 200x200 → 반환 {probe_shape[0]}x{probe_shape[1]}"
            + ("  (일치)" if probe_shape == (200, 200) else "  <-- 불일치: 캡처가 스케일링됨"))
    except Exception as e:
        log(f"  캡처 실패: {e}")

    # ---- 판정
    log("")
    result = {"mismatch": False, "detail": "", "pairs": []}

    if not screens:
        log("[B 판정] Qt 화면 정보를 못 얻어 판정 불가.")
        result["detail"] = "Qt 화면 정보 없음"
        return result

    phys = monitors[1:] if len(monitors) > 1 else monitors[:1]
    if len(screens) != len(phys):
        log(f"[B 판정] 화면 개수 불일치: Qt {len(screens)}개 vs mss {len(phys)}개. "
            f"자동 짝짓기가 부정확할 수 있으니 아래 수치를 직접 비교할 것.")

    qt_sorted = sorted(screens, key=lambda s: (s["top"], s["left"]))
    mss_sorted = sorted(phys, key=lambda m: (m["top"], m["left"]))
    worst = 1.0
    for q, m in zip(qt_sorted, mss_sorted):
        sx = m["width"] / q["width"] if q["width"] else 0.0
        sy = m["height"] / q["height"] if q["height"] else 0.0
        pair = {
            "qt": f"{q['width']}x{q['height']}@({q['left']},{q['top']})",
            "mss": f"{m['width']}x{m['height']}@({m['left']},{m['top']})",
            "sx": sx, "sy": sy, "dpr": q["dpr"], "name": q["name"],
        }
        result["pairs"].append(pair)
        same = abs(sx - 1.0) < 0.01 and abs(sy - 1.0) < 0.01
        origin_same = q["left"] == m["left"] and q["top"] == m["top"]
        log(f"  {q['name']}: Qt {pair['qt']}  vs  mss {pair['mss']}  "
            f"→ 배율 x{sx:.4g}, y{sy:.4g}" + ("" if same else "   <-- 불일치"))
        if not same:
            worst = max(worst, sx, sy, 1 / sx if sx else 1.0, 1 / sy if sy else 1.0)
            result["mismatch"] = True
        elif not origin_same:
            log(f"      크기는 같은데 원점이 다름: Qt({q['left']},{q['top']}) "
                f"vs mss({m['left']},{m['top']}) — 멀티모니터 배치 어긋남 가능")
            result["mismatch"] = True
            result.setdefault("origin_only", True)

    log("")
    if result["mismatch"]:
        p = result["pairs"][0]
        pct = p["sx"] * 100 if p["sx"] else 0
        log(f"[B 판정] Qt 논리 {p['qt'].split('@')[0]} vs mss 물리 {p['mss'].split('@')[0]} "
            f"→ 배율 {pct:.0f}% 불일치. 감시 영역이 어긋납니다.")
        log(f"         select_regions()는 Qt 논리 좌표를 돌려주고 ColorMonitorThread는 "
            f"그 값을 그대로 mss에 넘깁니다.")
        log(f"         화면 좌상단(0,0)에서는 오차가 0이고 우하단으로 갈수록 벌어집니다. "
            f"예: 논리 (1000,600)을 지정하면 실제로는 물리 "
            f"({int(1000 * p['sx'])},{int(600 * p['sy'])}) 를 봐야 하는데 (1000,600)을 봅니다.")
        dprs = {round(s["dpr"], 4) for s in screens}
        log(f"         Qt devicePixelRatio={sorted(dprs)} — "
            + ("이 값이 위 배율과 같으면 원인이 DPI 스케일링으로 완전히 설명됩니다."
               if any(abs(d - result['pairs'][0]['sx']) < 0.01 for d in dprs)
               else "DPR로는 설명되지 않는 불일치입니다. 멀티모니터 배치/가상 화면 원점을 의심하세요."))
        result["detail"] = f"배율 {pct:.0f}% 불일치 (최대 x{worst:.4g})"
    else:
        p = result["pairs"][0] if result["pairs"] else {"qt": "?", "mss": "?"}
        log(f"[B 판정] Qt {p['qt'].split('@')[0]} == mss {p['mss'].split('@')[0]} "
            f"→ 좌표계 정상. B 아님.")
        result["detail"] = "좌표계 일치"
    return result


# ------------------------------------------------------------ 2. 색 심도/디더링

def diagnose_color_depth(sct) -> dict:
    """가설 A 판정: 색 심도가 낮거나 픽셀 값이 시간에 따라 흔들리는가."""
    section("2. 색 심도 / 디더링  (가설 A 판정)")

    out = {"jitter": 0, "sigma": 0.0, "unique": 0, "bitspixel": None}

    log("[색 심도]")
    if not IS_WINDOWS:
        skip_windows_only("GetDeviceCaps(BITSPIXEL), GetDeviceCaps(COLORRES)")
    else:
        w = win_metrics()
        bpp = w.get("BITSPIXEL")
        out["bitspixel"] = bpp
        log(f"  BITSPIXEL = {bpp} (화면 1픽셀당 비트 수. 32 또는 24가 정상, 16이면 A 유력)")
        log(f"  PLANES    = {w.get('PLANES')}")
        log(f"  COLORRES  = {w.get('COLORRES')} (0이면 팔레트 장치가 아님 — 정상)")
        if isinstance(bpp, int) and bpp < 24:
            log(f"  ! 색 심도가 {bpp}비트입니다. 채널당 5~6비트라 지정 색과 감지 색이 "
                f"최대 8까지 차이 날 수 있습니다. A 유력.")

    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
    cx = mon["left"] + mon["width"] // 2
    cy = mon["top"] + mon["height"] // 2
    region = {"left": cx - 100, "top": cy - 100, "width": 200, "height": 200}

    log("")
    log(f"[고유 색 개수] 화면 중앙 200x200 영역 {region}")
    try:
        arr = np.array(sct.grab(region))[:, :, :3]  # BGR
        flat = arr.reshape(-1, 3)
        colors, counts = np.unique(flat, axis=0, return_counts=True)
        out["unique"] = int(len(colors))
        total = int(flat.shape[0])
        log(f"  총 {total}픽셀 중 고유 색 {out['unique']}개")
        order = np.argsort(-counts)[:10]
        for rank, i in enumerate(order, 1):
            b, g, r = (int(v) for v in colors[i])
            log(f"    {rank:2d}. RGB({r:3d},{g:3d},{b:3d})  {int(counts[i]):6d}회 "
                f"({counts[i] / total * 100:5.2f}%)")
        if out["unique"] > total * 0.3:
            log(f"  ! 고유 색이 매우 많습니다({out['unique']}/{total}). "
                f"평탄한 영역을 찍었다면 디더링 의심 — A 방향 근거.")
    except Exception as e:
        log(f"  캡처 실패: {e}")

    log("")
    log(f"[동일 픽셀 반복 샘플] 화면 중앙 1픽셀을 {INTERVAL}초 간격으로 {SAMPLE_COUNT}회")
    px_region = {"left": cx, "top": cy, "width": 5, "height": 5}
    samples = []
    try:
        for _ in range(SAMPLE_COUNT):
            a = np.array(sct.grab(px_region))[:, :, :3]
            b, g, r = (int(v) for v in a[2, 2])
            samples.append((r, g, b))
            time.sleep(INTERVAL)
    except Exception as e:
        log(f"  캡처 실패: {e}")

    if samples:
        s = np.array(samples, dtype=np.int32)
        spread = []
        parts = []
        for ch, name in enumerate("RGB"):
            lo, hi = int(s[:, ch].min()), int(s[:, ch].max())
            sd = float(s[:, ch].std())
            spread.append(hi - lo)
            parts.append(f"{name} {lo}~{hi}(σ={sd:.1f})")
        out["jitter"] = int(max(spread))
        out["sigma"] = float(s.std(axis=0).max())
        log(f"[A 판정] 동일 픽셀 {SAMPLE_COUNT}회 샘플: " + " ".join(parts))
        if out["jitter"] == 0:
            log(f"         → 값이 전혀 흔들리지 않습니다. 시간축 불안정성은 없음(A의 "
                f"'디더링/렌더링 흔들림' 근거 없음).")
        else:
            log(f"         → 값이 최대 {out['jitter']} 흔들립니다. "
                f"tolerance {min(TOLERANCE_SWEEP)}으로는 놓칠 수 있습니다.")
        log(f"         (주의: 화면 중앙에 움직이는 내용이 있으면 이 수치는 무의미합니다. "
            f"정지 화면에서 다시 실행해 보세요.)")
    return out


# --------------------------------------------------- 3. 감지 로직 재현 (가설 C)

def parse_rgb(text: str):
    t = text.strip().lstrip("#")
    if "," in t:
        parts = [p for p in t.replace(" ", "").split(",") if p != ""]
        if len(parts) == 3:
            return tuple(max(0, min(255, int(p))) for p in parts)
    if len(t) == 6:
        return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError(f"RGB 형식을 알 수 없습니다: {text!r}")


def parse_region(text: str, sct):
    t = text.strip().lower()
    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
    if t in ("", "full", "전체"):
        return dict(left=mon["left"], top=mon["top"],
                    width=mon["width"], height=mon["height"])
    parts = [p for p in t.replace(" ", "").split(",") if p != ""]
    if len(parts) != 4:
        raise ValueError(f"영역 형식을 알 수 없습니다: {text!r} (left,top,width,height)")
    l, t_, w, h = (int(p) for p in parts)
    return {"left": l, "top": t_, "width": w, "height": h}


def diagnose_detection(sct, auto: bool) -> dict:
    """ColorMonitorThread._monitor_loop 와 동일 연산을 하되 임계값에서 자르지 않는다."""
    section("3. 실제 감지 로직 재현  (가설 C 판정)")
    log(f"  감지 상수 출처: {_CONST_SOURCE}  (MIN_MATCHED={MIN_MATCHED}, INTERVAL={INTERVAL})")
    log("")

    default_region_text = "full"
    region = parse_region(ask(
        "감시 영역 [left,top,width,height] (엔터=전체 화면): ",
        default_region_text, auto), sct)
    log(f"  → 감시 영역: {region}")

    # 기본 target: 그 영역 중앙 픽셀의 실제 색(반드시 존재하는 색이므로 자기검사용)
    center = {"left": region["left"] + region["width"] // 2,
              "top": region["top"] + region["height"] // 2,
              "width": 5, "height": 5}
    try:
        c = np.array(sct.grab(center))[:, :, :3][2, 2]
        default_rgb = f"{int(c[2])},{int(c[1])},{int(c[0])}"
        default_is_probe = True
    except Exception:
        default_rgb, default_is_probe = "255,255,255", False

    target = parse_rgb(ask(
        f"target RGB [r,g,b 또는 #rrggbb] (엔터={default_rgb}): ", default_rgb, auto))
    log(f"  → target RGB{target}")
    if auto and default_is_probe:
        log("  ! 자동 모드: target을 '지금 화면 중앙에 실제로 있는 색'으로 잡았습니다. "
            "도구 자체의 동작 검증용이며 실제 문제 재현이 아닙니다.")

    tol_user = int(ask("tolerance (엔터=10): ", "10", auto))
    log(f"  → tolerance={tol_user}")

    r, g, b = target
    target_bgr = np.array([b, g, r], dtype=np.int16)
    sweep = sorted({tol_user, *TOLERANCE_SWEEP})

    log("")
    log(f"[{MONITOR_SECONDS:.0f}초간 {INTERVAL}초 간격 재현] "
        f"matched는 diff.max(axis=2) <= tolerance 인 픽셀 수 (감지 로직과 동일)")
    log(f"  해석(→) 줄은 해석이 바뀔 때만 출력합니다.")

    best_matched = {t: 0 for t in sweep}
    min_dist = 255
    nearest_rgb = None
    frames = 0
    last_note = None
    t_end = time.monotonic() + MONITOR_SECONDS
    frame = 0
    while time.monotonic() < t_end:
        time.sleep(INTERVAL)
        frame += 1
        try:
            cur = np.array(sct.grab(region), dtype=np.int16)[:, :, :3]
        except Exception as e:
            log(f"  frame {frame}: 캡처 실패: {e}")
            break
        diff = np.abs(cur - target_bgr)
        dist = diff.max(axis=2)
        matched = {t: int(np.count_nonzero(dist <= t)) for t in sweep}
        for t in sweep:
            best_matched[t] = max(best_matched[t], matched[t])
        flat = int(np.argmin(dist))
        yy, xx = divmod(flat, dist.shape[1])
        d = int(dist[yy, xx])
        px = cur[yy, xx]
        px_rgb = (int(px[2]), int(px[1]), int(px[0]))
        if d < min_dist:
            min_dist, nearest_rgb = d, px_rgb
        frames += 1

        flag = "충족" if matched[tol_user] >= MIN_MATCHED else f"MIN_MATCHED={MIN_MATCHED} 미달"
        sweep_txt = " ".join(f"{t}→{matched[t]}" for t in sweep)
        log(f"  frame {frame:2d}: matched={matched[tol_user]} ({flag}) | "
            f"최근접 픽셀 RGB{px_rgb} 거리={d} @영역내({xx},{yy}) | tol별: {sweep_txt}")

        if matched[tol_user] >= MIN_MATCHED:
            note = "정상 감지 조건 충족. 이 설정에서는 발화합니다."
        elif d <= tol_user:
            note = (f"색은 화면에 있는데 픽셀 수가 부족합니다({matched[tol_user]}<{MIN_MATCHED}). "
                    f"C 확정 방향.")
        elif any(matched[t] >= MIN_MATCHED for t in sweep if t > tol_user):
            hit = min(t for t in sweep if t > tol_user and matched[t] >= MIN_MATCHED)
            note = f"tolerance {hit}로 올리면 감지됩니다. A 방향(픽셀 값 미세 차이)."
        elif d > 50:
            note = (f"영역 안에 그 색이 아예 없습니다(최근접 거리 {d}). "
                    f"B(영역 어긋남) 의심.")
        else:
            note = f"근처 색은 있으나(거리 {d}) 어떤 tolerance로도 {MIN_MATCHED}개를 못 채웁니다."
        if note != last_note:
            log(f"            → {note}")
            last_note = note

    return {
        "frames": frames, "target": target, "region": region, "tolerance": tol_user,
        "best": best_matched, "min_dist": min_dist, "nearest": nearest_rgb,
        "sweep": sweep, "auto_probe": auto and default_is_probe,
    }


# ------------------------------------------------------------------- 4. 최종 요약

def summarize(coord: dict, depth: dict, det: dict) -> None:
    section("4. 최종 요약")

    lines = []
    b_hit = coord.get("mismatch", False)
    tol = det.get("tolerance", 10)
    best = det.get("best", {})
    min_dist = det.get("min_dist", 255)
    fired = best.get(tol, 0) >= MIN_MATCHED
    higher = [t for t in det.get("sweep", []) if t > tol and best.get(t, 0) >= MIN_MATCHED]
    c_hit = (not fired) and min_dist <= tol and best.get(tol, 0) > 0
    a_hit = (not fired) and bool(higher)

    log("[근거 정리]")
    log(f"  좌표계   : {coord.get('detail', '?')}")
    log(f"  색 심도  : BITSPIXEL={depth.get('bitspixel')} / 중앙 200x200 고유색 "
        f"{depth.get('unique')}개 / 동일 픽셀 흔들림 최대 {depth.get('jitter')}")
    log(f"  감지 재현: {det.get('frames')}프레임, tolerance {tol}에서 최대 matched="
        f"{best.get(tol, 0)} (MIN_MATCHED={MIN_MATCHED}), 최근접 거리={min_dist} "
        f"RGB{det.get('nearest')}")
    if best:
        log(f"             tolerance별 최대 matched: "
            + " ".join(f"{t}→{best[t]}" for t in sorted(best)))
    log("")

    if det.get("auto_probe"):
        log("! 감지 재현 섹션이 자동 기본값(현재 화면에 실제로 있는 색)으로 돌았습니다.")
        log("  문제 재현 판정에는 쓸 수 없습니다. 실제 대상 색/영역을 입력해 다시 실행하세요.")
        log("  (아래 결론은 좌표계·색 심도 근거만으로 내린 것입니다.)")
        log("")

    if b_hit:
        lines.append(f"[결론] B — DPI/좌표계 불일치. {coord.get('detail')}")
        lines.append("  근거: Qt가 돌려주는 논리 좌표와 mss가 쓰는 물리 픽셀의 눈금이 다릅니다.")
        lines.append("       돋보기는 커서 바로 밑을 찍어 오차가 드러나지 않았고, 화면 좌상단은")
        lines.append("       오차 0, 우하단으로 갈수록 벌어집니다.")
        if not det.get("auto_probe") and not fired and min_dist > 50:
            lines.append(f"       감지 재현에서도 최근접 거리 {min_dist}로 '영역에 그 색이 없음'이 "
                         f"확인돼 B와 일치합니다.")
    elif det.get("auto_probe"):
        lines.append("[결론] 판정 불가 — 좌표계는 정상(B 아님)이지만 감지 재현을 실제 대상으로 "
                     "돌리지 않았습니다.")
        lines.append("  필요한 추가 정보: 문제가 나는 그 PC에서 실제 target RGB와 감시 영역을 "
                     "입력해 3번 섹션을 다시 실행한 결과.")
    elif fired:
        lines.append("[결론] 재현 실패 — 입력한 색/영역으로는 이 실행에서 정상 감지 조건이 "
                     "충족됐습니다.")
        lines.append(f"  근거: tolerance {tol}에서 matched 최대 {best.get(tol, 0)} ≥ "
                     f"MIN_MATCHED({MIN_MATCHED}).")
        lines.append("  필요한 추가 정보: 실제로 실패하는 순간의 target RGB와 감시 영역, "
                     "그리고 그 순간 이 도구를 함께 돌린 출력.")
    elif c_hit:
        lines.append(f"[결론] C — MIN_MATCHED({MIN_MATCHED}) 미달. 색은 영역 안에 있습니다.")
        lines.append(f"  근거: 최근접 거리 {min_dist} ≤ tolerance {tol}인데 matched 최대 "
                     f"{best.get(tol, 0)}개로 {MIN_MATCHED}개에 못 미쳐 발화 자체를 안 합니다.")
        lines.append("       대상이 작을수록 확실히 재현됩니다.")
    elif a_hit:
        lines.append(f"[결론] A — 픽셀 값 미세 차이. tolerance {min(higher)}로 올리면 감지됩니다.")
        lines.append(f"  근거: tolerance {tol}에서는 matched {best.get(tol, 0)}개인데 "
                     f"{min(higher)}에서는 {best.get(min(higher), 0)}개로 늘어 "
                     f"MIN_MATCHED를 넘습니다.")
        if depth.get("jitter"):
            lines.append(f"       동일 픽셀이 시간에 따라 최대 {depth['jitter']} 흔들리는 것도 "
                         f"같은 방향의 근거입니다.")
        if isinstance(depth.get("bitspixel"), int) and depth["bitspixel"] < 24:
            lines.append(f"       색 심도 {depth['bitspixel']}비트도 같은 방향의 근거입니다.")
    elif min_dist > 50:
        lines.append(f"[결론] 판정 불가 — 영역 안에 target 색이 전혀 없습니다"
                     f"(최근접 거리 {min_dist}, RGB{det.get('nearest')}).")
        lines.append("  좌표계는 정상으로 나왔으므로 B는 아닙니다. 남은 가능성은")
        lines.append("  (1) 입력한 감시 영역이 실제 대상 위치가 아님, (2) 측정 시점에 그 색이 "
                     "화면에 없었음.")
        lines.append("  필요한 추가 정보: 대상이 화면에 확실히 보이는 상태에서 그 대상을 감싸는 "
                     "영역 좌표로 3번 섹션 재실행.")
    else:
        lines.append("[결론] 판정 불가 — A/B/C 어느 쪽도 근거가 충분하지 않습니다.")
        lines.append(f"  관측: 좌표계 정상, 최근접 거리 {min_dist}, tolerance {max(best) if best else '?'}"
                     f"까지 올려도 matched가 {MIN_MATCHED}개에 못 미칩니다.")
        lines.append("  필요한 추가 정보: 실패 순간의 화면 스크린샷과, 같은 순간 이 도구의 "
                     "3번 섹션 출력.")

    for line in lines:
        log(line)

    # 부수 관측(결론과 별개로 남겨 둔다)
    extra = []
    if not b_hit and depth.get("jitter"):
        caveat = ("다만 흔들림이 이 정도로 크면 디더링이 아니라 그 지점에 움직이는 내용이 "
                  "있었을 가능성이 큽니다. 정지 화면에서 재실행해 확인하세요."
                  if depth["jitter"] > 30 else
                  "정지 화면이었다면 디더링/색 심도 문제입니다.")
        extra.append(f"동일 픽셀이 최대 {depth['jitter']} 흔들립니다(A 보조 근거). {caveat}")
    if isinstance(depth.get("bitspixel"), int) and depth["bitspixel"] < 24:
        extra.append(f"색 심도가 {depth['bitspixel']}비트입니다(A 보조 근거).")
    if b_hit and not det.get("auto_probe") and fired:
        extra.append("좌표계는 어긋나 있는데 입력한 영역으로는 감지가 됐습니다. "
                     "직접 입력한 좌표와 select_regions()가 만드는 좌표는 다를 수 있습니다.")
    if extra:
        log("")
        log("[부수 관측]")
        for e in extra:
            log(f"  - {e}")


# ------------------------------------------------------------------------ main

def main() -> int:
    global _log_file
    auto = "--auto" in sys.argv or not sys.stdin or not sys.stdin.isatty()

    try:
        _log_file = open(LOG_PATH, "w", encoding="utf-8")
    except Exception as e:
        print(f"로그 파일을 열 수 없습니다({e}). 콘솔에만 출력합니다.")

    log("color-capture 컬러 감지 진단 도구")
    log(f"  실행 시각 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  플랫폼    : {platform.platform()} / {sys.platform}")
    log(f"  Python    : {sys.version.split()[0]}")
    log(f"  실행 모드 : {'자동(입력 없음)' if auto else '대화형'}")
    log(f"  로그 파일 : {LOG_PATH}")
    try:
        import PySide6
        log(f"  버전      : mss {mss.__version__} / numpy {np.__version__} / "
            f"PySide6 {PySide6.__version__}")
    except Exception:
        log(f"  버전      : mss {mss.__version__} / numpy {np.__version__}")

    # 실제 앱과 같은 순서로 초기화한다: Qt 먼저(bootstrap.create_app과 동일 설정),
    # 그 다음 mss. mss는 생성 시 SetProcessDpiAwareness(2)를 부르므로 순서가 중요하다.
    pre = win_metrics()
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtWidgets import QApplication
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    app = QApplication.instance() or QApplication(sys.argv)

    with mss.MSS() as sct:
        coord = diagnose_coordinates(app, sct, pre)
        depth = diagnose_color_depth(sct)
        det = diagnose_detection(sct, auto)
        summarize(coord, depth, det)

    log("")
    log(f"진단 종료. 이 출력 전체가 {LOG_PATH} 에도 저장됐습니다. 파일 내용을 그대로 보내 주세요.")
    if _log_file:
        _log_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
