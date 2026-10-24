# -*- coding: utf-8 -*-
"""
Style Transformer — Ridge/Joyplot vector mesh bender and VbA alpha engine.

Produces:
  - Ridge-line (Joy Division style) cross sections from DEM/raster data
  - Value-by-Alpha opacity maps for uncertainty visualisation
"""
from __future__ import annotations

import math
from typing import List, Optional

from qgis.core import (
    QgsFeature, QgsField, QgsGeometry,
    QgsLineString, QgsPoint, QgsVectorLayer,
    QgsRasterLayer, QgsRectangle,
)
from qgis.PyQt.QtCore import QVariant


# ---------------------------------------------------------------------------
# Ridge-line (Joyplot) generator
# ---------------------------------------------------------------------------

def generate_ridge_lines(
    raster: QgsRasterLayer,
    n_lines: int = 50,
    vertical_scale: float = 1.0,
    line_spacing: float = 1.0,
    smooth_iterations: int = 0,
    extent: Optional[QgsRectangle] = None,
) -> QgsVectorLayer:
    """
    Create a ridge-line (joy division style) vector layer from a raster.

    The raster's rows (or columns) become scanlines whose Y coordinate
    is deformed by the pixel value, creating overlapping wave profiles
    reminiscent of vintage Joy Division album art.

    Parameters
    ----------
    raster : QgsRasterLayer
        Single-band raster (DEM, density, temperature, etc.).
    n_lines : int
        Number of horizontal scanlines.
    vertical_scale : float
        Multiplier for vertical deformation.
    line_spacing : float
        Vertical gap between baseline scanlines (in map units).
    smooth_iterations : int
        Laplacian smoothing passes; 0 = raw.
    extent : QgsRectangle | None
        If given, clip to this extent; otherwise use raster extent.

    Returns
    -------
    QgsVectorLayer (memory, LineString)
    """
    if not raster.isValid():
        raise ValueError("Raster layer is not valid.")

    prov = raster.dataProvider()
    # An omitted optional extent arrives as an *empty* (non-None) rectangle, which
    # is still truthy; fall back to the full raster extent unless a real one is given.
    ext = extent if (extent is not None and not extent.isEmpty()) else raster.extent()
    cols = raster.width()
    rows = raster.height()

    block = prov.block(1, ext, cols, rows)
    if block is None or not block.isValid() or block.isEmpty():
        raise ValueError("No data in raster block.")

    # read values into a [row][col] grid. QgsRasterBlock.value takes
    # (row, col); NoData cells contribute no deformation (0).
    grid: List[List[float]] = []
    for row in range(rows):
        grid.append([
            0.0 if block.isNoData(row, col) else block.value(row, col)
            for col in range(cols)
        ])

    # determine scanline Y positions
    y_start = ext.yMinimum()
    y_end = ext.yMaximum()
    x_step = ext.width() / (cols - 1) if cols > 1 else ext.width()

    y_positions = [
        y_start + i * (y_end - y_start) / (n_lines - 1)
        for i in range(n_lines)
    ] if n_lines > 1 else [y_start]

    layer = QgsVectorLayer("LineString?crs=" + raster.crs().authid(), "RidgeLines", "memory")
    layer.startEditing()
    data_provider = layer.dataProvider()
    data_provider.addAttributes([QgsField("line_id", QVariant.Int)])
    layer.updateFields()

    for line_idx, baseline_y in enumerate(y_positions):
        # map baseline_y to the nearest raster row; raster row 0 is the
        # TOP (yMaximum) of the extent, so the bottom scanline reads the last row
        raster_row = int(round(
            (ext.yMaximum() - baseline_y) / ext.height() * (rows - 1)
        )) if ext.height() > 0 else 0
        raster_row = max(0, min(rows - 1, raster_row))

        points = []
        for col in range(cols):
            x = ext.xMinimum() + col * x_step
            pixel_val = grid[raster_row][col]
            # deform Y by pixel value
            y = baseline_y + pixel_val * vertical_scale
            points.append(QgsPoint(x, y))

        # apply optional smoothing
        if smooth_iterations > 0 and len(points) > 4:
            for _ in range(smooth_iterations):
                smoothed = [points[0]]
                for i in range(1, len(points) - 1):
                    sx = (points[i - 1].x() + points[i].x() + points[i + 1].x()) / 3.0
                    sy = (points[i - 1].y() + points[i].y() + points[i + 1].y()) / 3.0
                    smoothed.append(QgsPoint(sx, sy))
                smoothed.append(points[-1])
                points = smoothed

        line = QgsLineString(points)
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry(line))
        feat["line_id"] = line_idx
        data_provider.addFeature(feat)

    layer.commitChanges()
    return layer


# ---------------------------------------------------------------------------
# Value-by-Alpha symbology applier
# ---------------------------------------------------------------------------

def apply_value_by_alpha(
    vector_layer: QgsVectorLayer,
    colour_field: str,
    alpha_field: str,
    alpha_min: int = 30,
    alpha_max: int = 255,
    colour_ramp_name: str = "Viridis",
) -> None:
    """
    Apply Value-by-Alpha symbology to a vector layer.

    Fill colour is graduated on ``colour_field`` (``colour_ramp_name`` ramp);
    fill opacity is data-defined by ``alpha_field`` through a ``scale_linear``
    expression mapped into [alpha_min, alpha_max] / 255, so every feature keeps
    its own reliability-driven transparency. A layer with no valid values on
    either field is left untouched.
    """
    from qgis.core import (
        QgsClassificationCustom, QgsGraduatedSymbolRenderer,
        QgsProperty, QgsRendererRange, QgsSymbol, QgsSymbolLayer,
    )

    values: List[float] = []
    alpha_values: List[float] = []
    for feat in vector_layer.getFeatures():
        try:
            v = float(feat[colour_field])
        except (TypeError, ValueError):
            v = None
        try:
            a = float(feat[alpha_field])
        except (TypeError, ValueError):
            a = None
        if v is not None and math.isfinite(v):
            values.append(v)
        if a is not None and math.isfinite(a):
            alpha_values.append(a)

    if not values or not alpha_values:
        return

    n_classes = min(5, len(set(values)))
    breaks = _jenks_breaks(values, n_classes)
    ramp_colours = _get_ramp_colours(colour_ramp_name, n_classes)

    alpha_lo = min(alpha_values)
    alpha_hi = max(alpha_values)
    if alpha_hi <= alpha_lo:
        alpha_hi = alpha_lo + 1e-9
    quoted_field = '"' + alpha_field.replace('"', '""') + '"'
    opacity_expr = (
        f"scale_linear({quoted_field}, {alpha_lo}, {alpha_hi}, "
        f"{alpha_min / 255.0}, {alpha_max / 255.0})"
    )
    fill_opacity_prop = getattr(
        getattr(QgsSymbolLayer, "Property", QgsSymbolLayer),
        "FillOpacity",
        getattr(QgsSymbolLayer, "PropertyFillOpacity", None),
    )

    ranges = []
    for i in range(len(breaks) - 1):
        low_v, high_v = breaks[i], breaks[i + 1]
        col = ramp_colours[i % len(ramp_colours)]
        sym = QgsSymbol.defaultSymbol(vector_layer.geometryType()).clone()
        sym.setColor(col)
        if fill_opacity_prop is not None:
            for symbol_layer in sym.symbolLayers():
                symbol_layer.setDataDefinedProperty(
                    fill_opacity_prop, QgsProperty.fromExpression(opacity_expr))
        ranges.append(QgsRendererRange(low_v, high_v, sym, f"{low_v:g} – {high_v:g}"))

    renderer = QgsGraduatedSymbolRenderer(colour_field, ranges)
    renderer.setClassificationMethod(QgsClassificationCustom())
    vector_layer.setRenderer(renderer)


def _jenks_breaks(values: List[float], n: int) -> List[float]:
    """Simple Jenks-like breaks via k-means on sorted values."""
    clean = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if len(clean) <= n:
        return [clean[0]] + clean + [clean[-1] + 1e-9]
    step = len(clean) // n
    breaks = [clean[0]]
    for i in range(1, n):
        breaks.append(clean[i * step])
    breaks.append(clean[-1] + 1e-9)
    return breaks


def _get_ramp_colours(name: str, count: int) -> List:
    """Return `count` QColors from a named ramp."""
    from qgis.PyQt.QtGui import QColor
    # hard-coded ramps for reliability (no Style API dependency)
    ramps = {
        "Viridis": [
            QColor("#440154"), QColor("#3b528b"), QColor("#21918c"),
            QColor("#5ec962"), QColor("#fde725"),
        ],
        "Magma": [
            QColor("#000004"), QColor("#51127c"), QColor("#b73779"),
            QColor("#f1605d"), QColor("#fcfdbf"),
        ],
        "Spectral": [
            QColor("#d7191c"), QColor("#fdae61"), QColor("#ffffbf"),
            QColor("#abdda4"), QColor("#2b83ba"),
        ],
        "Plasma": [
            QColor("#0d0887"), QColor("#7e03a8"), QColor("#cc4778"),
            QColor("#f89540"), QColor("#f0f921"),
        ],
    }
    palette = ramps.get(name, ramps["Viridis"])
    # interpolate if count differs from palette length
    if count == len(palette):
        return palette
    result = []
    for i in range(count):
        frac = i / max(count - 1, 1) * (len(palette) - 1)
        lo = int(frac)
        hi = min(lo + 1, len(palette) - 1)
        t = frac - lo
        r = int(palette[lo].red() + t * (palette[hi].red() - palette[lo].red()))
        g = int(palette[lo].green() + t * (palette[hi].green() - palette[lo].green()))
        b = int(palette[lo].blue() + t * (palette[hi].blue() - palette[lo].blue()))
        result.append(QColor(r, g, b))
    return result
