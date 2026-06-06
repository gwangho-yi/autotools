from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor, QPen, QPixmap


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

    def reset(self):
        self.start_btn.setEnabled(True)
        self.status_label.setText("")
        self.show()
        self.raise_()
