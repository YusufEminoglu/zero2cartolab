# -*- coding: utf-8 -*-
"""
Colour palette library for CartoLab.

Pure logic (no ``qgis`` import) so it is unit-testable headless. Bundles the
palettes people actually search for — ColorBrewer (sequential / diverging /
qualitative) and the perceptually-uniform scientific ramps (Batlow, Viridis, Magma,
Plasma, Inferno, Cividis, Twilight, Sunset) — with a colour-blind-safe flag on each, and samples
any of them to an arbitrary class count.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

SEQUENTIAL = "sequential"
DIVERGING = "diverging"
QUALITATIVE = "qualitative"
KINDS = (SEQUENTIAL, DIVERGING, QUALITATIVE)


# name -> {"kind", "cb_safe", "colors": [hex, ...]}
# Sequential/diverging store an ordered gradient (sampled to N by interpolation);
# qualitative store discrete swatches (taken in order, cycled if N is larger).
PALETTES: Dict[str, dict] = {
    # ---- scientific, perceptually uniform, colour-blind safe ramps --------
    "Batlow": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#011959", "#114160", "#216863", "#3d8c5a", "#72ad48",
        "#b3ca34", "#f4e31d", "#f8b437", "#e7764a", "#bc3843", "#801438"]},
    "Viridis": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#440154", "#472d7b", "#3b528b", "#2c728e", "#21918c",
        "#28ae80", "#5ec962", "#addc30", "#fde725"]},
    "Magma": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f",
        "#cd4071", "#f1605d", "#fd9567", "#fcfdbf"]},
    "Plasma": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#0d0887", "#47039f", "#7301a8", "#9c179e", "#bd3786",
        "#d8576b", "#ed7953", "#fb9f3a", "#f0f921"]},
    "Inferno": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60",
        "#cf4446", "#ed6925", "#fb9b06", "#fcffa4"]},
    "Cividis": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#00204d", "#00336f", "#39486b", "#575d6d", "#707173",
        "#8a8779", "#a69d75", "#c4b56c", "#fee838"]},
    "Sunset": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#0c1048", "#2b2a6d", "#583f88", "#875097", "#b85c96",
        "#e16e86", "#f78d6e", "#fdb659", "#fbe382"]},
    "Twilight": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#e2d9e2", "#9ebcd3", "#5c79be", "#3b3662", "#47183e",
        "#7b1c3c", "#b64547", "#df8d76", "#e2d9e2"]},
    "Turbo": {"kind": SEQUENTIAL, "cb_safe": False, "colors": [
        "#30123b", "#4662d8", "#36aaf9", "#1ae4b6", "#72fe5e",
        "#c8ef34", "#faba39", "#f66b19", "#cb2a04", "#7a0403"]},
    "Mako": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#0b0405", "#241935", "#35365c", "#3b587c", "#3b7d86",
        "#42a284", "#69c47e", "#a8dc83", "#def5ac"]},
    "Rocket": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#03051a", "#291535", "#5c1846", "#90174c", "#c12844",
        "#e35338", "#f48648", "#fbb96b", "#faefa6"]},
    "Bamako": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#1b4028", "#335e38", "#537e4c", "#78a063", "#a1c27e",
        "#cfe49e", "#e8edb9", "#c6c39f", "#8e866a", "#4a4130"]},
    "Nuuk": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#0d2138", "#174360", "#286884", "#438ea4", "#6bb5be",
        "#9ed8d4", "#cff0e5", "#ecf9f0"]},
    "Earth": {"kind": SEQUENTIAL, "cb_safe": False, "colors": [
        "#1a4329", "#2d6a4f", "#74c69d", "#d8f3dc", "#e9d8a6",
        "#ee9b00", "#ca6702", "#9b2226", "#ffffff"]},
    "Bathymetry": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#03045e", "#023e8a", "#0077b6", "#0096c7", "#00b4d8",
        "#48cae4", "#90e0ef", "#ade8f4", "#caf0f8"]},
    # ---- ColorBrewer sequential (all colour-blind safe) -------------------
    "Blues": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#6baed6",
        "#4292c6", "#2171b5", "#08519c", "#08306b"]},
    "Greens": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476",
        "#41ab5d", "#238b45", "#006d2c", "#00441b"]},
    "Oranges": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b", "#fd8d3c",
        "#f16913", "#d94801", "#a63603", "#7f2704"]},
    "Reds": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#fff5f0", "#fee0d2", "#fcbba1", "#fc9272", "#fb6a4a",
        "#ef3b2c", "#cb181d", "#a50f15", "#67000d"]},
    "Purples": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#fcfbfd", "#efedf5", "#dadaeb", "#bcbddc", "#9e9ac8",
        "#807dba", "#6a51a3", "#54278f", "#3f007d"]},
    "Greys": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#ffffff", "#f0f0f0", "#d9d9d9", "#bdbdbd", "#969696",
        "#737373", "#525252", "#252525", "#000000"]},
    "YlOrRd": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c",
        "#fc4e2a", "#e31a1c", "#bd0026", "#800026"]},
    "YlGnBu": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#ffffd9", "#edf8b1", "#c7e9b4", "#7fcdbb", "#41b6c4",
        "#1d91c0", "#225ea8", "#253494", "#081d58"]},
    "BuGn": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#f7fcfd", "#e5f5f9", "#ccece6", "#99d8c9", "#66c2a4",
        "#41ae76", "#238b45", "#006d2c", "#00441b"]},
    "BuPu": {"kind": SEQUENTIAL, "cb_safe": True, "colors": [
        "#f7fcfd", "#e0ecf4", "#bfd3e6", "#9ebcda", "#8c96c6",
        "#8c6bb1", "#88419d", "#810f7c", "#4d004b"]},
    # ---- ColorBrewer diverging -------------------------------------------
    "RdBu": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#67001f", "#b2182b", "#d6604d", "#f4a582", "#fddbc7", "#f7f7f7",
        "#d1e5f0", "#92c5de", "#4393c3", "#2166ac", "#053061"]},
    "RdYlBu": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#a50026", "#d73027", "#f46d43", "#fdae61", "#fee090", "#ffffbf",
        "#e0f3f8", "#abd9e9", "#74add1", "#4575b4", "#313695"]},
    "BrBG": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#543005", "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f5f5f5",
        "#c7eae5", "#80cdc1", "#35978f", "#01665e", "#003c30"]},
    "PiYG": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#8e0152", "#c51b7d", "#de77ae", "#f1b6da", "#fde0ef", "#f7f7f7",
        "#e6f5d0", "#b8e186", "#7fbc41", "#4d9221", "#276419"]},
    "Spectral": {"kind": DIVERGING, "cb_safe": False, "colors": [
        "#9e0142", "#d53e4f", "#f46d43", "#fdae61", "#fee08b", "#ffffbf",
        "#e6f598", "#abdda4", "#66c2a5", "#3288bd", "#5e4fa2"]},
    "Roma": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#7e1700", "#ac4e03", "#d68b1a", "#e9c968", "#eef2b2",
        "#99cee3", "#579dc5", "#286ca0", "#023858"]},
    "TealRose": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#009392", "#39b185", "#9ccb86", "#e9e29c", "#eeb479",
        "#e88471", "#cf597e"]},
    "RdYlGn": {"kind": DIVERGING, "cb_safe": False, "colors": [
        "#a50026", "#d73027", "#f46d43", "#fdae61", "#fee08b", "#ffffbf",
        "#d9ef8b", "#a6d96a", "#66bd63", "#1a9850", "#006837"]},
    "IceFire": {"kind": DIVERGING, "cb_safe": True, "colors": [
        "#00204d", "#004785", "#0078b4", "#00abcc", "#45ded6", "#000000",
        "#e6550d", "#fd8d3c", "#fdae6b", "#fdd0a2", "#fff5eb"]},
    # ---- ColorBrewer qualitative -----------------------------------------
    "Set1": {"kind": QUALITATIVE, "cb_safe": False, "colors": [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
        "#ffff33", "#a65628", "#f781bf", "#999999"]},
    "Set2": {"kind": QUALITATIVE, "cb_safe": True, "colors": [
        "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854",
        "#ffd92f", "#e5c494", "#b3b3b3"]},
    "Set3": {"kind": QUALITATIVE, "cb_safe": False, "colors": [
        "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
        "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f"]},
    "Dark2": {"kind": QUALITATIVE, "cb_safe": True, "colors": [
        "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e",
        "#e6ab02", "#a6761d", "#666666"]},
    "Paired": {"kind": QUALITATIVE, "cb_safe": False, "colors": [
        "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c",
        "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a", "#ffff99", "#b15928"]},
    "Accent": {"kind": QUALITATIVE, "cb_safe": False, "colors": [
        "#7fc97f", "#beaed4", "#fdc086", "#ffff99", "#386cb0",
        "#f0027f", "#bf5b17", "#666666"]},
}

_DEFAULTS = {SEQUENTIAL: "Viridis", DIVERGING: "RdBu", QUALITATIVE: "Set2"}


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        return (0, 0, 0)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return (0, 0, 0)


def _rgb_to_hex(rgb: Tuple[int, int, int] | List[int]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(h: str) -> Tuple[int, int, int]:
    """Public helper to convert hex '#RRGGBB' to integer (r, g, b) in [0, 255]."""
    return _hex_to_rgb(h)


def rgb_to_hex(rgb: Tuple[int, int, int] | List[int]) -> str:
    """Public helper to convert integer (r, g, b) to '#RRGGBB' hex."""
    return _rgb_to_hex(rgb)


def blend_colors(c1: str, c2: str, t: float = 0.5) -> str:
    """Linearly blend two hex colours by parameter t in [0.0, 1.0]."""
    t_clamped = max(0.0, min(1.0, float(t)))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = r1 + (r2 - r1) * t_clamped
    g = g1 + (g2 - g1) * t_clamped
    b = b1 + (b2 - b1) * t_clamped
    return _rgb_to_hex((r, g, b))


def _sample_gradient(colors: List[str], n: int) -> List[str]:
    """Linearly sample ``n`` colours across an ordered gradient (RGB lerp)."""
    if n <= 0:
        return []
    stops = [_hex_to_rgb(c) for c in colors]
    if n == 1:
        return [colors[len(colors) // 2]]
    out = []
    last = len(stops) - 1
    for i in range(n):
        t = i / (n - 1)
        pos = t * last
        lo = int(math.floor(pos))
        hi = min(lo + 1, last)
        frac = pos - lo
        a, b = stops[lo], stops[hi]
        out.append(_rgb_to_hex(tuple(a[k] + (b[k] - a[k]) * frac for k in range(3))))
    return out


def interpolate_palette(colors: List[str], n: int) -> List[str]:
    """Public helper to interpolate an arbitrary sequence of hex colours to ``n`` steps."""
    return _sample_gradient(colors, n)


def reverse_palette(colors: List[str]) -> List[str]:
    """Return a reversed copy of the color list."""
    return list(reversed(colors))


def get_palette(name: str, n: int) -> List[str]:
    """
    Return ``n`` hex colours for palette ``name``.

    Sequential/diverging palettes are interpolated to exactly ``n`` colours;
    qualitative palettes return the first ``n`` swatches, cycling if ``n``
    exceeds the palette size. Unknown names raise ``ValueError``.
    """
    if name not in PALETTES:
        raise ValueError(f"Unknown palette: {name}")
    if n <= 0:
        return []
    spec = PALETTES[name]
    colors = spec["colors"]
    if spec["kind"] == QUALITATIVE:
        reps = (n + len(colors) - 1) // len(colors)
        return (colors * reps)[:n]
    return _sample_gradient(colors, n)


def list_palettes(kind: Optional[str] = None, cb_safe_only: bool = False) -> List[str]:
    """Palette names, optionally filtered by kind and colour-blind safety."""
    names = []
    for name, spec in PALETTES.items():
        if kind is not None and spec["kind"] != kind:
            continue
        if cb_safe_only and not spec["cb_safe"]:
            continue
        names.append(name)
    return names


def is_colorblind_safe(name: str) -> bool:
    return bool(PALETTES.get(name, {}).get("cb_safe", False))


def palette_kind(name: str) -> str:
    return PALETTES[name]["kind"]


def default_palette(kind: str = SEQUENTIAL) -> str:
    return _DEFAULTS.get(kind, "Viridis")


def ordered_names() -> List[str]:
    """All palette names grouped sequential -> diverging -> qualitative.

    A single source of truth for any UI/enum that must keep a stable order.
    """
    return (list_palettes(kind=SEQUENTIAL)
            + list_palettes(kind=DIVERGING)
            + list_palettes(kind=QUALITATIVE))
