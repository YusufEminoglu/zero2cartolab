# -*- coding: utf-8 -*-
"""
Classification helpers for Quick Style.

Pure logic (no ``qgis`` import): compute class-break edges for graduated
rendering. Returns ``n + 1`` monotonic edges ``[min, ..., max]`` so callers can
pair them into ``n`` ranges.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .utils import safe_float

QUANTILE = "quantile"
EQUAL = "equal"
GEOMETRIC = "geometric"
JENKS = "jenks"
HEAD_TAIL = "head_tail"
STD_DEV = "std_dev"
MAXIMUM = "maximum"
PRETTY = "pretty"
BOX_PLOT = "box_plot"
TUKEY = "tukey"
EQUAL_AREA = "equal_area"


def _clean(values) -> List[float]:
    cleaned = []
    for v in values:
        f = safe_float(v)
        if f is not None and not math.isnan(f) and not math.isinf(f):
            cleaned.append(f)
    return sorted(cleaned)


def quantile_breaks(values, n: int) -> List[float]:
    """``n + 1`` edges placing an equal count of features in each class."""
    xs = _clean(values)
    if not xs or n < 1:
        return []
    if xs[0] == xs[-1]:
        return [xs[0], xs[-1]]
    edges = [xs[0]]
    last = len(xs) - 1
    for i in range(1, n):
        idx = (i / n) * last
        lo = int(math.floor(idx))
        hi = min(lo + 1, last)
        frac = idx - lo
        edges.append(xs[lo] + (xs[hi] - xs[lo]) * frac)
    edges.append(xs[-1])
    return edges


def equal_interval_breaks(values, n: int) -> List[float]:
    """``n + 1`` evenly-spaced edges between the data min and max."""
    xs = _clean(values)
    if not xs or n < 1:
        return []
    lo, hi = xs[0], xs[-1]
    if lo == hi:
        return [lo, hi]
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def jenks_breaks(values, n: int = 5) -> List[float]:
    """Fisher-Jenks natural breaks minimizing within-class variance."""
    from .bivariate_engine import fisher_jenks_breaks
    xs = _clean(values)
    if not xs or n < 1:
        return []
    return fisher_jenks_breaks(xs, n_classes=n)


def head_tail_breaks_method(values) -> List[float]:
    """Jiang's Head/Tail Breaks classification for heavy-tailed data."""
    from .bivariate_engine import head_tail_breaks
    xs = _clean(values)
    if not xs:
        return []
    return head_tail_breaks(xs)


def std_dev_breaks(values, n: int = 5, interval_std: Optional[float] = None) -> List[float]:
    """Standard deviation interval breaks centered at the sample mean."""
    from .bivariate_engine import standard_deviation_breaks
    xs = _clean(values)
    if not xs:
        return []
    return standard_deviation_breaks(xs, n_classes=n, interval_std=interval_std)


def box_plot_breaks(values, n: int = 5, iqr_multiplier: float = 1.5) -> List[float]:
    """Box Plot / Tukey Outlier-resistant breaks (Q1, median, Q3, inner fences)."""
    from .bivariate_engine import box_plot_breaks as bp_breaks
    xs = _clean(values)
    if not xs:
        return []
    return bp_breaks(xs, iqr_multiplier=iqr_multiplier)


def tukey_breaks(values, iqr_multiplier: float = 1.5) -> List[float]:
    """Alias for box_plot_breaks."""
    return box_plot_breaks(values, iqr_multiplier=iqr_multiplier)


def equal_area_breaks(values, weights: Optional[List[float]] = None, n: int = 5) -> List[float]:
    """Equal Area / Weighted Quantile breaks."""
    from .bivariate_engine import equal_area_breaks as ea_breaks
    xs = _clean(values)
    if not xs:
        return []
    return ea_breaks(values, weights=weights, n_classes=n)


def maximum_breaks(values, n: int = 5) -> List[float]:
    """Maximum Breaks classifier: splits at the largest gaps between adjacent sorted values."""
    xs = _clean(values)
    if not xs or n < 1:
        return []
    if len(xs) <= n or xs[0] == xs[-1]:
        return equal_interval_breaks(xs, n)

    gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
    gaps.sort(key=lambda item: item[0], reverse=True)
    split_indices = sorted([idx for _, idx in gaps[:n - 1]])

    breaks = [xs[0]]
    for idx in split_indices:
        breaks.append((xs[idx] + xs[idx + 1]) / 2.0)
    breaks.append(xs[-1])
    return breaks


def pretty_breaks(values, n: int = 5) -> List[float]:
    """Pretty / Nice Round Number breaks using Heckbert nice-number algorithm."""
    xs = _clean(values)
    if not xs or n < 1:
        return []
    vmin, vmax = xs[0], xs[-1]
    if vmin == vmax:
        return [vmin, vmax]

    from .layout_math import nice_interval
    step = nice_interval(vmax - vmin, target_divisions=max(2, n))
    if step <= 0:
        return equal_interval_breaks(xs, n)

    first_break = math.floor(vmin / step) * step
    last_break = math.ceil(vmax / step) * step

    breaks = []
    curr = first_break
    while curr <= last_break + step * 0.5:
        breaks.append(round(curr, 6))
        curr += step

    if len(breaks) < 2:
        return equal_interval_breaks(xs, n)
    return breaks


def compute_breaks(
    values,
    method: str = QUANTILE,
    n: int = 5,
    weights: Optional[List[float]] = None,
) -> List[float]:
    """Unified entry point to compute classification break edges."""
    m = (method or "").lower()
    if m == EQUAL:
        return equal_interval_breaks(values, n)
    elif m == GEOMETRIC:
        from .bivariate_engine import geometric_interval_breaks
        return geometric_interval_breaks(values, n_classes=n)
    elif m in (JENKS, "fisher_jenks"):
        return jenks_breaks(values, n)
    elif m == HEAD_TAIL:
        return head_tail_breaks_method(values)
    elif m == STD_DEV:
        return std_dev_breaks(values, n)
    elif m in (BOX_PLOT, TUKEY):
        return box_plot_breaks(values, n)
    elif m == EQUAL_AREA:
        return equal_area_breaks(values, weights=weights, n=n)
    elif m == MAXIMUM:
        return maximum_breaks(values, n)
    elif m == PRETTY:
        return pretty_breaks(values, n)
    return quantile_breaks(values, n)


def dedupe_edges(edges: List[float]) -> List[float]:
    """Drop consecutive duplicate edges so no zero-width class is produced."""
    out: List[float] = []
    for e in edges:
        if not out or e > out[-1]:
            out.append(e)
    return out


def edges_to_ranges(edges: List[float]) -> List[Tuple[float, float]]:
    """Turn ``n + 1`` edges into ``n`` ``(lower, upper)`` pairs."""
    clean = dedupe_edges(edges)
    return [(clean[i], clean[i + 1]) for i in range(len(clean) - 1)]
