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
        engine.wait()

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
        engine.wait()

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
        engine.wait()

    # double click = press/release twice
    assert mock_mouse.press.call_count == 2
    assert mock_mouse.release.call_count == 2


def test_sequence_finished_emitted(qtbot):
    """시퀀스 완료 시 sequence_finished 시그널이 발생하는지 확인"""
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=100, y=200, ms=10, click_type="left")])

        with qtbot.waitSignal(engine.sequence_finished, timeout=3000):
            engine.start_standalone()
        engine.wait()


def test_sequence_finished_not_emitted_on_interrupt(qtbot):
    """인터럽트로 중단 시 sequence_finished가 발생하지 않는지 확인"""
    mock_mouse = MagicMock()
    with patch("core.click_engine.Controller", return_value=mock_mouse):
        from core.click_engine import ClickEngine

        engine = ClickEngine()
        engine.set_points([ClickPoint(x=100, y=200, ms=10000, click_type="left")])
        engine.start_standalone()

        import time; time.sleep(0.05)

        with qtbot.assertNotEmitted(engine.sequence_finished):
            engine.stop()
