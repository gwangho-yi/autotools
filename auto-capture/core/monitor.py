import time
import numpy as np
import mss
from PySide6.QtCore import QThread, Signal

from core.alert import alert

INTERVAL = 0.5
PIXEL_DIFF = 25
MIN_CHANGED = 15
ALERT_COOLDOWN = 3.0


class MonitorThread(QThread):
    motion_detected = Signal(int, int)
    stopped = Signal()

    def __init__(self, region, parent=None):
        super().__init__(parent)
        self.region = region

    def run(self):
        try:
            self._monitor_loop()
        finally:
            self.stopped.emit()

    def _monitor_loop(self):
        last_alert = 0.0
        with mss.mss() as sct:
            prev = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
            while not self.isInterruptionRequested():
                time.sleep(INTERVAL)
                try:
                    cur = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
                except Exception:
                    break
                delta = np.abs(cur - prev).sum(axis=2)
                mask = delta > PIXEL_DIFF
                changed = int(np.count_nonzero(mask))
                now = time.monotonic()
                if changed > MIN_CHANGED and (now - last_alert) >= ALERT_COOLDOWN:
                    ys, xs = np.where(mask)
                    h_px, w_px = mask.shape
                    fx = xs.mean() / w_px
                    fy = ys.mean() / h_px
                    cx = self.region["left"] + fx * self.region["width"]
                    cy = self.region["top"] + fy * self.region["height"]
                    self.motion_detected.emit(int(cx), int(cy))
                    alert()
                    last_alert = now
                    prev = cur  # reset baseline after alert
                else:
                    prev = cur
