import threading
import time
import numpy as np
import mss
from PySide6.QtCore import QThread, Signal

from autotools_shared.detection import select_target


INTERVAL = 0.1
MIN_MATCHED = 15
ALERT_COOLDOWN = 3.0


class ColorMonitorThread(QThread):
    color_detected = Signal(int, int)
    stopped = Signal()

    def __init__(self, region, target_rgb, tolerance, priority=None, parent=None):
        super().__init__(parent)
        self.region = region
        # target_rgb는 (r, g, b). mss 프레임은 BGR 순서이므로 비교용으로 뒤집어 둔다.
        r, g, b = target_rgb
        self._target_bgr = np.array([b, g, r], dtype=np.int16)
        self.tolerance = int(tolerance)
        self.priority = priority if priority is not None else ["left", "top"]
        self._pause_event = threading.Event()
        self._pause_event.set()  # running by default

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def run(self):
        try:
            self._monitor_loop()
        finally:
            self.stopped.emit()

    def _monitor_loop(self):
        last_alert = 0.0
        with mss.mss() as sct:
            while not self.isInterruptionRequested():
                if not self._pause_event.wait(timeout=0.1):
                    continue
                time.sleep(INTERVAL)
                try:
                    cur = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
                except Exception:
                    break
                diff = np.abs(cur - self._target_bgr)
                mask = diff.max(axis=2) <= self.tolerance
                matched = int(np.count_nonzero(mask))
                now = time.monotonic()
                if matched >= MIN_MATCHED and (now - last_alert) >= ALERT_COOLDOWN:
                    result = select_target(mask, self.priority)
                    if result is not None:
                        h_px, w_px = mask.shape
                        fx = result[0] / w_px
                        fy = result[1] / h_px
                        cx = self.region["left"] + fx * self.region["width"]
                        cy = self.region["top"] + fy * self.region["height"]
                        self.color_detected.emit(int(cx), int(cy))
                        last_alert = now
