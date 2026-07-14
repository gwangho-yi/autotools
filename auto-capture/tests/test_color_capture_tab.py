from unittest.mock import patch


def test_start_disabled_until_color_and_region_set(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    # 색·영역 둘 다 미지정 → 시작 불가
    assert tab.target_rgb is None
    assert tab.region is None
    assert not tab._start_btn.isEnabled()


def test_sampling_color_updates_swatch(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    assert tab.target_rgb == (200, 100, 30)


def test_start_emitted_with_params(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    with patch("ui.color_capture_tab.select_region",
               return_value={"left": 0, "top": 0, "width": 10, "height": 10}):
        tab._on_pick_region()
    tab._tolerance.setValue(12)

    with qtbot.waitSignal(tab.start_requested, timeout=1000) as blocker:
        tab._start_btn.click()
    region, rgb, tol = blocker.args
    assert rgb == (200, 100, 30)
    assert tol == 12
    assert region["width"] == 10
