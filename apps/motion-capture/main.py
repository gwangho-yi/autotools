import os
import sys
import traceback
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QCursor, QIcon
from pynput import keyboard

from ui.launcher import Launcher, make_icon_pixmap
from autotools_shared.bootstrap import create_app
from autotools_shared.tray import TrayIcon
from autotools_shared.overlay.region_select import select_regions
from autotools_shared.ipc.client import IpcClient
from autotools_shared.hotkey import HotkeyRelay
from core.monitor import MonitorThread


def _install_crash_logger() -> None:
    log_path = os.path.join(os.path.expanduser("~"), "motion-capture-crash.log")

    def _hook(exc_type, exc_value, exc_tb):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=== motion-capture crash ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _hook


def main():
    _install_crash_logger()
    app = create_app()
    app.setQuitOnLastWindowClosed(False)

    launcher = Launcher()
    try:
        tray = TrayIcon(QIcon(make_icon_pixmap(16)), app_name="motion-capture")
    except RuntimeError as e:
        QMessageBox.critical(None, "motion-capture", f"시스템 트레이를 사용할 수 없습니다:\n{e}")
        sys.exit(1)
    tray.set_status("대기 중")
    tray.show()

    monitor_threads: list[MonitorThread] = []
    ipc_client: IpcClient | None = None
    motion_paused = False

    def is_monitoring() -> bool:
        return any(t.isRunning() for t in monitor_threads)

    launcher.is_monitoring_check = is_monitoring

    def on_start():
        nonlocal monitor_threads
        if any(t.isRunning() for t in monitor_threads):
            return
        regions = select_regions()
        if not regions:
            launcher.reset()
            return
        threads = []
        for region in regions:
            t = MonitorThread(region)
            t.motion_detected.connect(on_motion)
            t.stopped.connect(on_stopped)
            t.start()
            threads.append(t)
        monitor_threads = threads
        launcher.set_monitoring(True, len(regions))
        tray.set_status(f"모니터링 중... ({len(regions)}개 영역)")

    def on_motion(x, y):
        nonlocal motion_paused
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_motion(x, y)
        for t in monitor_threads:
            t.pause()
        motion_paused = True
        launcher.set_paused()

    def on_pause():
        nonlocal motion_paused
        for t in monitor_threads:
            t.pause()
        motion_paused = True
        launcher.set_paused()
        tray.set_status("일시정지")

    def on_resume():
        nonlocal motion_paused
        for t in monitor_threads:
            if not t.isInterruptionRequested():
                t.resume()
        motion_paused = False
        count = len(monitor_threads)
        launcher.set_monitoring(True, count)
        tray.set_status(f"모니터링 중... ({count}개 영역)")

    def on_stopped():
        if not any(t.isRunning() for t in monitor_threads):
            tray.set_status("대기 중")
            launcher.reset()

    def on_stop():
        for t in monitor_threads:
            if t.isRunning():
                t.requestInterruption()
        for t in monitor_threads:
            t.wait()

    def on_connect_toggle(checked: bool) -> None:
        nonlocal ipc_client
        if checked:
            client = IpcClient(port=54321)
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

    def on_f6_toggle():
        if any(t.isRunning() for t in monitor_threads):
            on_resume() if motion_paused else on_pause()

    def on_quit():
        on_stop()
        if ipc_client:
            ipc_client.stop()
        hotkey_listener.stop()

    launcher.start_requested.connect(on_start)
    launcher.stop_requested.connect(on_stop)
    launcher.pause_requested.connect(on_pause)
    launcher.resume_requested.connect(on_resume)
    launcher.connect_toggled.connect(on_connect_toggle)
    tray.stop_requested.connect(on_stop)
    tray.open_requested.connect(on_open)
    app.aboutToQuit.connect(on_quit)

    f6_relay = HotkeyRelay(on_f6_toggle)
    hotkey_listener = keyboard.GlobalHotKeys({'<ctrl>+<f6>': f6_relay.notify})
    hotkey_listener.start()

    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
