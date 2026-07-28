def test_loupe_stays_right_when_space_available():
    from autotools_shared.overlay.color_picker import _loupe_geometry
    # 커서 x=100, 패널폭 140, 화면폭 1920 → 오른쪽 배치 (커서 + 여백)
    x = _loupe_geometry(cursor_x=100, panel_w=140, screen_w=1920)
    assert x > 100


def test_loupe_flips_left_near_right_edge():
    from autotools_shared.overlay.color_picker import _loupe_geometry
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


def test_compensate_alpha_blend_recovers_white_from_overlay_tint():
    from autotools_shared.overlay.color_picker import _compensate_alpha_blend
    # 실제 흰색(255)이 알파1 검정 오버레이와 섞이면 254로 캡처된다(255*254/255=254) — 원복 확인
    assert _compensate_alpha_blend((254, 254, 254)) == (255, 255, 255)


def test_compensate_alpha_blend_leaves_black_unchanged():
    from autotools_shared.overlay.color_picker import _compensate_alpha_blend
    assert _compensate_alpha_blend((0, 0, 0)) == (0, 0, 0)


def test_compensate_alpha_blend_clamps_to_255():
    from autotools_shared.overlay.color_picker import _compensate_alpha_blend
    assert _compensate_alpha_blend((255, 255, 255)) == (255, 255, 255)


def test_click_result_uses_event_global_position_not_qcursor_pos(qtbot, qapp):
    from autotools_shared.overlay.color_picker import _ColorPickerOverlay
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    shared = {"result": None, "close_fn": lambda: None}
    overlay = _ColorPickerOverlay(screen, shared)
    qtbot.addWidget(overlay)

    fake_frame = _fake_frame((30, 20, 10))

    fake_event = MagicMock()
    fake_event.globalPosition.return_value.toPoint.return_value = QPoint(500, 300)

    # QCursor.pos()는 완전히 다른 값으로 mock — 이 값이 결과에 쓰이면 버그가 재발한 것
    with patch("autotools_shared.overlay.color_picker.QCursor.pos", return_value=QPoint(1, 1)), \
         patch("autotools_shared.overlay.color_picker.mss.mss", return_value=_FakeSct(fake_frame)):
        overlay.mousePressEvent(fake_event)

    assert shared["result"] == (500, 300, (30, 20, 10))


def test_click_result_compensates_overlay_alpha_tint(qtbot, qapp):
    from autotools_shared.overlay.color_picker import _ColorPickerOverlay
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    shared = {"result": None, "close_fn": lambda: None}
    overlay = _ColorPickerOverlay(screen, shared)
    qtbot.addWidget(overlay)

    # 실제 화면은 흰색(255)이지만, 오버레이 자신의 알파1 검정 채우기가 섞여
    # mss에는 254로 캡처된다 — 보정을 거쳐 255로 복원돼야 한다
    fake_frame = _fake_frame((254, 254, 254))

    fake_event = MagicMock()
    fake_event.globalPosition.return_value.toPoint.return_value = QPoint(500, 300)

    with patch("autotools_shared.overlay.color_picker.QCursor.pos", return_value=QPoint(1, 1)), \
         patch("autotools_shared.overlay.color_picker.mss.mss", return_value=_FakeSct(fake_frame)):
        overlay.mousePressEvent(fake_event)

    assert shared["result"] == (500, 300, (255, 255, 255))


def test_mouse_move_syncs_loupe_from_event_global_position(qtbot, qapp):
    from autotools_shared.overlay.color_picker import _ColorPickerOverlay, _compensate_alpha_blend
    from PySide6.QtGui import QGuiApplication

    screen = QGuiApplication.primaryScreen()
    shared = {"result": None, "close_fn": lambda: None}
    overlay = _ColorPickerOverlay(screen, shared)
    qtbot.addWidget(overlay)

    fake_frame = _fake_frame((200, 100, 50))

    fake_event = MagicMock()
    fake_event.globalPosition.return_value.toPoint.return_value = QPoint(640, 480)

    with patch("autotools_shared.overlay.color_picker.QCursor.pos", return_value=QPoint(9, 9)), \
         patch("autotools_shared.overlay.color_picker.mss.mss", return_value=_FakeSct(fake_frame)):
        overlay.mouseMoveEvent(fake_event)

    assert overlay._global_pos == QPoint(640, 480)
    # 오버레이 자신의 알파1 채우기가 섞인 캡처값(200,100,50)을 보정한 결과
    assert overlay._center_rgb == _compensate_alpha_blend((200, 100, 50))
