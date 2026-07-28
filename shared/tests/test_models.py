from autotools_shared.models import ClickPoint


def test_delay_ms_default():
    assert ClickPoint().delay_ms == 500


def test_delay_ms_seconds_and_ms():
    assert ClickPoint(seconds=2, ms=500).delay_ms == 2500


def test_delay_ms_all_fields():
    # 1h=3600s, 2m=120s, 3s → total 3723s → 3723000ms + 100 = 3723100
    assert ClickPoint(hours=1, minutes=2, seconds=3, ms=100).delay_ms == 3723100


def test_click_type_default():
    assert ClickPoint().click_type == "left"
