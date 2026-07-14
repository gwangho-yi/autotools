import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest


def make_frame(shape=(100, 100, 4), bgr=(0, 0, 0)):
    """mss grab 반환 흉내: BGRA 순서 프레임."""
    arr = np.zeros(shape, dtype=np.uint8)
    arr[:, :, 0] = bgr[0]  # B
    arr[:, :, 1] = bgr[1]  # G
    arr[:, :, 2] = bgr[2]  # R
    return arr


def test_color_detected_within_tolerance(qtbot, qapp):
    """목표색과 채널차가 tolerance 이내면 color_detected가 emit되는지."""
    from core.color_monitor import ColorMonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}
    # 목표 RGB (10, 20, 30). 프레임은 BGR로 (12, 22, 32) → 채널차 2 <= tolerance 5
    frame = make_frame(bgr=(12, 22, 32))

    with patch("core.color_monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.return_value = frame

        thread = ColorMonitorThread(region, target_rgb=(30, 20, 10), tolerance=5)
        with qtbot.waitSignal(thread.color_detected, timeout=3000):
            thread.start()
        thread.requestInterruption()
        thread.wait()


def test_no_detection_outside_tolerance(qtbot, qapp):
    """채널차가 tolerance를 초과하면 emit되지 않는지."""
    from core.color_monitor import ColorMonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}
    # 목표 RGB (30, 20, 10) → BGR 목표 (10,20,30). 프레임 BGR (30,20,10) → R차 20, B차 20 > tol 5
    frame = make_frame(bgr=(30, 20, 10))

    emitted = []
    with patch("core.color_monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.return_value = frame

        thread = ColorMonitorThread(region, target_rgb=(30, 20, 10), tolerance=5)
        thread.color_detected.connect(lambda x, y: emitted.append((x, y)))
        thread.start()
        time.sleep(0.8)
        thread.requestInterruption()
        thread.wait()

    assert emitted == []
