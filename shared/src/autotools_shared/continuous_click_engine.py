import random
import time
from PySide6.QtCore import QThread, Signal
from pynput.mouse import Button, Controller

_PRESS_HOLD_S = 0.02
_MOVE_SETTLE_S = 0.02


class ContinuousClickEngine(QThread):
    stopped = Signal()

    def __init__(self, points: list[tuple[int, int]], min_ms: int, max_ms: int,
                 click_type: str = "left", loop: bool = False, parent=None):
        super().__init__(parent)
        self._points = [(int(x), int(y)) for x, y in points]
        self._min_ms = int(min_ms)
        self._max_ms = int(max_ms)
        self._click_type = click_type
        self._loop = loop

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
            if not self._points:
                return
            if self._loop:
                self._run_loop(mouse)
            else:
                self._run_single(mouse)
        finally:
            self.stopped.emit()

    def _run_single(self, mouse: Controller) -> None:
        """첫 지점 하나만 무한 반복(시작 시 1회 이동 후 클릭만 반복)."""
        mouse.position = self._points[0]
        time.sleep(_MOVE_SETTLE_S)
        while not self.isInterruptionRequested():
            self._do_click(mouse)
            self._interruptible_sleep(self._next_interval_ms() / 1000)

    def _run_loop(self, mouse: Controller) -> None:
        """지점들을 0 → 1 → … → N-1 → 0 으로 순환하며 클릭(매번 이동)."""
        i = 0
        while not self.isInterruptionRequested():
            mouse.position = self._points[i]
            time.sleep(_MOVE_SETTLE_S)
            self._do_click(mouse)
            i = (i + 1) % len(self._points)
            self._interruptible_sleep(self._next_interval_ms() / 1000)

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
