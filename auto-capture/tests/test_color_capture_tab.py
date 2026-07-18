from unittest.mock import patch


def test_start_disabled_until_color_set(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    # 색 미지정 → 시작 불가 (영역은 시작 버튼 클릭 시 지정하므로 조건에서 제외)
    assert tab.target_rgb is None
    assert not tab._start_btn.isEnabled()


def test_sampling_color_updates_swatch(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    assert tab.target_rgb == (200, 100, 30)


def test_picked_color_syncs_rgb_spinboxes(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    values = tuple(spin.value() for spin in tab._rgb_spins)
    assert values == (200, 100, 30)


def test_editing_rgb_spinboxes_updates_target_and_enables_start(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    assert not tab._start_btn.isEnabled()

    r_spin, g_spin, b_spin = tab._rgb_spins
    r_spin.setValue(10)
    g_spin.setValue(20)
    b_spin.setValue(30)

    assert tab.target_rgb == (10, 20, 30)
    assert tab._start_btn.isEnabled()


def test_start_opens_region_select_and_emits_params(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()
    tab._tolerance.setValue(12)

    with patch("ui.color_capture_tab.select_region",
               return_value={"left": 0, "top": 0, "width": 10, "height": 10}):
        with qtbot.waitSignal(tab.start_requested, timeout=1000) as blocker:
            tab._start_btn.click()
    region, rgb, tol = blocker.args
    assert rgb == (200, 100, 30)
    assert tol == 12
    assert region["width"] == 10


def test_start_cancelled_when_region_selection_cancelled(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()

    emitted = []
    tab.start_requested.connect(lambda *args: emitted.append(args))
    with patch("ui.color_capture_tab.select_region", return_value=None):
        tab._start_btn.click()

    assert emitted == []
    assert tab._start_btn.isEnabled()
