import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QCursor

from ui.launcher import Launcher
from ui.tray import TrayIcon
from ui.region_select import select_region
from core.monitor import MonitorThread
from core.ipc_client import IpcClient


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    launcher = Launcher()
    try:
        tray = TrayIcon()
    except RuntimeError as e:
        QMessageBox.critical(None, "auto-capture", f"시스템 트레이를 사용할 수 없습니다:\n{e}")
        sys.exit(1)

    monitor_thread: MonitorThread | None = None
    ipc_client: IpcClient | None = None

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

        launcher.set_monitoring(True)
        tray.show()
        tray.set_status("모니터링 중...")

    def on_motion(x, y):
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_motion(x, y)
        if monitor_thread:
            monitor_thread.pause()
        launcher.set_paused()

    def on_pause():
        if monitor_thread:
            monitor_thread.pause()
        launcher.set_paused()
        tray.set_status("일시정지")

    def on_resume():
        if monitor_thread and not monitor_thread.isInterruptionRequested():
            monitor_thread.resume()
        launcher.set_monitoring(True)
        tray.set_status("모니터링 중...")

    def on_stopped():
        tray.hide()
        launcher.reset()

    def on_stop():
        if monitor_thread and monitor_thread.isRunning():
            monitor_thread.requestInterruption()
            monitor_thread.wait()

    def on_connect_toggle(checked: bool) -> None:
        nonlocal ipc_client
        if checked:
            client = IpcClient()
            ipc_client = client
            client.connected.connect(
                lambda: launcher.set_connect_status("연결됨 ●", True)
            )
            client.disconnected.connect(on_ipc_disconnected)
            client.start()
        else:
            if ipc_client:
                ipc_client.stop()
                ipc_client = None
            launcher.reset_connect_btn()

    def on_ipc_disconnected() -> None:
        nonlocal ipc_client
        ipc_client = None
        launcher.reset_connect_btn()

    def on_open():
        launcher.show()
        launcher.raise_()

    def on_quit():
        on_stop()
        if ipc_client:
            ipc_client.stop()

    launcher.start_requested.connect(on_start)
    launcher.stop_requested.connect(on_stop)
    launcher.pause_requested.connect(on_pause)
    launcher.resume_requested.connect(on_resume)
    launcher.connect_toggled.connect(on_connect_toggle)
    tray.stop_requested.connect(on_stop)
    tray.open_requested.connect(on_open)
    app.aboutToQuit.connect(on_quit)

    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
