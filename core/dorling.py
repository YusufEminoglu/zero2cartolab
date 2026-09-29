# -*- coding: utf-8 -*-
"""
Dorling (1996) non-contiguous circle cartograms.

Each areal unit becomes a circle whose area is proportional to its value.
Circles start on their unit's interior point and are pushed apart until
none overlap, while a fading pull toward home keeps the layout
geographically recognisable.

Pure Python; neighbour search uses a uniform hash grid, so one iteration is
O(n) for typical inputs rather than O(n^2).
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

Point = Tuple[float, float]


def dorling_radii(values: Sequence[float], target_area: float) -> List[float]:
    """Radii with ``pi * r_i**2`` proportional to ``values[i]``.

    The circles' total area equals ``target_area``. Missing, non-finite and
    non-positive values get radius 0 (the unit is kept but not drawn).
    """
    clean = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            f = 0.0
        clean.append(f if math.isfinite(f) and f > 0 else 0.0)
    total = sum(clean)
    if total <= 0 or target_area <= 0:
        return [0.0] * len(clean)
    k = target_area / total
    return [math.sqrt(v * k / math.pi) for v in clean]


def _cells(positions: Sequence[Point], radii: Sequence[float], cell: float) -> Dict[Tuple[int, int], List[int]]:
    grid: Dict[Tuple[int, int], List[int]] = {}
    for i, (x, y) in enumerate(positions):
        if radii[i] <= 0:
            continue
        grid.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))), []).append(i)
    return grid


def _cell_size(radii: Sequence[float], gap: float) -> float:
    live = sorted(r for r in radii if r > 0)
    median = live[len(live) // 2]
    return max(2.0 * median + gap, 1e-9)


def _owned_pairs(positions, radii, gap, grid, cell):
    """Yield each candidate pair once, from its larger circle.

    Two circles can only touch when their distance is below
    ``r_i + r_j + gap <= 2 * max(r_i, r_j) + gap``, so the larger one finds
    the smaller one within its own reach. Cells are sized by the median
    radius, which keeps skewed (few huge, many tiny) inputs close to O(n).
    """
    for (cx, cy), members in grid.items():
        for i in members:
            ri = radii[i]
            reach = int(math.ceil((2.0 * ri + gap) / cell))
            for gx in range(cx - reach, cx + reach + 1):
                for gy in range(cy - reach, cy + reach + 1):
                    for j in grid.get((gx, gy), ()):
                        rj = radii[j]
                        if j == i or rj > ri or (rj == ri and j < i):
                            continue
                        yield i, j


def max_overlap(positions: Sequence[Point], radii: Sequence[float], gap: float = 0.0) -> float:
    """Largest ``(r_i + r_j + gap) - distance`` over all circle pairs (<= 0 means none)."""
    if sum(1 for r in radii if r > 0) < 2:
        return 0.0
    cell = _cell_size(radii, gap)
    grid = _cells(positions, radii, cell)
    worst = -math.inf
    for i, j in _owned_pairs(positions, radii, gap, grid, cell):
        (xi, yi), (xj, yj) = positions[i], positions[j]
        worst = max(worst, radii[i] + radii[j] + gap - math.hypot(xj - xi, yj - yi))
    return worst if worst != -math.inf else 0.0


def dorling_layout(
    centers: Sequence[Point],
    radii: Sequence[float],
    iterations: int = 150,
    attraction: float = 0.1,
    gap: float = 0.0,
    tolerance: float = 0.005,
    max_separation: int = 2000,
    callback=None,
) -> Tuple[List[Point], int, float]:
    """Separate circles, returning ``(positions, iterations_used, residual)``.

    Phase 1 runs ``iterations`` rounds of repulsion plus a pull back toward
    home; ``attraction`` (0..1) is the fraction of the way home moved per
    round and fades linearly to zero, so the layout settles instead of
    oscillating. Phase 2 repels only, until the worst overlap is below
    ``tolerance`` times the mean radius or ``max_separation`` rounds pass.
    ``gap`` is extra spacing between circles in map units. ``residual`` is
    the final worst overlap as a fraction of the mean radius (<= 0 means
    fully separated). ``callback(round, phase)`` is called every round and
    stops the run early when it returns True (cancellation).
    """
    n = len(centers)
    pos = [(float(x), float(y)) for x, y in centers]
    live = [i for i in range(n) if radii[i] > 0]
    if len(live) < 2:
        return pos, 0, 0.0
    mean_r = sum(radii[i] for i in live) / len(live)
    cell = _cell_size(radii, gap)
    limit = tolerance * mean_r
    iterations = max(1, int(iterations))
    golden = math.pi * (3.0 - math.sqrt(5.0))

    def repel() -> float:
        worst = 0.0
        grid = _cells(pos, radii, cell)
        for i, j in _owned_pairs(pos, radii, gap, grid, cell):
            xi, yi = pos[i]
            xj, yj = pos[j]
            need = radii[i] + radii[j] + gap
            dx, dy = xj - xi, yj - yi
            dist = math.hypot(dx, dy)
            if dist >= need:
                continue
            overlap = need - dist
            worst = max(worst, overlap)
            if dist < 1e-12:
                # coincident centres: split along a deterministic angle
                ang = (i * 7919 + j) * golden
                ux, uy = math.cos(ang), math.sin(ang)
            else:
                ux, uy = dx / dist, dy / dist
            # the smaller circle moves more (share by area)
            ai, aj = radii[i] ** 2, radii[j] ** 2
            si, sj = aj / (ai + aj), ai / (ai + aj)
            pos[i] = (xi - ux * overlap * si, yi - uy * overlap * si)
            pos[j] = (xj + ux * overlap * sj, yj + uy * overlap * sj)
        return worst

    used = 0
    for it in range(iterations):
        used += 1
        if callback is not None and callback(used, 1):
            break
        repel()
        pull = attraction * (1.0 - it / iterations)
        for i in live:
            x, y = pos[i]
            hx, hy = centers[i]
            pos[i] = (x + (hx - x) * pull, y + (hy - y) * pull)
    for _ in range(max(0, int(max_separation))):
        used += 1
        if callback is not None and callback(used, 2):
            break
        if repel() <= limit:
            break

    residual = max_overlap(pos, radii, gap) / mean_r
    return pos, used, residual


def displacement(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])
