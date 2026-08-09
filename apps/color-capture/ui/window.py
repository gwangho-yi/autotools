from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QApplication
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPixmap, QPainter, QColor, QPen

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


_CONN_BTN_STYLE = """
    QPushButton {{
        background-color: transparent;
        color: {color}; border: 1px solid {color};
        border-radius: 6px; font-size: 12px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{ background-color: rgba(78,204,163,0.07); }}
"""


class ColorCaptureWindow(QWidget):
    connect_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self.is_monitoring_check = lambda: False
        self.color_tab = ColorCaptureTab()
        self._build_ui()
        self._center()

    def closeEvent(self, event):
        if self.is_monitoring_check():
            event.ignore()
            self.hide()
        else:
            event.accept()
            QApplication.quit()

    def _build_ui(self):
        self.setWindowTitle("color-capture")
        self.setFixedSize(460, 410)
        self.setStyleSheet("background-color: #1a1a2e;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(2)
        outer.addWidget(self.color_tab)
        conn_row = QHBoxLayout()
        conn_row.setContentsMargins(20, 0, 20, 0)
        self._conn_btn = QPushButton("color-clicker 연결")
        self._conn_btn.setFixedHeight(34)
        self._conn_btn.setCheckable(True)
        self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
        self._conn_btn.toggled.connect(self._on_conn_toggled)
        conn_row.addWidget(self._conn_btn)
        outer.addLayout(conn_row)

    def _center(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def _on_conn_toggled(self, checked: bool) -> None:
        if checked:
            self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#888888"))
            self._conn_btn.setText("연결 중...")
        else:
            self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
            self._conn_btn.setText("color-clicker 연결")
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
        self._conn_btn.setText("color-clicker 연결")
        self._conn_btn.setStyleSheet(_CONN_BTN_STYLE.format(color="#8888bb"))
        self._conn_btn.blockSignals(False)
