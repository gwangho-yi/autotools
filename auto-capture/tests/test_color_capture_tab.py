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


def test_pause_button_shown_when_monitoring_and_emits_pause_requested(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    tab.set_monitoring(True)
    assert tab._btn_stack.currentIndex() == 1

    with qtbot.waitSignal(tab.pause_requested, timeout=1000):
        tab._pause_btn.click()


def test_set_paused_shows_resume_and_stop_buttons(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    tab.set_monitoring(True)
    tab.set_paused()
    assert tab._btn_stack.currentIndex() == 2

    with qtbot.waitSignal(tab.resume_requested, timeout=1000):
        tab._resume_btn.click()


def test_stop_button_in_paused_state_emits_stop_requested(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    tab.set_monitoring(True)
    tab.set_paused()

    with qtbot.waitSignal(tab.stop_requested, timeout=1000):
        tab._stop_btn.click()


def test_start_btn_reenabled_after_stopping(qtbot, qapp):
    from ui.color_capture_tab import ColorCaptureTab

    tab = ColorCaptureTab()
    qtbot.addWidget(tab)
    with patch("ui.color_capture_tab.pick_pixel_color",
               return_value=(50, 60, (200, 100, 30))):
        tab._on_pick_color()

    with patch("ui.color_capture_tab.select_region",
               return_value={"left": 0, "top": 0, "width": 10, "height": 10}):
        tab._start_btn.click()
    assert not tab._start_btn.isEnabled()  # 영역 선택 중/모니터링 중에는 비활성

    tab.set_monitoring(True)
    assert not tab._start_btn.isEnabled()  # 모니터링 중에도 비활성 유지

    tab.set_monitoring(False)
    assert tab._start_btn.isEnabled()  # 정지 후에는 다시 활성화되어야 함
