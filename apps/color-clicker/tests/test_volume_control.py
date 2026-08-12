from PySide6.QtCore import QPoint, Qt


def _make(qtbot, play=None):
    from ui.volume_control import VolumeControl

    calls = [] if play is None else None
    vol = VolumeControl(play=play or (lambda v: calls.append(v)))
    qtbot.addWidget(vol)
    vol.resize(300, 40)
    vol.show()
    qtbot.waitExposed(vol)
    return vol, calls


def test_default_value_is_100_percent(qtbot):
    vol, _ = _make(qtbot)
    assert vol.value == 100
    assert vol.volume == 1.0
    assert vol._pct_label.text() == "100%"


def test_changing_slider_updates_label_and_emits_volume_changed(qtbot):
    vol, _ = _make(qtbot)

    with qtbot.waitSignal(vol.volume_changed, timeout=1000) as blocker:
        vol._slider.setValue(40)

    assert blocker.args == [40]
    assert vol._pct_label.text() == "40%"
    assert vol.volume == 0.4


def test_dragging_without_release_does_not_preview(qtbot):
    vol, calls = _make(qtbot)

    vol._slider.setValue(10)
    vol._slider.setValue(90)
    assert calls == []


def test_dragging_the_handle_previews_once_at_final_value(qtbot):
    vol, calls = _make(qtbot)
    slider = vol._slider
    slider.setValue(50)  # 핸들을 중간으로 옮겨둔다(현재 핸들 위치와 다른 지점을 눌러야 함)
    y = slider.height() // 2

    qtbot.mousePress(slider, Qt.LeftButton, pos=QPoint(2, y))
    qtbot.mouseMove(slider, pos=QPoint(slider.width() - 2, y))
    qtbot.mouseRelease(slider, Qt.LeftButton, pos=QPoint(slider.width() - 2, y))

    assert len(calls) == 1
    assert calls[0] == vol.volume


def test_clicking_the_groove_previews_once_at_final_value(qtbot):
    """핸들이 아닌 트랙의 다른 지점을 클릭(드래그 없이)해도 미리듣기가 재생돼야 한다."""
    vol, calls = _make(qtbot)
    slider = vol._slider
    slider.setValue(50)  # 핸들은 가운데, 클릭은 왼쪽 끝(핸들이 아닌 트랙)을 노린다
    y = slider.height() // 2

    qtbot.mouseClick(slider, Qt.LeftButton, pos=QPoint(2, y))

    assert len(calls) == 1
    assert calls[0] == vol.volume


def test_clicking_left_edge_jumps_directly_to_minimum(qtbot):
    """단계별(page-step)로 조금씩 움직이지 않고, 클릭한 위치로 한 번에 이동해야 한다."""
    vol, _ = _make(qtbot)
    slider = vol._slider
    slider.setValue(50)
    y = slider.height() // 2

    qtbot.mouseClick(slider, Qt.LeftButton, pos=QPoint(0, y))

    assert slider.value() == 0


def test_clicking_right_edge_jumps_directly_to_maximum(qtbot):
    vol, _ = _make(qtbot)
    slider = vol._slider
    slider.setValue(50)
    y = slider.height() // 2

    qtbot.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 1, y))

    assert slider.value() == 100


def test_clicking_middle_jumps_close_to_midpoint(qtbot):
    vol, _ = _make(qtbot)
    slider = vol._slider
    slider.setValue(0)
    y = slider.height() // 2

    qtbot.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() // 2, y))

    assert 40 <= slider.value() <= 60
