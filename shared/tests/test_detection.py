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


def test_empty_mask_returns_none():
    assert select_target(np.zeros((50, 50), dtype=bool), ["left"]) is None


def test_left_priority_picks_leftmost():
    cx, cy = select_target(_mask_with_blobs(), ["left"])
    assert round(cx) == 14 or round(cx) == 15   # 왼쪽 위 덩어리 x≈14.5


def test_right_priority_picks_rightmost():
    cx, cy = select_target(_mask_with_blobs(), ["right"])
    assert round(cx) in (84, 85)                # 오른쪽 위 덩어리 x≈84.5


def test_bottom_priority_picks_bottommost():
    cx, cy = select_target(_mask_with_blobs(), ["bottom"])
    assert round(cy) in (84, 85)                # 아래 덩어리 y≈84.5


def test_top_left_order_vs_left_top_order():
    # 두 덩어리가 위쪽에 나란히(같은 y대), 하나는 아래. "top" 1순위면 위쪽 둘 중 하나,
    # 그중 "left" 2순위로 가장 왼쪽 → 왼쪽 위 덩어리(x≈14.5)
    cx, cy = select_target(_mask_with_blobs(), ["top", "left"])
    assert round(cx) in (14, 15) and round(cy) in (14, 15)


def test_random_returns_one_of_blobs():
    m = _mask_with_blobs()
    centers = set((round(cx), round(cy)) for cx, cy in find_blobs(m))
    cx, cy = select_target(m, "random")
    assert (round(cx), round(cy)) in centers


def test_downsample_path_still_finds_blobs():
    # 매우 큰 덩어리로 다운샘플 경로 강제(임계값 초과)
    m = np.zeros((400, 400), dtype=bool)
    m[50:250, 50:250] = True   # 200x200 = 40000 픽셀 > 임계값
    blobs = find_blobs(m)
    assert len(blobs) == 1
    cx, cy = blobs[0]
    assert 140 <= cx <= 160 and 140 <= cy <= 160   # 중심 ≈ (150, 150)
