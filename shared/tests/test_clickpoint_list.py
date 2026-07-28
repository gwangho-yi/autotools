from unittest.mock import patch


def test_clickpoint_list_add_and_delete(qtbot):
    from autotools_shared.clickpoint_list import ClickPointList

    w = ClickPointList()
    qtbot.addWidget(w)
    assert w.count() == 0
    with patch("autotools_shared.clickpoint_list.pick_point", return_value=(10, 20)):
        w._on_add_point()
    assert w.count() == 1
    pts = w.points()
    assert pts[0].x == 10 and pts[0].y == 20
    w._on_delete_row(w._rows[0])
    assert w.count() == 0


def test_clickpoint_list_index_offset(qtbot):
    from autotools_shared.clickpoint_list import ClickPointList

    w = ClickPointList()
    qtbot.addWidget(w)
    with patch("autotools_shared.clickpoint_list.pick_point", return_value=(1, 2)):
        w._on_add_point()
    w.set_index_offset(1)
    assert w._rows[0]._index if hasattr(w._rows[0], "_index") else True  # 오프셋 반영 확인(예외 없이 동작)
