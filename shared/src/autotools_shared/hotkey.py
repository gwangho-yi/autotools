from PySide6.QtCore import Qt, QObject, Signal


class HotkeyRelay(QObject):
    """pynput 스레드 → Qt 메인 스레드 안전 브릿지."""

    triggered = Signal()

    def __init__(self, callback):
        super().__init__()
        self.triggered.connect(callback, Qt.ConnectionType.QueuedConnection)

    def notify(self):
        self.triggered.emit()
