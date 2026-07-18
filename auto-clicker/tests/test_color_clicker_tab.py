from unittest.mock import patch


def test_start_disabled_until_point_set(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab.point is None
    assert not tab._start_btn.isEnabled()


def test_pick_point_enables_start(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    assert tab.point == (333, 444)
    assert tab._start_btn.isEnabled()


def test_min_max_defaults_and_start_signal(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    tab._min_spin.setValue(50)
    tab._max_spin.setValue(150)
    with qtbot.waitSignal(tab.start_requested, timeout=1000):
        tab._start_btn.click()
    assert tab.min_ms == 50
    assert tab.max_ms == 150


def test_min_greater_than_max_is_clamped_with_error(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)
    assert tab._min_spin.value() == 200
    assert tab._ms_error_label.text() != ""


def test_max_less_than_min_is_clamped_with_error(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    tab._min_spin.setValue(100)
    tab._max_spin.setValue(50)
    assert tab._max_spin.value() == 100
    assert tab._ms_error_label.text() != ""


def test_valid_min_max_clears_error(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)  # 에러 발생
    tab._min_spin.setValue(50)   # 다시 유효한 값
    assert tab._ms_error_label.text() == ""
