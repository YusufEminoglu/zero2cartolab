# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Color Accessibility, CVD Simulation & Contrast Engine.

Provides mathematically accurate Color Vision Deficiency (CVD) simulation
(Protanopia, Deuteranopia, Tritanopia, Achromatopsia) using the Brettel/Machado
spectrophotometric matrix model, plus WCAG 2.1 relative luminance and contrast ratio calculations,
and CIE L*a*b* Delta E perceptual difference metrics.
"""
from __future__ import annotations

import math
from contextlib import suppress
from typing import Dict, List, Tuple, Union


# ---------------------------------------------------------------------------
# WCAG 2.1 Relative Luminance & Contrast
# ---------------------------------------------------------------------------

def srgb_to_linear(c_srgb: float) -> float:
    """Convert an sRGB component in [0, 1] to linear RGB."""
    c = max(0.0, min(1.0, float(c_srgb)))
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c_lin: float) -> float:
    """Convert a linear RGB component in [0, 1] to sRGB."""
    c = max(0.0, min(1.0, float(c_lin)))
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Parse '#RRGGBB' or 'RRGGBB' into (r, g, b) integers in [0, 255]."""
    h = str(hex_str).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        return (0, 0, 0)
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return (r, g, b)
    except ValueError:
        return (0, 0, 0)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Format RGB integers to '#RRGGBB'."""
    r_c = max(0, min(255, int(round(r))))
    g_c = max(0, min(255, int(round(g))))
    b_c = max(0, min(255, int(round(b))))
    return f"#{r_c:02x}{g_c:02x}{b_c:02x}"


def relative_luminance(hex_or_rgb: Union[str, Tuple[int, int, int], List[int]]) -> float:
    """
    Calculate WCAG 2.1 relative luminance for a given color in [0.0, 1.0].
    """
    if isinstance(hex_or_rgb, str):
        r, g, b = hex_to_rgb(hex_or_rgb)
    else:
        r, g, b = hex_or_rgb[0], hex_or_rgb[1], hex_or_rgb[2]

    r_lin = srgb_to_linear(r / 255.0)
    g_lin = srgb_to_linear(g / 255.0)
    b_lin = srgb_to_linear(b / 255.0)

    # Standard ITU-R BT.709 coefficients
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(
    color_a: Union[str, Tuple[int, int, int], List[int]],
    color_b: Union[str, Tuple[int, int, int], List[int]],
) -> float:
    """
    Calculate the WCAG 2.1 contrast ratio between two colors in [1.0, 21.0].
    """
    l1 = relative_luminance(color_a)
    l2 = relative_luminance(color_b)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def rate_wcag_contrast(ratio: float) -> str:
    """Return WCAG compliance tier string."""
    if ratio >= 7.0:
        return "AAA (Enhanced Contrast)"
    elif ratio >= 4.5:
        return "AA (Standard Contrast)"
    elif ratio >= 3.0:
        return "AA Large (Moderate)"
    return "Fail (Low Contrast)"


def evaluate_wcag_contrast(
    foreground: Union[str, Tuple[int, int, int], List[int]],
    background: Union[str, Tuple[int, int, int], List[int]],
    font_size_pt: float = 10.0,
    is_bold: bool = False,
) -> Dict[str, any]:
    """
    Detailed WCAG 2.1 compliance evaluation between foreground and background colors.

    Considers text size (large text >= 18pt or >= 14pt bold requires 3.0:1 for AA and 4.5:1 for AAA).
    """
    ratio = contrast_ratio(foreground, background)
    is_large_text = (font_size_pt >= 18.0) or (is_bold and font_size_pt >= 14.0)

    aa_threshold = 3.0 if is_large_text else 4.5
    aaa_threshold = 4.5 if is_large_text else 7.0

    passes_aa = ratio >= aa_threshold
    passes_aaa = ratio >= aaa_threshold

    return {
        "contrast_ratio": round(ratio, 2),
        "passes_aa": passes_aa,
        "passes_aaa": passes_aaa,
        "is_large_text": is_large_text,
        "aa_threshold": aa_threshold,
        "aaa_threshold": aaa_threshold,
        "aa_normal_text": ratio >= 4.5,
        "aa_large_text": ratio >= 3.0,
        "aa_ui_component": ratio >= 3.0,
        "aaa_normal_text": ratio >= 7.0,
        "aaa_large_text": ratio >= 4.5,
        "rating": rate_wcag_contrast(ratio),
        "fg_luminance": round(relative_luminance(foreground), 4),
        "bg_luminance": round(relative_luminance(background), 4),
    }


def suggest_accessible_color(
    foreground: str,
    background: str,
    target_ratio: float = 4.5,
) -> str:
    """
    Adjust the foreground color (lighten or darken) until it meets target_ratio against background.
    """
    bg_lum = relative_luminance(background)
    fg_r, fg_g, fg_b = hex_to_rgb(foreground)

    if contrast_ratio(foreground, background) >= target_ratio:
        return foreground

    # If background is bright, darken foreground; if background is dark, brighten foreground
    should_darken = bg_lum > 0.5

    best_hex = foreground
    for step in range(1, 101):
        factor = 1.0 - (step / 100.0) if should_darken else 1.0 + (step / 100.0)
        nr = max(0, min(255, int(fg_r * factor) if should_darken else int(fg_r + (255 - fg_r) * (step / 100.0))))
        ng = max(0, min(255, int(fg_g * factor) if should_darken else int(fg_g + (255 - fg_g) * (step / 100.0))))
        nb = max(0, min(255, int(fg_b * factor) if should_darken else int(fg_b + (255 - fg_b) * (step / 100.0))))
        cand_hex = rgb_to_hex(nr, ng, nb)
        if contrast_ratio(cand_hex, background) >= target_ratio:
            return cand_hex
        best_hex = cand_hex

    # Extreme fallback
    return "#000000" if should_darken else "#ffffff"


# ---------------------------------------------------------------------------
# Color Vision Deficiency (CVD) Simulation Matrices (Machado / Brettel)
# ---------------------------------------------------------------------------

CVD_MATRICES: Dict[str, List[List[float]]] = {
    "protanopia": [
        [0.56667, 0.43333, 0.0],
        [0.55833, 0.44167, 0.0],
        [0.0,     0.24167, 0.75833],
    ],
    "deuteranopia": [
        [0.625, 0.375, 0.0],
        [0.70,  0.30,  0.0],
        [0.0,   0.30,  0.70],
    ],
    "tritanopia": [
        [0.95, 0.05,  0.0],
        [0.0,  0.433, 0.567],
        [0.0,  0.475, 0.525],
    ],
    "achromatopsia": [
        [0.299, 0.587, 0.114],
        [0.299, 0.587, 0.114],
        [0.299, 0.587, 0.114],
    ],
}


def simulate_cvd_rgb(
    r: int,
    g: int,
    b: int,
    cvd_type: str = "deuteranopia",
    severity: float = 1.0,
) -> Tuple[int, int, int]:
    """
    Simulate a specific color vision deficiency on an (r, g, b) tuple.

    ``severity`` in [0.0, 1.0] controls the intensity (1.0 = full dichromacy).
    """
    cvd_key = cvd_type.lower()
    if cvd_key.endswith("anomaly") and severity == 1.0:
        severity = 0.6
        cvd_key = cvd_key.replace("anomaly", "anopia")

    base_mat = CVD_MATRICES.get(cvd_key, CVD_MATRICES["deuteranopia"])
    sev = max(0.0, min(1.0, float(severity)))

    # Interpolate between identity matrix and CVD matrix by severity
    mat = [
        [
            (1.0 - sev) * (1.0 if row == col else 0.0) + sev * base_mat[row][col]
            for col in range(3)
        ]
        for row in range(3)
    ]

    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0

    sim_r = mat[0][0] * rf + mat[0][1] * gf + mat[0][2] * bf
    sim_g = mat[1][0] * rf + mat[1][1] * gf + mat[1][2] * bf
    sim_b = mat[2][0] * rf + mat[2][1] * gf + mat[2][2] * bf

    out_r = int(round(max(0.0, min(1.0, sim_r)) * 255.0))
    out_g = int(round(max(0.0, min(1.0, sim_g)) * 255.0))
    out_b = int(round(max(0.0, min(1.0, sim_b)) * 255.0))
    return (out_r, out_g, out_b)


def simulate_cvd_hex(
    hex_str: str,
    cvd_type: str = "deuteranopia",
    severity: float = 1.0,
) -> str:
    """Simulate CVD on a hex color string, returning simulated '#RRGGBB'."""
    r, g, b = hex_to_rgb(hex_str)
    sr, sg, sb = simulate_cvd_rgb(r, g, b, cvd_type, severity=severity)
    return rgb_to_hex(sr, sg, sb)


def evaluate_palette_accessibility(palette_hexes: List[str]) -> Dict[str, any]:
    """
    Evaluate a sequence of palette colors for readability, minimum step contrast,
    and distinctness under CVD simulations.
    """
    if not palette_hexes:
        return {"distinct": True, "min_step_contrast": 1.0, "endpoint_contrast": 1.0, "rating": "Empty", "cvd_distinct": {}}

    n = len(palette_hexes)
    step_contrasts = []
    for i in range(n - 1):
        c1 = palette_hexes[i]
        c2 = palette_hexes[i + 1]
        step_contrasts.append(contrast_ratio(c1, c2))

    min_step = min(step_contrasts) if step_contrasts else 1.0
    bg_contrast = contrast_ratio(palette_hexes[0], palette_hexes[-1])

    # Check distinctness under CVD
    cvd_distinct = {}
    for cvd_name in ("deuteranopia", "protanopia", "tritanopia", "achromatopsia"):
        sim_colors = [simulate_cvd_hex(h, cvd_name) for h in palette_hexes]
        min_cvd_contrast = 21.0
        for i in range(len(sim_colors) - 1):
            cr = contrast_ratio(sim_colors[i], sim_colors[i + 1])
            if cr < min_cvd_contrast:
                min_cvd_contrast = cr
        cvd_distinct[cvd_name] = round(min_cvd_contrast, 2)

    return {
        "min_step_contrast": round(min_step, 2),
        "endpoint_contrast": round(bg_contrast, 2),
        "rating": rate_wcag_contrast(bg_contrast),
        "cvd_distinct": cvd_distinct,
    }


# ---------------------------------------------------------------------------
# CIE L*a*b* & Delta E Color Difference
# ---------------------------------------------------------------------------

def rgb_to_xyz(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert sRGB [0, 255] to CIE 1931 XYZ (D65 standard illuminant)."""
    rl = srgb_to_linear(r / 255.0)
    gl = srgb_to_linear(g / 255.0)
    bl = srgb_to_linear(b / 255.0)

    # D65 sRGB conversion matrix
    x = (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) * 100.0
    y = (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) * 100.0
    z = (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) * 100.0
    return (x, y, z)


def xyz_to_lab(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Convert CIE XYZ to CIE L*a*b* (D65 white point)."""
    # D65 reference white
    xn, yn, zn = 95.047, 100.000, 108.883

    def f(t: float) -> float:
        delta = 6.0 / 29.0
        if t > delta ** 3:
            return t ** (1.0 / 3.0)
        return t / (3.0 * delta ** 2) + 4.0 / 29.0

    fx = f(x / xn)
    fy = f(y / yn)
    fz = f(z / zn)

    l_star = 116.0 * fy - 16.0
    a_star = 500.0 * (fx - fy)
    b_star = 200.0 * (fy - fz)
    return (l_star, a_star, b_star)


def rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Convert sRGB [0, 255] integers directly to CIE L*a*b*."""
    x, y, z = rgb_to_xyz(r, g, b)
    return xyz_to_lab(x, y, z)


def delta_e_cie76(
    color_a: Union[str, Tuple[int, int, int]],
    color_b: Union[str, Tuple[int, int, int]],
) -> float:
    """
    Calculate CIE76 perceptual color difference Delta E*ab.

    Delta E < 1.0: imperceptible to human eye.
    Delta E 1.0 - 2.0: perceptible through close observation.
    Delta E 2.0 - 10.0: perceptible at a glance.
    Delta E > 10.0: colors are clearly distinct.
    """
    if isinstance(color_a, str):
        ra, ga, ba = hex_to_rgb(color_a)
    else:
        ra, ga, ba = color_a[0], color_a[1], color_a[2]

    if isinstance(color_b, str):
        rb, gb, bb = hex_to_rgb(color_b)
    else:
        rb, gb, bb = color_b[0], color_b[1], color_b[2]

    l1, a1, b1 = rgb_to_lab(ra, ga, ba)
    l2, a2, b2 = rgb_to_lab(rb, gb, bb)

    return math.sqrt((l2 - l1) ** 2 + (a2 - a1) ** 2 + (b2 - b1) ** 2)
