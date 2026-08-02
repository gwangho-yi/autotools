import numpy as np

from autotools_shared.detection import find_blobs, select_target


def _mask_with_blobs():
    # 100x100. 잘 떨어진 3개 덩어리(사각형)
    m = np.zeros((100, 100), dtype=bool)
    m[10:20, 10:20] = True    # 중심 (14.5, 14.5)  왼쪽 위
    m[10:20, 80:90] = True    # 중심 (84.5, 14.5)  오른쪽 위
    m[80:90, 45:55] = True    # 중심 (49.5, 84.5)  아래 가운데
    return m


def test_find_blobs_counts_three():
    blobs = find_blobs(_mask_with_blobs())
    assert len(blobs) == 3
    # (cx, cy, w, h) 형식
    for b in blobs:
        assert len(b) == 4
        assert b[2] > 0 and b[3] > 0   # 크기 양수


def test_empty_mask_returns_none():
    assert select_target(np.zeros((50, 50), dtype=bool), ["left"]) is None


def test_left_priority_picks_leftmost():
    cx, cy = select_target(_mask_with_blobs(), ["left"])
    assert round(cx) in (14, 15)


def test_right_priority_picks_rightmost():
    cx, cy = select_target(_mask_with_blobs(), ["right"])
    assert round(cx) in (84, 85)


def test_bottom_priority_picks_bottommost():
    cx, cy = select_target(_mask_with_blobs(), ["bottom"])
    assert round(cy) in (84, 85)


def test_random_returns_one_of_blobs():
    m = _mask_with_blobs()
    centers = set((round(b[0]), round(b[1])) for b in find_blobs(m))
    cx, cy = select_target(m, "random")
    assert (round(cx), round(cy)) in centers


def test_downsample_path_still_finds_blobs():
    m = np.zeros((400, 400), dtype=bool)
    m[50:250, 50:250] = True   # 200x200 = 40000 픽셀 > 임계값
    blobs = find_blobs(m)
    assert len(blobs) == 1
    cx, cy = blobs[0][0], blobs[0][1]
    assert 140 <= cx <= 160 and 140 <= cy <= 160


def _grid_mask():
    """2x2 격자. 아래줄 두 좌석의 세로좌표가 살짝 다르게(왼쪽이 1px 더 아래) 배치 —
    엄격 사전식이면 2순위가 무시되어 왼쪽이 잡히는 상황을 재현."""
    m = np.zeros((120, 120), dtype=bool)
    # 위줄
    m[10:30, 10:30] = True      # 위-왼
    m[10:30, 90:110] = True     # 위-오
    # 아래줄: 왼쪽을 1px 더 아래로(90~111) vs 오른쪽(90~110)
    m[90:111, 10:30] = True     # 아래-왼 (살짝 더 아래)
    m[90:110, 90:110] = True    # 아래-오
    return m


def test_bottom_right_bucketing_picks_bottom_right():
    # "아래①, 오른쪽②": 아래줄을 버킷으로 묶고 그중 오른쪽을 골라야 한다.
    # (엄격 사전식이면 1px 더 아래인 아래-왼이 잡혀서 실패했던 케이스)
    cx, cy = select_target(_grid_mask(), ["bottom", "right"])
    assert cx > 60    # 오른쪽 열(x≈99)이어야 함, 왼쪽(x≈19) 아님
    assert cy > 60    # 아래줄


def test_right_bottom_symmetric():
    # "오른쪽①, 아래②": 오른쪽 열을 버킷으로 묶고 그중 아래를 골라야 한다(대칭).
    cx, cy = select_target(_grid_mask(), ["right", "bottom"])
    assert cx > 60    # 오른쪽 열
    assert cy > 60    # 그중 아래줄


def test_top_left_picks_top_left():
    cx, cy = select_target(_grid_mask(), ["top", "left"])
    assert cx < 60 and cy < 60   # 위-왼
