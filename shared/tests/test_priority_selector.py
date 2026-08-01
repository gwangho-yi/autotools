def test_default_is_left_top(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    assert w.priority() == ["left", "top"]


def test_replace_same_axis_keeps_order(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    # 기본 ["left","top"]에서 right 누르면 x축 교체 → ["right","top"]
    w._on_dir("right")
    assert w.priority() == ["right", "top"]
    # bottom 누르면 y축 교체 → ["right","bottom"]
    w._on_dir("bottom")
    assert w.priority() == ["right", "bottom"]


def test_random_is_exclusive(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()
    assert w.priority() == "random"
    # 방향 다시 누르면 랜덤 해제되고 그 방향이 1순위
    w._on_dir("top")
    assert w.priority() == ["top"]


def test_press_order_is_priority(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()            # 초기화
    w._on_dir("top")          # 1순위 세로
    w._on_dir("left")         # 2순위 가로
    assert w.priority() == ["top", "left"]


def test_changed_signal_emitted(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.changed, timeout=1000):
        w._on_dir("right")
