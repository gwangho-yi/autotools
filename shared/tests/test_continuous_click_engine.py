import time
from unittest.mock import MagicMock, patch


class FakeMouse:
    """pynput Controller 대역. position 대입 이력을 순서대로 기록한다."""

    def __init__(self):
        self.moves: list[tuple[int, int]] = []
        self._position = (0, 0)
        self.press = MagicMock()
        self.release = MagicMock()

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.moves.append(tuple(value))


def test_intervals_within_range():
    """가우시안 샘플이 [min_ms, max_ms] 범위 내로 clip되는지 통계적으로 검증."""
    from autotools_shared.continuous_click_engine import ContinuousClickEngine

    eng = ContinuousClickEngine([(0, 0)], min_ms=100, max_ms=300)
    samples = [eng._next_interval_ms() for _ in range(2000)]
    assert all(100 <= s <= 300 for s in samples)
    mean = sum(samples) / len(samples)
    # 평균이 중앙값(200) 근처인지 (clip 때문에 정확히 200은 아니지만 근접)
    assert 180 <= mean <= 220


def test_continuous_clicks_repeatedly_until_stop(qtbot):
    mouse = FakeMouse()
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine([(10, 20)], min_ms=10, max_ms=20)
        eng.start()
        time.sleep(0.3)
        eng.stop()

    # 0.3초 동안 ~10-20ms 간격이면 최소 여러 번 클릭됨
    assert mouse.press.call_count >= 3


def test_loop_off_clicks_only_first_point(qtbot):
    mouse = FakeMouse()
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine(
            [(10, 20), (30, 40), (50, 60)], min_ms=10, max_ms=20, loop=False
        )
        eng.start()
        time.sleep(0.3)
        eng.stop()

    assert mouse.press.call_count >= 3
    # 시작 시 1회만 이동하고 이후엔 그 자리에서 클릭만 반복
    assert mouse.moves == [(10, 20)]


def test_loop_on_cycles_through_points(qtbot):
    mouse = FakeMouse()
    points = [(10, 20), (30, 40), (50, 60)]
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine(points, min_ms=10, max_ms=20, loop=True)
        eng.start()
        time.sleep(0.5)
        eng.stop()

    moves = mouse.moves
    # 최소 한 바퀴 이상 돌아야 순환을 검증할 수 있다
    assert len(moves) >= 6
    assert mouse.press.call_count >= 6
    # 매 클릭 직전에 이동한다. 중단이 이동 직후·클릭 직전에 걸리면 이동이 1회 더 많을 수 있다
    assert len(moves) - mouse.press.call_count in (0, 1)
    # 지점들이 등록 순서대로 순환한다
    for i, move in enumerate(moves):
        assert move == points[i % len(points)]


def test_single_point_with_loop_on_behaves_like_off(qtbot):
    mouse = FakeMouse()
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine([(7, 8)], min_ms=10, max_ms=20, loop=True)
        eng.start()
        time.sleep(0.3)
        eng.stop()

    assert mouse.press.call_count >= 3
    assert set(mouse.moves) == {(7, 8)}


def test_empty_points_finishes_immediately_without_clicking(qtbot):
    mouse = FakeMouse()
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine([], min_ms=10, max_ms=20)
        with qtbot.waitSignal(eng.stopped, timeout=1000):
            eng.start()
        eng.wait()

    assert not eng.isRunning()
    assert mouse.press.call_count == 0
    assert mouse.moves == []
