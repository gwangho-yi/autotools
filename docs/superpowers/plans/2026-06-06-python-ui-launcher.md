# ticketure Python UI 런처 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PySide6 기반 런처 창(아이콘 + 앱명 + 시작 버튼)과 시스템 트레이 아이콘을 추가해 비개발자도 사용할 수 있는 GUI 앱으로 전환한다.

**Architecture:** 모니터링 루프를 QThread로 분리해 UI 반응성을 확보하고, Launcher → RegionSelect → MonitorThread → TrayIcon 순서로 상태를 전이한다. 플랫폼 분기(macOS/Windows)는 `core/alert.py` 한 곳에 격리한다.

**Tech Stack:** Python 3.14, PySide6 6.11+, mss, numpy

---

## 파일 맵

| 경로 | 상태 | 역할 |
|------|------|------|
| `core/__init__.py` | 신규 | 패키지 마커 |
| `core/alert.py` | 신규 | 플랫폼별 알림음 |
| `core/monitor.py` | 신규 | 모니터링 QThread |
| `ui/__init__.py` | 신규 | 패키지 마커 (현재 없음) |
| `ui/launcher.py` | 신규 | 런처 창 위젯 |
| `ui/tray.py` | 신규 | 시스템 트레이 아이콘 |
| `main.py` | 수정 | 진입점 — 런처 기동 방식으로 교체 |
| `ui/region_select.py` | 유지 | 변경 없음 |

---

## Task 1: 패키지 마커 및 플랫폼별 알림음

**Files:**
- Create: `core/__init__.py`
- Create: `core/alert.py`
- Create: `ui/__init__.py`

- [ ] **Step 1: `core/__init__.py` 생성**

```python
# core/__init__.py
```

- [ ] **Step 2: `ui/__init__.py` 생성**

```python
# ui/__init__.py
```

- [ ] **Step 3: `core/alert.py` 작성**

```python
import sys
import os


def alert():
    if sys.platform == "darwin":
        os.system("afplay /System/Library/Sounds/Glass.aiff &")
    elif sys.platform == "win32":
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
```

- [ ] **Step 4: 동작 확인 (macOS)**

```bash
cd /Users/yi-gwangho/Projects/ticketure
source .venv/bin/activate
python -c "from core.alert import alert; alert(); import time; time.sleep(1)"
```

Expected: Glass 알림음이 재생됨.

- [ ] **Step 5: 커밋**

```bash
git init   # 아직 git 저장소가 없으므로 초기화
git add core/__init__.py core/alert.py ui/__init__.py
git commit -m "feat: add core package and platform-specific alert"
```

---

## Task 2: 모니터 QThread

**Files:**
- Create: `core/monitor.py`

- [ ] **Step 1: `core/monitor.py` 작성**

```python
import time
import numpy as np
import mss
from PySide6.QtCore import QThread, Signal

from core.alert import alert

INTERVAL = 0.5
PIXEL_DIFF = 25
MIN_CHANGED = 15


class MonitorThread(QThread):
    motion_detected = Signal(int, int)
    stopped = Signal()

    def __init__(self, region, parent=None):
        super().__init__(parent)
        self.region = region

    def run(self):
        with mss.MSS() as sct:
            prev = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
            while not self.isInterruptionRequested():
                time.sleep(INTERVAL)
                cur = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
                delta = np.abs(cur - prev).sum(axis=2)
                mask = delta > PIXEL_DIFF
                changed = int(np.count_nonzero(mask))
                if changed > MIN_CHANGED:
                    ys, xs = np.where(mask)
                    h_px, w_px = mask.shape
                    fx = xs.mean() / w_px
                    fy = ys.mean() / h_px
                    cx = self.region["left"] + fx * self.region["width"]
                    cy = self.region["top"] + fy * self.region["height"]
                    self.motion_detected.emit(int(cx), int(cy))
                    alert()
                prev = cur
        self.stopped.emit()
```

- [ ] **Step 2: 시그널 및 인스턴스 생성 확인**

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from core.monitor import MonitorThread
t = MonitorThread({'left':0,'top':0,'width':100,'height':100})
print('motion_detected signal:', t.motion_detected)
print('stopped signal:', t.stopped)
print('OK')
"
```

Expected: 오류 없이 `OK` 출력.

- [ ] **Step 3: 커밋**

```bash
git add core/monitor.py
git commit -m "feat: add MonitorThread (QThread-based monitoring loop)"
```

---

## Task 3: SVG 아이콘 헬퍼 및 런처 창

**Files:**
- Create: `ui/launcher.py`

- [ ] **Step 1: `ui/launcher.py` 작성**

```python
import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QPixmap, QIcon


def make_icon_pixmap(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)

    stroke = max(2, int(size * 0.06))
    pen = QPen(QColor("#4ecca3"), stroke)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    margin = max(2, int(size * 0.1))
    w = size - 2 * margin
    h = int(size * 0.55)
    y = int(size * 0.2)
    radius = max(2, int(size * 0.08))

    # 티켓 외곽
    p.drawRoundedRect(margin, y, w, h, radius, radius)

    # 좌우 반원 노치
    notch_r = max(2, int(size * 0.07))
    notch_y = y + h // 2
    p.setBrush(QColor("#1a1a2e"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(margin - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)
    p.drawEllipse(margin + w - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)

    # 점선 구분선
    dash_pen = QPen(QColor("#4ecca3"), max(1, int(size * 0.04)), Qt.DashLine)
    p.setPen(dash_pen)
    p.drawLine(margin + notch_r, notch_y, margin + w - notch_r, notch_y)

    p.end()
    return px


class Launcher(QWidget):
    start_requested = Signal()

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._center()

    def _build_ui(self):
        self.setWindowTitle("ticketure")
        self.setFixedSize(320, 400)
        self.setStyleSheet("background-color: #1a1a2e;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 50, 40, 50)

        icon_label = QLabel()
        icon_label.setPixmap(make_icon_pixmap(72))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("ticketure")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("화면 변화를 감지하고 커서를 이동합니다")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        self.start_btn = QPushButton("시작")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3;
                color: #1a1a2e;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3db89a; }
            QPushButton:disabled { background-color: #2a4a3e; color: #555; }
        """)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)

    def _center(self):
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _on_start(self):
        self.start_btn.setEnabled(False)
        self.status_label.setText("영역을 선택하세요...")
        self.start_requested.emit()

    def reset(self):
        self.start_btn.setEnabled(True)
        self.status_label.setText("")
        self.show()
        self.raise_()
```

- [ ] **Step 2: 런처 창 단독 실행 확인**

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from ui.launcher import Launcher
w = Launcher()
w.show()
app.exec()
"
```

Expected: 320×400 다크 창이 화면 중앙에 표시됨. 티켓 아이콘, "ticketure" 제목, 녹색 "시작" 버튼 확인.

- [ ] **Step 3: 커밋**

```bash
git add ui/__init__.py ui/launcher.py
git commit -m "feat: add Launcher window with SVG ticket icon"
```

---

## Task 4: 시스템 트레이 아이콘

**Files:**
- Create: `ui/tray.py`

- [ ] **Step 1: `ui/tray.py` 작성**

```python
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, QObject

from ui.launcher import make_icon_pixmap


class TrayIcon(QObject):
    stop_requested = Signal()
    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(make_icon_pixmap(16)))
        self._tray.setToolTip("ticketure — 모니터링 중")
        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        status_action = menu.addAction("● 모니터링 중...")
        status_action.setEnabled(False)
        menu.addSeparator()
        open_action = menu.addAction("창 열기")
        open_action.triggered.connect(self.open_requested.emit)
        stop_action = menu.addAction("중지")
        stop_action.triggered.connect(self.stop_requested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("종료")
        quit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
```

- [ ] **Step 2: 트레이 아이콘 단독 확인**

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
from ui.tray import TrayIcon
t = TrayIcon()
t.show()
print('트레이 아이콘 표시됨. 우클릭 메뉴 확인 후 종료를 선택하세요.')
app.exec()
"
```

Expected: macOS 메뉴바(또는 Windows 알림 영역)에 티켓 아이콘이 표시됨. 우클릭 시 "모니터링 중... / 창 열기 / 중지 / 종료" 메뉴 확인.

- [ ] **Step 3: 커밋**

```bash
git add ui/tray.py
git commit -m "feat: add TrayIcon with context menu"
```

---

## Task 5: main.py 교체 및 전체 연결

**Files:**
- Modify: `main.py`

- [ ] **Step 1: `main.py` 전체 교체**

```python
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor

from ui.launcher import Launcher
from ui.tray import TrayIcon
from ui.region_select import select_region
from core.monitor import MonitorThread


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    launcher = Launcher()
    tray = TrayIcon()
    monitor_thread = None

    def on_start():
        region = select_region()
        if not region:
            launcher.reset()
            return

        nonlocal monitor_thread
        monitor_thread = MonitorThread(region)
        monitor_thread.motion_detected.connect(on_motion)
        monitor_thread.stopped.connect(on_stopped)
        monitor_thread.start()

        launcher.hide()
        tray.show()

    def on_motion(x, y):
        QCursor.setPos(x, y)

    def on_stopped():
        tray.hide()
        launcher.reset()

    def on_stop():
        if monitor_thread and monitor_thread.isRunning():
            monitor_thread.requestInterruption()
            monitor_thread.wait()

    def on_open():
        launcher.show()
        launcher.raise_()

    launcher.start_requested.connect(on_start)
    tray.stop_requested.connect(on_stop)
    tray.open_requested.connect(on_open)

    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 전체 흐름 동작 확인**

```bash
cd /Users/yi-gwangho/Projects/ticketure
source .venv/bin/activate
python main.py
```

확인 체크리스트:
1. 런처 창이 화면 중앙에 표시됨
2. "시작" 버튼 클릭 → "영역을 선택하세요..." 텍스트 + 버튼 비활성화
3. 화면 오버레이가 나타나고 드래그로 영역 선택 가능
4. 영역 선택 후 런처 창이 사라지고 트레이 아이콘 활성화
5. 선택된 영역에서 화면 변화 발생 시 커서 이동 + 알림음
6. 트레이 우클릭 → "중지" → 모니터링 종료 + 런처 창 복귀
7. 트레이 "창 열기" → 런처 창 다시 표시
8. 트레이 "종료" → 앱 완전 종료

- [ ] **Step 3: ESC 취소 흐름 확인**

```bash
python main.py
```

"시작" 클릭 후 영역 선택 화면에서 ESC 키 입력.
Expected: 런처 창 복귀, "시작" 버튼 다시 활성화.

- [ ] **Step 4: 커밋**

```bash
git add main.py
git commit -m "feat: wire Launcher, TrayIcon, and MonitorThread in main.py"
```

---

## 자체 검토 (Spec Coverage)

| 스펙 요구사항 | 구현 태스크 |
|---|---|
| 런처 창 (아이콘 + 앱명 + 시작 버튼) | Task 3 |
| SVG 아이콘 (해상도 독립) | Task 3 `make_icon_pixmap()` |
| 다크 테마 `#1a1a2e` | Task 3 |
| 시스템 트레이 아이콘 | Task 4 |
| 트레이 메뉴 (창 열기 / 중지 / 종료) | Task 4 |
| MonitorThread (QThread, 시그널) | Task 2 |
| 플랫폼 알림음 분기 | Task 1 |
| main.py — `setQuitOnLastWindowClosed(False)` | Task 5 |
| ESC 취소 시 런처 복귀 | Task 5 (on_start 분기) |
