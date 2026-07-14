# RGB Color Catch Catch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 픽셀-변화 감지와 나란히, "지정한 RGB 값이 감시 영역에 나타나는지"를 감지해 클릭을 트리거하는 컬러캡쳐/컬러클리커 모드를 두 앱에 탭으로 추가한다.

**Architecture:** `auto-capture`, `auto-clicker` 양쪽 UI 최상단에 `QTabWidget`을 도입한다 — 탭1은 기존 화면(무변경), 탭2는 신규 컬러 모드. 감지는 신규 `ColorMonitorThread`(RGB 허용오차 매칭), 클릭 트리거는 auto-capture가 소켓으로 보내는 신규 `"color_match"` 이벤트를 auto-clicker가 수신해 `ContinuousClickEngine.stop()` → `ClickEngine.start_from_color(x, y)`로 처리한다. 기존 `motion` 플로우와 소켓(`127.0.0.1:54321`)은 완전히 무변경이며 하위호환 확장이다.

**Tech Stack:** Python, PySide6, mss(화면 캡처), pynput(클릭 실행), TCP 소켓 IPC, pytest + pytest-qt(qtbot).

## Global Constraints

이 계획은 두 독립 워커(Phase A = auto-capture, Phase B = auto-clicker)에게 별도로 위임된다. 두 그룹 사이의 **유일한 결합점은 아래 IPC 계약뿐**이며, 양쪽 워커는 반드시 아래 정확한 문자열/필드명을 동일하게 구현해야 한다.

**IPC 계약 (양쪽 앱이 반드시 동일하게 준수):**

- 소켓: `127.0.0.1`, 포트 `54321` (기존과 동일, 무변경)
- 메시지 포맷: 개행(`\n`)으로 구분되는 JSON 한 줄
- 신규 이벤트 문자열: `"color_match"` (기존 `"motion"`은 절대 변경 금지)
- 신규 메시지 형태 (정확히 이 필드명·이 순서):
  ```json
  {"event": "color_match", "x": <int>, "y": <int>}
  ```
- **auto-capture(Phase A)**: 매칭 감지 시 `IpcClient.send_color_match(x, y)`가 위 JSON을 전송한다.
- **auto-clicker(Phase B)**: `IpcServer`가 `msg.get("event") == "color_match"` 분기에서 `int(msg["x"])`, `int(msg["y"])`를 읽어 `color_match_received(int, int)` 시그널을 발신한다.
- 좌표 `x`, `y`는 **글로벌 화면 좌표(멀티 모니터 포함 절대 좌표)** 이며 정수다. auto-clicker는 이 좌표로 마우스를 이동시킨 뒤 클릭한다.

**공통 스타일/규칙 (기존 코드 관례 준수):**

- 배경색 `#1a1a2e`, 강조색 `#4ecca3`, 위험색 `#e05555`.
- 스핀박스는 각 앱의 기존 `_spinbox_style()`/`_spin_style()` 헬퍼를 재사용한다(assets 화살표 PNG 사용).
- QThread 종료: `requestInterruption()` + `wait()` 패턴. 스레드 내부 루프는 `isInterruptionRequested()`를 폴링한다.
- mss 프레임은 `np.array(sct.grab(region))[:, :, :3]`로 BGRA→RGB가 아닌 **BGR 순서**의 앞 3채널을 얻는다(기존 `monitor.py`와 동일). 색 비교는 채널 순서에 무관한 채널별 절대차 방식이므로 순서 변환은 불필요하다.

---

## Phase A — auto-capture (워커: surface:3)

작업 디렉토리 기준 경로: 모든 경로는 `auto-capture/` 하위. 테스트 실행은 `auto-capture/` 디렉토리에서 `python -m pytest` (conftest.py가 `sys.path`에 프로젝트 루트를 추가함).

TDD 순서: 순수 로직(색 감지 스레드) → IPC 확장 → UI 위젯(색 피커, 탭) → 진입점 와이어링.

---

### Task A1: ColorMonitorThread (RGB 허용오차 감지 스레드)

**Files:**
- Create: `auto-capture/core/color_monitor.py`
- Test: `auto-capture/tests/test_color_monitor.py`

**Interfaces:**
- Consumes: `region` dict `{"left", "top", "width", "height"}` (기존 `select_region()` 반환 형태), `target_rgb` 튜플 `(r, g, b)`, `tolerance` int.
- Produces: `ColorMonitorThread(region, target_rgb, tolerance)` — `color_detected(int, int)` 시그널(글로벌 좌표), `stopped()` 시그널. `MonitorThread`와 동일하게 `pause()`/`resume()` 지원.

**감지 알고리즘 (스펙 §2, §5):** 프레임의 각 픽셀에 대해 `max(|Δb|, |Δg|, |Δr|) <= tolerance`이면 매칭. 매칭 픽셀 수가 `MIN_MATCHED` 이상이고 마지막 감지 후 `ALERT_COOLDOWN` 초 지났을 때만 감지로 판단. 매칭 좌표의 평균(중심)을 글로벌 좌표로 변환해 emit(기존 `MonitorThread`의 `motion_detected` 좌표 계산 스타일 그대로).

- [ ] **Step 1: Write the failing test**

`auto-capture/tests/test_color_monitor.py`:
```python
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def make_frame(shape=(100, 100, 4), bgr=(0, 0, 0)):
    """mss grab 반환 흉내: BGRA 순서 프레임."""
    arr = np.zeros(shape, dtype=np.uint8)
    arr[:, :, 0] = bgr[0]  # B
    arr[:, :, 1] = bgr[1]  # G
    arr[:, :, 2] = bgr[2]  # R
    return arr


def test_color_detected_within_tolerance(qtbot, qapp):
    """목표색과 채널차가 tolerance 이내면 color_detected가 emit되는지."""
    from core.color_monitor import ColorMonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}
    # 목표 RGB (10, 20, 30). 프레임은 BGR로 (12, 22, 32) → 채널차 2 <= tolerance 5
    frame = make_frame(bgr=(12, 22, 32))

    with patch("core.color_monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.return_value = frame

        thread = ColorMonitorThread(region, target_rgb=(30, 20, 10), tolerance=5)
        with qtbot.waitSignal(thread.color_detected, timeout=3000):
            thread.start()
        thread.requestInterruption()
        thread.wait()


def test_no_detection_outside_tolerance(qtbot, qapp):
    """채널차가 tolerance를 초과하면 emit되지 않는지."""
    from core.color_monitor import ColorMonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}
    # 목표 RGB (30, 20, 10) → BGR 목표 (10,20,30). 프레임 BGR (30,20,10) → R차 20, B차 20 > tol 5
    frame = make_frame(bgr=(30, 20, 10))

    emitted = []
    with patch("core.color_monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.return_value = frame

        thread = ColorMonitorThread(region, target_rgb=(30, 20, 10), tolerance=5)
        thread.color_detected.connect(lambda x, y: emitted.append((x, y)))
        thread.start()
        time.sleep(0.8)
        thread.requestInterruption()
        thread.wait()

    assert emitted == []
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-capture && python -m pytest tests/test_color_monitor.py -v
  ```
  예상: `ModuleNotFoundError: No module named 'core.color_monitor'` (2개 테스트 collection 에러).

- [ ] **Step 3: Write minimal implementation**

`auto-capture/core/color_monitor.py`:
```python
import threading
import time
import numpy as np
import mss
from PySide6.QtCore import QThread, Signal


INTERVAL = 0.5
MIN_MATCHED = 15
ALERT_COOLDOWN = 3.0


class ColorMonitorThread(QThread):
    color_detected = Signal(int, int)
    stopped = Signal()

    def __init__(self, region, target_rgb, tolerance, parent=None):
        super().__init__(parent)
        self.region = region
        # target_rgb는 (r, g, b). mss 프레임은 BGR 순서이므로 비교용으로 뒤집어 둔다.
        r, g, b = target_rgb
        self._target_bgr = np.array([b, g, r], dtype=np.int16)
        self.tolerance = int(tolerance)
        self._pause_event = threading.Event()
        self._pause_event.set()  # running by default

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def run(self):
        try:
            self._monitor_loop()
        finally:
            self.stopped.emit()

    def _monitor_loop(self):
        last_alert = 0.0
        with mss.mss() as sct:
            while not self.isInterruptionRequested():
                if not self._pause_event.wait(timeout=0.1):
                    continue
                time.sleep(INTERVAL)
                try:
                    cur = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
                except Exception:
                    break
                diff = np.abs(cur - self._target_bgr)
                mask = diff.max(axis=2) <= self.tolerance
                matched = int(np.count_nonzero(mask))
                now = time.monotonic()
                if matched >= MIN_MATCHED and (now - last_alert) >= ALERT_COOLDOWN:
                    ys, xs = np.where(mask)
                    h_px, w_px = mask.shape
                    fx = xs.mean() / w_px
                    fy = ys.mean() / h_px
                    cx = self.region["left"] + fx * self.region["width"]
                    cy = self.region["top"] + fy * self.region["height"]
                    self.color_detected.emit(int(cx), int(cy))
                    last_alert = now
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-capture && python -m pytest tests/test_color_monitor.py -v
  ```
  예상: `2 passed`.

- [ ] **Step 5: Commit**
  ```
  cd auto-capture && git add core/color_monitor.py tests/test_color_monitor.py && git commit -m "feat(capture): ColorMonitorThread RGB 허용오차 감지 스레드 추가"
  ```

---

### Task A2: IpcClient.send_color_match 확장

**Files:**
- Modify: `auto-capture/core/ipc_client.py:20-27` (`send_motion` 뒤에 `send_color_match` 추가)
- Test: `auto-capture` 프로젝트에는 IPC 클라이언트 단위 테스트가 없으므로 신규 테스트 파일을 추가하지 않는다. 대신 Phase C 통합 확인에서 검증한다. (송신 로직이 `send_motion`과 동일 패턴이므로 별도 유닛테스트 불필요 — 스펙 §2 "기존 send_motion과 동일한 패턴".)

**Interfaces:**
- Produces: `IpcClient.send_color_match(x: int, y: int) -> None` — Global Constraints의 `color_match` JSON을 소켓으로 전송.

- [ ] **Step 1: (테스트 없음 근거 확인)** 이 태스크는 기존 `send_motion`과 완전 동일한 구조의 단순 메서드 추가이며, auto-capture에 IPC 클라이언트 유닛테스트 하네스가 없다. Phase C에서 실제 소켓 연동으로 검증하므로 유닛테스트를 생략한다.

- [ ] **Step 2: Write minimal implementation**

`ipc_client.py`의 `send_motion` 메서드(20-27줄) 바로 뒤에 추가:
```python
    def send_color_match(self, x: int, y: int) -> None:
        msg = (json.dumps({"event": "color_match", "x": x, "y": y}) + "\n").encode()
        with self._lock:
            if self._sock:
                try:
                    self._sock.sendall(msg)
                except OSError:
                    pass
```

- [ ] **Step 3: Verify import/syntax**
  ```
  cd auto-capture && python -c "from core.ipc_client import IpcClient; assert hasattr(IpcClient, 'send_color_match')"
  ```
  예상: 에러 없이 종료(exit 0).

- [ ] **Step 4: Commit**
  ```
  cd auto-capture && git add core/ipc_client.py && git commit -m "feat(capture): IpcClient.send_color_match 추가"
  ```

---

### Task A3: pick_pixel_color + 돋보기 패널

**Files:**
- Create: `auto-capture/ui/color_picker.py`
- Test: 풀스크린 오버레이·실시간 mss 캡처는 GUI 상호작용 의존이라 유닛테스트가 부적합하다. 헤드리스 검증이 가능한 순수 헬퍼(`_loupe_geometry`)만 유닛테스트한다.
- Test file: `auto-capture/tests/test_color_picker.py`

**Interfaces:**
- Consumes: 없음(독립 진입 함수). `point_picker.py`의 풀스크린 오버레이 패턴 재사용.
- Produces:
  - `pick_pixel_color() -> tuple[int, int, tuple[int, int, int]] | None` — 사용자가 클릭한 `(글로벌x, 글로벌y, (r, g, b))`. ESC 시 `None`.
  - `_loupe_geometry(cursor_x, panel_w, screen_w) -> int` — 돋보기 패널의 x 위치(커서 오른쪽 기본, 우측 경계 부족 시 왼쪽 flip)를 반환하는 순수 함수.

**돋보기 사양 (스펙 §2):** 커서 주변 15×15px를 mss로 캡처 → 8배 nearest-neighbor 확대(120×120px) → 패널을 커서 오른쪽에 렌더링, 우측 경계 여유 없으면 왼쪽 flip. 중앙 픽셀(실제 선택될 픽셀)은 강조 테두리, 하단에 현재 `(r, g, b)` 텍스트 표시. 캡처 실패 프레임은 조용히 건너뛰고 다음 `mouseMoveEvent`에서 재시도.

- [ ] **Step 1: Write the failing test**

`auto-capture/tests/test_color_picker.py`:
```python
def test_loupe_stays_right_when_space_available():
    from ui.color_picker import _loupe_geometry
    # 커서 x=100, 패널폭 140, 화면폭 1920 → 오른쪽 배치 (커서 + 여백)
    x = _loupe_geometry(cursor_x=100, panel_w=140, screen_w=1920)
    assert x > 100


def test_loupe_flips_left_near_right_edge():
    from ui.color_picker import _loupe_geometry
    # 커서가 오른쪽 끝 근처 → 왼쪽으로 flip (패널 오른쪽 끝이 화면 안)
    x = _loupe_geometry(cursor_x=1900, panel_w=140, screen_w=1920)
    assert x + 140 <= 1900
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-capture && python -m pytest tests/test_color_picker.py -v
  ```
  예상: `ModuleNotFoundError` 또는 `ImportError: cannot import name '_loupe_geometry'`.

- [ ] **Step 3: Write minimal implementation**

`auto-capture/ui/color_picker.py`:
```python
import sys

import numpy as np
import mss
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QEventLoop, QPoint, QObject, QEvent, Signal, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication, QImage

_LOUPE_SRC = 15        # 캡처할 원본 영역 한 변(px)
_LOUPE_SCALE = 8       # 확대 배율
_LOUPE_PANEL = _LOUPE_SRC * _LOUPE_SCALE  # 120px
_PANEL_MARGIN = 20     # 커서와 패널 사이 여백
_TEXT_H = 22           # 하단 RGB 텍스트 영역 높이


def _loupe_geometry(cursor_x: int, panel_w: int, screen_w: int) -> int:
    """돋보기 패널 좌상단 x 좌표. 기본은 커서 오른쪽, 우측 여유 없으면 왼쪽 flip."""
    right_x = cursor_x + _PANEL_MARGIN
    if right_x + panel_w <= screen_w:
        return right_x
    return max(0, cursor_x - _PANEL_MARGIN - panel_w)


class _EscFilter(QObject):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._callback()
            return True
        return False


class _ColorPickerOverlay(QWidget):
    def __init__(self, screen, shared: dict):
        super().__init__()
        self._screen = screen
        self._shared = shared
        self._cursor_pos = QPoint(0, 0)
        self._loupe_img: QImage | None = None
        self._center_rgb = (0, 0, 0)

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.show()
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

    def mouseMoveEvent(self, event):
        self._cursor_pos = event.position().toPoint()
        self._update_loupe()
        self.update()

    def _update_loupe(self):
        origin = self._screen.geometry().topLeft()
        gx = self._cursor_pos.x() + origin.x()
        gy = self._cursor_pos.y() + origin.y()
        half = _LOUPE_SRC // 2
        region = {"left": gx - half, "top": gy - half,
                  "width": _LOUPE_SRC, "height": _LOUPE_SRC}
        try:
            with mss.mss() as sct:
                raw = np.array(sct.grab(region))[:, :, :3]  # BGR
        except Exception:
            return  # 경계 근처 캡처 실패 → 조용히 스킵, 다음 move에서 재시도
        if raw.shape[0] != _LOUPE_SRC or raw.shape[1] != _LOUPE_SRC:
            return
        b, g, r = int(raw[half, half, 0]), int(raw[half, half, 1]), int(raw[half, half, 2])
        self._center_rgb = (r, g, b)
        # BGR → RGB 후 QImage 생성, nearest-neighbor 8배 확대
        rgb = raw[:, :, ::-1].copy()
        img = QImage(rgb.data, _LOUPE_SRC, _LOUPE_SRC,
                     3 * _LOUPE_SRC, QImage.Format_RGB888)
        self._loupe_img = img.scaled(_LOUPE_PANEL, _LOUPE_PANEL,
                                     Qt.IgnoreAspectRatio, Qt.FastTransformation)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))

        x = self._cursor_pos.x()
        y = self._cursor_pos.y()

        pen = QPen(QColor("#4ecca3"), 1)
        p.setPen(pen)
        p.drawLine(0, y, self.width(), y)
        p.drawLine(x, 0, x, self.height())

        hint = "클릭하여 색 지정  |  ESC 취소"
        p.setPen(QColor(255, 255, 255, 160))
        hint_font = QFont()
        hint_font.setPixelSize(14)
        p.setFont(hint_font)
        p.drawText(self.width() // 2 - 110, 32, hint)

        if self._loupe_img is not None:
            panel_h = _LOUPE_PANEL + _TEXT_H
            px = _loupe_geometry(x, _LOUPE_PANEL, self.width())
            py = max(0, min(y - _LOUPE_PANEL // 2, self.height() - panel_h))
            # 패널 배경
            p.setBrush(QColor(15, 15, 30, 230))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(px - 2, py - 2, _LOUPE_PANEL + 4, panel_h + 4, 6, 6)
            # 확대 이미지
            p.drawImage(QRect(px, py, _LOUPE_PANEL, _LOUPE_PANEL), self._loupe_img)
            # 중앙 픽셀 강조 테두리
            cell = _LOUPE_SCALE
            cx = px + (_LOUPE_SRC // 2) * cell
            cy = py + (_LOUPE_SRC // 2) * cell
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#4ecca3"), 2))
            p.drawRect(cx, cy, cell, cell)
            # RGB 텍스트
            r, g, b = self._center_rgb
            p.setPen(QColor("#cccccc"))
            txt_font = QFont()
            txt_font.setPixelSize(12)
            p.setFont(txt_font)
            p.drawText(px, py + _LOUPE_PANEL, _LOUPE_PANEL, _TEXT_H,
                       Qt.AlignCenter, f"RGB({r}, {g}, {b})")

    def mousePressEvent(self, event):
        self._update_loupe()
        pos = event.position().toPoint()
        origin = self._screen.geometry().topLeft()
        self._shared["result"] = (
            pos.x() + origin.x(), pos.y() + origin.y(), self._center_rgb
        )
        self._shared["close_fn"]()


def pick_pixel_color() -> tuple[int, int, tuple[int, int, int]] | None:
    """풀스크린 오버레이로 픽셀 색을 샘플링. (글로벌x, 글로벌y, (r,g,b)) 반환, ESC시 None."""
    loop = QEventLoop()
    shared: dict = {"result": None, "loop": loop, "widgets": [],
                    "close_fn": None, "_closed": False, "_esc_filter": None}

    def close_all():
        if shared["_closed"]:
            return
        shared["_closed"] = True
        app = QApplication.instance()
        if app and shared["_esc_filter"]:
            app.removeEventFilter(shared["_esc_filter"])
        for w in shared["widgets"]:
            w.close()
        loop.quit()

    shared["close_fn"] = close_all
    esc_filter = _EscFilter(close_all)
    shared["_esc_filter"] = esc_filter
    QApplication.instance().installEventFilter(esc_filter)

    for screen in QGuiApplication.screens():
        overlay = _ColorPickerOverlay(screen, shared)
        shared["widgets"].append(overlay)

    loop.exec()
    return shared["result"]
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-capture && python -m pytest tests/test_color_picker.py -v
  ```
  예상: `2 passed`.

- [ ] **Step 5: Commit**
  ```
  cd auto-capture && git add ui/color_picker.py tests/test_color_picker.py && git commit -m "feat(capture): pick_pixel_color 돋보기 색 피커 추가"
  ```

---

### Task A4: ColorCaptureTab 위젯

**Files:**
- Create: `auto-capture/ui/color_capture_tab.py`
- Test: `auto-capture/tests/test_color_capture_tab.py`

**Interfaces:**
- Consumes: `pick_pixel_color()`(A3), `select_region()`(기존 `ui/region_select.py`).
- Produces: `ColorCaptureTab(QWidget)`
  - 시그널: `start_requested(dict, tuple, int)` (region, target_rgb, tolerance), `stop_requested()`.
  - 프로퍼티/메서드: `target_rgb -> tuple | None`, `region -> dict | None`, `set_monitoring(active: bool)`, `set_status(text: str)`.
  - 위젯: RGB 샘플 버튼 + 색상 스와치 라벨, 허용오차 스핀박스(range 0–100, 기본 10), 감시영역 지정 버튼, 시작/정지 버튼(QStackedWidget으로 전환), 상태 라벨.

- [ ] **Step 1: Write the failing test**

`auto-capture/tests/test_color_capture_tab.py`:
```python
from unittest.mock import patch


def test_start_disabled_until_color_and_region_set(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    # 색·영역 둘 다 미지정 → 시작 불가
    assert tab.target_rgb is None
    assert tab.region is None
    assert not tab._start_btn.isEnabled()


def test_sampling_color_updates_swatch(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    assert tab.target_rgb == (200, 100, 30)


def test_start_emitted_with_params(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    with patch("ui.color_capture_tab.select_region",
               return_value={"left": 0, "top": 0, "width": 10, "height": 10}):
        tab._on_pick_region()
    tab._tolerance.setValue(12)

    with qtbot.waitSignal(tab.start_requested, timeout=1000) as blocker:
        tab._start_btn.click()
    region, rgb, tol = blocker.args
    assert rgb == (200, 100, 30)
    assert tol == 12
    assert region["width"] == 10
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-capture && python -m pytest tests/test_color_capture_tab.py -v
  ```
  예상: `ModuleNotFoundError: No module named 'ui.color_capture_tab'`.

- [ ] **Step 3: Write minimal implementation**

`auto-capture/ui/color_capture_tab.py`:
```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget
)
from PySide6.QtCore import Qt, Signal

from ui.color_picker import pick_pixel_color
from ui.region_select import select_region

_BTN_GREEN = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 15px; font-weight: bold;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_RED = """
    QPushButton {
        background-color: #e05555; color: white;
        border: none; border-radius: 8px;
        font-size: 15px; font-weight: bold;
    }
    QPushButton:hover { background-color: #c04444; }
"""

_BTN_OUTLINE = """
    QPushButton {
        background-color: transparent; color: #4ecca3;
        border: 1px solid #4ecca3; border-radius: 8px;
        font-size: 13px; padding: 6px;
    }
    QPushButton:hover { background-color: rgba(78,204,163,0.1); }
"""

_SPIN_STYLE = """
    QSpinBox {
        background-color: #2a2a4e; color: #cccccc;
        border: 1px solid #3a3a6e; border-radius: 4px;
        font-size: 13px; padding: 2px 4px;
    }
"""


class ColorCaptureTab(QWidget):
    start_requested = Signal(dict, tuple, int)
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_rgb: tuple[int, int, int] | None = None
        self._region: dict | None = None
        self._build_ui()

    @property
    def target_rgb(self) -> tuple[int, int, int] | None:
        return self._target_rgb

    @property
    def region(self) -> dict | None:
        return self._region

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)

        # 색 샘플 행
        color_row = QHBoxLayout()
        self._pick_color_btn = QPushButton("색 지정")
        self._pick_color_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_color_btn.clicked.connect(self._on_pick_color)
        color_row.addWidget(self._pick_color_btn)
        self._swatch = QLabel()
        self._swatch.setFixedSize(40, 28)
        self._swatch.setStyleSheet("background-color: #2a2a4e; border-radius: 4px;")
        color_row.addWidget(self._swatch)
        layout.addLayout(color_row)

        # 허용오차 행
        tol_row = QHBoxLayout()
        tol_lbl = QLabel("허용오차:")
        tol_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        tol_row.addWidget(tol_lbl)
        self._tolerance = QSpinBox()
        self._tolerance.setRange(0, 100)
        self._tolerance.setValue(10)
        self._tolerance.setStyleSheet(_SPIN_STYLE)
        tol_row.addWidget(self._tolerance)
        tol_row.addStretch()
        layout.addLayout(tol_row)

        # 감시영역 행
        self._pick_region_btn = QPushButton("감시 영역 지정")
        self._pick_region_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_region_btn.clicked.connect(self._on_pick_region)
        layout.addWidget(self._pick_region_btn)

        layout.addStretch()

        # 시작/정지 스택
        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)
        self._start_btn = QPushButton("시작")
        self._start_btn.setFixedHeight(44)
        self._start_btn.setStyleSheet(_BTN_GREEN)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start)
        self._btn_stack.addWidget(self._start_btn)
        self._stop_btn = QPushButton("중지")
        self._stop_btn.setFixedHeight(44)
        self._stop_btn.setStyleSheet(_BTN_RED)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        self._btn_stack.addWidget(self._stop_btn)
        layout.addWidget(self._btn_stack)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _refresh_start_enabled(self) -> None:
        self._start_btn.setEnabled(
            self._target_rgb is not None and self._region is not None
        )

    def _on_pick_color(self) -> None:
        result = pick_pixel_color()
        if result is None:
            return
        _x, _y, rgb = result
        self._target_rgb = rgb
        r, g, b = rgb
        self._swatch.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border-radius: 4px;"
        )
        self._refresh_start_enabled()

    def _on_pick_region(self) -> None:
        region = select_region()
        if region is None:
            return
        self._region = region
        self._pick_region_btn.setText("감시 영역 지정됨 ✓")
        self._refresh_start_enabled()

    def _on_start(self) -> None:
        if self._target_rgb is None or self._region is None:
            return
        self.start_requested.emit(self._region, self._target_rgb, self._tolerance.value())

    def set_monitoring(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._pick_color_btn.setEnabled(not active)
        self._pick_region_btn.setEnabled(not active)
        self._tolerance.setEnabled(not active)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-capture && python -m pytest tests/test_color_capture_tab.py -v
  ```
  예상: `3 passed`.

- [ ] **Step 5: Commit**
  ```
  cd auto-capture && git add ui/color_capture_tab.py tests/test_color_capture_tab.py && git commit -m "feat(capture): ColorCaptureTab 위젯 추가"
  ```

---

### Task A5: Launcher QTabWidget 도입 + main.py 와이어링

**Files:**
- Modify: `auto-capture/ui/launcher.py` (`_build_ui`에 `QTabWidget` 도입, 기존 콘텐츠 탭1, `ColorCaptureTab` 탭2; `setFixedSize` → 탭 수용 크기)
- Modify: `auto-capture/main.py` (`ColorMonitorThread` 임포트, 컬러 탭 start/stop 핸들러 및 `color_detected → QCursor.setPos + ipc_client.send_color_match` 와이어링, 두 모드 상호배타)
- Test: 없음 — 순수 통합·GUI 와이어링이며 Phase C 수동 확인으로 검증.

**Interfaces:**
- Consumes: `ColorCaptureTab`(A4)의 `start_requested(dict, tuple, int)`/`stop_requested()`, `ColorMonitorThread`(A1)의 `color_detected`/`stopped`, `IpcClient.send_color_match`(A2).
- Produces: `Launcher.color_tab` 속성(외부에서 `ColorCaptureTab` 인스턴스 접근용). 기존 `start_requested` 등 탭1 시그널은 무변경.

**상호배타 규칙 (스펙 §4):** 컬러 탭 감시 중에는 기존 탭의 시작 버튼 비활성화(역방향 동일). auto-capture는 탭1(MonitorThread)과 탭2(ColorMonitorThread)를 동시에 실행하지 않는다 — `main.py`에서 한쪽이 running이면 다른 쪽 시작 요청을 무시.

- [ ] **Step 1: Launcher에 QTabWidget 도입**

`launcher.py` 임포트에 `QTabWidget` 추가하고 `from ui.color_capture_tab import ColorCaptureTab` 추가. `_build_ui`를 다음 구조로 변경한다:
  - `self.setFixedSize(320, 440)` → `self.setFixedSize(360, 520)` (탭바 + 컬러 탭 컨트롤 수용).
  - 최상단에 `QTabWidget` 생성. 기존 `_build_ui`가 만들던 위젯 트리 전체를 내부 헬퍼 `_build_capture_page() -> QWidget`로 옮겨 탭1("화면 변화")로 addTab. `self.color_tab = ColorCaptureTab()`를 탭2("컬러 감지")로 addTab.
  - `QTabWidget` 스타일시트(기존 팔레트 유지):
    ```python
    self._tabs.setStyleSheet("""
        QTabWidget::pane { border: none; }
        QTabBar::tab {
            background: #2a2a4e; color: #888888;
            padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px;
        }
        QTabBar::tab:selected { background: #4ecca3; color: #1a1a2e; font-weight: bold; }
    """)
    ```
  - 기존 `set_monitoring`/`set_paused`/`reset`/연결 버튼 로직은 탭1 페이지 위젯을 대상으로 그대로 유지.

- [ ] **Step 2: main.py 컬러 모드 와이어링**

`main.py`에 `from core.color_monitor import ColorMonitorThread` 추가. 다음 핸들러를 추가하고 `launcher.color_tab` 시그널에 연결:
```python
    color_thread: ColorMonitorThread | None = None

    def on_color_start(region, target_rgb, tolerance):
        nonlocal color_thread
        # 상호배타: 기존 탭1 모니터가 돌고 있으면 무시
        if any(t.isRunning() for t in monitor_threads):
            return
        if color_thread is not None and color_thread.isRunning():
            return
        t = ColorMonitorThread(region, target_rgb, tolerance)
        t.color_detected.connect(on_color_detected)
        t.stopped.connect(on_color_stopped)
        t.start()
        color_thread = t
        launcher.color_tab.set_monitoring(True)
        launcher.color_tab.set_status("컬러 감시 중...")
        tray.show()
        tray.set_status("컬러 감시 중...")

    def on_color_detected(x, y):
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_color_match(x, y)
        launcher.color_tab.set_status(f"감지! ({x}, {y}) 신호 전송")

    def on_color_stop():
        nonlocal color_thread
        if color_thread is not None and color_thread.isRunning():
            color_thread.requestInterruption()
            color_thread.wait()

    def on_color_stopped():
        launcher.color_tab.set_monitoring(False)
        launcher.color_tab.set_status("")
        if not any(t.isRunning() for t in monitor_threads):
            tray.hide()

    launcher.color_tab.start_requested.connect(on_color_start)
    launcher.color_tab.stop_requested.connect(on_color_stop)
```
  또한 기존 `on_start`(탭1)에 상호배타 가드 추가: `if color_thread is not None and color_thread.isRunning(): return`. `on_quit`에 `on_color_stop()` 호출 추가.

- [ ] **Step 3: 전체 회귀 테스트**
  ```
  cd auto-capture && python -m pytest -v
  ```
  예상: 기존 `test_monitor.py` 2개 + 신규 `test_color_monitor.py` 2개 + `test_color_picker.py` 2개 + `test_color_capture_tab.py` 3개 = `9 passed`. 기존 테스트 무회귀.

- [ ] **Step 4: 임포트/기동 스모크 확인**
  ```
  cd auto-capture && python -c "import ui.launcher, main; print('import ok')"
  ```
  예상: `import ok`.

- [ ] **Step 5: Commit**
  ```
  cd auto-capture && git add ui/launcher.py main.py && git commit -m "feat(capture): QTabWidget 도입 및 컬러 감지 모드 와이어링"
  ```

---

## Phase B — auto-clicker (워커: surface:2)

작업 디렉토리 기준 경로: 모든 경로는 `auto-clicker/` 하위. 테스트 실행은 `auto-clicker/` 디렉토리에서 `python -m pytest`.

TDD 순서: 순수 로직(click_engine 리팩터 + 연속클릭 엔진) → IPC 확장 → UI 위젯(탭) → 진입점 와이어링.

---

### Task B1: click_engine 리팩터 — _run_points_sequence + start_from_color

**Files:**
- Modify: `auto-clicker/core/click_engine.py:34-67` (`run`에서 포인트 순회를 `_run_points_sequence(mouse)`로 추출, `start_from_color` 진입점 추가)
- Test: `auto-clicker/tests/test_click_engine.py` (기존 파일에 테스트 추가)

**Interfaces:**
- Consumes: 기존 `set_points(points)`, `ClickPoint`.
- Produces: `ClickEngine.start_from_color(x: int, y: int, click_type: str = "left") -> None` — 지정 좌표로 마우스 이동 후 클릭하고 이어서 `_run_points_sequence()` 실행. 기존 `start_standalone`/`start_from_capture`는 동작 무변경(내부적으로 `_run_points_sequence` 공유).

- [ ] **Step 1: Write the failing test**

`auto-clicker/tests/test_click_engine.py` 파일 끝에 추가:
```python
def test_start_from_color_moves_to_coord_then_sequence(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=100, y=200, ms=10, click_type="left")])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_from_color(777, 888, "left")
        engine.wait()

    # 감지 좌표 클릭 1 + 시퀀스 포인트 1 = press 2회
    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2
```

> 주: `pynput` Controller의 `position`은 프로퍼티 대입(`mouse.position = (x, y)`)이라 MagicMock 속성 대입 순서 검증은 번거롭다. 이 테스트는 **클릭 횟수(press/release 각 2회)**만 강하게 검증한다. 감지 좌표 이동이 시퀀스보다 먼저 실행되는 순서는 아래 Step 3 구현이 보장하며(코드상 `_color_target` 처리가 `_run_points_sequence()` 호출보다 앞에 위치), Phase C에서 육안으로도 확인한다.

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-clicker && python -m pytest tests/test_click_engine.py::test_start_from_color_moves_to_coord_then_sequence -v
  ```
  예상: `AttributeError: 'ClickEngine' object has no attribute 'start_from_color'`.

- [ ] **Step 3: Write minimal implementation**

`click_engine.py`를 다음과 같이 리팩터한다. `__init__`에 `self._color_target: tuple[int, int, str] | None = None` 추가. 진입점 추가:
```python
    def start_from_color(self, x: int, y: int, click_type: str = "left") -> None:
        if self.isRunning():
            return
        self._capture_click_type = None
        self._color_target = (x, y, click_type)
        self.start()
```
`run`을 다음으로 교체(포인트 순회를 `_run_points_sequence`로 추출):
```python
    def run(self) -> None:
        mouse = Controller()

        if self._capture_click_type is not None:
            if self._capture_click_type == "double":
                self._do_click(mouse, Button.left)
                time.sleep(_PRESS_HOLD_S)
                self._do_click(mouse, Button.left)
            else:
                btn = Button.left if self._capture_click_type == "left" else Button.right
                self._do_click(mouse, btn)

        if self._color_target is not None:
            cx, cy, ctype = self._color_target
            self._color_target = None
            mouse.position = (cx, cy)
            time.sleep(_MOVE_SETTLE_S)
            if ctype == "double":
                self._do_click(mouse, Button.left)
                time.sleep(_PRESS_HOLD_S)
                self._do_click(mouse, Button.left)
            else:
                btn = Button.left if ctype == "left" else Button.right
                self._do_click(mouse, btn)

        self._run_points_sequence(mouse)

        if not self.isInterruptionRequested():
            self.sequence_finished.emit()

    def _run_points_sequence(self, mouse: Controller) -> None:
        for point in self._points:
            if self.isInterruptionRequested():
                break
            self._interruptible_sleep(point.delay_ms / 1000)
            if self.isInterruptionRequested():
                break
            mouse.position = (point.x, point.y)
            time.sleep(_MOVE_SETTLE_S)
            if self.isInterruptionRequested():
                break
            if point.click_type == "double":
                self._do_click(mouse, Button.left)
                time.sleep(_PRESS_HOLD_S)
                self._do_click(mouse, Button.left)
            else:
                button = Button.left if point.click_type == "left" else Button.right
                self._do_click(mouse, button)
```
  또한 `start_standalone`/`start_from_capture`에 `self._color_target = None` 초기화를 추가해 상태 누수를 막는다.

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-clicker && python -m pytest tests/test_click_engine.py -v
  ```
  예상: 기존 5개 + 신규 1개 = `6 passed`(기존 무회귀).

- [ ] **Step 5: Commit**
  ```
  cd auto-clicker && git add core/click_engine.py tests/test_click_engine.py && git commit -m "feat(clicker): _run_points_sequence 추출 및 start_from_color 진입점 추가"
  ```

---

### Task B2: ContinuousClickEngine (가우시안 지터 연속 클릭)

**Files:**
- Create: `auto-clicker/core/continuous_click_engine.py`
- Test: `auto-clicker/tests/test_continuous_click_engine.py`

**Interfaces:**
- Consumes: 없음(고정 좌표·min/max ms를 생성자로 받음).
- Produces: `ContinuousClickEngine(x: int, y: int, min_ms: int, max_ms: int, click_type: str = "left")` — `start()` 시 고정 좌표를 가우시안 지터 간격으로 반복 클릭. `stop()`(`requestInterruption()`+`wait()`)으로 즉시 중단.

**지터 알고리즘 (스펙 §1, §2):** 간격은 정규분포에서 샘플링. 평균 `mu = (min_ms + max_ms) / 2`, 표준편차 `sigma = (max_ms - min_ms) / 4`(양끝이 ±2σ). 샘플값은 `[min_ms, max_ms]`로 clip.

- [ ] **Step 1: Write the failing test**

`auto-clicker/tests/test_continuous_click_engine.py`:
```python
import time
from unittest.mock import MagicMock, patch


def test_intervals_within_range():
    """가우시안 샘플이 [min_ms, max_ms] 범위 내로 clip되는지 통계적으로 검증."""
    from core.continuous_click_engine import ContinuousClickEngine

    eng = ContinuousClickEngine(x=0, y=0, min_ms=100, max_ms=300)
    samples = [eng._next_interval_ms() for _ in range(2000)]
    assert all(100 <= s <= 300 for s in samples)
    mean = sum(samples) / len(samples)
    # 평균이 중앙값(200) 근처인지 (clip 때문에 정확히 200은 아니지만 근접)
    assert 180 <= mean <= 220


def test_continuous_clicks_repeatedly_until_stop(qtbot):
    mock_mouse = MagicMock()
    with patch("core.continuous_click_engine.Controller", return_value=mock_mouse):
        from core.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine(x=10, y=20, min_ms=10, max_ms=20)
        eng.start()
        time.sleep(0.3)
        eng.stop()

    # 0.3초 동안 ~10-20ms 간격이면 최소 여러 번 클릭됨
    assert mock_mouse.press.call_count >= 3
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-clicker && python -m pytest tests/test_continuous_click_engine.py -v
  ```
  예상: `ModuleNotFoundError: No module named 'core.continuous_click_engine'`.

- [ ] **Step 3: Write minimal implementation**

`auto-clicker/core/continuous_click_engine.py`:
```python
import random
import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

_PRESS_HOLD_S = 0.02
_MOVE_SETTLE_S = 0.02


class ContinuousClickEngine(QThread):
    stopped = Signal()

    def __init__(self, x: int, y: int, min_ms: int, max_ms: int,
                 click_type: str = "left", parent=None):
        super().__init__(parent)
        self._x = x
        self._y = y
        self._min_ms = int(min_ms)
        self._max_ms = int(max_ms)
        self._click_type = click_type

    def _next_interval_ms(self) -> float:
        mu = (self._min_ms + self._max_ms) / 2
        sigma = (self._max_ms - self._min_ms) / 4
        if sigma <= 0:
            return float(self._min_ms)
        sample = random.gauss(mu, sigma)
        return max(self._min_ms, min(self._max_ms, sample))

    def run(self) -> None:
        mouse = Controller()
        try:
            mouse.position = (self._x, self._y)
            time.sleep(_MOVE_SETTLE_S)
            while not self.isInterruptionRequested():
                self._do_click(mouse)
                self._interruptible_sleep(self._next_interval_ms() / 1000)
        finally:
            self.stopped.emit()

    def _do_click(self, mouse: Controller) -> None:
        if self.isInterruptionRequested():
            return
        try:
            if self._click_type == "double":
                mouse.press(Button.left); time.sleep(_PRESS_HOLD_S); mouse.release(Button.left)
                time.sleep(_PRESS_HOLD_S)
                mouse.press(Button.left); time.sleep(_PRESS_HOLD_S); mouse.release(Button.left)
            else:
                btn = Button.left if self._click_type == "left" else Button.right
                mouse.press(btn); time.sleep(_PRESS_HOLD_S); mouse.release(btn)
        except Exception:
            pass

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.isInterruptionRequested():
                return
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-clicker && python -m pytest tests/test_continuous_click_engine.py -v
  ```
  예상: `2 passed`.

- [ ] **Step 5: Commit**
  ```
  cd auto-clicker && git add core/continuous_click_engine.py tests/test_continuous_click_engine.py && git commit -m "feat(clicker): ContinuousClickEngine 가우시안 지터 연속 클릭 추가"
  ```

---

### Task B3: IpcServer color_match 이벤트 파싱

**Files:**
- Modify: `auto-clicker/core/ipc_server.py:9-13` (신규 시그널 선언), `:83-88` (`_handle` 파싱 분기 추가)
- Test: `auto-clicker/tests/test_ipc_server.py` (기존 파일에 테스트 추가)

**Interfaces:**
- Consumes: Global Constraints의 `color_match` JSON.
- Produces: `IpcServer.color_match_received(int, int)` 시그널. 기존 `motion_received` 분기 무변경.

- [ ] **Step 1: Write the failing test**

`auto-clicker/tests/test_ipc_server.py` 파일 끝에 추가:
```python
def test_color_match_signal_emitted(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    server.start()
    time.sleep(0.15)

    try:
        with qtbot.waitSignal(server.color_match_received, timeout=2000) as blocker:
            with socket.create_connection(("127.0.0.1", 54321), timeout=1.0) as s:
                s.sendall(
                    json.dumps({"event": "color_match", "x": 111, "y": 222}).encode() + b"\n"
                )
    finally:
        server.stop()

    assert blocker.args == [111, 222]
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-clicker && python -m pytest tests/test_ipc_server.py::test_color_match_signal_emitted -v
  ```
  예상: `AttributeError: 'IpcServer' object has no attribute 'color_match_received'`.

- [ ] **Step 3: Write minimal implementation**

`ipc_server.py` 클래스 시그널 선언에 추가(9-13줄 영역):
```python
    color_match_received = Signal(int, int)
```
`_handle`의 JSON 파싱 분기(85-86줄)에 `elif`를 추가:
```python
                    if msg.get("event") == "motion":
                        self.motion_received.emit(int(msg["x"]), int(msg["y"]))
                    elif msg.get("event") == "color_match":
                        self.color_match_received.emit(int(msg["x"]), int(msg["y"]))
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-clicker && python -m pytest tests/test_ipc_server.py -v
  ```
  예상: 기존 2개 + 신규 1개 = `3 passed`(기존 `motion` 무회귀).

- [ ] **Step 5: Commit**
  ```
  cd auto-clicker && git add core/ipc_server.py tests/test_ipc_server.py && git commit -m "feat(clicker): IpcServer color_match 이벤트 파싱 추가"
  ```

---

### Task B4: ColorClickerTab 위젯

**Files:**
- Create: `auto-clicker/ui/color_clicker_tab.py`
- Test: `auto-clicker/tests/test_color_clicker_tab.py`

**Interfaces:**
- Consumes: `pick_point()`(기존 `ui/point_picker.py`).
- Produces: `ColorClickerTab(QWidget)`
  - 시그널: `start_requested()`, `stop_requested()`.
  - 프로퍼티/메서드: `point -> tuple[int, int] | None`, `min_ms -> int`, `max_ms -> int`, `click_type -> str`, `set_running(active: bool)`, `set_status(text: str)`.
  - 위젯: 연속클릭 지점 지정 버튼(`pick_point` 재사용), min/max ms 스핀박스 2개(기존 `_spin_style` 재사용), 시작/정지 버튼(QStackedWidget), 상태 라벨. 기본 탭 `ClickPoint` 목록은 `MainWindow`가 소유하므로 이 위젯은 참조하지 않는다(감지 후 시퀀스는 B5에서 `MainWindow._rows`로 주입).

- [ ] **Step 1: Write the failing test**

`auto-clicker/tests/test_color_clicker_tab.py`:
```python
from unittest.mock import patch


def test_start_disabled_until_point_set(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab.point is None
    assert not tab._start_btn.isEnabled()


def test_pick_point_enables_start(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    assert tab.point == (333, 444)
    assert tab._start_btn.isEnabled()


def test_min_max_defaults_and_start_signal(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    tab._min_spin.setValue(50)
    tab._max_spin.setValue(150)
    with qtbot.waitSignal(tab.start_requested, timeout=1000):
        tab._start_btn.click()
    assert tab.min_ms == 50
    assert tab.max_ms == 150
```

- [ ] **Step 2: Run test to verify it fails**
  ```
  cd auto-clicker && python -m pytest tests/test_color_clicker_tab.py -v
  ```
  예상: `ModuleNotFoundError: No module named 'ui.color_clicker_tab'`.

- [ ] **Step 3: Write minimal implementation**

`auto-clicker/ui/color_clicker_tab.py`:
```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QStackedWidget, QApplication
)
from PySide6.QtCore import Qt, Signal

from ui.point_picker import pick_point
from ui.click_point_row import _spin_style  # 기존 스핀박스 스타일 재사용

_BTN_PRIMARY = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 14px; font-weight: bold; padding: 8px 20px;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_DANGER = """
    QPushButton {
        background-color: transparent; color: #e05555;
        border: 1px solid #e05555; border-radius: 8px;
        font-size: 14px; font-weight: bold; padding: 8px 20px;
    }
    QPushButton:hover { background-color: rgba(224,85,85,0.1); }
"""

_BTN_OUTLINE = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
"""


class ColorClickerTab(QWidget):
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._point: tuple[int, int] | None = None
        self._build_ui()

    @property
    def point(self) -> tuple[int, int] | None:
        return self._point

    @property
    def min_ms(self) -> int:
        return self._min_spin.value()

    @property
    def max_ms(self) -> int:
        return self._max_spin.value()

    @property
    def click_type(self) -> str:
        return "left"

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        desc = QLabel("컬러 감지 전까지 이 지점을 연속 클릭합니다")
        desc.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc)

        self._pick_btn = QPushButton("연속 클릭 지점 지정")
        self._pick_btn.setStyleSheet(_BTN_OUTLINE)
        self._pick_btn.clicked.connect(self._on_pick_point)
        layout.addWidget(self._pick_btn)

        # min/max ms 행
        ms_row = QHBoxLayout()
        min_lbl = QLabel("최소:")
        min_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        ms_row.addWidget(min_lbl)
        self._min_spin = QSpinBox()
        self._min_spin.setRange(1, 10000)
        self._min_spin.setValue(80)
        self._min_spin.setSuffix(" ms")
        self._min_spin.setFixedWidth(90)
        self._min_spin.setStyleSheet(_spin_style())
        ms_row.addWidget(self._min_spin)
        max_lbl = QLabel("최대:")
        max_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        ms_row.addWidget(max_lbl)
        self._max_spin = QSpinBox()
        self._max_spin.setRange(1, 10000)
        self._max_spin.setValue(200)
        self._max_spin.setSuffix(" ms")
        self._max_spin.setFixedWidth(90)
        self._max_spin.setStyleSheet(_spin_style())
        ms_row.addWidget(self._max_spin)
        ms_row.addStretch()
        layout.addLayout(ms_row)

        layout.addStretch()

        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)
        self._start_btn = QPushButton("▶ 시작")
        self._start_btn.setStyleSheet(_BTN_PRIMARY)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(lambda: self.start_requested.emit())
        self._btn_stack.addWidget(self._start_btn)
        self._stop_btn = QPushButton("■ 중지")
        self._stop_btn.setStyleSheet(_BTN_DANGER)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        self._btn_stack.addWidget(self._stop_btn)
        layout.addWidget(self._btn_stack)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _on_pick_point(self) -> None:
        win = self.window()
        win.hide()
        QApplication.processEvents()
        result = pick_point()
        win.show()
        win.raise_()
        win.activateWindow()
        if result is None:
            return
        x, y = result
        self._point = (x, y)
        self._pick_btn.setText(f"연속 클릭 지점: ({x}, {y})")
        self._start_btn.setEnabled(True)

    def set_running(self, active: bool) -> None:
        self._btn_stack.setCurrentIndex(1 if active else 0)
        self._pick_btn.setEnabled(not active)
        self._min_spin.setEnabled(not active)
        self._max_spin.setEnabled(not active)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)
```

- [ ] **Step 4: Run test to verify it passes**
  ```
  cd auto-clicker && python -m pytest tests/test_color_clicker_tab.py -v
  ```
  예상: `3 passed`.

- [ ] **Step 5: Commit**
  ```
  cd auto-clicker && git add ui/color_clicker_tab.py tests/test_color_clicker_tab.py && git commit -m "feat(clicker): ColorClickerTab 위젯 추가"
  ```

---

### Task B5: MainWindow QTabWidget 도입 + color_match 와이어링

**Files:**
- Modify: `auto-clicker/ui/main_window.py` (`_build_ui`에 `QTabWidget` 도입, 기존 콘텐츠 탭1, `ColorClickerTab` 탭2; `ContinuousClickEngine`/`ColorClickerTab` 임포트; `color_match_received` 와이어링; `closeEvent`에 연속엔진 정리)
- Modify: `auto-clicker/main.py` — 변경 없음(진입점은 `MainWindow`만 생성하므로 수정 불필요). 확인만 수행.
- Test: 없음 — 순수 통합·GUI 와이어링이며 Phase C 수동 확인으로 검증.

**Interfaces:**
- Consumes: `ColorClickerTab`(B4) 시그널, `ContinuousClickEngine`(B2), `IpcServer.color_match_received`(B3), 기존 `ClickEngine.start_from_color`(B1), 기존 `self._rows`(탭1의 `ClickPoint` 목록).
- Produces: 없음(최종 통합 지점).

**감지 후 시퀀스 (스펙 §3 6단계):** `color_match_received(x, y)` 수신 시 → 실행 중인 `ContinuousClickEngine.stop()` → `ClickEngine.set_points([r.point for r in self._rows])` → `ClickEngine.start_from_color(x, y, self.color_tab.click_type)`. 상호배타: 두 엔진이 동시에 `isRunning()`이면 시작 요청 무시(기존 `_capture_blocked` 스타일).

- [ ] **Step 1: MainWindow에 QTabWidget 도입 및 엔진 추가**

`main_window.py` 임포트에 추가:
```python
from PySide6.QtWidgets import QTabWidget  # 기존 import 줄에 병합
from core.continuous_click_engine import ContinuousClickEngine
from ui.color_clicker_tab import ColorClickerTab
```
`__init__`에 필드 추가: `self._continuous: ContinuousClickEngine | None = None`.

`_build_ui`를 리팩터한다: 현재 `root` 레이아웃이 만들던 위젯 트리 전체(header~status)를 내부 헬퍼 `_build_clicker_page() -> QWidget`로 옮겨 `QWidget` 하나에 담고, 최상단에 `QTabWidget`을 생성해 탭1("순서 클릭")로 addTab, `self.color_tab = ColorClickerTab()`를 탭2("컬러 클리커")로 addTab. `setMinimumSize(650, 460)` → `setMinimumSize(650, 520)`(탭바 수용). `QTabWidget` 스타일시트는 Phase A A5 Step 1의 스타일과 동일한 팔레트를 사용한다.

`color_tab` 시그널 연결(`__init__` 끝, `self._ipc.start()` 전후):
```python
        self.color_tab.start_requested.connect(self._on_color_start)
        self.color_tab.stop_requested.connect(self._on_color_stop)
        self._ipc.color_match_received.connect(
            self._on_color_match, Qt.ConnectionType.QueuedConnection
        )
```

- [ ] **Step 2: 컬러 클리커 핸들러 추가**

`main_window.py`에 메서드 추가:
```python
    def _on_color_start(self) -> None:
        if self.color_tab.point is None:
            return
        if self._engine.isRunning():
            return
        if self._continuous is not None and self._continuous.isRunning():
            return
        x, y = self.color_tab.point
        self._continuous = ContinuousClickEngine(
            x, y, self.color_tab.min_ms, self.color_tab.max_ms,
            self.color_tab.click_type,
        )
        self._continuous.start()
        self.color_tab.set_running(True)
        self.color_tab.set_status("연속 클릭 중... (컬러 감지 대기)")

    def _on_color_stop(self) -> None:
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        self.color_tab.set_running(False)
        self.color_tab.set_status("중지됨.")

    def _on_color_match(self, x: int, y: int) -> None:
        # 이미 시퀀스 실행 중이면 무시(상호배타)
        if self._engine.isRunning():
            return
        # 연속 클릭 정지 후 감지 좌표 클릭 → 기존 포인트 시퀀스
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
        self.color_tab.set_running(False)
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_from_color(x, y, self.color_tab.click_type)
        self.color_tab.set_status(f"감지 ({x}, {y}) → 클릭 시퀀스 실행 중...")
```

- [ ] **Step 3: closeEvent 정리 추가**

`closeEvent`에 연속 엔진 정리를 추가(`self._ipc.stop()` 뒤):
```python
        if self._continuous is not None and self._continuous.isRunning():
            self._continuous.stop()
```

- [ ] **Step 4: 전체 회귀 테스트 + 스모크**
  ```
  cd auto-clicker && python -m pytest -v && python -c "import ui.main_window, main; print('import ok')"
  ```
  예상: `test_models.py`(4) + `test_click_engine.py`(6) + `test_ipc_server.py`(3) + `test_continuous_click_engine.py`(2) + `test_color_clicker_tab.py`(3) = `18 passed`, 이어서 `import ok`. 기존 테스트 무회귀.

- [ ] **Step 5: Commit**
  ```
  cd auto-clicker && git add ui/main_window.py && git commit -m "feat(clicker): QTabWidget 도입 및 color_match 클릭 트리거 와이어링"
  ```

---

## Phase C — 통합 확인 (수동 체크리스트)

Phase A/B가 각각 완료되고 모든 유닛테스트가 통과한 뒤, 두 프로세스를 실제로 띄워 IPC 연동을 육안 검증한다. **자동화 테스트가 아니라 수동 확인이다** — 실제 화면 캡처·마우스 제어·소켓 연결이 필요하기 때문이다. 이 Phase는 오케스트레이터(또는 사용자)가 직접 수행한다.

준비: 터미널 2개. 화면에 색이 확실히 구분되는 영역(예: 특정 색 버튼/배지)을 준비.

- [ ] **C1: 두 앱 기동**
  - 터미널1: `cd auto-clicker && python main.py` → 콘솔에 `[IpcServer] listening on port 54321` 출력 확인.
  - 터미널2: `cd auto-capture && python main.py` → 런처 창 표시 확인.
  - 확인: 두 창 모두 상단에 탭 2개(기존 / 컬러)가 보이는지.

- [ ] **C2: IPC 연결**
  - auto-capture 런처의 "auto-clicker 연결" 버튼 클릭 → "연결됨 ●"으로 바뀌는지.
  - auto-clicker 콘솔에 `[IpcServer] client connected from ...` 출력 확인.
  - (기존 motion 플로우 무회귀 확인: auto-capture 탭1에서 기존 화면변화 감지 시작 → 변화 발생 → auto-clicker가 반응하는지 1회 확인.)

- [ ] **C3: 컬러 클리커 준비 (auto-clicker 탭2)**
  - 탭2("컬러 클리커")로 이동 → "연속 클릭 지점 지정" 클릭 → 화면의 아무 안전한 지점(예: 빈 바탕화면) 클릭 → 버튼에 좌표 표시되는지.
  - min/max ms를 확인(기본 80/200).
  - 탭1("순서 클릭")에 포인트 1–2개 추가(감지 후 실행될 시퀀스).
  - 탭2 "▶ 시작" 클릭 → 지정 지점을 불규칙 간격으로 연속 클릭하기 시작하는지(마우스가 해당 지점에서 반복 클릭).

- [ ] **C4: 컬러 캡쳐 감지 (auto-capture 탭2)**
  - 탭2("컬러 감지")로 이동 → "색 지정" 클릭 → 돋보기 패널이 커서를 따라다니며 확대/RGB 텍스트가 보이는지, 화면 우측 끝에서 패널이 왼쪽으로 flip되는지 확인 → 목표 색 픽셀 클릭 → 스와치에 색 반영 확인.
  - "감시 영역 지정" 클릭 → 목표 색이 나타날 영역을 드래그 선택.
  - 허용오차 확인(기본 10).
  - "시작" 클릭 → "컬러 감시 중..." 상태 확인.

- [ ] **C5: 엔드투엔드 트리거 검증 (핵심)**
  - 감시 영역 안에 목표 색을 등장시킨다(예: 해당 색 요소를 영역 안으로 이동/표시).
  - 기대 동작 순서:
    1. auto-capture: "감지! (x, y) 신호 전송" 상태 표시.
    2. auto-clicker: 연속 클릭이 **즉시 멈추고**, 마우스가 감지 좌표(x, y)로 이동해 클릭한 뒤, 탭1의 포인트 시퀀스를 순서대로 클릭.
    3. auto-clicker 상태: "감지 (x, y) → 클릭 시퀀스 실행 중..." → 완료 후 대기.
  - 확인: 감지 좌표가 화면상 실제 색 위치와 일치하는지(±영역 크기 오차 허용).

- [ ] **C6: 상호배타 / 정리 확인**
  - auto-clicker: 탭2 연속 클릭 중 탭1 "시작"을 눌러도 중복 실행되지 않는지(또는 시퀀스 실행 중 color_match가 무시되는지).
  - auto-capture: 탭2 감시 중 탭1 시작이 무시되는지(역방향도).
  - 양쪽 앱 창 닫기 → 스레드가 정리되고 프로세스가 정상 종료되는지(좀비 프로세스/포트 점유 없음: `lsof -ti :54321`가 비어야 함).

- [ ] **C7: 최종 회귀**
  ```
  cd auto-capture && python -m pytest -q
  cd auto-clicker && python -m pytest -q
  ```
  예상: 양쪽 모두 all passed, 기존 테스트 무회귀.

---

## Self-Review

### 1. 스펙 커버리지 체크

| 스펙 섹션 / 요구사항 | 구현 태스크 |
|---|---|
| §2 auto-capture `ColorMonitorThread` (허용오차, MIN_MATCHED/쿨다운) | A1 |
| §2 auto-capture `pick_pixel_color` + 돋보기(15×15, 8배, flip, 중앙강조, RGB텍스트) | A3 |
| §2 auto-capture `ColorCaptureTab` (샘플버튼+스와치, 허용오차 스핀, 영역지정, 시작/정지, 상태) | A4 |
| §2 auto-capture `ipc_client.send_color_match(x, y)` | A2 |
| §2 auto-capture `launcher.py` QTabWidget + 창 크기 조정 | A5 |
| §2 auto-clicker `click_engine` `_run_points_sequence` 추출 + `start_from_color` | B1 |
| §2 auto-clicker `continuous_click_engine.py` (가우시안 지터, min/max, stop) | B2 |
| §2 auto-clicker `ipc_server` color_match 파싱 + `color_match_received` | B3 |
| §2 auto-clicker `color_clicker_tab.py` (지점지정, ms범위, 시작/정지, ClickPoint 재사용) | B4 |
| §2 auto-clicker `main_window.py` QTabWidget + color_match 와이어링(Continuous.stop→start_from_color) | B5 |
| §3 데이터 흐름 1–7 (샘플→감시→연속클릭→감지→소켓→stop→start_from_color→시퀀스) | A3/A4/A1(A쪽), B4/B2/B3/B1/B5(B쪽), C5(검증) |
| §4 상호배타(_capture_blocked 스타일) | A5(capture), B5(clicker), C6(검증) |
| §4 IPC 끊김 시 기존 흐름 재사용 | 신규 분기 불필요(스펙 명시) — 기존 client_disconnected 무변경 |
| §4 돋보기 경계 캡처 실패 시 스킵 | A3 (`_update_loupe`의 try/except + shape 가드) |
| §4 스핀박스 range로 입력 제한 | A4(tolerance 0–100), B4(ms 1–10000) |
| §5 test_color_monitor 경계값 | A1 (within/outside tolerance) |
| §5 test start_from_color 좌표 이동 | B1 |
| §5 test color_match 파싱 | B3 |
| §5 test_continuous_click_engine 간격 통계 검증 | B2 |
| §6 Out of scope (랜덤영역/hex입력/다중RGB) | 미구현(스펙 준수) |

전 스펙 섹션이 태스크에 매핑됨. 누락 없음.

### 2. Placeholder 스캔

전 태스크의 코드 블록은 실행 가능한 완성 코드다. "TBD"/"implement later"/"add appropriate error handling"/"similar to Task N" 표현 없음. A5/B5의 UI 리팩터는 "기존 위젯 트리를 헬퍼로 이동"이라는 기계적 변형이며, 이동 대상(header~status 트리)과 새 구조(QTabWidget + 2 addTab)를 명시했고 신규 로직(핸들러)은 전부 완성 코드로 제공함. (A2는 유닛테스트 생략을 명시적 근거와 함께 결정 — placeholder 아님.)

### 3. 타입/시그니처 일관성 체크

- IPC 이벤트/필드: Global Constraints `{"event": "color_match", "x": int, "y": int}` — A2(`send_color_match`)와 B3(`_handle` 파싱)이 동일 문자열/필드 사용. ✓
- `ColorMonitorThread(region, target_rgb, tolerance)`(A1) — A5 `on_color_start(region, target_rgb, tolerance)`에서 동일 순서로 생성. ✓
- `ColorCaptureTab.start_requested(dict, tuple, int)`(A4) — A5에서 `on_color_start(region, target_rgb, tolerance)`로 동일 순서 수신. ✓
- `pick_pixel_color() -> (x, y, (r,g,b))`(A3) — A4 `_on_pick_color`에서 `_x, _y, rgb` 언패킹. ✓
- `ClickEngine.start_from_color(x, y, click_type="left")`(B1) — B5 `_on_color_match`에서 `start_from_color(x, y, self.color_tab.click_type)` 호출. ✓
- `ContinuousClickEngine(x, y, min_ms, max_ms, click_type)`(B2) — B5 `_on_color_start`에서 동일 순서 생성. ✓
- `ColorClickerTab.point/min_ms/max_ms/click_type`(B4) — B5에서 동일 프로퍼티명 접근. ✓
- `IpcServer.color_match_received(int, int)`(B3) — B5에서 `self._ipc.color_match_received.connect(self._on_color_match)`로 연결, `_on_color_match(self, x, y)` 시그니처 일치. ✓
- `_spin_style()` import: B4가 `from ui.click_point_row import _spin_style` — 해당 모듈에 함수 존재 확인됨. ✓

일관성 문제 없음.
