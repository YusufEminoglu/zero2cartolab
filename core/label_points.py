# -*- coding: utf-8 -*-
"""
Pole of inaccessibility ("polylabel") — the most distant interior point of a
polygon, i.e. the best place to drop a label.

Pure-Python port of Mapbox's polylabel (ISC licence) with no QGIS imports, so it
is unit-testable headless. Operates on rings of (x, y) tuples; ``rings[0]`` is the
exterior, the rest are holes.
"""
from __future__ import annotations

import heapq
import math
from typing import Sequence, Tuple

Ring = Sequence[Tuple[float, float]]


def _seg_dist_sq(px, py, ax, ay, bx, by) -> float:
    """Squared distance from point (px, py) to segment a-b."""
    dx = bx - ax
    dy = by - ay
    if dx != 0.0 or dy != 0.0:
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        if t > 1.0:
            ax, ay = bx, by
        elif t > 0.0:
            ax, ay = ax + dx * t, ay + dy * t
    dx = px - ax
    dy = py - ay
    return dx * dx + dy * dy


def point_to_polygon_dist(x: float, y: float, rings: Sequence[Ring]) -> float:
    """Signed distance from (x, y) to the polygon boundary (positive inside)."""
    inside = False
    min_dist_sq = math.inf
    for ring in rings:
        n = len(ring)
        if n < 2:
            continue
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            d = _seg_dist_sq(x, y, xi, yi, xj, yj)
            if d < min_dist_sq:
                min_dist_sq = d
            j = i
    dist = math.sqrt(min_dist_sq) if min_dist_sq != math.inf else 0.0
    return dist if inside else -dist


class _Cell:
    __slots__ = ("x", "y", "h", "d", "max")

    def __init__(self, x: float, y: float, h: float, rings: Sequence[Ring]):
        self.x = x
        self.y = y
        self.h = h  # half the cell size
        self.d = point_to_polygon_dist(x, y, rings)
        # the largest distance the cell could possibly contain
        self.max = self.d + h * math.sqrt(2)


def polylabel(rings: Sequence[Ring], precision: float = 1.0) -> Tuple[float, float, float]:
    """Return (x, y, distance) of the polygon's pole of inaccessibility.

    ``distance`` is the radius of the largest inscribed circle at that point —
    a useful proxy for how much label room the polygon offers.
    """
    if not rings or len(rings[0]) < 3:
        if rings and rings[0]:
            return rings[0][0][0], rings[0][0][1], 0.0
        return 0.0, 0.0, 0.0

    exterior = rings[0]
    min_x = min(p[0] for p in exterior)
    max_x = max(p[0] for p in exterior)
    min_y = min(p[1] for p in exterior)
    max_y = max(p[1] for p in exterior)
    width = max_x - min_x
    height = max_y - min_y
    cell_size = min(width, height)
    if cell_size == 0:
        return min_x, min_y, 0.0

    h = cell_size / 2.0
    counter = 0
    heap: list = []

    def _push(cell: _Cell) -> None:
        nonlocal counter
        # max-heap on cell.max via negation; counter keeps tuples orderable
        heapq.heappush(heap, (-cell.max, counter, cell))
        counter += 1

    x = min_x
    while x < max_x:
        y = min_y
        while y < max_y:
            _push(_Cell(x + h, y + h, h, rings))
            y += cell_size
        x += cell_size

    best = _Cell(min_x + width / 2.0, min_y + height / 2.0, 0.0, rings)
    centroid = _centroid_cell(exterior, rings)
    if centroid is not None and centroid.d > best.d:
        best = centroid

    while heap:
        _, _, cell = heapq.heappop(heap)
        if cell.d > best.d:
            best = cell
        if cell.max - best.d <= precision:
            continue
        nh = cell.h / 2.0
        _push(_Cell(cell.x - nh, cell.y - nh, nh, rings))
        _push(_Cell(cell.x + nh, cell.y - nh, nh, rings))
        _push(_Cell(cell.x - nh, cell.y + nh, nh, rings))
        _push(_Cell(cell.x + nh, cell.y + nh, nh, rings))

    return best.x, best.y, best.d


def _centroid_cell(exterior: Ring, rings: Sequence[Ring]):
    """Area-weighted centroid of the exterior ring as a seed cell."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(exterior)
    j = n - 1
    for i in range(n):
        xi, yi = exterior[i]
        xj, yj = exterior[j]
        a = xi * yj - xj * yi
        area += a
        cx += (xi + xj) * a
        cy += (yi + yj) * a
        j = i
    if area == 0.0:
        return None
    cx /= 3.0 * area
    cy /= 3.0 * area
    return _Cell(cx, cy, 0.0, rings)


def polygon_orientation_angle(ring: Ring) -> float:
    """
    Calculate the principal orientation angle (degrees in [-90, 90]) of a polygon ring
    using second central spatial moments for optimal cartographic text alignment.
    """
    if not ring or len(ring) < 3:
        return 0.0

    area2 = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        cross = xj * yi - xi * yj
        area2 += cross
        cx += (xi + xj) * cross
        cy += (yi + yj) * cross
        j = i

    if abs(area2) < 1e-12:
        return 0.0

    cx /= (3.0 * area2)
    cy /= (3.0 * area2)

    mxx = 0.0
    myy = 0.0
    mxy = 0.0
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        cross = xj * yi - xi * yj

        x0 = xi - cx
        y0 = yi - cy
        x1 = xj - cx
        y1 = yj - cy

        mxx += cross * (x0 * x0 + x0 * x1 + x1 * x1)
        myy += cross * (y0 * y0 + y0 * y1 + y1 * y1)
        mxy += cross * (2.0 * x0 * y0 + x0 * y1 + x1 * y0 + 2.0 * x1 * y1)
        j = i

    mxx /= 12.0
    myy /= 12.0
    mxy /= 24.0

    theta = 0.5 * math.atan2(2.0 * mxy, mxx - myy)
    deg = math.degrees(theta)

    while deg > 90.0:
        deg -= 180.0
    while deg < -90.0:
        deg += 180.0
    return round(deg, 2)
