import os
import sys
import traceback
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QCursor, QIcon
from pynput import keyboard

from ui.window import ColorCaptureWindow, make_icon_pixmap
from autotools_shared.bootstrap import create_app
from autotools_shared.tray import TrayIcon
from autotools_shared.ipc.client import IpcClient
from autotools_shared.hotkey import HotkeyRelay
from core.color_monitor import ColorMonitorThread


def _install_crash_logger() -> None:
    log_path = os.path.join(os.path.expanduser("~"), "color-capture-crash.log")

    def _hook(exc_type, exc_value, exc_tb):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=== color-capture crash ===\n")
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

    window = ColorCaptureWindow()
    try:
        tray = TrayIcon(QIcon(make_icon_pixmap(16)), app_name="color-capture")
    except RuntimeError as e:
        QMessageBox.critical(None, "color-capture", f"시스템 트레이를 사용할 수 없습니다:\n{e}")
        sys.exit(1)
    tray.set_status("대기 중")
    tray.show()

    color_threads: list[ColorMonitorThread] = []
    ipc_client: IpcClient | None = None
    color_paused = False

    def is_monitoring() -> bool:
        return any(t.isRunning() for t in color_threads)

    window.is_monitoring_check = is_monitoring

    def on_color_start(regions, target_rgb, tolerance):
        nonlocal color_threads
        if any(t.isRunning() for t in color_threads):
            return
        priority = window.color_tab.priority()
        threads = []
        for region in regions:
            t = ColorMonitorThread(region, target_rgb, tolerance, priority)
            t.color_detected.connect(on_color_detected)
            t.stopped.connect(on_color_stopped)
            t.start()
            threads.append(t)
        color_threads = threads
        window.color_tab.set_monitoring(True)
        window.color_tab.set_status("컬러 감시 중...")
        tray.set_status("컬러 감시 중...")

    def on_color_detected(x, y):
        nonlocal color_paused
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_color_match(x, y)
        for t in color_threads:
            t.pause()
        color_paused = True
        window.color_tab.set_paused()
        window.color_tab.set_status(f"감지! ({x}, {y}) → 일시정지 (재시작을 눌러야 다시 감지)")

    def on_color_pause():
        nonlocal color_paused
        for t in color_threads:
            t.pause()
        color_paused = True
        window.color_tab.set_paused()
        window.color_tab.set_status("일시정지 — 컬러 감시 대기 중")
        tray.set_status("컬러 감시 일시정지")

    def on_color_resume():
        nonlocal color_paused
        for t in color_threads:
            if not t.isInterruptionRequested():
                t.resume()
        color_paused = False
        window.color_tab.set_monitoring(True)
        window.color_tab.set_status("컬러 감시 중...")
        tray.set_status("컬러 감시 중...")

    def on_color_stop():
        for t in color_threads:
            if t.isRunning():
                t.requestInterruption()
        for t in color_threads:
            t.wait()

    def on_color_stopped():
        if any(t.isRunning() for t in color_threads):
            return
        window.color_tab.set_monitoring(False)
        window.color_tab.set_status("")
        tray.set_status("대기 중")

    def on_connect_toggle(checked: bool) -> None:
        nonlocal ipc_client
        if checked:
            client = IpcClient(port=54322)
            ipc_client = client
            client.connected.connect(
                lambda: window.set_connect_status("연결됨 ●", True)
            )
            client.disconnected.connect(on_ipc_disconnected)
            client.start()
        else:
            if ipc_client:
                ipc_client.stop()
                ipc_client = None
            window.reset_connect_btn()

    def on_ipc_disconnected() -> None:
        nonlocal ipc_client
        ipc_client = None
        window.reset_connect_btn()

    def on_open():
        window.show()
        window.raise_()

    def on_f6_toggle():
        if any(t.isRunning() for t in color_threads):
            on_color_resume() if color_paused else on_color_pause()

    def on_quit():
        on_color_stop()
        if ipc_client:
            ipc_client.stop()
        hotkey_listener.stop()

    window.color_tab.start_requested.connect(on_color_start)
    window.color_tab.stop_requested.connect(on_color_stop)
    window.color_tab.pause_requested.connect(on_color_pause)
    window.color_tab.resume_requested.connect(on_color_resume)
    window.connect_toggled.connect(on_connect_toggle)
    tray.stop_requested.connect(on_color_stop)
    tray.open_requested.connect(on_open)
    app.aboutToQuit.connect(on_quit)

    f6_relay = HotkeyRelay(on_f6_toggle)
    hotkey_listener = keyboard.GlobalHotKeys({'<ctrl>+<f6>': f6_relay.notify})
    hotkey_listener.start()

    window.show()
    window.raise_()
    window.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
