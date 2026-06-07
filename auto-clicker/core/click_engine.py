import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

from core.models import ClickPoint


class ClickEngine(QThread):
    sequence_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[ClickPoint] = []
        self._immediate_first = False
        self._mouse = Controller()

    def set_points(self, points: list[ClickPoint]) -> None:
        self._points = list(points)

    def start_standalone(self) -> None:
        """시작 버튼으로 실행: 첫 포인트도 설정된 딜레이 후 클릭."""
        if self.isRunning():
            return
        self._immediate_first = False
        self.start()

    def start_from_capture(self) -> None:
        """auto-capture 신호로 실행: 현재 커서 위치 즉시 클릭 후 시퀀스 실행."""
        if self.isRunning():
            return
        self._immediate_first = True
        self.start()

    def run(self) -> None:
        if self._immediate_first:
            self._do_click_button(Button.left)

        for point in self._points:
            if self.isInterruptionRequested():
                break
            self._interruptible_sleep(point.delay_ms / 1000)
            if self.isInterruptionRequested():
                break
            self._mouse.position = (point.x, point.y)
            if point.click_type == "double":
                self._mouse.click(Button.left, 2)
            else:
                button = Button.left if point.click_type == "left" else Button.right
                self._do_click_button(button)

        if not self.isInterruptionRequested():
            self.sequence_finished.emit()

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.isInterruptionRequested():
                return
            time.sleep(min(0.05, end - time.monotonic()))

    def _do_click_button(self, button: Button) -> None:
        self._mouse.press(button)
        self._mouse.release(button)

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
