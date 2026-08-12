from unittest.mock import patch


def _build_window(qtbot):
    from ui.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    qtbot.wait(200)  # IpcServer 스레드가 bind할 시간을 준 뒤 닫아야 stop()과 레이스가 안 남
    return win


def test_main_window_constructs_without_capture_row(qtbot):
    win = _build_window(qtbot)
    try:
        assert win._capture_row is None
        assert win._list.count() == 0
    finally:
        win.close()


def test_client_connected_inserts_capture_row_and_offsets_list(qtbot):
    win = _build_window(qtbot)
    try:
        win._on_client_connected()

        assert win._capture_row is not None
        assert win._list._index_offset == 1
    finally:
        win.close()


def test_client_disconnected_removes_capture_row_and_resets_offset(qtbot):
    win = _build_window(qtbot)
    try:
        win._on_client_connected()
        win._on_client_disconnected()

        assert win._capture_row is None
        assert win._list._index_offset == 0
    finally:
        win.close()


def test_color_match_uses_capture_row_click_type(qtbot):
    win = _build_window(qtbot)
    try:
        win._on_client_connected()
        win._capture_row._type_group.button(1).setChecked(True)  # "우"(right)

        with patch.object(win._engine, "start_from_color") as mock_start:
            win._on_color_match(10, 20)

        mock_start.assert_called_once_with(10, 20, "right")
    finally:
        win.close()


def test_color_match_defaults_to_left_when_capture_not_connected(qtbot):
    win = _build_window(qtbot)
    try:
        with patch.object(win._engine, "start_from_color") as mock_start:
            win._on_color_match(10, 20)

        mock_start.assert_called_once_with(10, 20, "left")
    finally:
        win.close()
