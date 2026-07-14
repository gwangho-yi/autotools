import random
import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

_PRESS_HOLD_S = 0.02
_MOVE_SETTLE_S = 0.02


class ContinuousClickEngine(QThread):
    stopped = Signal()

    def __init__(self, x: int, y: int, min_ms: int, max_ms: int,
                 click_type: str = "left", parent=None):
        super().__init__(parent)
        self._x = x
        self._y = y
        self._min_ms = int(min_ms)
        self._max_ms = int(max_ms)
        self._click_type = click_type

    def _next_interval_ms(self) -> float:
        mu = (self._min_ms + self._max_ms) / 2
        sigma = (self._max_ms - self._min_ms) / 4
        if sigma <= 0:
            return float(self._min_ms)
        sample = random.gauss(mu, sigma)
        return max(self._min_ms, min(self._max_ms, sample))

    def run(self) -> None:
        mouse = Controller()
        try:
            mouse.position = (self._x, self._y)
            time.sleep(_MOVE_SETTLE_S)
            while not self.isInterruptionRequested():
                self._do_click(mouse)
                self._interruptible_sleep(self._next_interval_ms() / 1000)
        finally:
            self.stopped.emit()

    def _do_click(self, mouse: Controller) -> None:
        if self.isInterruptionRequested():
            return
        try:
            if self._click_type == "double":
                mouse.press(Button.left); time.sleep(_PRESS_HOLD_S); mouse.release(Button.left)
                time.sleep(_PRESS_HOLD_S)
                mouse.press(Button.left); time.sleep(_PRESS_HOLD_S); mouse.release(Button.left)
            else:
                btn = Button.left if self._click_type == "left" else Button.right
                mouse.press(btn); time.sleep(_PRESS_HOLD_S); mouse.release(btn)
        except Exception:
            pass

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.isInterruptionRequested():
                return
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))

    def stop(self) -> None:
        self.requestInterruption()
        self.wait()
