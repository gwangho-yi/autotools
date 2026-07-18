import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QCursor

from ui.launcher import Launcher
from ui.tray import TrayIcon
from ui.region_select import select_regions
from core.monitor import MonitorThread
from core.ipc_client import IpcClient
from core.color_monitor import ColorMonitorThread


def main():
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
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_motion(x, y)
        for t in monitor_threads:
            t.pause()
        launcher.set_paused()

    def on_pause():
        for t in monitor_threads:
            t.pause()
        launcher.set_paused()
        tray.set_status("일시정지")

    def on_resume():
        for t in monitor_threads:
            if not t.isInterruptionRequested():
                t.resume()
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
        QCursor.setPos(x, y)
        if ipc_client:
            ipc_client.send_color_match(x, y)
        launcher.color_tab.set_status(f"감지! ({x}, {y}) 신호 전송")

    def on_color_pause():
        if color_thread is not None and color_thread.isRunning():
            color_thread.pause()
        launcher.color_tab.set_paused()
        launcher.color_tab.set_status("일시정지 — 컬러 감시 대기 중")
        tray.set_status("컬러 감시 일시정지")

    def on_color_resume():
        if color_thread is not None and not color_thread.isInterruptionRequested():
            color_thread.resume()
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

    def on_quit():
        on_stop()
        on_color_stop()
        if ipc_client:
            ipc_client.stop()

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

    launcher.show()
    launcher.raise_()
    launcher.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
