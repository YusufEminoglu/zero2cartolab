# -*- coding: utf-8 -*-
"""
Style Transformer — Ridge/Joyplot vector mesh bender and VbA alpha engine.

Produces:
  - Ridge-line (Joy Division style) cross sections from DEM/raster data
  - Value-by-Alpha opacity maps for uncertainty visualisation
"""
from __future__ import annotations

import math
from typing import List, Tuple, Optional

from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsGeometry,
    QgsLineString, QgsPoint, QgsPolygon, QgsVectorLayer,
    QgsRasterLayer, QgsRasterBlock, QgsRectangle,
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

    # read values into 2D grid
    grid: List[List[float]] = []
    for row in range(rows):
        grid.append([block.value(col, row) for col in range(cols)])

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
        # map baseline_y to nearest raster row
        raster_row = int(
            (baseline_y - ext.yMinimum()) / ext.height() * (rows - 1)
        )
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
    Apply Value-by-Alpha graduated symbology to a vector layer.

    The fill colour is determined by `colour_field` (using the given ramp)
    and the opacity is driven by `alpha_field` (mapped to alpha channel).

    Parameters
    ----------
    vector_layer : QgsVectorLayer
        The layer to symbolise (modified in-place).
    colour_field : str
        Field name for determining hue/saturation.
    alpha_field : str
        Field name for determining opacity (lower = more transparent).
    alpha_min, alpha_max : int
        Alpha channel range [0-255] for the reliability field.
    colour_ramp_name : str
        Name of a QGIS colour ramp (e.g. "Viridis", "Magma", "Spectral").
    """
    from qgis.core import (
        QgsClassificationCustom, QgsGraduatedSymbolRenderer,
        QgsRendererRange, QgsSymbol, QgsClassificationJenks,
    )
    from qgis.PyQt.QtGui import QColor

    # gather values
    values = []
    alphas = []
    for feat in vector_layer.getFeatures():
        v = feat[colour_field]
        a = feat[alpha_field]
        if v is not None and a is not None:
            values.append(float(v))
            alphas.append(float(a))

    if not values:
        return

    # classify colour field
    n_classes = min(5, len(set(values)))
    breaks = _jenks_breaks(values, n_classes)

    # classify alpha field
    alpha_breaks = _jenks_breaks(alphas, n_classes)
    alpha_step = (alpha_max - alpha_min) / max(len(alpha_breaks) - 2, 1)

    # build colour ramp
    import random
    ramp_colours = _get_ramp_colours(colour_ramp_name, n_classes)

    ranges = []
    for i in range(n_classes):
        low_v, high_v = breaks[i], breaks[i + 1]
        col = ramp_colours[i % len(ramp_colours)]

        for j in range(n_classes):
            alpha_low = alpha_breaks[j]
            alpha_high = alpha_breaks[j + 1]
            alpha_val = int(alpha_min + j * alpha_step)

            sym = QgsSymbol.defaultSymbol(vector_layer.geometryType()).clone()
            sym.setColor(col)
            sym.setOpacity(alpha_val / 255.0)

            label = f"{col.name()} alpha={alpha_val}"
            ranges.append(QgsRendererRange(
                low_v * 1000 + alpha_low,  # compound key
                high_v * 1000 + alpha_high,
                sym, label,
            ))

    renderer = QgsGraduatedSymbolRenderer("", ranges)
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
