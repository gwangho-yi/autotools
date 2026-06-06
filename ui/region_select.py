import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect, QEventLoop
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication


class RegionSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.start = None
        self.end = None
        self.selected_region = None
        self._loop = None  # set by select_region()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        geo = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(geo)
        self.show()

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
        self.selected_region = {
            "left": rect.x(),
            "top": rect.y(),
            "width": rect.width(),
            "height": rect.height(),
        }
        self.close()
        if self._loop:
            self._loop.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selected_region = None
            self.close()
            if self._loop:
                self._loop.quit()


def select_region():
    app = QApplication.instance() or QApplication(sys.argv)
    loop = QEventLoop()
    selector = RegionSelector()
    selector._loop = loop
    loop.exec()
    return selector.selected_region


if __name__ == "__main__":
    region = select_region()
    print("선택한 영역(물리 픽셀):", region)
