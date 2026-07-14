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
