"""감지 mask에서 덩어리(연결 성분)를 찾아 우선순위/랜덤으로 하나를 고르는 유틸.

scipy 없이 numpy만 사용한다. 좌석처럼 서로 떨어진 대상에 적합.
"""
import random

import numpy as np

# 매칭 픽셀이 이보다 많으면 다운샘플 후 묶기(파이썬 플러드필 과부하 방지)
_DOWNSAMPLE_THRESHOLD = 20000


def find_blobs(mask: np.ndarray) -> list[tuple[float, float, float, float]]:
    """4-이웃 연결 성분을 찾아 각 덩어리의 (cx, cy, w, h)를 반환.

    cx=중심 열(가로), cy=중심 행(세로), w=가로 픽셀 폭, h=세로 픽셀 높이(원배율).
    감지 덩어리가 없으면 빈 리스트. 매칭 픽셀이 매우 많으면 2배 다운샘플 후 좌표/크기를
    원배율로 되돌린다.
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
    blobs: list[tuple[float, float, float, float]] = []
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if visited[y0, x0]:
            continue
        stack = [(y0, x0)]
        visited[y0, x0] = True
        sum_x = 0.0
        sum_y = 0.0
        cnt = 0
        min_x = max_x = x0
        min_y = max_y = y0
        while stack:
            y, x = stack.pop()
            sum_x += x
            sum_y += y
            cnt += 1
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y
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
        cx = sum_x / cnt * scale
        cy = sum_y / cnt * scale
        w = (max_x - min_x + 1) * scale
        h = (max_y - min_y + 1) * scale
        blobs.append((cx, cy, w, h))
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


def _bucketed_key(blob, dirs, tol_x: float, tol_y: float) -> tuple:
    """정렬 키: 각 축을 (버킷 인덱스, 원좌표) 순으로 쌓는다.

    버킷 인덱스로 같은 줄/열을 동점 처리하고, 다음 축(2순위)이 그 동점을 가른다.
    같은 축의 원좌표는 마지막에 최종 tie-break으로 붙인다.
    """
    cx, cy = blob[0], blob[1]
    bx = round(cx / tol_x)
    by = round(cy / tol_y)
    key = []
    for d in dirs:
        if d == "left":
            key.append(bx)
        elif d == "right":
            key.append(-bx)
        elif d == "top":
            key.append(by)
        elif d == "bottom":
            key.append(-by)
    # 모든 버킷이 같은 경우의 최종 결정: 원좌표
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

    방향 우선순위는 덩어리 크기 기반 허용범위로 각 축을 버킷 처리해, 같은 줄/열의
    덩어리를 동점으로 보고 다음 순위로 세부 결정한다(1·2순위 대칭).
    """
    blobs = find_blobs(mask)
    if not blobs:
        return None
    # 중심 좌표만 뽑아 반환용으로 쓴다.
    if priority == "random":
        b = random.choice(blobs)
        return (b[0], b[1])
    dirs = _fill_priority(list(priority))
    # 허용범위 = 덩어리 크기 중앙값의 절반(최소 1px). 같은 줄/열 판정 기준.
    ws = sorted(b[2] for b in blobs)
    hs = sorted(b[3] for b in blobs)
    med_w = ws[len(ws) // 2]
    med_h = hs[len(hs) // 2]
    tol_x = max(1.0, med_w * 0.5)
    tol_y = max(1.0, med_h * 0.5)
    best = min(blobs, key=lambda b: _bucketed_key(b, dirs, tol_x, tol_y))
    return (best[0], best[1])
