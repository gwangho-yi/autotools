from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, QObject

from ui.launcher import make_icon_pixmap


class TrayIcon(QObject):
    stop_requested = Signal()
    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("System tray is not available on this platform/session")
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(make_icon_pixmap(16)))
        self._tray.setToolTip("ticketure — 모니터링 중")
        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self):
        self._menu = QMenu()
        self._status_action = self._menu.addAction("● 모니터링 중...")
        self._status_action.setEnabled(False)
        self._menu.addSeparator()
        open_action = self._menu.addAction("창 열기")
        open_action.triggered.connect(self.open_requested.emit)
        stop_action = self._menu.addAction("중지")
        stop_action.triggered.connect(self.stop_requested.emit)
        self._menu.addSeparator()
        quit_action = self._menu.addAction("종료")
        quit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(self._menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_requested.emit()

    def set_status(self, text: str) -> None:
        self._status_action.setText(text)
        self._tray.setToolTip(f"ticketure — {text}")

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
