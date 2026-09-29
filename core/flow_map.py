# -*- coding: utf-8 -*-
"""
Origin-destination flow maps.

Pure-Python geometry and scaling for desire-line maps:

  - ``aggregate_flows`` : sum OD records into one volume per zone pair
  - ``select_flows``    : threshold / top-N filtering, largest first
  - ``flow_arc``        : curved (quadratic Bezier) or straight flow line
  - ``flow_width``      : line width linear in volume (Tobler 1987)

Curves bend to the right of the direction of travel, so the two directions
between a pair of zones become two separate arcs instead of one overdrawn
line, and both keep a readable arrowhead.
"""
from __future__ import annotations

import math
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Pair = Tuple[Hashable, Hashable]


def aggregate_flows(
    records: Iterable[Tuple[Hashable, Hashable, object]],
    directed: bool = True,
    drop_self: bool = True,
) -> Dict[Pair, float]:
    """Sum ``(origin, destination, volume)`` records per zone pair.

    Non-numeric, non-finite and non-positive volumes are skipped. With
    ``directed=False`` both directions are merged under one pair whose key is
    ordered by ``str`` of the zone ids, so ``(a, b)`` and ``(b, a)`` meet.
    """
    totals: Dict[Pair, float] = {}
    for origin, dest, raw in records:
        if origin is None or dest is None:
            continue
        if drop_self and origin == dest:
            continue
        try:
            volume = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(volume) or volume <= 0:
            continue
        key = (origin, dest)
        if not directed and str(dest) < str(origin):
            key = (dest, origin)
        totals[key] = totals.get(key, 0.0) + volume
    return totals


def select_flows(
    flows: Dict[Pair, float],
    min_volume: float = 0.0,
    top_n: int = 0,
) -> List[Tuple[Pair, float]]:
    """Return ``(pair, volume)`` sorted largest first after filtering.

    ``min_volume`` drops flows below the threshold; ``top_n > 0`` then keeps
    only the largest ``top_n``. Ties keep a deterministic order.
    """
    kept = [(pair, v) for pair, v in flows.items() if v >= min_volume]
    kept.sort(key=lambda item: (-item[1], str(item[0][0]), str(item[0][1])))
    if top_n and top_n > 0:
        kept = kept[:top_n]
    return kept


def flow_width(volume: float, v_max: float, max_width: float, min_width: float = 0.0) -> float:
    """Line width in [min_width, max_width], linear in volume.

    Width is a length, so linear scaling keeps perceived magnitude honest
    (unlike area symbols, which need a square-root or Flannery exponent).
    """
    if v_max is None or v_max <= 0 or max_width <= min_width:
        return min_width
    try:
        v = float(volume)
    except (TypeError, ValueError):
        return min_width
    if not math.isfinite(v) or v <= 0:
        return min_width
    return min_width + (max_width - min_width) * min(1.0, v / float(v_max))


def _bezier(p0: Point, c: Point, p1: Point, t: float) -> Point:
    u = 1.0 - t
    return (
        u * u * p0[0] + 2.0 * u * t * c[0] + t * t * p1[0],
        u * u * p0[1] + 2.0 * u * t * c[1] + t * t * p1[1],
    )


def arc_control_point(p0: Point, p1: Point, curvature: float) -> Point:
    """Control point offset to the right of travel by ``curvature * length``."""
    mx, my = (p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    # (dy, -dx) is the right-hand normal of the travel vector (dx, dy)
    return (mx + dy * curvature, my - dx * curvature)


def flow_arc(
    p0: Point,
    p1: Point,
    curvature: float = 0.2,
    segments: int = 32,
    trim_start: float = 0.0,
    trim_end: float = 0.0,
) -> List[Point]:
    """Vertices of a flow line from ``p0`` to ``p1``.

    ``curvature`` is the control-point offset as a fraction of the chord
    length (0 draws a straight line). ``trim_start`` / ``trim_end`` cut that
    fraction of the chord length off each end, measured along the curve, so
    an arrowhead does not sit on top of the zone point. Returns an empty list
    for coincident points or when the trims consume the whole line.
    """
    chord = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if chord <= 0 or not math.isfinite(chord):
        return []
    segments = max(2, int(segments))
    trim_start = max(0.0, float(trim_start))
    trim_end = max(0.0, float(trim_end))

    if abs(curvature) < 1e-12:
        t0 = trim_start
        t1 = 1.0 - trim_end
        if t1 <= t0:
            return []
        return [
            (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
            for t in (t0, t1)
        ]

    c = arc_control_point(p0, p1, curvature)
    # sample finely, then cut by arc length so the trims are true distances
    fine = max(64, segments * 4)
    pts = [_bezier(p0, c, p1, i / fine) for i in range(fine + 1)]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    start = trim_start * chord
    end = total - trim_end * chord
    if end - start <= total * 1e-6:
        return []

    def at(dist: float) -> Point:
        lo, hi = 0, len(cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if cum[mid] <= dist:
                lo = mid
            else:
                hi = mid
        span = cum[hi] - cum[lo]
        f = 0.0 if span <= 0 else (dist - cum[lo]) / span
        a, b = pts[lo], pts[hi]
        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)

    return [at(start + (end - start) * i / segments) for i in range(segments + 1)]


def polyline_length(points: Sequence[Point]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def zone_lookup(values: Iterable[Tuple[object, Point]]) -> Tuple[Dict[str, Point], List[str]]:
    """Map zone id -> point, keyed by the id's text so an integer id in the
    zone layer matches the same id stored as text in an OD table.

    Returns the map and the ids that appeared more than once (first wins).
    """
    lookup: Dict[str, Point] = {}
    duplicates: List[str] = []
    for zid, pt in values:
        key = normalise_zone_id(zid)
        if key is None:
            continue
        if key in lookup:
            duplicates.append(key)
            continue
        lookup[key] = pt
    return lookup, duplicates


def normalise_zone_id(value) -> Optional[str]:
    """Text key for a zone id: ``7``, ``7.0`` and ``"7"`` all become ``"7"``."""
    if value is None:
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return None
    return text
