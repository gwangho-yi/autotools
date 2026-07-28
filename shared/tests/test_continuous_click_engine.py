import time
from unittest.mock import MagicMock, patch


def test_intervals_within_range():
    """가우시안 샘플이 [min_ms, max_ms] 범위 내로 clip되는지 통계적으로 검증."""
    from autotools_shared.continuous_click_engine import ContinuousClickEngine

    eng = ContinuousClickEngine(x=0, y=0, min_ms=100, max_ms=300)
    samples = [eng._next_interval_ms() for _ in range(2000)]
    assert all(100 <= s <= 300 for s in samples)
    mean = sum(samples) / len(samples)
    # 평균이 중앙값(200) 근처인지 (clip 때문에 정확히 200은 아니지만 근접)
    assert 180 <= mean <= 220


def test_continuous_clicks_repeatedly_until_stop(qtbot):
    mock_mouse = MagicMock()
    with patch("autotools_shared.continuous_click_engine.Controller", return_value=mock_mouse):
        from autotools_shared.continuous_click_engine import ContinuousClickEngine

        eng = ContinuousClickEngine(x=10, y=20, min_ms=10, max_ms=20)
        eng.start()
        time.sleep(0.3)
        eng.stop()

    # 0.3초 동안 ~10-20ms 간격이면 최소 여러 번 클릭됨
    assert mock_mouse.press.call_count >= 3
