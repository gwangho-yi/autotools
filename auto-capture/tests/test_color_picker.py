def test_loupe_stays_right_when_space_available():
    from ui.color_picker import _loupe_geometry
    # 커서 x=100, 패널폭 140, 화면폭 1920 → 오른쪽 배치 (커서 + 여백)
    x = _loupe_geometry(cursor_x=100, panel_w=140, screen_w=1920)
    assert x > 100


def test_loupe_flips_left_near_right_edge():
    from ui.color_picker import _loupe_geometry
    # 커서가 오른쪽 끝 근처 → 왼쪽으로 flip (패널 오른쪽 끝이 화면 안)
    x = _loupe_geometry(cursor_x=1900, panel_w=140, screen_w=1920)
    assert x + 140 <= 1900


from unittest.mock import patch, MagicMock

import numpy as np
from PySide6.QtCore import QPoint


def _fake_frame(rgb):
    r, g, b = rgb
    frame = np.zeros((15, 15, 3), dtype=np.uint8)
    frame[:, :, 0] = b
    frame[:, :, 1] = g
    frame[:, :, 2] = r
    return frame


class _FakeSct:
    def __init__(self, frame):
        self._frame = frame

    def grab(self, region):
        return self._frame

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_click_result_uses_event_global_position_not_qcursor_pos(qtbot, qapp):
    from ui.color_picker import _ColorPickerOverlay
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    shared = {"result": None, "close_fn": lambda: None}
    overlay = _ColorPickerOverlay(screen, shared)
    qtbot.addWidget(overlay)

    fake_frame = _fake_frame((30, 20, 10))

    fake_event = MagicMock()
    fake_event.globalPosition.return_value.toPoint.return_value = QPoint(500, 300)

    # QCursor.pos()는 완전히 다른 값으로 mock — 이 값이 결과에 쓰이면 버그가 재발한 것
    with patch("ui.color_picker.QCursor.pos", return_value=QPoint(1, 1)), \
         patch("ui.color_picker.mss.mss", return_value=_FakeSct(fake_frame)):
        overlay.mousePressEvent(fake_event)

    assert shared["result"] == (500, 300, (30, 20, 10))


def test_mouse_move_syncs_loupe_from_event_global_position(qtbot, qapp):
    from ui.color_picker import _ColorPickerOverlay
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    shared = {"result": None, "close_fn": lambda: None}
    overlay = _ColorPickerOverlay(screen, shared)
    qtbot.addWidget(overlay)

    fake_frame = _fake_frame((200, 100, 50))

    fake_event = MagicMock()
    fake_event.globalPosition.return_value.toPoint.return_value = QPoint(640, 480)

    with patch("ui.color_picker.QCursor.pos", return_value=QPoint(9, 9)), \
         patch("ui.color_picker.mss.mss", return_value=_FakeSct(fake_frame)):
        overlay.mouseMoveEvent(fake_event)

    assert overlay._global_pos == QPoint(640, 480)
    assert overlay._center_rgb == (200, 100, 50)
