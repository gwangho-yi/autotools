import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect, QEventLoop
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication


class RegionSelector(QWidget):
    def __init__(self, screen, shared):
        super().__init__()
        self._screen = screen
        self._shared = shared  # {'result': None, 'loop': None, 'widgets': []}
        self.start = None
        self.end = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        # show() 먼저 호출해야 windowHandle()이 생성됨
        self.show()
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.setGeometry(screen.geometry())

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.start and self.end:
            rect = QRect(self.start, self.end).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(rect, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(0, 200, 0), 2))
            p.drawRect(rect)

    def mousePressEvent(self, event):
        self.start = event.position().toPoint()
        self.end = self.start
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        rect = QRect(self.start, event.position().toPoint()).normalized()
        # 로컬 좌표 → 글로벌 좌표 변환 (스크린 원점 더하기)
        origin = self._screen.geometry().topLeft()
        self._shared['result'] = {
            "left": rect.x() + origin.x(),
            "top": rect.y() + origin.y(),
            "width": rect.width(),
            "height": rect.height(),
        }
        self._close_all()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._shared['result'] = None
            self._close_all()

    def _close_all(self):
        for w in self._shared['widgets']:
            w.close()
        if self._shared['loop']:
            self._shared['loop'].quit()


def select_region():
    app = QApplication.instance() or QApplication(sys.argv)
    screens = QGuiApplication.screens()
    if not screens:
        return None

    loop = QEventLoop()
    shared = {'result': None, 'loop': loop, 'widgets': []}

    for screen in screens:
        selector = RegionSelector(screen, shared)
        shared['widgets'].append(selector)

    loop.exec()
    return shared['result']


if __name__ == "__main__":
    region = select_region()
    print("선택한 영역:", region)
