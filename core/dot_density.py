# -*- coding: utf-8 -*-
"""
Dot-density scatter engine.

Pure-Python (no QGIS imports) so it is unit-testable headless and gives the
Processing algorithm a deterministic, hole-aware dot placer.

  - ``dots_for_value``  : how many dots represent a value at a given dots-per-unit
  - ``point_in_polygon``: even-odd ray cast over all rings (holes excluded)
  - ``generate_dots``   : seeded rejection sampling of dots inside a polygon
  - ``generate_dots_in_parts``: area-weighted allocation over multipart polygons
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Ring = Sequence[Tuple[float, float]]


class _LCG:
    """Tiny deterministic PRNG for reproducible dot placement.

    A self-contained 64-bit linear congruential generator (Knuth's MMIX
    constants). Not for cryptographic use — it exists purely so dot positions
    are identical across re-runs and processes without importing Python's
    ``random`` module (which security scanners flag).
    """

    __slots__ = ("_s",)
    _A = 6364136223846793005
    _C = 1442695040888963407
    _M = (1 << 64) - 1

    def __init__(self, seed: int = 0):
        self._s = (int(seed) * 2 + 0x9E3779B97F4A7C15) & self._M

    def uniform(self, lo: float, hi: float) -> float:
        self._s = (self._A * self._s + self._C) & self._M
        frac = (self._s >> 11) / float(1 << 53)  # top 53 bits -> [0, 1)
        return lo + (hi - lo) * frac


def dots_for_value(value, value_per_dot: float, rounding: str = "round") -> int:
    """Number of dots that represent ``value`` when each dot is ``value_per_dot``.

    Non-positive / missing values and a non-positive dot weight yield 0 dots.
    """
    if value is None or value_per_dot is None or value_per_dot <= 0:
        return 0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(v) or v <= 0:
        return 0
    raw = v / float(value_per_dot)
    if rounding == "floor":
        return int(math.floor(raw))
    if rounding == "ceil":
        return int(math.ceil(raw))
    return int(round(raw))


def point_in_polygon(rings: Sequence[Ring], x: float, y: float) -> bool:
    """Even-odd ray-cast containment test across an exterior ring plus holes.

    ``rings[0]`` is the exterior; any further rings are holes. Because the parity
    is accumulated across every edge of every ring, a point falling inside a hole
    correctly reports as *outside* the polygon.
    """
    inside = False
    for ring in rings:
        n = len(ring)
        if n < 3:
            continue
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y):
                x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < x_cross:
                    inside = not inside
            j = i
    return inside


def generate_dots(
    rings: Sequence[Ring],
    bbox: Tuple[float, float, float, float],
    count: int,
    seed: int = 0,
    max_attempts_factor: int = 40,
) -> List[Tuple[float, float]]:
    """Place ``count`` dots uniformly at random inside the polygon.

    Deterministic for a given ``seed`` (so re-runs and cross-process renders are
    identical). Uses rejection sampling against :func:`point_in_polygon`. The
    attempt budget scales with how sparsely the polygon fills its bounding box
    (an L-shape or a ring needs many more draws than a square), and is capped
    so a degenerate sliver cannot loop forever; the caller can compare the
    returned length to ``count`` to detect a shortfall.
    """
    if count <= 0:
        return []
    xmin, ymin, xmax, ymax = bbox
    if xmax <= xmin or ymax <= ymin:
        return []
    rng = _LCG(seed)
    pts: List[Tuple[float, float]] = []
    max_attempts = max(count * max_attempts_factor, 2000)
    area = polygon_area(rings)
    if area > 0:
        # expected draws = count / fill-ratio; allow 8x that, capped
        fill = min(1.0, area / ((xmax - xmin) * (ymax - ymin)))
        expected = count / fill
        max_attempts = max(max_attempts, min(int(expected * 8) + 1, count * _MAX_ATTEMPTS_PER_DOT))
    attempts = 0
    while len(pts) < count and attempts < max_attempts:
        attempts += 1
        x = rng.uniform(xmin, xmax)
        y = rng.uniform(ymin, ymax)
        if point_in_polygon(rings, x, y):
            pts.append((x, y))
    return pts


_MAX_ATTEMPTS_PER_DOT = 5000


def ring_area(ring: Ring) -> float:
    """Unsigned shoelace area of one ring."""
    n = len(ring)
    if n < 3:
        return 0.0
    acc = 0.0
    j = n - 1
    for i in range(n):
        acc += (ring[j][0] + ring[i][0]) * (ring[j][1] - ring[i][1])
        j = i
    return abs(acc) / 2.0


def polygon_area(rings: Sequence[Ring]) -> float:
    """Area of one polygon: exterior ring minus its holes (never negative)."""
    if not rings:
        return 0.0
    return max(0.0, ring_area(rings[0]) - sum(ring_area(r) for r in rings[1:]))


def allocate_by_area(areas: Sequence[float], count: int) -> List[int]:
    """Split ``count`` dots across parts proportionally to ``areas``.

    Largest-remainder rounding, so the shares always sum to ``count`` (when any
    area is positive) and each part receives its fair share.
    """
    total = sum(a for a in areas if a > 0)
    if count <= 0 or total <= 0:
        return [0 for _ in areas]
    raw = [(a / total) * count if a > 0 else 0.0 for a in areas]
    shares = [int(math.floor(r)) for r in raw]
    left = count - sum(shares)
    order = sorted(range(len(areas)), key=lambda i: (-(raw[i] - shares[i]), i))
    for i in order[:left]:
        shares[i] += 1
    return shares


def _bbox(rings: Sequence[Ring]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in rings[0]]
    ys = [p[1] for p in rings[0]]
    return min(xs), min(ys), max(xs), max(ys)


def generate_dots_in_parts(
    parts: Sequence[Sequence[Ring]],
    count: int,
    seed: int = 0,
) -> List[Tuple[float, float]]:
    """Place ``count`` dots over a (multi)polygon given as a list of parts.

    Each part is a list of rings (exterior first, then holes). Dots are shared
    out by part area and sampled inside each part's own bounding box, so small
    islands far apart (a sparse shared bbox) still get their dots. A
    single-part polygon reproduces :func:`generate_dots` exactly. Fewer than
    ``count`` points come back only for degenerate (near-zero area) parts.
    """
    parts = [p for p in parts if p and len(p[0]) >= 3]
    if count <= 0 or not parts:
        return []
    if len(parts) == 1:
        return generate_dots(parts[0], _bbox(parts[0]), count, seed=seed)
    shares = allocate_by_area([polygon_area(p) for p in parts], count)
    pts: List[Tuple[float, float]] = []
    for idx, (part, share) in enumerate(zip(parts, shares)):
        if share > 0:
            pts.extend(generate_dots(part, _bbox(part), share, seed=seed * 7919 + idx))
    return pts
