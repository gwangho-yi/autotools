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
