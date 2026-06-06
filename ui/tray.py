from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, QObject

from ui.launcher import make_icon_pixmap


class TrayIcon(QObject):
    stop_requested = Signal()
    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(make_icon_pixmap(16)))
        self._tray.setToolTip("ticketure — 모니터링 중")
        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        status_action = menu.addAction("● 모니터링 중...")
        status_action.setEnabled(False)
        menu.addSeparator()
        open_action = menu.addAction("창 열기")
        open_action.triggered.connect(self.open_requested.emit)
        stop_action = menu.addAction("중지")
        stop_action.triggered.connect(self.stop_requested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("종료")
        quit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_requested.emit()

    def show(self):
        self._tray.show()

    def hide(self):
        self._tray.hide()
