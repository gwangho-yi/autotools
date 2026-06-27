from unittest.mock import MagicMock, patch
from core.models import ClickPoint


def test_standalone_executes_all_points(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([
            ClickPoint(x=100, y=200, ms=10, click_type="left"),
            ClickPoint(x=300, y=400, ms=10, click_type="right"),
        ])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()

    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_capture_mode_clicks_immediately_then_sequence(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([
            ClickPoint(x=100, y=200, ms=10, click_type="left"),
        ])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_from_capture()

    # 즉시 클릭(auto-capture 위치) + 시퀀스 1개 = 총 2번 클릭
    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_double_click(qtbot):
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=50, y=50, ms=10, click_type="double")])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()

    # double click = press/release twice
    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_alert_called_on_sequence_finish(qtbot):
    """시퀀스 완료 시 alert()가 1회 호출되는지 확인"""
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse), \
         patch("core.click_engine.alert") as mock_alert:
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=100, y=200, ms=10, click_type="left")])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()

    mock_alert.assert_called_once()


def test_alert_not_called_on_interrupt(qtbot):
    """인터럽트로 중단 시 alert()가 호출되지 않는지 확인"""
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse), \
         patch("core.click_engine.alert") as mock_alert:
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        # 매우 긴 딜레이로 실행 중 중단
        engine.set_points([ClickPoint(x=100, y=200, ms=10000, click_type="left")])
        engine.start_standalone()
        import time; time.sleep(0.05)
        engine.stop()

    mock_alert.assert_not_called()
