import time
import numpy as np
import mss
from PySide6.QtCore import QThread, Signal

from core.alert import alert

INTERVAL = 0.5
PIXEL_DIFF = 25
MIN_CHANGED = 15


class MonitorThread(QThread):
    motion_detected = Signal(int, int)
    stopped = Signal()

    def __init__(self, region, parent=None):
        super().__init__(parent)
        self.region = region

    def run(self):
        with mss.mss() as sct:
            prev = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
            while not self.isInterruptionRequested():
                time.sleep(INTERVAL)
                cur = np.array(sct.grab(self.region), dtype=np.int16)[:, :, :3]
                delta = np.abs(cur - prev).sum(axis=2)
                mask = delta > PIXEL_DIFF
                changed = int(np.count_nonzero(mask))
                if changed > MIN_CHANGED:
                    ys, xs = np.where(mask)
                    h_px, w_px = mask.shape
                    fx = xs.mean() / w_px
                    fy = ys.mean() / h_px
                    cx = self.region["left"] + fx * self.region["width"]
                    cy = self.region["top"] + fy * self.region["height"]
                    self.motion_detected.emit(int(cx), int(cy))
                    alert()
                prev = cur
        self.stopped.emit()
