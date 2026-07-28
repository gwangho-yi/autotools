import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect, QEventLoop
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication, QFont


class RegionSelector(QWidget):
    def __init__(self, screen, shared):
        super().__init__()
        self._screen = screen
        self._shared = shared  # {'regions': [], 'loop': None, 'widgets': []}
        self._state = "drawing"
        self._start = None
        self._end = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

        self.show()
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

    def paintEvent(self, event):
        p = QPainter(self)
        origin = self._screen.geometry().topLeft()

        p.fillRect(self.rect(), QColor(0, 0, 0, 90))

        # Confirmed regions
        for i, region in enumerate(self._shared['regions']):
            local = QRect(
                region['left'] - origin.x(),
                region['top'] - origin.y(),
                region['width'],
                region['height'],
            )
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(78, 204, 163), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(local)
            badge = QRect(local.left() + 2, local.top() + 2, 22, 22)
            p.setBrush(QColor(78, 204, 163))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(badge, 4, 4)
            p.setPen(QColor(20, 20, 40))
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.drawText(badge, Qt.AlignCenter, str(i + 1))

        # In-progress drag
        if self._state == "drawing" and self._start and self._end:
            rect = QRect(self._start, self._end).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(rect, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(255, 200, 50), 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(rect)

        if self._shared['regions']:
            self._draw_toolbar(p)

    def _draw_toolbar(self, p):
        sw, sh = self.rect().width(), self.rect().height()
        bar_w, bar_h = 360, 42
        bar_x = (sw - bar_w) // 2
        bar_y = sh - bar_h - 20

        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setBrush(QColor(15, 15, 30, 210))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 10, 10)

        p.setPen(QColor(200, 200, 200))
        p.setFont(QFont("Arial", 12))
        hint = f"영역 {len(self._shared['regions'])}개 선택됨  |  Enter 완료  |  ESC 취소"
        p.drawText(bar_x, bar_y, bar_w, bar_h, Qt.AlignCenter, hint)

    def mousePressEvent(self, event):
        self._state = "drawing"
        self._start = event.position().toPoint()
        self._end = self._start
        self.update()

    def mouseMoveEvent(self, event):
        if self._state == "drawing" and self._start:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if self._state != "drawing" or not self._start:
            return
        rect = QRect(self._start, event.position().toPoint()).normalized()
        self._start = None
        self._end = None
        if rect.width() < 8 or rect.height() < 8:
            self.update()
            return
        origin = self._screen.geometry().topLeft()
        self._shared['regions'].append({
            "left": rect.x() + origin.x(),
            "top": rect.y() + origin.y(),
            "width": rect.width(),
            "height": rect.height(),
        })
        for w in self._shared['widgets']:
            w.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._shared['regions']:
                self._close_all()
        elif event.key() == Qt.Key_Escape:
            self._shared['regions'].clear()
            self._close_all()

    def _close_all(self):
        for w in self._shared['widgets']:
            w.close()
        if self._shared['loop']:
            self._shared['loop'].quit()


def select_regions() -> list[dict]:
    app = QApplication.instance() or QApplication(sys.argv)
    screens = QGuiApplication.screens()
    if not screens:
        return []

    loop = QEventLoop()
    shared = {'regions': [], 'loop': loop, 'widgets': []}

    for screen in screens:
        selector = RegionSelector(screen, shared)
        shared['widgets'].append(selector)

    loop.exec()
    return shared['regions']


def select_region():
    regions = select_regions()
    return regions[0] if regions else None


if __name__ == "__main__":
    regions = select_regions()
    print("선택한 영역들:", regions)
