from unittest.mock import patch

_PICK = "autotools_shared.continuous_point_list.pick_point"


def _add_point(tab, x: int, y: int) -> None:
    with patch(_PICK, return_value=(x, y)):
        tab._point_list._on_add_point()


def test_start_disabled_until_point_added(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab.points == []
    assert not tab._start_btn.isEnabled()


def test_add_point_enables_start_and_delete_disables_again(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 333, 444)
    assert tab.points == [(333, 444)]
    assert tab._start_btn.isEnabled()

    tab._point_list._on_delete_row(tab._point_list._rows[0])
    assert tab.points == []
    assert not tab._start_btn.isEnabled()


def test_points_returned_in_insertion_order(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 10, 11)
    _add_point(tab, 20, 21)
    _add_point(tab, 30, 31)
    assert tab.points == [(10, 11), (20, 21), (30, 31)]


def test_rows_renumbered_after_delete(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 10, 11)
    _add_point(tab, 20, 21)
    _add_point(tab, 30, 31)
    lst = tab._point_list
    lst._on_delete_row(lst._rows[0])
    assert tab.points == [(20, 21), (30, 31)]
    assert [r._num_label.text() for r in lst._rows] == ["1", "2"]


def test_cancelled_pick_adds_nothing(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    with patch(_PICK, return_value=None):
        tab._point_list._on_add_point()
    assert tab.points == []
    assert not tab._start_btn.isEnabled()


def test_loop_button_defaults_off_and_toggles(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab.loop is False
    off_text = tab._loop_btn.text()
    assert "꺼짐" in off_text

    tab._loop_btn.click()
    assert tab.loop is True
    assert "켜짐" in tab._loop_btn.text()
    assert tab._loop_btn.text() != off_text

    tab._loop_btn.click()
    assert tab.loop is False
    assert tab._loop_btn.text() == off_text


def test_set_running_locks_list_loop_and_spins(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 10, 11)

    tab.set_running(True)
    assert not tab._loop_btn.isEnabled()
    assert not tab._min_spin.isEnabled()
    assert not tab._max_spin.isEnabled()
    assert not tab._point_list._add_btn.isEnabled()
    assert not tab._point_list._rows[0]._pos_btn.isEnabled()
    assert not tab._point_list._rows[0]._del_btn.isEnabled()

    tab.set_running(False)
    assert tab._loop_btn.isEnabled()
    assert tab._min_spin.isEnabled()
    assert tab._max_spin.isEnabled()
    assert tab._point_list._add_btn.isEnabled()
    assert tab._point_list._rows[0]._pos_btn.isEnabled()
    assert tab._point_list._rows[0]._del_btn.isEnabled()


def test_min_max_defaults_and_start_signal(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 333, 444)
    tab._min_spin.setValue(50)
    tab._max_spin.setValue(150)
    with qtbot.waitSignal(tab.start_requested, timeout=1000):
        tab._start_btn.click()
    assert tab.min_ms == 50
    assert tab.max_ms == 150


def test_ms_spins_step_by_100(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab._min_spin.singleStep() == 100
    assert tab._max_spin.singleStep() == 100

    tab._max_spin.setValue(200)
    tab._max_spin.stepUp()
    assert tab._max_spin.value() == 300
    tab._max_spin.stepDown()
    assert tab._max_spin.value() == 200


def test_ms_spin_defaults_unchanged(qtbot):
    """기본값은 100의 배수로 바꾸지 않는다(80 / 200 유지)."""
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    assert tab.min_ms == 80
    assert tab.max_ms == 200
    assert tab._min_spin.minimum() == 1
    assert tab._min_spin.maximum() == 10000


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

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 333, 444)
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)

    emitted = []
    tab.start_requested.connect(lambda: emitted.append(True))
    tab._start_btn.click()

    assert emitted == []
    assert tab._ms_error_label.text() != ""


def test_start_succeeds_and_clears_error_when_min_max_valid(qtbot):
    from ui.color_clicker_tab import ColorClickerTab

    tab = ColorClickerTab()
    qtbot.addWidget(tab)
    _add_point(tab, 333, 444)
    tab._max_spin.setValue(200)
    tab._min_spin.setValue(300)  # 먼저 잘못된 값으로 에러를 만들어두고
    tab._min_spin.setValue(50)   # 다시 유효한 값으로 고친 뒤

    with qtbot.waitSignal(tab.start_requested, timeout=1000):
        tab._start_btn.click()
    assert tab._ms_error_label.text() == ""
