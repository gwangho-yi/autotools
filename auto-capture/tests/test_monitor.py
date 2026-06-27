import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication
import sys


@pytest.fixture(scope="session")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    return app


def make_frame(shape=(100, 100, 4), value=0):
    arr = np.zeros(shape, dtype=np.uint8)
    arr[:] = value
    return arr


def test_motion_detected_emitted_on_change(qtbot, qapp):
    """픽셀 변화가 충분하면 motion_detected가 emit되는지 확인"""
    from core.monitor import MonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}

    frame1 = make_frame(value=0)
    frame2 = make_frame(value=100)  # 큰 변화

    with patch("core.monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.side_effect = [frame1, frame2] + [frame2] * 100

        thread = MonitorThread(region)
        with qtbot.waitSignal(thread.motion_detected, timeout=3000):
            thread.start()
        thread.requestInterruption()
        thread.wait()


def test_no_motion_when_frames_identical(qtbot, qapp):
    """프레임이 동일하면 motion_detected가 emit되지 않는지 확인"""
    from core.monitor import MonitorThread

    region = {"left": 0, "top": 0, "width": 100, "height": 100}
    frame = make_frame(value=50)

    emitted = []

    with patch("core.monitor.mss") as mock_mss:
        mock_sct = MagicMock()
        mock_mss.mss.return_value.__enter__.return_value = mock_sct
        mock_sct.grab.return_value = frame

        thread = MonitorThread(region)
        thread.motion_detected.connect(lambda x, y: emitted.append((x, y)))
        thread.start()
        time.sleep(0.8)
        thread.requestInterruption()
        thread.wait()

    assert emitted == []
