# -*- coding: utf-8 -*-
"""
Choropleth data-preparation transforms.

Pure-Python (no QGIS imports) so it is unit-testable headless. Every transform
returns a list aligned to the input, with ``None`` where an input value is
missing / non-finite (so the caller can leave those features unclassified).

Mapping a *count* straight onto a choropleth is the classic cartographic error
(it just re-draws population); these transforms turn raw fields into rates and
comparable standardised values.
"""
from __future__ import annotations

import math
from typing import List, Optional

METHODS = [
    ("Rate (numerator / denominator)", "rate"),
    ("Z-score (standardise)", "zscore"),
    ("Robust z-score (median / MAD)", "robust_z"),
    ("Robust IQR (median / IQR)", "robust_iqr"),
    ("Min-max to 0-1", "minmax"),
    ("Percentile rank (0-100)", "percentile"),
    ("Log (base 10)", "log"),
    ("Location Quotient (Specialisation Index)", "lq"),
    ("Winsorized Min-Max (5th-95th percentile clamp)", "winsorized"),
    ("Decile rank (1-10)", "decile"),
    ("Tukey Hinge Rank (1-6 Box Plot class)", "tukey_hinge"),
    ("Sigmoid logistic scaling (0-1)", "sigmoid"),
    ("Power transform (Box-Cox / Yeo-Johnson)", "power"),
    ("Quantile uniform normalization (0-1)", "quantile_norm"),
]


from .utils import safe_float


def _finite(v) -> bool:
    f = safe_float(v)
    return f is not None and not math.isnan(f) and not math.isinf(f)


def _clean(values) -> List[float]:
    cleaned = []
    for v in values:
        f = safe_float(v)
        if f is not None and not math.isnan(f) and not math.isinf(f):
            cleaned.append(f)
    return cleaned


def mean(values) -> float:
    c = _clean(values)
    return sum(c) / len(c) if c else 0.0


def pstdev(values) -> float:
    c = _clean(values)
    if not c:
        return 0.0
    m = sum(c) / len(c)
    return math.sqrt(sum((v - m) ** 2 for v in c) / len(c))


def median(values) -> float:
    c = sorted(_clean(values))
    n = len(c)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return c[mid]
    return (c[mid - 1] + c[mid]) / 2.0


def z_scores(values) -> List[Optional[float]]:
    m = mean(values)
    sd = pstdev(values)
    if sd == 0:
        return [0.0 if _finite(v) else None for v in values]
    return [(safe_float(v) - m) / sd if _finite(v) else None for v in values]


def robust_z(values) -> List[Optional[float]]:
    """Median-centred, MAD-scaled z (1.4826 makes MAD ~ stdev for normal data)."""
    med = median(values)
    abs_dev = [abs(safe_float(v) - med) for v in values if _finite(v)]
    mad = median(abs_dev) if abs_dev else 0.0
    if mad == 0:
        return [0.0 if _finite(v) else None for v in values]
    scale = 1.4826 * mad
    return [(safe_float(v) - med) / scale if _finite(v) else None for v in values]


def min_max(values, lo: float = 0.0, hi: float = 1.0) -> List[Optional[float]]:
    c = _clean(values)
    if not c:
        return [None for _ in values]
    vmin, vmax = min(c), max(c)
    if vmax == vmin:
        return [lo if _finite(v) else None for v in values]
    span = vmax - vmin
    return [
        (lo + (safe_float(v) - vmin) / span * (hi - lo)) if _finite(v) else None
        for v in values
    ]


def percentile_rank(values) -> List[Optional[float]]:
    """0-100 rank: pct of values below each, plus half the ties (mid-rank)."""
    c = _clean(values)
    n = len(c)
    if n == 0:
        return [None for _ in values]
    ordered = sorted(c)
    out: List[Optional[float]] = []
    for v in values:
        fv = safe_float(v)
        if fv is None or math.isnan(fv) or math.isinf(fv):
            out.append(None)
            continue
        below = sum(1 for x in ordered if x < fv)
        equal = sum(1 for x in ordered if x == fv)
        out.append(100.0 * (below + 0.5 * equal) / n)
    return out


def log_scale(values, base: float = 10.0) -> List[Optional[float]]:
    """Log transform; if any value <= 0 the whole series is shifted to be > 0."""
    c = _clean(values)
    if not c:
        return [None for _ in values]
    vmin = min(c)
    shift = 0.0
    if vmin <= 0:
        shift = -vmin + 1.0
    log_base = math.log(base)
    return [
        (math.log(safe_float(v) + shift) / log_base) if _finite(v) else None
        for v in values
    ]


def rate(numerators, denominators, scale: float = 1.0) -> List[Optional[float]]:
    """Element-wise numerator/denominator * scale; None when either is bad or d==0."""
    out: List[Optional[float]] = []
    for num, den in zip(numerators, denominators):
        fn = safe_float(num)
        fd = safe_float(den)
        if fn is None or fd is None or fd == 0.0:
            out.append(None)
        else:
            out.append(fn / fd * scale)
    return out


def location_quotient(numerators, denominators) -> List[Optional[float]]:
    """
    Calculate Location Quotient (LQ) / Specialisation Index:
    LQ_i = (num_i / den_i) / (total_num / total_den)
    """
    cleaned_pairs = []
    for num, den in zip(numerators, denominators):
        fn = safe_float(num)
        fd = safe_float(den)
        if fn is not None and fd is not None and fd > 0:
            cleaned_pairs.append((fn, fd))

    if not cleaned_pairs:
        return [None for _ in numerators]

    total_num = sum(p[0] for p in cleaned_pairs)
    total_den = sum(p[1] for p in cleaned_pairs)

    if total_num <= 0 or total_den <= 0:
        return [None for _ in numerators]

    base_rate = total_num / total_den
    out: List[Optional[float]] = []
    for num, den in zip(numerators, denominators):
        fn = safe_float(num)
        fd = safe_float(den)
        if fn is None or fd is None or fd == 0.0:
            out.append(None)
        else:
            local_rate = fn / fd
            out.append(round(local_rate / base_rate, 4))
    return out


def winsorized_min_max(values, lower_pct: float = 5.0, upper_pct: float = 95.0, lo: float = 0.0, hi: float = 1.0) -> List[Optional[float]]:
    """
    Winsorize outliers at lower and upper percentiles, then apply min-max scaling.
    """
    c = sorted(_clean(values))
    if not c:
        return [None for _ in values]
    n = len(c)
    idx_lo = int(math.floor(lower_pct / 100.0 * (n - 1)))
    idx_hi = int(math.ceil(upper_pct / 100.0 * (n - 1)))
    v_lo = c[max(0, min(idx_lo, n - 1))]
    v_hi = c[max(0, min(idx_hi, n - 1))]

    if v_hi == v_lo:
        return [lo if _finite(v) else None for v in values]

    span = v_hi - v_lo
    out: List[Optional[float]] = []
    for v in values:
        fv = safe_float(v)
        if fv is None or math.isnan(fv) or math.isinf(fv):
            out.append(None)
        else:
            clamped = max(v_lo, min(fv, v_hi))
            scaled = lo + (clamped - v_lo) / span * (hi - lo)
            out.append(round(scaled, 4))
    return out


def decile_rank(values) -> List[Optional[int]]:
    """
    Convert numerical distribution into decile ranks (integers 1 to 10).
    """
    ranks = percentile_rank(values)
    out: List[Optional[int]] = []
    for r in ranks:
        if r is None:
            out.append(None)
        else:
            dec = int(math.ceil(r / 10.0))
            out.append(max(1, min(10, dec)))
    return out


def sigmoid_scale(values, k: float = 1.0) -> List[Optional[float]]:
    """
    Map values to standard logistic sigmoid in [0.0, 1.0]: 1 / (1 + exp(-k * z_score)).
    Smoothly squashes unbounded distributions while preserving central distinctions.
    """
    zs = z_scores(values)
    out: List[Optional[float]] = []
    for z in zs:
        if z is None:
            out.append(None)
        else:
            # Clamp z to avoid overflow
            clamped_z = max(-20.0, min(20.0, z * k))
            sig = 1.0 / (1.0 + math.exp(-clamped_z))
            out.append(round(sig, 4))
    return out


def power_transform(values, lmbda: float = 0.5) -> List[Optional[float]]:
    """
    Box-Cox / Yeo-Johnson style power transform for variance stabilization.
    For positive shifted data: (x^lambda - 1) / lambda (or log(x) if lambda == 0).
    """
    c = _clean(values)
    if not c:
        return [None for _ in values]
    vmin = min(c)
    shift = 0.0
    if vmin <= 0:
        shift = -vmin + 1.0

    out: List[Optional[float]] = []
    for v in values:
        fv = safe_float(v)
        if fv is None or math.isnan(fv) or math.isinf(fv):
            out.append(None)
        else:
            x = fv + shift
            if abs(lmbda) < 1e-6:
                val = math.log(x)
            else:
                val = (math.pow(x, lmbda) - 1.0) / lmbda
            out.append(round(val, 4))
    return out


def quantile_normalize(values, n_quantiles: int = 100) -> List[Optional[float]]:
    """
    Map empirical distribution uniformly to [0.0, 1.0] using percentile ranking.
    """
    pr = percentile_rank(values)
    return [round(r / 100.0, 4) if r is not None else None for r in pr]


def robust_iqr(values) -> List[Optional[float]]:
    """
    Median-centred, Interquartile Range (IQR) scaled robust standardization:
    (x - median) / IQR.
    """
    c = sorted(_clean(values))
    if not c:
        return [None for _ in values]
    n = len(c)

    def _percentile(p: float) -> float:
        idx = p * (n - 1)
        lo = int(math.floor(idx))
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return c[lo] + (c[hi] - c[lo]) * frac

    med = median(c)
    q1 = _percentile(0.25)
    q3 = _percentile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return [0.0 if _finite(v) else None for v in values]

    return [
        round((safe_float(v) - med) / iqr, 4) if _finite(v) else None
        for v in values
    ]


def tukey_hinge_rank(values, iqr_multiplier: float = 1.5) -> List[Optional[int]]:
    """
    Classify distribution into Box Plot / Tukey categories (integers 1 to 6):
    1: Lower Outlier (< Q1 - 1.5*IQR)
    2: Lower Whisker (Q1 - 1.5*IQR to Q1)
    3: Lower Central Box (Q1 to Median)
    4: Upper Central Box (Median to Q3)
    5: Upper Whisker (Q3 to Q3 + 1.5*IQR)
    6: Upper Outlier (> Q3 + 1.5*IQR)
    """
    c = sorted(_clean(values))
    if not c:
        return [None for _ in values]
    n = len(c)

    def _percentile(p: float) -> float:
        idx = p * (n - 1)
        lo = int(math.floor(idx))
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return c[lo] + (c[hi] - c[lo]) * frac

    med = median(c)
    q1 = _percentile(0.25)
    q3 = _percentile(0.75)
    iqr = q3 - q1

    f_low = q1 - iqr_multiplier * iqr
    f_high = q3 + iqr_multiplier * iqr

    out: List[Optional[int]] = []
    for v in values:
        fv = safe_float(v)
        if fv is None or math.isnan(fv) or math.isinf(fv):
            out.append(None)
        elif fv < f_low:
            out.append(1)
        elif fv < q1:
            out.append(2)
        elif fv <= med:
            out.append(3)
        elif fv <= q3:
            out.append(4)
        elif fv <= f_high:
            out.append(5)
        else:
            out.append(6)
    return out
