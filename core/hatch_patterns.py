# -*- coding: utf-8 -*-
"""
Monochrome (black-and-white) fill patterns for print-safe thematic maps.

Journals, theses and photocopies often reproduce maps in greyscale, where
a colour ramp collapses into indistinguishable greys. Patterns survive it:

  - ``graduated_patterns(n)``  : n fills whose ink coverage strictly
                                 increases, so darker still means "more"
  - ``categorical_patterns(n)``: n fills that differ in texture or
                                 orientation, not just darkness

Each pattern is a plain dict; ``ink_coverage`` gives the fraction of the
area printed black, which is what orders the graduated ramp.
"""
from __future__ import annotations

import math
from typing import Dict, List

Pattern = Dict[str, object]

# Ordered light -> dark. Units are millimetres on paper.
_RAMP: List[Pattern] = [
    {"kind": "none"},
    {"kind": "dots", "spacing": 3.0, "size": 0.5},
    {"kind": "dots", "spacing": 2.0, "size": 0.6},
    {"kind": "lines", "angle": 45.0, "spacing": 2.5, "width": 0.25},
    {"kind": "lines", "angle": 45.0, "spacing": 1.6, "width": 0.3},
    {"kind": "cross", "angle": 45.0, "spacing": 2.0, "width": 0.3},
    {"kind": "cross", "angle": 45.0, "spacing": 1.4, "width": 0.35},
    {"kind": "lines", "angle": 45.0, "spacing": 1.0, "width": 0.55},
    {"kind": "cross", "angle": 45.0, "spacing": 1.0, "width": 0.45},
    {"kind": "solid"},
]

MAX_GRADUATED = len(_RAMP)

# Distinct textures at a similar, mid-grey density.
_TEXTURES: List[Pattern] = [
    {"kind": "lines", "angle": 45.0, "spacing": 2.0, "width": 0.3},
    {"kind": "lines", "angle": 135.0, "spacing": 2.0, "width": 0.3},
    {"kind": "lines", "angle": 0.0, "spacing": 2.0, "width": 0.3},
    {"kind": "lines", "angle": 90.0, "spacing": 2.0, "width": 0.3},
    {"kind": "cross", "angle": 0.0, "spacing": 2.4, "width": 0.25},
    {"kind": "cross", "angle": 45.0, "spacing": 2.4, "width": 0.25},
    {"kind": "dots", "spacing": 1.8, "size": 0.7},
    {"kind": "none"},
]

MAX_CATEGORICAL = len(_TEXTURES) * 2


def ink_coverage(pattern: Pattern) -> float:
    """Fraction (0..1) of the fill area printed black."""
    kind = pattern.get("kind")
    if kind == "none":
        return 0.0
    if kind == "solid":
        return 1.0
    if kind == "dots":
        s, d = float(pattern["spacing"]), float(pattern["size"])
        # staggered rows: one dot per spacing x spacing cell
        return min(1.0, math.pi * (d / 2.0) ** 2 / (s * s))
    w, s = float(pattern["width"]), float(pattern["spacing"])
    single = min(1.0, w / s)
    if kind == "lines":
        return single
    if kind == "cross":
        return 1.0 - (1.0 - single) ** 2
    raise ValueError(f"Unknown pattern kind: {kind}")


def graduated_patterns(n: int) -> List[Pattern]:
    """``n`` patterns of strictly increasing ink coverage, lightest first.

    Picks evenly across the ramp so the first class is always blank and the
    last always the darkest. ``n`` is clamped to ``1..MAX_GRADUATED``.
    """
    n = max(1, min(int(n), MAX_GRADUATED))
    if n == 1:
        return [dict(_RAMP[len(_RAMP) // 2])]
    last = len(_RAMP) - 1
    picks = sorted({round(i * last / (n - 1)) for i in range(n)})
    return [dict(_RAMP[i]) for i in picks]


def categorical_patterns(n: int) -> List[Pattern]:
    """``n`` visually distinct patterns; each texture comes sparse, then dense.

    Beyond ``MAX_CATEGORICAL`` the sequence repeats, which is why a
    monochrome categorical map should stay well below that.
    """
    dense = []
    for p in _TEXTURES:
        q = dict(p)
        if q["kind"] == "none":
            q = {"kind": "solid"}
        else:
            q["spacing"] = float(q["spacing"]) * 0.6
        dense.append(q)
    base = [dict(p) for p in _TEXTURES] + dense
    return [dict(base[i % len(base)]) for i in range(max(0, int(n)))]


def pattern_key(pattern: Pattern) -> tuple:
    """Hashable identity of a pattern (for distinctness checks)."""
    return tuple(sorted(pattern.items()))
