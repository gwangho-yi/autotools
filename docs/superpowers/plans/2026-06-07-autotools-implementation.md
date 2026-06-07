# autotools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ticketure 레포를 autotools uv workspace 모노레포로 재구성하고, 화면 클릭 시퀀스를 실행하는 auto-clicker 앱을 새로 추가한다.

**Architecture:** uv workspace 기반 모노레포. auto-capture(기존 ticketure)와 auto-clicker가 독립 패키지로 공존. auto-clicker는 TCP 서버(localhost:54321)를 열고 auto-capture의 motion 신호를 받아 즉시 클릭 후 사용자 정의 시퀀스를 실행한다. auto-clicker는 auto-capture 없이도 Start 버튼으로 단독 동작한다.

**Tech Stack:** Python 3.14+, PySide6 6.11+, pynput 1.7+, uv workspace, PyInstaller 6.20+

---

## File Map

**Task 1 — 이동:**
- `main.py`, `core/`, `ui/`, `assets/`, `scripts/`, `build.sh`, `build-windows.bat`, `ticketure.spec`, `ticketure-windows.spec` → `auto-capture/` 하위

**Task 1 — 교체:**
- `pyproject.toml` → workspace 전용 (members만)

**Task 1 — 수정:**
- `auto-capture/pyproject.toml` — name `"ticketure"` → `"auto-capture"`

**Task 2 — 수정:**
- `auto-capture/core/alert.py` — x, y 파라미터 추가 + TCP 전송
- `auto-capture/core/monitor.py` — `alert(int(cx), int(cy))` 호출

**Task 3-9 — 신규:**
- `auto-clicker/pyproject.toml`
- `auto-clicker/main.py`
- `auto-clicker/core/__init__.py`
- `auto-clicker/core/models.py`
- `auto-clicker/core/ipc_server.py`
- `auto-clicker/core/click_engine.py`
- `auto-clicker/ui/__init__.py`
- `auto-clicker/ui/point_picker.py`
- `auto-clicker/ui/click_point_row.py`
- `auto-clicker/ui/main_window.py`
- `auto-clicker/tests/__init__.py`
- `auto-clicker/tests/test_models.py`
- `auto-clicker/tests/test_ipc_server.py`
- `auto-clicker/tests/test_click_engine.py`
- `auto-clicker/auto-clicker.spec`
- `auto-clicker/build.sh`
- `auto-clicker/build-windows.bat`

---

### Task 1: 모노레포 구조 구성

**Files:**
- Create dir: `auto-capture/`
- Move: 기존 소스 파일들
- Replace: `pyproject.toml`
- Modify: `auto-capture/pyproject.toml`

- [ ] **Step 1: auto-capture 폴더 생성 및 파일 이동**

```bash
mkdir auto-capture
mv main.py core ui assets scripts auto-capture/
mv build.sh build-windows.bat auto-capture/
mv ticketure.spec ticketure-windows.spec auto-capture/
cp pyproject.toml auto-capture/pyproject.toml
```

- [ ] **Step 2: auto-capture/pyproject.toml — name 변경**

`auto-capture/pyproject.toml` 전체:
```toml
[project]
name = "auto-capture"
version = "0.1.0"
description = "Screen change detection and cursor automation"
requires-python = ">=3.14"
dependencies = [
    "mss>=10.2.0",
    "numpy>=2.4.6",
    "pyinstaller>=6.20.0",
    "pyside6>=6.11.1",
]
```

- [ ] **Step 3: 루트 pyproject.toml을 workspace 전용으로 교체**

`pyproject.toml` (루트):
```toml
[tool.uv.workspace]
members = ["auto-capture", "auto-clicker"]
```

- [ ] **Step 4: auto-clicker 기본 폴더 구조 생성**

```bash
mkdir -p auto-clicker/core auto-clicker/ui auto-clicker/tests
touch auto-clicker/core/__init__.py
touch auto-clicker/ui/__init__.py
touch auto-clicker/tests/__init__.py
```

- [ ] **Step 5: uv sync 실행 (auto-clicker는 아직 없어서 workspace 부분 sync만)**

```bash
uv sync --package auto-capture
```
Expected: `Resolved X packages` (에러 없음)

- [ ] **Step 6: auto-capture 정상 실행 확인**

```bash
cd auto-capture && uv run python main.py
```
Expected: 기존 ticketure 창이 정상 표시됨. ESC 또는 창 닫기로 종료.

- [ ] **Step 7: 커밋**

```bash
git add -A
git commit -m "refactor: restructure as autotools monorepo, rename to auto-capture"
```

---

### Task 2: auto-capture — 소켓 신호 전송 추가

**Files:**
- Modify: `auto-capture/core/alert.py`
- Modify: `auto-capture/core/monitor.py`

- [ ] **Step 1: auto-capture/core/alert.py 전체 교체**

```python
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent.parent

_SOUND = _base / "assets" / "notify.wav"
_CLICKER_PORT = 54321


def _send_to_clicker(x: int, y: int) -> None:
    try:
        with socket.create_connection(("localhost", _CLICKER_PORT), timeout=0.1) as s:
            msg = json.dumps({"event": "motion", "x": x, "y": y}) + "\n"
            s.sendall(msg.encode())
    except OSError:
        pass


def alert(x: int = 0, y: int = 0) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", str(_SOUND)])
    elif sys.platform == "win32":
        import winsound
        winsound.PlaySound(str(_SOUND), winsound.SND_FILENAME | winsound.SND_ASYNC)
    threading.Thread(target=_send_to_clicker, args=(x, y), daemon=True).start()
```

- [ ] **Step 2: auto-capture/core/monitor.py — alert 호출에 좌표 전달**

`alert()` 호출 라인을 찾아 `alert(int(cx), int(cy))`로 변경:
```python
                    self.motion_detected.emit(int(cx), int(cy))
                    alert(int(cx), int(cy))
```

- [ ] **Step 3: 동작 확인 — 실제 auto-clicker 없이 소켓 전송이 조용히 실패하는지 확인**

```bash
cd auto-capture && uv run python -c "
from core.alert import alert
alert(100, 200)
print('alert() completed without exception')
"
```
Expected: `alert() completed without exception` (연결 실패해도 예외 없음)

- [ ] **Step 4: 커밋**

```bash
git add auto-capture/core/alert.py auto-capture/core/monitor.py
git commit -m "feat(auto-capture): send motion signal to auto-clicker via TCP"
```

---

### Task 3: auto-clicker — 패키지 스캐폴드 + ClickPoint 데이터 모델

**Files:**
- Create: `auto-clicker/pyproject.toml`
- Create: `auto-clicker/main.py`
- Create: `auto-clicker/core/models.py`
- Create: `auto-clicker/tests/test_models.py`

- [ ] **Step 1: auto-clicker/pyproject.toml 작성**

```toml
[project]
name = "auto-clicker"
version = "0.1.0"
description = "Automated mouse click sequencer"
requires-python = ">=3.14"
dependencies = [
    "pyside6>=6.11.1",
    "pynput>=1.7.7",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-qt>=4.4.0"]
```

- [ ] **Step 2: auto-clicker/core/models.py 작성**

```python
from dataclasses import dataclass, field


@dataclass
class ClickPoint:
    x: int = 0
    y: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    ms: int = 500
    click_type: str = "left"  # "left" | "right" | "double"

    @property
    def delay_ms(self) -> int:
        return (self.hours * 3600 + self.minutes * 60 + self.seconds) * 1000 + self.ms
```

- [ ] **Step 3: 실패 테스트 작성 — auto-clicker/tests/test_models.py**

```python
from core.models import ClickPoint


def test_delay_ms_default():
    assert ClickPoint().delay_ms == 500


def test_delay_ms_seconds_and_ms():
    assert ClickPoint(seconds=2, ms=500).delay_ms == 2500


def test_delay_ms_all_fields():
    # 1h=3600s, 2m=120s, 3s → total 3723s → 3723000ms + 100 = 3723100
    assert ClickPoint(hours=1, minutes=2, seconds=3, ms=100).delay_ms == 3723100


def test_click_type_default():
    assert ClickPoint().click_type == "left"
```

- [ ] **Step 4: 테스트 실행 — 실패 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_models.py -v
```
Expected: `ModuleNotFoundError` (models.py 없음)

- [ ] **Step 5: 테스트 재실행 — 통과 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_models.py -v
```
Expected:
```
PASSED tests/test_models.py::test_delay_ms_default
PASSED tests/test_models.py::test_delay_ms_seconds_and_ms
PASSED tests/test_models.py::test_delay_ms_all_fields
PASSED tests/test_models.py::test_click_type_default
4 passed
```

- [ ] **Step 6: auto-clicker/main.py 기본 스캐폴드**

```python
import sys
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt


def main():
    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("auto-clicker")
    win.setFixedSize(560, 400)
    win.setStyleSheet("background-color: #1a1a2e;")
    lbl = QLabel("auto-clicker")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: white; font-size: 24px;")
    QVBoxLayout(win).addWidget(lbl)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: 창 표시 확인**

```bash
cd auto-clicker && uv run python main.py
```
Expected: 어두운 배경에 "auto-clicker" 텍스트 창이 열림.

- [ ] **Step 8: 커밋**

```bash
git add auto-clicker/
git commit -m "feat(auto-clicker): scaffold package with ClickPoint model"
```

---

### Task 4: auto-clicker — IPC 서버 (TCP listener)

**Files:**
- Create: `auto-clicker/core/ipc_server.py`
- Create: `auto-clicker/tests/test_ipc_server.py`

- [ ] **Step 1: 실패 테스트 작성 — auto-clicker/tests/test_ipc_server.py**

```python
import json
import socket
import time


def test_motion_signal_emitted(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    server.start()
    time.sleep(0.15)  # wait for server to start listening

    try:
        with qtbot.waitSignal(server.motion_received, timeout=2000) as blocker:
            with socket.create_connection(("localhost", 54321), timeout=1.0) as s:
                s.sendall(
                    json.dumps({"event": "motion", "x": 42, "y": 99}).encode() + b"\n"
                )
    finally:
        server.stop()

    assert blocker.args == [42, 99]


def test_invalid_message_ignored(qtbot):
    from core.ipc_server import IpcServer

    server = IpcServer()
    received = []
    server.motion_received.connect(lambda x, y: received.append((x, y)))
    server.start()
    time.sleep(0.15)

    try:
        with socket.create_connection(("localhost", 54321), timeout=1.0) as s:
            s.sendall(b"not json\n")
        time.sleep(0.1)
    finally:
        server.stop()

    assert received == []
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_ipc_server.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.ipc_server'`

- [ ] **Step 3: auto-clicker/core/ipc_server.py 구현**

```python
import json
import socket
from PySide6.QtCore import QThread, Signal


class IpcServer(QThread):
    motion_received = Signal(int, int)
    client_connected = Signal()
    client_disconnected = Signal()

    PORT = 54321

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._sock: socket.socket | None = None

    def run(self):
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind(("localhost", self.PORT))
            self._sock.listen(1)
            self._sock.settimeout(1.0)
        except OSError:
            self._running = False
            return

        while self._running:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.client_connected.emit()
            self._handle(conn)
            self.client_disconnected.emit()

        try:
            self._sock.close()
        except OSError:
            pass

    def _handle(self, conn: socket.socket) -> None:
        buf = b""
        conn.settimeout(1.0)
        while self._running:
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                    if msg.get("event") == "motion":
                        self.motion_received.emit(int(msg["x"]), int(msg["y"]))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    pass
        conn.close()

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self.wait()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_ipc_server.py -v
```
Expected:
```
PASSED tests/test_ipc_server.py::test_motion_signal_emitted
PASSED tests/test_ipc_server.py::test_invalid_message_ignored
2 passed
```

- [ ] **Step 5: 커밋**

```bash
git add auto-clicker/core/ipc_server.py auto-clicker/tests/test_ipc_server.py
git commit -m "feat(auto-clicker): add TCP IPC server for auto-capture integration"
```

---

### Task 5: auto-clicker — 클릭 실행 엔진

**Files:**
- Create: `auto-clicker/core/click_engine.py`
- Create: `auto-clicker/tests/test_click_engine.py`

- [ ] **Step 1: 실패 테스트 작성 — auto-clicker/tests/test_click_engine.py**

```python
from unittest.mock import MagicMock, patch
from core.models import ClickPoint


def test_standalone_executes_all_points(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([
            ClickPoint(x=100, y=200, ms=10, click_type="left"),
            ClickPoint(x=300, y=400, ms=10, click_type="right"),
        ])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()

    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_capture_mode_clicks_immediately_then_sequence(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([
            ClickPoint(x=100, y=200, ms=10, click_type="left"),
        ])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_from_capture()

    # 즉시 클릭(auto-capture 위치) + 시퀀스 1개 = 총 2번 클릭
    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_double_click(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=50, y=50, ms=10, click_type="double")])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()

    # pynput click(button, 2) 사용
    from pynput.mouse import Button
    mock_mouse.click.assert_called_once_with(Button.left, 2)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_click_engine.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.click_engine'`

- [ ] **Step 3: auto-clicker/core/click_engine.py 구현**

```python
import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

from core.models import ClickPoint


class ClickEngine(QThread):
    sequence_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[ClickPoint] = []
        self._immediate_first = False
        self._mouse = Controller()

    def set_points(self, points: list[ClickPoint]) -> None:
        self._points = list(points)

    def start_standalone(self) -> None:
        """시작 버튼으로 실행: 첫 포인트도 설정된 딜레이 후 클릭."""
        if self.isRunning():
            return
        self._immediate_first = False
        self.start()

    def start_from_capture(self) -> None:
        """auto-capture 신호로 실행: 현재 커서 위치 즉시 클릭 후 시퀀스 실행."""
        if self.isRunning():
            return
        self._immediate_first = True
        self.start()

    def run(self) -> None:
        if self._immediate_first:
            self._do_click("left")

        for point in self._points:
            if self.isInterruptionRequested():
                break
            time.sleep(point.delay_ms / 1000)
            if self.isInterruptionRequested():
                break
            self._mouse.position = (point.x, point.y)
            if point.click_type == "double":
                self._mouse.click(Button.left, 2)
            else:
                button = Button.left if point.click_type == "left" else Button.right
                self._do_click_button(button)

        self.sequence_finished.emit()

    def _do_click(self, click_type: str) -> None:
        button = Button.left if click_type != "right" else Button.right
        self._do_click_button(button)

    def _do_click_button(self, button: Button) -> None:
        self._mouse.press(button)
        self._mouse.release(button)

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

```bash
cd auto-clicker && uv run --extra dev pytest tests/test_click_engine.py -v
```
Expected:
```
PASSED tests/test_click_engine.py::test_standalone_executes_all_points
PASSED tests/test_click_engine.py::test_capture_mode_clicks_immediately_then_sequence
PASSED tests/test_click_engine.py::test_double_click
3 passed
```

- [ ] **Step 5: 커밋**

```bash
git add auto-clicker/core/click_engine.py auto-clicker/tests/test_click_engine.py
git commit -m "feat(auto-clicker): add click sequence engine with auto-capture integration"
```

---

### Task 6: auto-clicker — 포인트 피커 오버레이

**Files:**
- Create: `auto-clicker/ui/point_picker.py`

- [ ] **Step 1: auto-clicker/ui/point_picker.py 구현**

region_select.py 패턴(QEventLoop 기반)을 따름.

```python
import sys
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEventLoop, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication


class _PointPickerOverlay(QWidget):
    def __init__(self, screen, shared: dict):
        super().__init__()
        self._screen = screen
        self._shared = shared
        self._cursor_pos = QPoint(0, 0)

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
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))

        x = self._cursor_pos.x()
        y = self._cursor_pos.y()

        pen = QPen(QColor("#4ecca3"), 1)
        p.setPen(pen)
        p.drawLine(0, y, self.width(), y)
        p.drawLine(x, 0, x, self.height())

        origin = self._screen.geometry().topLeft()
        gx = x + origin.x()
        gy = y + origin.y()
        font = QFont()
        font.setPixelSize(13)
        p.setFont(font)
        p.setPen(QColor("#4ecca3"))
        p.drawText(x + 14, y - 8, f"({gx}, {gy})")

        p.setPen(QColor(255, 255, 255, 160))
        hint_font = QFont()
        hint_font.setPixelSize(14)
        p.setFont(hint_font)
        hint = "클릭하여 포인트 지정  |  ESC 취소"
        p.drawText(self.width() // 2 - 130, 32, hint)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        origin = self._screen.geometry().topLeft()
        self._shared["result"] = (pos.x() + origin.x(), pos.y() + origin.y())
        self._close_all()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._shared["result"] = None
            self._close_all()

    def _close_all(self):
        for w in self._shared["widgets"]:
            w.close()
        if self._shared["loop"]:
            self._shared["loop"].quit()


def pick_point() -> tuple[int, int] | None:
    """전체 화면 오버레이를 표시하고 사용자가 클릭한 글로벌 좌표를 반환. ESC시 None."""
    loop = QEventLoop()
    shared = {"result": None, "loop": loop, "widgets": []}

    for screen in QGuiApplication.screens():
        overlay = _PointPickerOverlay(screen, shared)
        shared["widgets"].append(overlay)

    loop.exec()
    return shared["result"]
```

- [ ] **Step 2: 수동 테스트**

```bash
cd auto-clicker && uv run python -c "
from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from ui.point_picker import pick_point
result = pick_point()
print('Selected:', result)
"
```
Expected: 반투명 오버레이 표시 → 클릭 시 `Selected: (x, y)` 출력. ESC 시 `Selected: None`.

- [ ] **Step 3: 커밋**

```bash
git add auto-clicker/ui/point_picker.py
git commit -m "feat(auto-clicker): add fullscreen point picker overlay"
```

---

### Task 7: auto-clicker — ClickPointRow 위젯

**Files:**
- Create: `auto-clicker/ui/click_point_row.py`

- [ ] **Step 1: auto-clicker/ui/click_point_row.py 구현**

```python
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton
)
from PySide6.QtCore import Signal

from core.models import ClickPoint

_BTN_STYLE = """
    QPushButton {{
        background-color: #2a2a4e;
        color: {color};
        border: 1px solid {border};
        border-radius: 4px;
        font-size: 11px;
        padding: 2px 6px;
    }}
    QPushButton:hover {{ background-color: #3a3a5e; }}
"""

_SPIN_STYLE = """
    QSpinBox {
        background-color: #2a2a4e;
        color: white;
        border: 1px solid #3a3a5e;
        border-radius: 4px;
        padding: 1px 2px;
    }
    QSpinBox::up-button, QSpinBox::down-button { width: 14px; }
"""

_COMBO_STYLE = """
    QComboBox {
        background-color: #2a2a4e;
        color: white;
        border: 1px solid #3a3a5e;
        border-radius: 4px;
        padding: 1px 4px;
    }
    QComboBox QAbstractItemView {
        background-color: #2a2a4e;
        color: white;
        selection-background-color: #4ecca3;
        selection-color: #1a1a2e;
    }
"""

_CLICK_TYPES = [("왼쪽 클릭", "left"), ("오른쪽 클릭", "right"), ("더블 클릭", "double")]


class ClickPointRow(QWidget):
    delete_requested = Signal(object)  # emits self

    def __init__(self, index: int, point: ClickPoint, parent=None):
        super().__init__(parent)
        self._point = point
        self._build_ui(index)

    @property
    def point(self) -> ClickPoint:
        self._point.hours = self._h_spin.value()
        self._point.minutes = self._m_spin.value()
        self._point.seconds = self._s_spin.value()
        self._point.ms = self._ms_spin.value()
        self._point.click_type = _CLICK_TYPES[self._type_combo.currentIndex()][1]
        return self._point

    def set_index(self, index: int) -> None:
        self._num_label.setText(str(index + 1))

    def set_position(self, x: int, y: int) -> None:
        self._point.x = x
        self._point.y = y
        self._pos_btn.setText(f"({x}, {y})")

    def _build_ui(self, index: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self._num_label = QLabel(str(index + 1))
        self._num_label.setFixedWidth(18)
        self._num_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._num_label)

        self._pos_btn = QPushButton(f"({self._point.x}, {self._point.y})")
        self._pos_btn.setFixedWidth(100)
        self._pos_btn.setStyleSheet(_BTN_STYLE.format(color="#4ecca3", border="#4ecca3"))
        layout.addWidget(self._pos_btn)

        for attr, label_text, max_val, init_val in [
            ("_h_spin",  "h",  23,  self._point.hours),
            ("_m_spin",  "m",  59,  self._point.minutes),
            ("_s_spin",  "s",  59,  self._point.seconds),
            ("_ms_spin", "ms", 999, self._point.ms),
        ]:
            spin = QSpinBox()
            spin.setRange(0, max_val)
            spin.setValue(init_val)
            spin.setFixedWidth(52)
            spin.setStyleSheet(_SPIN_STYLE)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #666666; font-size: 11px;")
            lbl.setFixedWidth(16)
            layout.addWidget(spin)
            layout.addWidget(lbl)
            setattr(self, attr, spin)

        self._type_combo = QComboBox()
        for label, _ in _CLICK_TYPES:
            self._type_combo.addItem(label)
        default_idx = next(
            (i for i, (_, v) in enumerate(_CLICK_TYPES) if v == self._point.click_type), 0
        )
        self._type_combo.setCurrentIndex(default_idx)
        self._type_combo.setFixedWidth(95)
        self._type_combo.setStyleSheet(_COMBO_STYLE)
        layout.addWidget(self._type_combo)

        layout.addStretch()

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #666666; border: none; font-size: 14px; }
            QPushButton:hover { color: #e05555; }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(del_btn)

        self.setStyleSheet("""
            ClickPointRow {
                background-color: #1e1e3a;
                border-radius: 6px;
            }
        """)
        self.setFixedHeight(48)
```

- [ ] **Step 2: 커밋**

```bash
git add auto-clicker/ui/click_point_row.py
git commit -m "feat(auto-clicker): add ClickPointRow widget with delay and click type inputs"
```

---

### Task 8: auto-clicker — MainWindow + main.py 완성

**Files:**
- Create: `auto-clicker/ui/main_window.py`
- Replace: `auto-clicker/main.py`

- [ ] **Step 1: auto-clicker/ui/main_window.py 구현**

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from core.models import ClickPoint
from core.click_engine import ClickEngine
from core.ipc_server import IpcServer
from ui.point_picker import pick_point
from ui.click_point_row import ClickPointRow

_BTN_PRIMARY = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 14px; font-weight: bold;
        padding: 8px 20px;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_OUTLINE = """
    QPushButton {{
        background-color: transparent;
        color: {color}; border: 1px solid {color};
        border-radius: 8px; font-size: 13px;
        padding: 8px 16px;
    }}
    QPushButton:hover {{ background-color: rgba(78,204,163,0.1); }}
    QPushButton:checked {{
        background-color: rgba(78,204,163,0.15);
        color: #4ecca3; border-color: #4ecca3;
    }}
"""

_BTN_ADD = """
    QPushButton {
        background-color: #2a2a4e; color: #4ecca3;
        border: 1px dashed #4ecca3; border-radius: 6px;
        font-size: 13px; padding: 8px;
    }
    QPushButton:hover { background-color: #3a3a5e; }
"""


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._rows: list[ClickPointRow] = []
        self._engine = ClickEngine()
        self._server: IpcServer | None = None
        self._build_ui()
        self._engine.sequence_finished.connect(self._on_sequence_finished)
        self._center()

    def _build_ui(self) -> None:
        self.setWindowTitle("auto-clicker")
        self.setMinimumSize(580, 460)
        self.setStyleSheet("background-color: #1a1a2e;")

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 20, 20, 16)

        # Header
        title = QLabel("auto-clicker")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        subtitle = QLabel("클릭할 포인트를 순서대로 추가하세요")
        subtitle.setStyleSheet("color: #666666; font-size: 12px;")
        root.addWidget(subtitle)

        # Column header labels
        header = QHBoxLayout()
        header.setContentsMargins(8, 0, 8, 0)
        for text, width in [("#", 26), ("위치", 108), ("딜레이 (h/m/s/ms)", 230), ("종류", 103)]:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet("color: #444466; font-size: 11px;")
            header.addWidget(lbl)
        header.addStretch()
        root.addLayout(header)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setAlignment(Qt.AlignTop)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._list_container)
        root.addWidget(scroll, stretch=1)

        # Add point button
        self._add_btn = QPushButton("+ 포인트 추가")
        self._add_btn.setStyleSheet(_BTN_ADD)
        self._add_btn.clicked.connect(self._on_add_point)
        root.addWidget(self._add_btn)

        # Bottom row
        bottom = QHBoxLayout()
        self._start_btn = QPushButton("▶ 시작")
        self._start_btn.setStyleSheet(_BTN_PRIMARY)
        self._start_btn.clicked.connect(self._on_start)
        bottom.addWidget(self._start_btn)
        bottom.addStretch()
        self._connect_btn = QPushButton("auto-capture 연결")
        self._connect_btn.setCheckable(True)
        self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color="#888888"))
        self._connect_btn.clicked.connect(self._on_toggle_connect)
        bottom.addWidget(self._connect_btn)
        root.addLayout(bottom)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666666; font-size: 11px;")
        root.addWidget(self._status_label)

    def _center(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _on_add_point(self) -> None:
        self.hide()
        QApplication.processEvents()
        result = pick_point()
        self.show()
        self.raise_()
        self.activateWindow()
        if result is None:
            return
        x, y = result
        point = ClickPoint(x=x, y=y)
        row = ClickPointRow(len(self._rows), point)
        row.delete_requested.connect(self._on_delete_row)
        self._rows.append(row)
        self._list_layout.addWidget(row)

    def _on_delete_row(self, row: ClickPointRow) -> None:
        self._rows.remove(row)
        self._list_layout.removeWidget(row)
        row.deleteLater()
        for i, r in enumerate(self._rows):
            r.set_index(i)

    def _on_start(self) -> None:
        if not self._rows:
            self._status_label.setText("포인트를 먼저 추가하세요.")
            return
        if self._engine.isRunning():
            return
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_standalone()
        self._start_btn.setEnabled(False)
        self._status_label.setText("실행 중...")

    def _on_sequence_finished(self) -> None:
        self._start_btn.setEnabled(True)
        self._status_label.setText("완료.")

    def _on_toggle_connect(self, checked: bool) -> None:
        if checked:
            self._server = IpcServer()
            self._server.motion_received.connect(self._on_motion_from_capture)
            self._server.client_connected.connect(
                lambda: self._set_connect_status("auto-capture 연결됨 ●", "#4ecca3")
            )
            self._server.client_disconnected.connect(
                lambda: self._set_connect_status("연결 대기 중...", "#888888")
            )
            self._server.start()
            self._set_connect_status("연결 대기 중...", "#888888")
        else:
            if self._server:
                self._server.stop()
                self._server = None
            self._connect_btn.setText("auto-capture 연결")
            self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color="#888888"))
            self._status_label.setText("")

    def _set_connect_status(self, text: str, color: str) -> None:
        self._connect_btn.setText(text)
        self._connect_btn.setStyleSheet(_BTN_OUTLINE.format(color=color))

    def _on_motion_from_capture(self, x: int, y: int) -> None:
        if self._engine.isRunning():
            return
        self._engine.set_points([r.point for r in self._rows])
        self._engine.start_from_capture()
        self._status_label.setText(f"auto-capture 신호 수신 → 클릭 실행 중...")

    def closeEvent(self, event) -> None:
        if self._server:
            self._server.stop()
        if self._engine.isRunning():
            self._engine.stop()
        event.accept()
```

- [ ] **Step 2: auto-clicker/main.py 교체**

```python
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 앱 실행 확인**

```bash
cd auto-clicker && uv run python main.py
```
Expected:
- 어두운 배경 창 표시
- "포인트 추가" 버튼 클릭 → 오버레이 표시 → 클릭하면 포인트 행 추가
- 딜레이/종류 수정 가능
- "▶ 시작" 클릭 → 시퀀스 실행 후 "완료." 표시
- "auto-capture 연결" 클릭 → "연결 대기 중..." 표시

- [ ] **Step 4: auto-capture 연동 테스트**

터미널 1에서:
```bash
cd auto-clicker && uv run python main.py
# "auto-capture 연결" 버튼 클릭
```

터미널 2에서:
```bash
python -c "
import socket, json
with socket.create_connection(('localhost', 54321)) as s:
    s.sendall(json.dumps({'event':'motion','x':500,'y':300}).encode() + b'\n')
print('sent')
"
```
Expected: auto-clicker에 "auto-capture 연결됨 ●" 표시, 시퀀스 실행.

- [ ] **Step 5: 전체 테스트 실행**

```bash
cd auto-clicker && uv run --extra dev pytest tests/ -v
```
Expected: 전체 9개 테스트 PASSED

- [ ] **Step 6: 커밋**

```bash
git add auto-clicker/ui/main_window.py auto-clicker/main.py
git commit -m "feat(auto-clicker): complete main window UI and app wiring"
```

---

### Task 9: auto-clicker — 빌드 설정

**Files:**
- Create: `auto-clicker/scripts/make_icon.py`
- Create: `auto-clicker/scripts/make_sound.py`
- Create: `auto-clicker/assets/` (빌드 시 생성)
- Create: `auto-clicker/auto-clicker.spec`
- Create: `auto-clicker/auto-clicker-windows.spec`
- Create: `auto-clicker/build.sh`
- Create: `auto-clicker/build-windows.bat`

- [ ] **Step 1: scripts 폴더 생성 및 아이콘/사운드 스크립트 복사**

```bash
mkdir -p auto-clicker/scripts
cp auto-capture/scripts/make_icon.py auto-clicker/scripts/
cp auto-capture/scripts/make_sound.py auto-clicker/scripts/
```

- [ ] **Step 2: auto-clicker/auto-clicker.spec (macOS)**

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/notify.wav', 'assets'),
        ('assets/icon.icns', 'assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'pynput.mouse._darwin',
        'pynput.keyboard._darwin',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='auto-clicker',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='auto-clicker',
)

app = BUNDLE(
    coll,
    name='auto-clicker.app',
    icon='assets/icon.icns',
    bundle_identifier='com.autotools.auto-clicker',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleDisplayName': 'auto-clicker',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
    },
)
```

- [ ] **Step 3: auto-clicker/auto-clicker-windows.spec**

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('assets/notify.wav', 'assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'pynput.mouse._win32',
        'pynput.keyboard._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='auto-clicker',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='assets/icon.ico',
)
```

- [ ] **Step 4: auto-clicker/build.sh**

```bash
#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Generating icon..."
../.venv/bin/python scripts/make_icon.py

echo "==> Generating sound..."
../.venv/bin/python scripts/make_sound.py

echo "==> Building .app bundle..."
../.venv/bin/pyinstaller auto-clicker.spec --clean --noconfirm

echo ""
echo "Done: dist/auto-clicker.app"
```

```bash
chmod +x auto-clicker/build.sh
```

- [ ] **Step 5: auto-clicker/build-windows.bat**

```batch
@echo off
setlocal

echo =^=> Setting up dependencies...
uv sync
if errorlevel 1 (echo uv sync failed. Install uv from https://docs.astral.sh/uv/ & pause & exit /b 1)
uv add pyinstaller pynput
if errorlevel 1 goto :error

echo =^=> Generating icon...
uv run python scripts\make_icon.py
if errorlevel 1 goto :error

echo =^=> Generating sound...
uv run python scripts\make_sound.py
if errorlevel 1 goto :error

echo =^=> Building .exe...
uv run pyinstaller auto-clicker-windows.spec --clean --noconfirm
if errorlevel 1 goto :error

echo.
echo Done: dist\auto-clicker.exe
goto :end

:error
echo.
echo Build failed.
pause
exit /b 1

:end
pause
```

- [ ] **Step 6: .gitignore 업데이트 — auto-clicker spec 추가**

`/.gitignore`의 `*.spec` 예외 규칙에 추가:
```
!auto-clicker/auto-clicker.spec
!auto-clicker/auto-clicker-windows.spec
```

- [ ] **Step 7: macOS 빌드 테스트**

```bash
cd auto-clicker && bash build.sh
```
Expected: `Done: dist/auto-clicker.app`

- [ ] **Step 8: 커밋**

```bash
git add auto-clicker/scripts/ auto-clicker/auto-clicker.spec auto-clicker/auto-clicker-windows.spec auto-clicker/build.sh auto-clicker/build-windows.bat .gitignore
git commit -m "feat(auto-clicker): add PyInstaller build config for macOS and Windows"
```
