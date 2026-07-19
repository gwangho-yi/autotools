import os
import sys
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt, QObject, Signal
from pynput import keyboard

from ui.launcher import Launcher
from ui.tray import TrayIcon
from ui.region_select import select_regions
from core.monitor import MonitorThread
from core.ipc_client import IpcClient
from core.color_monitor import ColorMonitorThread


def _install_crash_logger() -> None:
    """Qt 슬롯 안에서 잡히지 않은 예외를 홈 디렉터리 로그 파일에 남긴다.

    PyInstaller windowed(console=False) 빌드에서는 sys.stderr가 None이라,
    기본 예외 출력 시도 자체가 다시 예외를 던지며 아무 흔적 없이 앱이
    죽는 경우가 있다. 그걸 막고 항상 파일로 기록되게 한다.
    """
    log_path = os.path.join(os.path.expanduser("~"), "auto-capture-crash.log")

    def _hook(exc_type, exc_value, exc_tb):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("=== auto-capture crash ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _hook


class _F6Relay(QObject):
    """pynput 스레드 → Qt 메인 스레드 안전 브릿지."""

    triggered = Signal()

    def __init__(self, callback):
        super().__init__()
        self.triggered.connect(callback, Qt.ConnectionType.QueuedConnection)

    def notify(self):
        self.triggered.emit()


def main():
    _install_crash_logger()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    launcher = Launcher()
    try:
        tray = TrayIcon()
    except RuntimeError as e:
        QMessageBox.critical(None, "auto-capture", f"시스템 트레이를 사용할 수 없습니다:\n{e}")
        sys.exit(1)

    monitor_threads: list[MonitorThread] = []
    ipc_client: IpcClient | None = None
    color_thread: ColorMonitorThread | None = None
    motion_paused = False
    color_paused = False

    def on_start():
        nonlocal monitor_threads
        if any(t.isRunning() for t in monitor_threads):
            return
        if color_thread is not None and color_thread.isRunning():
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
        tray.show()
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
            tray.hide()
            launcher.reset()

    def on_stop():
        for t in monitor_threads:
            if t.isRunning():
                t.requestInterruption()
        for t in monitor_threads:
            t.wait()

    def on_color_start(region, target_rgb, tolerance):
        nonlocal color_thread
        # 상호배타: 기존 탭1 모니터가 돌고 있으면 무시
        if any(t.isRunning() for t in monitor_threads):
            return
        if color_thread is not None and color_thread.isRunning():
            return
        t = ColorMonitorThread(region, target_rgb, tolerance)
        t.color_detected.connect(on_color_detected)
        t.stopped.connect(on_color_stopped)
        t.start()
        color_thread = t
        launcher.color_tab.set_monitoring(True)
        launcher.color_tab.set_status("컬러 감시 중...")
        tray.show()
        tray.set_status("컬러 감시 중...")

    def on_color_detected(x, y):
        nonlocal color_paused
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_color_match(x, y)
        if color_thread is not None:
            color_thread.pause()
        color_paused = True
        launcher.color_tab.set_paused()
        launcher.color_tab.set_status(f"감지! ({x}, {y}) → 일시정지 (재시작을 눌러야 다시 감지)")

    def on_color_pause():
        nonlocal color_paused
        if color_thread is not None and color_thread.isRunning():
            color_thread.pause()
        color_paused = True
        launcher.color_tab.set_paused()
        launcher.color_tab.set_status("일시정지 — 컬러 감시 대기 중")
        tray.set_status("컬러 감시 일시정지")

    def on_color_resume():
        nonlocal color_paused
        if color_thread is not None and not color_thread.isInterruptionRequested():
            color_thread.resume()
        color_paused = False
        launcher.color_tab.set_monitoring(True)
        launcher.color_tab.set_status("컬러 감시 중...")
        tray.set_status("컬러 감시 중...")

    def on_color_stop():
        nonlocal color_thread
        if color_thread is not None and color_thread.isRunning():
            color_thread.requestInterruption()
            color_thread.wait()

    def on_color_stopped():
        launcher.color_tab.set_monitoring(False)
        launcher.color_tab.set_status("")
        if not any(t.isRunning() for t in monitor_threads):
            tray.hide()

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

    def on_f6_toggle():
        if any(t.isRunning() for t in monitor_threads):
            on_resume() if motion_paused else on_pause()
        elif color_thread is not None and color_thread.isRunning():
            on_color_resume() if color_paused else on_color_pause()

    def on_quit():
        on_stop()
        on_color_stop()
        if ipc_client:
            ipc_client.stop()
        hotkey_listener.stop()

    launcher.start_requested.connect(on_start)
    launcher.stop_requested.connect(on_stop)
    launcher.pause_requested.connect(on_pause)
    launcher.resume_requested.connect(on_resume)
    launcher.connect_toggled.connect(on_connect_toggle)
    launcher.color_tab.start_requested.connect(on_color_start)
    launcher.color_tab.stop_requested.connect(on_color_stop)
    launcher.color_tab.pause_requested.connect(on_color_pause)
    launcher.color_tab.resume_requested.connect(on_color_resume)
    tray.stop_requested.connect(on_stop)
    tray.open_requested.connect(on_open)
    app.aboutToQuit.connect(on_quit)

    f6_relay = _F6Relay(on_f6_toggle)
    hotkey_listener = keyboard.GlobalHotKeys({'<f6>': f6_relay.notify})
    hotkey_listener.start()

    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
