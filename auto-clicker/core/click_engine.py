import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

from core.models import ClickPoint

_PRESS_HOLD_S = 0.02   # press→release hold time (20ms)
_MOVE_SETTLE_S = 0.02  # position set → click settle time (20ms)


class ClickEngine(QThread):
    sequence_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[ClickPoint] = []
        self._capture_click_type: str | None = None

    def set_points(self, points: list[ClickPoint]) -> None:
        self._points = list(points)

    def start_standalone(self) -> None:
        if self.isRunning():
            return
        self._capture_click_type = None
        self.start()

    def start_from_capture(self, click_type: str = "left") -> None:
        if self.isRunning():
            return
        self._capture_click_type = click_type
        self.start()

    def run(self) -> None:
        # Create Controller in the worker thread so Quartz events are posted
        # from the correct thread context on macOS.
        mouse = Controller()

        if self._capture_click_type is not None:
            if self._capture_click_type == "double":
                self._do_click(mouse, Button.left)
                time.sleep(_PRESS_HOLD_S)
                self._do_click(mouse, Button.left)
            else:
                btn = Button.left if self._capture_click_type == "left" else Button.right
                self._do_click(mouse, btn)

        for point in self._points:
            if self.isInterruptionRequested():
                break
            self._interruptible_sleep(point.delay_ms / 1000)
            if self.isInterruptionRequested():
                break
            mouse.position = (point.x, point.y)
            time.sleep(_MOVE_SETTLE_S)
            if self.isInterruptionRequested():
                break
            if point.click_type == "double":
                self._do_click(mouse, Button.left)
                time.sleep(_PRESS_HOLD_S)
                self._do_click(mouse, Button.left)
            else:
                button = Button.left if point.click_type == "left" else Button.right
                self._do_click(mouse, button)

        if not self.isInterruptionRequested():
            self.sequence_finished.emit()

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.isInterruptionRequested():
                return
            time.sleep(min(0.05, end - time.monotonic()))

    def _do_click(self, mouse: Controller, button: Button) -> None:
        try:
            mouse.press(button)
            time.sleep(_PRESS_HOLD_S)
            mouse.release(button)
        except Exception:
            pass

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
