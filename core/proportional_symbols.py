# -*- coding: utf-8 -*-
"""
Proportional / graduated symbol sizing.

Pure-Python helpers for perceptually scaled point symbols:

  - ``symbol_size``        : Flannery-compensated (or true area) size mapping
  - ``nice_legend_values`` : round representative values for a nested legend
"""
from __future__ import annotations

import math
from typing import List

# Flannery (1971) apparent-magnitude compensation exponent. Readers systematically
# under-estimate circle area, so scaling radius by value**0.5716 (rather than the
# geometric 0.5) restores perceived proportionality.
FLANNERY_EXP = 0.5716


def symbol_size(
    value,
    v_max: float,
    max_size: float,
    min_size: float = 0.0,
    flannery: bool = True,
) -> float:
    """Map ``value`` to a symbol size in [min_size, max_size].

    ``flannery=True`` applies the perceptual exponent; ``False`` gives true
    area-proportional scaling (exponent 0.5). Non-positive / missing values
    collapse to ``min_size``.
    """
    if v_max is None or v_max <= 0 or max_size <= min_size:
        return min_size
    if value is None:
        return min_size
    try:
        v = float(value)
    except (TypeError, ValueError):
        return min_size
    if not math.isfinite(v) or v <= 0:
        return min_size
    ratio = v / float(v_max)
    if ratio > 1.0:
        ratio = 1.0
    exponent = FLANNERY_EXP if flannery else 0.5
    return min_size + (max_size - min_size) * (ratio ** exponent)


def _nice_floor(x: float) -> float:
    """Round ``x`` down to a 1/2/5 * 10^k 'nice' number."""
    if x <= 0:
        return 0.0
    mag = 10 ** math.floor(math.log10(x))
    norm = x / mag
    if norm >= 5.0:
        nice = 5.0
    elif norm >= 2.0:
        nice = 2.0
    else:
        nice = 1.0
    return nice * mag


def nice_legend_values(v_min: float, v_max: float, n: int = 3) -> List[float]:
    """Return up to ``n`` descending 'nice' values for a nested proportional legend.

    The largest is a nice number at or below ``v_max`` (so no legend circle is
    bigger than any drawn symbol); smaller entries are spaced geometrically so
    the reference circles are visibly different.
    """
    if v_max is None or v_max <= 0 or n < 1:
        return []
    top = _nice_floor(v_max)
    if top <= 0:
        return []
    values = []
    for i in range(n):
        frac = (1.0 / 3.0) ** i  # 1, 1/3, 1/9, ...
        cand = _nice_floor(top * frac)
        if cand > 0:
            values.append(cand)
    # de-duplicate while keeping descending order
    seen = set()
    out = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    out.sort(reverse=True)
    return out
