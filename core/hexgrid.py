# -*- coding: utf-8 -*-
"""
Pointy-top hexagonal binning geometry.

Pure-Python axial-coordinate maths (no QGIS imports) so it is unit-testable and
gives the hexbin Processing algorithm a robust point->cell mapping.

  - ``point_to_cell`` : pixel (x, y) -> integer axial cell (q, r) via cube rounding
  - ``cell_center``   : axial cell -> pixel centre
  - ``hex_vertices``  : 6 vertices of the pointy-top hexagon around a centre

The hexagon ``size`` is the centre-to-vertex distance (circumradius).
"""
from __future__ import annotations

import math
from typing import List, Tuple

SQRT3 = math.sqrt(3.0)


def axial_from_point(x: float, y: float, size: float) -> Tuple[float, float]:
    """Fractional axial coordinates (q, r) for a pixel, origin at (0, 0)."""
    q = (SQRT3 / 3.0 * x - 1.0 / 3.0 * y) / size
    r = (2.0 / 3.0 * y) / size
    return q, r


def cube_round(q: float, r: float) -> Tuple[int, int]:
    """Round fractional axial coordinates to the nearest hex cell (cube rounding)."""
    x = q
    z = r
    y = -x - z
    rx = round(x)
    ry = round(y)
    rz = round(z)
    dx = abs(rx - x)
    dy = abs(ry - y)
    dz = abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def point_to_cell(x: float, y: float, size: float) -> Tuple[int, int]:
    """Integer axial cell (q, r) containing the pixel (x, y)."""
    q, r = axial_from_point(x, y, size)
    return cube_round(q, r)


def cell_center(q: int, r: int, size: float) -> Tuple[float, float]:
    """Pixel centre of axial cell (q, r)."""
    x = size * (SQRT3 * (q + r / 2.0))
    y = size * (1.5 * r)
    return x, y


def hex_vertices(cx: float, cy: float, size: float) -> List[Tuple[float, float]]:
    """Six vertices of the pointy-top hexagon centred at (cx, cy)."""
    verts = []
    for i in range(6):
        angle = math.radians(60.0 * i - 30.0)
        verts.append((cx + size * math.cos(angle), cy + size * math.sin(angle)))
    return verts
