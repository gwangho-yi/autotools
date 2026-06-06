import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QCursor

from ui.launcher import Launcher
from ui.tray import TrayIcon
from ui.region_select import select_region
from core.monitor import MonitorThread


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    launcher = Launcher()
    try:
        tray = TrayIcon()
    except RuntimeError as e:
        QMessageBox.critical(None, "ticketure", f"시스템 트레이를 사용할 수 없습니다:\n{e}")
        sys.exit(1)

    monitor_thread: MonitorThread | None = None

    def on_start():
        nonlocal monitor_thread
        if monitor_thread and monitor_thread.isRunning():
            return

        region = select_region()
        if not region or region["width"] < 8 or region["height"] < 8:
            launcher.reset()
            return

        thread = MonitorThread(region)
        thread.motion_detected.connect(on_motion)
        thread.stopped.connect(on_stopped)
        thread.start()
        monitor_thread = thread

        launcher.hide()
        tray.show()
        tray.set_status("모니터링 중...")

    def on_motion(x, y):
        QCursor.setPos(x, y)

    def on_stopped():
        tray.hide()
        launcher.reset()

    def on_stop():
        if monitor_thread and monitor_thread.isRunning():
            monitor_thread.requestInterruption()
            monitor_thread.wait()

    def on_open():
        launcher.show()
        launcher.raise_()

    launcher.start_requested.connect(on_start)
    tray.stop_requested.connect(on_stop)
    tray.open_requested.connect(on_open)
    app.aboutToQuit.connect(on_stop)

    launcher.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
