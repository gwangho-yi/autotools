from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QPixmap

from ui.color_capture_tab import ColorCaptureTab


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

    p.drawRoundedRect(margin, y, w, h, radius, radius)

    notch_r = max(2, int(size * 0.07))
    notch_y = y + h // 2
    p.setBrush(QColor("#1a1a2e"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(margin - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)
    p.drawEllipse(margin + w - notch_r, notch_y - notch_r, notch_r * 2, notch_r * 2)

    dash_pen = QPen(QColor("#4ecca3"), max(1, int(size * 0.04)), Qt.DashLine)
    p.setPen(dash_pen)
    p.drawLine(margin + notch_r, notch_y, margin + w - notch_r, notch_y)

    p.end()
    return px


_BTN_GREEN = """
    QPushButton {
        background-color: #4ecca3; color: #1a1a2e;
        border: none; border-radius: 8px;
        font-size: 16px; font-weight: bold;
    }
    QPushButton:hover { background-color: #3db89a; }
    QPushButton:disabled { background-color: #2a4a3e; color: #555; }
"""

_BTN_RED = """
    QPushButton {
        background-color: #e05555; color: white;
        border: none; border-radius: 8px;
        font-size: 16px; font-weight: bold;
    }
    QPushButton:hover { background-color: #c04444; }
"""

_BTN_OUTLINE = """
    QPushButton {
        background-color: transparent; color: #4ecca3;
        border: 1px solid #4ecca3; border-radius: 8px;
        font-size: 16px; font-weight: bold;
    }
    QPushButton:hover { background-color: rgba(78,204,163,0.1); }
"""

_CONN_BTN_STYLE = """
    QPushButton {{
        background-color: transparent;
        color: {color}; border: 1px solid {color};
        border-radius: 6px; font-size: 12px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{ background-color: rgba(78,204,163,0.07); }}
"""


class Launcher(QWidget):
    start_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    connect_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self._build_ui()
        self._center()

    def _build_ui(self):
        self.setWindowTitle("auto-capture")
        self.setFixedSize(360, 520)
        self.setStyleSheet("background-color: #1a1a2e;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(8)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: #2a2a4e; color: #888888;
                padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #4ecca3; color: #1a1a2e; font-weight: bold; }
        """)
        self._tabs.addTab(self._build_capture_page(), "화면 변화")
        self.color_tab = ColorCaptureTab()
        self._tabs.addTab(self.color_tab, "컬러 감지")
        outer.addWidget(self._tabs)

        # auto-clicker 연결 버튼 — 탭과 무관하게 항상 보이는 공유 영역
        conn_row = QHBoxLayout()
        conn_row.setContentsMargins(20, 0, 20, 0)
        self._conn_btn = QPushButton("auto-clicker 연결")
        self._conn_btn.setFixedHeight(34)
        self._conn_btn.setCheckable(True)
        self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
        self._conn_btn.toggled.connect(self._on_conn_toggled)
        conn_row.addWidget(self._conn_btn)
        outer.addLayout(conn_row)

    def _build_capture_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 16, 24, 16)

        icon_label = QLabel()
        icon_label.setPixmap(make_icon_pixmap(64))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("auto-capture")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("화면 변화를 감지하고 커서를 이동합니다")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(subtitle)

        layout.addStretch()

        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedHeight(44)

        # Page 0: idle
        p0 = QWidget()
        p0_l = QVBoxLayout(p0)
        p0_l.setContentsMargins(0, 0, 0, 0)
        self.start_btn = QPushButton("시작")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setStyleSheet(_BTN_GREEN)
        self.start_btn.clicked.connect(self._on_start)
        p0_l.addWidget(self.start_btn)
        self._btn_stack.addWidget(p0)

        # Page 1: monitoring
        p1 = QWidget()
        p1_l = QVBoxLayout(p1)
        p1_l.setContentsMargins(0, 0, 0, 0)
        self.pause_btn = QPushButton("일시정지")
        self.pause_btn.setFixedHeight(44)
        self.pause_btn.setStyleSheet(_BTN_OUTLINE)
        self.pause_btn.clicked.connect(lambda: self.pause_requested.emit())
        p1_l.addWidget(self.pause_btn)
        self._btn_stack.addWidget(p1)

        # Page 2: paused
        p2 = QWidget()
        p2_l = QHBoxLayout(p2)
        p2_l.setContentsMargins(0, 0, 0, 0)
        p2_l.setSpacing(8)
        self.resume_btn = QPushButton("재시작")
        self.resume_btn.setFixedHeight(44)
        self.resume_btn.setStyleSheet(_BTN_GREEN)
        self.resume_btn.clicked.connect(lambda: self.resume_requested.emit())
        p2_l.addWidget(self.resume_btn)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.setStyleSheet(_BTN_RED)
        self.stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        p2_l.addWidget(self.stop_btn)
        self._btn_stack.addWidget(p2)

        layout.addWidget(self._btn_stack)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)

        return page

    def _center(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _on_start(self):
        self.start_btn.setEnabled(False)
        self.status_label.setText("영역을 선택하세요...")
        self.start_requested.emit()

    def _on_conn_toggled(self, checked: bool) -> None:
        if checked:
            self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#888888"))
            self._conn_btn.setText("연결 중...")
        else:
            self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
            self._conn_btn.setText("auto-clicker 연결")
        self.connect_toggled.emit(checked)

    def set_connect_status(self, text: str, connected: bool) -> None:
        self._conn_btn.blockSignals(True)
        self._conn_btn.setText(text)
        color = "#4ecca3" if connected else "#888888"
        self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color=color))
        self._conn_btn.blockSignals(False)

    def reset_connect_btn(self) -> None:
        self._conn_btn.blockSignals(True)
        self._conn_btn.setChecked(False)
        self._conn_btn.setText("auto-clicker 연결")
        self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
        self._conn_btn.blockSignals(False)

    def set_monitoring(self, active: bool, region_count: int = 1) -> None:
        if active:
            self._btn_stack.setCurrentIndex(1)
            label = f"모니터링 중... ({region_count}개 영역)" if region_count > 1 else "모니터링 중..."
            self.status_label.setText(label)
        else:
            self._btn_stack.setCurrentIndex(0)
            self.start_btn.setEnabled(True)
            self.status_label.setText("")

    def set_paused(self) -> None:
        self._btn_stack.setCurrentIndex(2)
        self.status_label.setText("일시정지 — 변화 감지 후 대기 중")

    def reset(self) -> None:
        self.set_monitoring(False)
        self.show()
        self.raise_()
