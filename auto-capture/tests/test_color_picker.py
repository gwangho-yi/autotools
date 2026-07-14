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
