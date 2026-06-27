from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QEventLoop, QPoint, QObject, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication


class _EscFilter(QObject):
    """앱 레벨에서 ESC 키를 가로채는 이벤트 필터."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._callback()
            return True
        return False


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
        self._shared["close_fn"]()


def pick_point() -> tuple[int, int] | None:
    """전체 화면 오버레이를 표시하고 사용자가 클릭한 글로벌 좌표를 반환. ESC시 None."""
    loop = QEventLoop()
    shared = {"result": None, "loop": loop, "widgets": [], "close_fn": None}

    def close_all():
        app = QApplication.instance()
        if app and shared.get("_esc_filter"):
            app.removeEventFilter(shared["_esc_filter"])
        for w in shared["widgets"]:
            w.close()
        loop.quit()

    shared["close_fn"] = close_all

    esc_filter = _EscFilter(close_all)
    shared["_esc_filter"] = esc_filter
    QApplication.instance().installEventFilter(esc_filter)

    for screen in QGuiApplication.screens():
        overlay = _PointPickerOverlay(screen, shared)
        shared["widgets"].append(overlay)

    loop.exec()
    return shared["result"]
