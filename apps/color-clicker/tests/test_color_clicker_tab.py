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


def test_typing_min_greater_than_max_is_not_blocked(qtbot):
    """입력 도중에는 값을 강제로 건드리거나 막지 않아야 한다(시작 시점에만 검사)."""
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)  # 일시적으로 min > max 이어도 그대로 입력 가능해야 함
    assert tab._min_spin.value() == 300
    assert tab._max_spin.value() == 200


def test_start_blocked_with_error_when_min_greater_than_max(qtbot):
    from ui.color_clicker_tab import ColorClickerTab
    from unittest.mock import patch

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)

    emitted = []
    tab.start_requested.connect(lambda: emitted.append(True))
    tab._start_btn.click()

    assert emitted == []
    assert tab._ms_error_label.text() != ""


def test_start_succeeds_and_clears_error_when_min_max_valid(qtbot):
    from ui.color_clicker_tab import ColorClickerTab
    from unittest.mock import patch

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch("ui.color_clicker_tab.pick_point", return_value=(333, 444)):
        tab._on_pick_point()
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)  # 먼저 잘못된 값으로 에러를 만들어두고
    tab._min_spin.setValue(50)   # 다시 유효한 값으로 고친 뒤

    with qtbot.waitSignal(tab.start_requested, timeout=1000):
        tab._start_btn.click()
    assert tab._ms_error_label.text() == ""
