"""감지 mask에서 덩어리(연결 성분)를 찾아 우선순위/랜덤으로 하나를 고르는 유틸.

scipy 없이 numpy만 사용한다. 좌석처럼 서로 떨어진 대상에 적합.
"""
import random

import numpy as np

# 매칭 픽셀이 이보다 많으면 다운샘플 후 묶기(파이썬 플러드필 과부하 방지)
_DOWNSAMPLE_THRESHOLD = 20000


def find_blobs(mask: np.ndarray) -> list[tuple[float, float]]:
    """4-이웃 연결 성분을 찾아 각 덩어리의 중심 (cx, cy)(픽셀 좌표) 리스트를 반환.

    cx=열(가로), cy=행(세로). 감지 덩어리가 없으면 빈 리스트.
    매칭 픽셀이 매우 많으면 2배 다운샘플한 mask로 묶고 좌표를 원배율로 되돌린다.
    """
    matched = int(np.count_nonzero(mask))
    if matched == 0:
        return []

    scale = 1
    work = mask
    if matched > _DOWNSAMPLE_THRESHOLD:
        work = mask[::2, ::2]
        scale = 2

    H, W = work.shape
    visited = np.zeros_like(work, dtype=bool)
    ys, xs = np.where(work)
    blobs: list[tuple[float, float]] = []
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if visited[y0, x0]:
            continue
        stack = [(y0, x0)]
        visited[y0, x0] = True
        sum_x = 0.0
        sum_y = 0.0
        cnt = 0
        while stack:
            y, x = stack.pop()
            sum_x += x
            sum_y += y
            cnt += 1
            if y > 0 and work[y - 1, x] and not visited[y - 1, x]:
                visited[y - 1, x] = True
                stack.append((y - 1, x))
            if y < H - 1 and work[y + 1, x] and not visited[y + 1, x]:
                visited[y + 1, x] = True
                stack.append((y + 1, x))
            if x > 0 and work[y, x - 1] and not visited[y, x - 1]:
                visited[y, x - 1] = True
                stack.append((y, x - 1))
            if x < W - 1 and work[y, x + 1] and not visited[y, x + 1]:
                visited[y, x + 1] = True
                stack.append((y, x + 1))
        blobs.append((sum_x / cnt * scale, sum_y / cnt * scale))
    return blobs


def _fill_priority(priority: list[str]) -> list[str]:
    """방향 우선순위에 빠진 축을 기본값으로 채워 완전한 2D 정렬 순서를 만든다.

    미지정 세로축 → 'top', 미지정 가로축 → 'left'.
    """
    dirs = list(priority)
    has_x = any(d in ("left", "right") for d in dirs)
    has_y = any(d in ("top", "bottom") for d in dirs)
    if not has_y:
        dirs.append("top")
    if not has_x:
        dirs.append("left")
    return dirs


def _blob_key(blob: tuple[float, float], dirs: list[str]) -> tuple:
    cx, cy = blob
    key = []
    for d in dirs:
        if d == "left":
            key.append(cx)
        elif d == "right":
            key.append(-cx)
        elif d == "top":
            key.append(cy)
        elif d == "bottom":
            key.append(-cy)
    return tuple(key)


def select_target(mask: np.ndarray, priority) -> tuple[float, float] | None:
    """mask에서 덩어리 하나를 골라 그 중심 (cx, cy)(픽셀 좌표)를 반환. 없으면 None.

    priority: "random" 또는 방향 리스트(1순위부터). 각 원소는
              "left" | "right" | "top" | "bottom".
    """
    blobs = find_blobs(mask)
    if not blobs:
        return None
    if priority == "random":
        return random.choice(blobs)
    dirs = _fill_priority(list(priority))
    return min(blobs, key=lambda b: _blob_key(b, dirs))
