# -*- coding: utf-8 -*-
"""
Graticule / reference-grid coordinate generation.

Pure-Python (no QGIS imports) so it is unit-testable headless. Produces meridian
(vertical) and parallel (horizontal) lines clipped to an extent, on 'nice' round
coordinate intervals, each carrying a formatted label.
"""
from __future__ import annotations

import math
from typing import Dict, List


def nice_interval(span: float, target: int = 8) -> float:
    """A 1/2/5 * 10^k 'nice' step that divides ``span`` into ~``target`` cells."""
    if span <= 0:
        return 1.0
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    norm = raw / mag
    if norm < 1.5:
        nice = 1.0
    elif norm < 3.0:
        nice = 2.0
    elif norm < 7.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * mag


def aligned_values(lo: float, hi: float, step: float) -> List[float]:
    """Multiples of ``step`` lying within [lo, hi], aligned to the global origin."""
    if step <= 0 or hi < lo:
        return []
    start_k = math.ceil(lo / step)
    values = []
    k = 0
    while True:
        v = (start_k + k) * step
        if v > hi + step * 1e-9:
            break
        values.append(round(v, 10))
        k += 1
        if k > 100000:  # safety valve against pathological inputs
            break
    return values


def format_coord(value: float) -> str:
    """Compact label: integers without a decimal point, else trimmed decimals."""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def graticule_lines(
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
    x_step: float,
    y_step: float,
) -> List[Dict]:
    """Return graticule line descriptors covering the extent.

    Each item is a dict with ``orientation`` ('meridian' or 'parallel'),
    ``coord`` (the constant coordinate), ``points`` (two endpoints) and
    ``label`` (formatted coordinate).
    """
    lines: List[Dict] = []
    for xv in aligned_values(xmin, xmax, x_step):
        lines.append({
            "orientation": "meridian",
            "coord": xv,
            "points": [(xv, ymin), (xv, ymax)],
            "label": format_coord(xv),
        })
    for yv in aligned_values(ymin, ymax, y_step):
        lines.append({
            "orientation": "parallel",
            "coord": yv,
            "points": [(xmin, yv), (xmax, yv)],
            "label": format_coord(yv),
        })
    return lines
