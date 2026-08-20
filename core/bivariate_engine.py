# -*- coding: utf-8 -*-
"""
Bivariate Rendering & Statistical Classification Engine.

Implements:
  - Adaptive Geometric Interval Classifier (GIC)
  - Head/Tail Breaks for heavy-tailed distributions
  - Fisher-Jenks natural breaks optimisation
  - Standard Deviation classification
  - Box Plot / Tukey Outlier-resistant classification
  - Equal Area & refined Quantile classification
  - Bivariate choropleth colour-matrix generation
  - Value-by-Alpha (VbA) alpha mapping
"""
from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter
from contextlib import suppress
from itertools import accumulate
from typing import List, Tuple, Optional, Union

from qgis.PyQt.QtGui import QColor

from .utils import safe_float


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _validate_values(values: List[float]) -> List[float]:
    """Filter None/NaN/inf and return sorted finite float values."""
    clean = []
    for v in values:
        f = safe_float(v)
        if f is not None and not math.isnan(f) and not math.isinf(f):
            clean.append(f)
    if not clean:
        raise ValueError("No valid numeric values provided for classification.")
    return sorted(clean)


# ---------------------------------------------------------------------------
# Adaptive Geometric Interval Classifier
# ---------------------------------------------------------------------------

def geometric_interval_breaks(
    values: List[float],
    n_classes: int = 5,
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
) -> List[float]:
    """
    Compute class breaks using an adaptive Geometric Interval algorithm.

    The method fits a geometric series C_i = a * r^i and optimises (r, a)
    to minimise the sum of squared deviations of class frequencies from the
    mean frequency. This preserves variance at distribution tails while
    keeping mid-range data balanced.

    Returns (n_classes + 1) break values [b0, b1, ..., b_n].
    """
    clean = _validate_values(values)
    n = len(clean)
    if n_classes < 2:
        return [clean[0], clean[-1] + 1e-9]
    if n_classes >= n:
        # more classes than values: fall back to quantile-like unique breaks
        step = max(1, n // n_classes)
        breaks = [clean[0]]
        for i in range(1, n_classes):
            idx = min(i * step, n - 1)
            if clean[idx] > breaks[-1]:
                breaks.append(clean[idx])
            else:
                breaks.append(breaks[-1] + 1e-9)
        breaks.append(clean[-1] + 1e-9)
        return breaks

    vmin, vmax = clean[0], clean[-1]
    if vmin == vmax:
        return [vmin + i * 1e-9 for i in range(n_classes + 1)]

    # handle non-positive values with a shift
    shift = 0.0
    if vmin <= 0:
        shift = abs(vmin) + 1.0
        shifted = [v + shift for v in clean]
        vmin_s, vmax_s = shifted[0], shifted[-1]
    else:
        shifted = clean
        vmin_s, vmax_s = vmin, vmax

    vmax_s += 1e-9
    mean_freq = n / n_classes

    best_r, best_a, best_score = 1.5, vmin_s, float("inf")
    candidate = [vmin_s + i * (vmax_s - vmin_s) / n_classes for i in range(n_classes + 1)]

    # coarse → fine search for optimal ratio
    for r in _frange(1.01, 5.0, 0.05):
        a = vmin_s  # anchor at minimum
        cand = [a * (r ** k) for k in range(n_classes + 1)]
        if cand[-1] < vmax_s:
            ratio_adj = math.pow(vmax_s / cand[-1], 1.0 / n_classes)
            cand = [a * ((r * ratio_adj) ** k) for k in range(n_classes + 1)]

        # count per class
        counts = [0] * n_classes
        idx = 0
        for v in shifted:
            while idx < n_classes and v > cand[idx + 1]:
                idx += 1
            if idx >= n_classes:
                idx = n_classes - 1
            counts[idx] += 1
        score = sum((c - mean_freq) ** 2 for c in counts)
        if score < best_score:
            best_score, best_r, best_a = score, r, a
            candidate = cand
            if score < tolerance * n:
                break

    # refine around best_r
    for r in _frange(max(1.005, best_r - 0.1), best_r + 0.11, 0.005):
        a = vmin_s
        cand = [a * (r ** k) for k in range(n_classes + 1)]
        if cand[-1] < vmax_s:
            ratio_adj = math.pow(vmax_s / cand[-1], 1.0 / n_classes)
            cand = [a * ((r * ratio_adj) ** k) for k in range(n_classes + 1)]
        counts = [0] * n_classes
        idx = 0
        for v in shifted:
            while idx < n_classes and v > cand[idx + 1]:
                idx += 1
            if idx >= n_classes:
                idx = n_classes - 1
            counts[idx] += 1
        score = sum((c - mean_freq) ** 2 for c in counts)
        if score < best_score:
            best_score, candidate = score, cand

    # shift breaks back
    breaks = [b - shift for b in candidate]
    breaks[0] = vmin
    breaks[-1] = vmax + 1e-9
    return breaks


def _frange(start: float, stop: float, step: float):
    while start <= stop:
        yield start
        start += step


# ---------------------------------------------------------------------------
# Head / Tail Breaks
# ---------------------------------------------------------------------------

def head_tail_breaks(values: List[float]) -> List[float]:
    """
    Head/Tail Breaks classification for heavy-tailed (power-law) data.

    Recursively partitions values at the arithmetic mean until the 'head'
    subset is no longer heavy-tailed relative to the whole set.

    Returns sorted list of class break values.
    """
    clean = _validate_values(values)
    breaks = []

    def _recurse(data: List[float]) -> None:
        if len(data) < 4:
            return
        mean_val = sum(data) / len(data)
        head = [v for v in data if v > mean_val]
        if len(head) < 2 or len(head) >= len(data) * 0.8:
            # stop recursion when head dominates or is trivial
            breaks.append(mean_val)
            return
        breaks.append(mean_val)
        _recurse(head)

    _recurse(clean)
    breaks.sort()
    if not breaks or breaks[0] > clean[0]:
        breaks.insert(0, clean[0])
    if breaks[-1] < clean[-1]:
        breaks.append(clean[-1] + 1e-9)
    return breaks


# ---------------------------------------------------------------------------
# Fisher-Jenks Natural Breaks (optimised for modest n)
# ---------------------------------------------------------------------------

def fisher_jenks_breaks(values: List[float], n_classes: int = 5) -> List[float]:
    """
    Fisher-Jenks natural breaks minimising within-class variance.

    Uses a dynamic-programming approach. For very large datasets (>5000)
    a stratified sample is used automatically.
    """
    clean = _validate_values(values)
    n = len(clean)

    if n_classes >= n:
        return [clean[0]] + clean[1:n_classes] + [clean[-1] + 1e-9]

    # sample if too large
    if n > 5000:
        step = n // 5000
        clean = clean[::step]
        n = len(clean)

    # cumulative sums for fast variance computation
    cum_sum = list(accumulate(clean, initial=0.0))
    cum_sq = list(accumulate((v * v for v in clean), initial=0.0))

    def _ssq(i: int, j: int) -> float:
        """Sum of squared deviations from mean for clean[i:j]."""
        s = cum_sum[j] - cum_sum[i]
        sq = cum_sq[j] - cum_sq[i]
        cnt = j - i
        return sq - (s * s) / cnt if cnt > 0 else 0.0

    # DP matrix: best SSQ for first j items into k classes
    INF = float("inf")
    dp = [[INF] * (n + 1) for _ in range(n_classes + 1)]
    dp[1] = [_ssq(0, j) for j in range(n + 1)]
    split = [[0] * (n + 1) for _ in range(n_classes + 1)]

    for k in range(2, n_classes + 1):
        for j in range(k, n + 1):
            best, best_i = INF, -1
            for i in range(k - 1, j):
                cost = dp[k - 1][i] + _ssq(i, j)
                if cost < best:
                    best, best_i = cost, i
            dp[k][j] = best
            split[k][j] = best_i

    # backtrack
    breaks = [clean[-1] + 1e-9]
    pos = n
    for k in range(n_classes, 1, -1):
        pos = split[k][pos]
        breaks.append(clean[pos])
    breaks.append(clean[0])
    breaks.sort()
    return breaks


# ---------------------------------------------------------------------------
# Standard Deviation Classification
# ---------------------------------------------------------------------------

def standard_deviation_breaks(
    values: List[float],
    n_classes: int = 5,
    interval_std: Optional[float] = None,
) -> List[float]:
    """
    Standard Deviation classification creating symmetric breaks around the mean.

    Breaks are placed at mean +/- k*std (e.g. +/- 0.5*std, 1.0*std, 1.5*std, 2.0*std).
    Returns (n_classes + 1) monotonic break values [min, ..., max + 1e-9].
    """
    clean = _validate_values(values)
    n = len(clean)
    vmin, vmax = clean[0], clean[-1]
    mean_val = sum(clean) / n
    variance = sum((x - mean_val) ** 2 for x in clean) / n
    std_val = math.sqrt(variance)

    if vmin == vmax or std_val < 1e-9:
        return [vmin, vmax + 1e-9]

    step = interval_std if interval_std is not None and interval_std > 0 else 0.5

    # Determine multipliers based on n_classes or standard steps
    if n_classes <= 2:
        k_steps = [0.0]
    elif n_classes == 3:
        k_steps = [-1.0 * step, 1.0 * step]
    elif n_classes == 4:
        k_steps = [-2.0 * step, 0.0, 2.0 * step]
    elif n_classes == 5:
        k_steps = [-1.5 * step * 2, -0.5 * step * 2, 0.5 * step * 2, 1.5 * step * 2]
    elif n_classes == 6:
        k_steps = [-2.5 * step * 2, -1.5 * step * 2, -0.5 * step * 2, 0.5 * step * 2, 1.5 * step * 2]
    else:
        # Generic symmetrical class generation
        half = (n_classes - 1) / 2.0
        k_steps = [(i - half) * step * 2 for i in range(n_classes - 1)]

    raw_breaks = [mean_val + k * std_val for k in k_steps]
    # Filter breaks strictly between vmin and vmax
    valid_interior = [b for b in raw_breaks if vmin < b < vmax]
    
    breaks = [vmin] + sorted(list(set(valid_interior))) + [vmax + 1e-9]
    return breaks


# ---------------------------------------------------------------------------
# Box Plot / Tukey Outlier-Resistant Classification
# ---------------------------------------------------------------------------

def box_plot_breaks(
    values: List[float],
    iqr_multiplier: float = 1.5,
) -> List[float]:
    """
    Box Plot / Tukey Outlier-resistant Classification.

    Uses quartiles (Q1, Median, Q3) and inner fences (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
    to isolate lower/upper outliers into dedicated tail classes while dividing
    the central distribution at the median and hinges.

    Returns monotonic break values spanning [min, ..., max + 1e-9].
    """
    clean = _validate_values(values)
    n = len(clean)
    vmin, vmax = clean[0], clean[-1]
    if vmin == vmax or n < 4:
        return [vmin, vmax + 1e-9]

    def _percentile(p: float) -> float:
        idx = p * (n - 1)
        lo = int(math.floor(idx))
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return clean[lo] + (clean[hi] - clean[lo]) * frac

    q1 = _percentile(0.25)
    med = _percentile(0.50)
    q3 = _percentile(0.75)
    iqr = q3 - q1

    f_low = q1 - iqr_multiplier * iqr
    f_high = q3 + iqr_multiplier * iqr

    candidates = [vmin]
    if f_low > vmin:
        candidates.append(f_low)
    if q1 > candidates[-1]:
        candidates.append(q1)
    if med > candidates[-1]:
        candidates.append(med)
    if q3 > candidates[-1]:
        candidates.append(q3)
    if f_high > candidates[-1] and f_high < vmax:
        candidates.append(f_high)
    candidates.append(vmax + 1e-9)

    # Deduplicate and sort
    out = []
    for c in candidates:
        if not out or c > out[-1]:
            out.append(c)
    return out


def tukey_breaks(values: List[float], iqr_multiplier: float = 1.5) -> List[float]:
    """Alias for box_plot_breaks."""
    return box_plot_breaks(values, iqr_multiplier=iqr_multiplier)


# ---------------------------------------------------------------------------
# Equal Area & Quantile Refinement
# ---------------------------------------------------------------------------

def equal_area_breaks(
    values: List[float],
    weights: Optional[List[float]] = None,
    n_classes: int = 5,
) -> List[float]:
    """
    Equal Area / Weighted Quantile classification.

    When polygon areas/weights are provided, creates class boundaries such that
    the cumulative sum of weights in each class is balanced equally.
    Falls back to unweighted quantile interpolation when weights are omitted.
    """
    if weights is None or len(weights) != len(values):
        # Unweighted quantile
        clean = _validate_values(values)
        n = len(clean)
        if n_classes < 1 or not clean:
            return []
        if clean[0] == clean[-1]:
            return [clean[0], clean[-1] + 1e-9]
        edges = [clean[0]]
        last = n - 1
        for i in range(1, n_classes):
            idx = (i / n_classes) * last
            lo = int(math.floor(idx))
            hi = min(lo + 1, last)
            frac = idx - lo
            edges.append(clean[lo] + (clean[hi] - clean[lo]) * frac)
        edges.append(clean[-1] + 1e-9)
        return edges

    # Weighted equal area
    pairs = []
    for v, w in zip(values, weights):
        fv = safe_float(v)
        fw = safe_float(w)
        if fv is not None and fw is not None and fw > 0:
            pairs.append((fv, fw))

    if not pairs:
        return equal_area_breaks(values, weights=None, n_classes=n_classes)

    pairs.sort(key=lambda p: p[0])
    total_weight = sum(p[1] for p in pairs)
    if total_weight <= 0:
        return equal_area_breaks([p[0] for p in pairs], weights=None, n_classes=n_classes)

    target_per_class = total_weight / n_classes
    breaks = [pairs[0][0]]
    cum_w = 0.0
    target_next = target_per_class

    for v, w in pairs:
        cum_w += w
        if cum_w >= target_next and len(breaks) < n_classes:
            if v > breaks[-1]:
                breaks.append(v)
            else:
                breaks.append(breaks[-1] + 1e-9)
            target_next += target_per_class

    breaks.append(pairs[-1][0] + 1e-9)
    # Ensure monotonic
    for i in range(1, len(breaks)):
        if breaks[i] <= breaks[i - 1]:
            breaks[i] = breaks[i - 1] + 1e-9
    return breaks


# ---------------------------------------------------------------------------
# Curated Bivariate Palettes & Colour Matrix
# ---------------------------------------------------------------------------

BIVARIATE_PALETTE_PRESETS = {
    "teal_brown": {
        "label": "Teal - Brown (Environment & Resilience)",
        "ll": "#e8e8e8", "lh": "#5ab4ac", "hl": "#d8b365", "hh": "#8c510a",
    },
    "stevens_pink_cyan": {
        "label": "Stevens Pink - Cyan (Demographics & Social)",
        "ll": "#e8e8e8", "lh": "#00bbf9", "hl": "#f72585", "hh": "#4a0e4e",
    },
    "blue_orange": {
        "label": "Blue - Orange (Density & Economy)",
        "ll": "#f0f3f8", "lh": "#2b5c8f", "hl": "#e27c38", "hh": "#3d2645",
    },
    "purple_green": {
        "label": "Purple - Green (Land Use & Canopy)",
        "ll": "#f3f3f3", "lh": "#38b000", "hl": "#7b2cbf", "hh": "#1b4332",
    },
    "pink_green": {
        "label": "Pink - Green (Vulnerability & Health)",
        "ll": "#e8e8e8", "lh": "#2a9d8f", "hl": "#e76f51", "hh": "#264653",
    },
    "night_neon": {
        "label": "Night Neon (Dark Theme Visuals)",
        "ll": "#222831", "lh": "#00fff5", "hl": "#ff007f", "hh": "#7900ff",
    },
}


def bivariate_colour_matrix_hex(
    size: int = 3,
    color_ll: str = "#e8e8e8",
    color_lh: str = "#5ab4ac",
    color_hl: str = "#d8b365",
    color_hh: str = "#8c510a",
    preset: Optional[str] = None,
    n_classes: Optional[int] = None,
) -> List[List[str]]:
    """
    Generate a size×size bivariate colour matrix returned as hexadecimal string codes.
    Supports preset name and/or corner colors, and accepts either size or n_classes.
    """
    if isinstance(size, str):
        preset = size
        size = n_classes or 3
    elif n_classes is not None:
        size = n_classes

    if preset and preset in BIVARIATE_PALETTE_PRESETS:
        p = BIVARIATE_PALETTE_PRESETS[preset]
        color_ll, color_lh, color_hl, color_hh = p["ll"], p["lh"], p["hl"], p["hh"]

    mat = bivariate_colour_matrix(size, color_ll, color_lh, color_hl, color_hh)
    return [[c.name() for c in row] for row in mat]


def bivariate_colour_matrix(
    size: int = 4,
    color_ll: str | QColor = "#e8e8e8",
    color_lh: str | QColor = "#5ab4ac",
    color_hl: str | QColor = "#d8b365",
    color_hh: str | QColor = "#8c510a",
) -> List[List[QColor]]:
    """
    Generate a size×size bivariate colour legend matrix.

    Uses a perceptually grounded 2D interpolation between four corner
    colours: low-low, low-high, high-low, high-high.

    Returns a nested list [row][col] of QColor.
    """
    c_ll = QColor(color_ll) if isinstance(color_ll, str) else color_ll
    c_lh = QColor(color_lh) if isinstance(color_lh, str) else color_lh
    c_hl = QColor(color_hl) if isinstance(color_hl, str) else color_hl
    c_hh = QColor(color_hh) if isinstance(color_hh, str) else color_hh

    matrix = []
    for row in range(size):
        row_cols = []
        y_frac = row / max(size - 1, 1)
        for col in range(size):
            x_frac = col / max(size - 1, 1)
            # bilinear interpolation
            r = int(
                (1 - y_frac) * (1 - x_frac) * c_ll.red()
                + (1 - y_frac) * x_frac * c_lh.red()
                + y_frac * (1 - x_frac) * c_hl.red()
                + y_frac * x_frac * c_hh.red()
            )
            g = int(
                (1 - y_frac) * (1 - x_frac) * c_ll.green()
                + (1 - y_frac) * x_frac * c_lh.green()
                + y_frac * (1 - x_frac) * c_hl.green()
                + y_frac * x_frac * c_hh.green()
            )
            b = int(
                (1 - y_frac) * (1 - x_frac) * c_ll.blue()
                + (1 - y_frac) * x_frac * c_lh.blue()
                + y_frac * (1 - x_frac) * c_hl.blue()
                + y_frac * x_frac * c_hh.blue()
            )
            row_cols.append(QColor(
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
            ))
        matrix.append(row_cols)
    return matrix


# ---------------------------------------------------------------------------
# Value-by-Alpha mapper
# ---------------------------------------------------------------------------

def compute_alpha_values(
    primary_values: List[float],
    reliability_values: List[float],
    alpha_min: int = 30,
    alpha_max: int = 255,
) -> List[int]:
    """
    Map a reliability/uncertainty variable to alpha (opacity) channel.

    Higher reliability → more opaque. Uses Jenks on the reliability
    field to produce balanced alpha bins; linear fallback if values
    are too few.
    """
    if len(reliability_values) != len(primary_values):
        raise ValueError("Primary and reliability arrays must have same length.")
    clean_r = _validate_values(reliability_values)
    n = len(reliability_values)

    if len(clean_r) < 4:
        # fallback: linear stretch
        rmin, rmax = clean_r[0], clean_r[-1]
        if rmax == rmin:
            return [alpha_max] * n
        return [
            int(alpha_min + (v - rmin) / (rmax - rmin) * (alpha_max - alpha_min))
            for v in reliability_values
        ]

    try:
        breaks = fisher_jenks_breaks(clean_r, 5)
    except Exception:
        breaks = [
            clean_r[0] + i * (clean_r[-1] - clean_r[0]) / 5
            for i in range(6)
        ]

    alpha_steps = [
        alpha_min + i * (alpha_max - alpha_min) // max(1, len(breaks) - 2)
        for i in range(len(breaks) - 1)
    ]

    result = []
    for v in reliability_values:
        fv = safe_float(v)
        if fv is None:
            result.append(alpha_min)
            continue
        idx = bisect_left(breaks, fv) - 1
        idx = max(0, min(idx, len(alpha_steps) - 1))
        result.append(alpha_steps[idx])
    return result
