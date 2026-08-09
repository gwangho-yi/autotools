def test_default_is_left_top(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    assert w.priority() == ["left", "top"]


def test_repress_removes_badge(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    # 기본 [left, top]에서 left 다시 누르면 제거 → [top]
    w._on_dir("left")
    assert w.priority() == ["top"]
    # top도 누르면 제거 → [] (선택 없음)
    w._on_dir("top")
    assert w.priority() == []


def test_add_in_press_order(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()            # 비우기(랜덤)
    w._on_dir("bottom")       # ① 아래
    w._on_dir("right")        # ② 오른쪽
    assert w.priority() == ["bottom", "right"]


def test_same_axis_replaces(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    # 기본 [left, top]. right 누르면 x축 교체 → [right, top]
    w._on_dir("right")
    assert w.priority() == ["right", "top"]
    # bottom 누르면 y축 교체 → [right, bottom]
    w._on_dir("bottom")
    assert w.priority() == ["right", "bottom"]


def test_random_is_exclusive(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()
    assert w.priority() == "random"
    w._on_dir("top")          # 방향 누르면 랜덤 해제
    assert w.priority() == ["top"]


def test_max_two_axes(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()            # 비우기
    w._on_dir("left")         # [left]
    w._on_dir("top")          # [left, top]
    w._on_dir("bottom")       # y축 교체 → [left, bottom]
    assert w.priority() == ["left", "bottom"]


def test_changed_signal(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    with qtbot.waitSignal(w.changed, timeout=1000):
        w._on_dir("right")


def test_badge_label_reflects_order(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_random()
    w._on_dir("bottom")
    w._on_dir("right")
    txt = w._badge_label.text()
    assert "①" in txt and "②" in txt
    assert "아래" in txt and "오른쪽" in txt


def test_empty_shows_default_label(qtbot):
    from autotools_shared.priority_selector import PrioritySelector
    w = PrioritySelector()
    qtbot.addWidget(w)
    w._on_dir("left")   # [top]
    w._on_dir("top")    # []
    assert w.priority() == []
    assert "기본" in w._badge_label.text()
