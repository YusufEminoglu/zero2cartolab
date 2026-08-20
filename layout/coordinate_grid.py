# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Publication-Ready Coordinate Grid Decorator.

Calculates optimal publication intervals (approx 5-7 horizontal, 4-6 vertical divisions)
using Heckbert nice numbers, auto-detecting CRS units and applying clean Swiss/academic cartographic styling.
"""
from __future__ import annotations

import math
from typing import Optional

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemMap,
        QgsLayoutItemMapGrid,
        QgsLineSymbol,
    )
    from qgis.PyQt.QtGui import QColor, QFont
except ImportError:
    QgsLayout = QgsLayoutItemMap = QgsLayoutItemMapGrid = QgsLineSymbol = QColor = QFont = None

from ..core.layout_math import nice_interval

GRID_NAME = "PlanXCoordGrid"


def apply_coordinate_grid_decorator(
    layout: QgsLayout,
    main_map: Optional[QgsLayoutItemMap] = None,
    interval_x: Optional[float] = None,
    interval_y: Optional[float] = None,
    target_divisions_x: int = 6,
    target_divisions_y: int = 5,
    grid_style: str = "Solid",        # "Solid", "Cross", "Markers"
    frame_style: str = "Zebra",        # "Zebra", "LineBorder", "NoFrame"
    show_annotations: bool = True,
    frame_width_mm: float = 1.5,
) -> bool:
    """
    Apply a publication-standard coordinate grid to the layout's primary map frame.

    Derives clean, rounded intervals from the map's current extent and scale,
    preventing over-crowding or dense divisions.
    """
    if layout is None or QgsLayoutItemMap is None or QgsLayoutItemMapGrid is None:
        return False

    if main_map is None:
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                main_map = item
                break

    if main_map is None:
        return False

    extent = main_map.extent()
    w = extent.width() if extent else 0.0
    h = extent.height() if extent else 0.0

    # 1. Derive optimal publication intervals if not explicitly provided
    if interval_x is None or interval_x <= 0:
        interval_x = nice_interval(w, target_divisions=target_divisions_x)
        if interval_x <= 0:
            interval_x = (w / float(target_divisions_x)) if w > 0 else 1000.0

    if interval_y is None or interval_y <= 0:
        interval_y = nice_interval(h, target_divisions=target_divisions_y)
        if interval_y <= 0:
            interval_y = (h / float(target_divisions_y)) if h > 0 else 1000.0

    # Check if geographic (degrees) vs projected (meters/feet)
    is_geographic = (w > 0 and w < 360.0 and h > 0 and h < 180.0)

    # 2. Get or create PlanX grid on map item
    grid = None
    stack = main_map.grids()
    for g in list(stack.asList()):
        if g.name() == GRID_NAME:
            grid = g
            break

    if grid is None:
        grid = QgsLayoutItemMapGrid(GRID_NAME, main_map)
        stack.addGrid(grid)

    grid.setEnabled(True)
    _MapUnit = getattr(getattr(QgsLayoutItemMapGrid, "GridUnit", QgsLayoutItemMapGrid), "MapUnit", getattr(QgsLayoutItemMapGrid, "MapUnit", 0))
    grid.setUnits(_MapUnit)
    grid.setIntervalX(interval_x)
    grid.setIntervalY(interval_y)

    # 3. Grid Line Style (Solid, Cross, Markers)
    style_map = {
        "Solid": getattr(getattr(QgsLayoutItemMapGrid, "GridStyle", QgsLayoutItemMapGrid), "Solid", 0),
        "Cross": getattr(getattr(QgsLayoutItemMapGrid, "GridStyle", QgsLayoutItemMapGrid), "Cross", 1),
        "Markers": getattr(getattr(QgsLayoutItemMapGrid, "GridStyle", QgsLayoutItemMapGrid), "Markers", 2),
        "FrameAndAnnotationsOnly": getattr(getattr(QgsLayoutItemMapGrid, "GridStyle", QgsLayoutItemMapGrid), "FrameAndAnnotationsOnly", 3),
    }
    grid.setStyle(style_map.get(grid_style, style_map["Solid"]))

    # Subtle cartographic line symbol
    if QgsLineSymbol is not None:
        line_sym = QgsLineSymbol.createSimple({"color": "#cbd5e1", "width": "0.15"})
        grid.setLineSymbol(line_sym)

    # 4. Frame Style (Zebra, LineBorder, NoFrame)
    frame_map = {
        "Zebra": getattr(getattr(QgsLayoutItemMapGrid, "FrameStyle", QgsLayoutItemMapGrid), "Zebra", 1),
        "LineBorder": getattr(getattr(QgsLayoutItemMapGrid, "FrameStyle", QgsLayoutItemMapGrid), "LineBorder", 4),
        "NoFrame": getattr(getattr(QgsLayoutItemMapGrid, "FrameStyle", QgsLayoutItemMapGrid), "NoFrame", 0),
    }
    grid.setFrameStyle(frame_map.get(frame_style, frame_map["Zebra"]))
    grid.setFrameWidth(frame_width_mm)
    grid.setFramePenColor(QColor("#0f172a"))
    grid.setFrameFillColor1(QColor("#0f172a"))
    grid.setFrameFillColor2(QColor("#ffffff"))

    # 5. Publication Annotations
    if show_annotations and hasattr(grid, "setAnnotationEnabled"):
        grid.setAnnotationEnabled(True)
        _ShowAll = getattr(getattr(QgsLayoutItemMapGrid, "DisplayMode", QgsLayoutItemMapGrid), "ShowAll", getattr(QgsLayoutItemMapGrid, "ShowAll", 0))
        _Disabled = getattr(getattr(QgsLayoutItemMapGrid, "DisplayMode", QgsLayoutItemMapGrid), "HideAll", getattr(QgsLayoutItemMapGrid, "HideAll", 2))
        _Left = getattr(getattr(QgsLayoutItemMapGrid, "BorderSide", QgsLayoutItemMapGrid), "Left", getattr(QgsLayoutItemMapGrid, "Left", 0))
        _Right = getattr(getattr(QgsLayoutItemMapGrid, "BorderSide", QgsLayoutItemMapGrid), "Right", getattr(QgsLayoutItemMapGrid, "Right", 1))
        _Bottom = getattr(getattr(QgsLayoutItemMapGrid, "BorderSide", QgsLayoutItemMapGrid), "Bottom", getattr(QgsLayoutItemMapGrid, "Bottom", 2))
        _Top = getattr(getattr(QgsLayoutItemMapGrid, "BorderSide", QgsLayoutItemMapGrid), "Top", getattr(QgsLayoutItemMapGrid, "Top", 3))

        # Show on Left and Bottom only for clean layout presentation
        grid.setAnnotationDisplay(_ShowAll, _Left)
        grid.setAnnotationDisplay(_ShowAll, _Bottom)
        grid.setAnnotationDisplay(_Disabled, _Right)
        grid.setAnnotationDisplay(_Disabled, _Top)

        # Precision
        if is_geographic:
            grid.setAnnotationPrecision(2 if interval_x >= 0.05 else 3)
        else:
            grid.setAnnotationPrecision(0)

        grid.setAnnotationFontColor(QColor("#475569"))
        if QFont is not None:
            f_grid = QFont("Segoe UI", 8)
            f_grid.setFamily("Segoe UI")
            grid.setAnnotationFont(f_grid)
        grid.setAnnotationFrameDistance(1.5)

    main_map.updateBoundingRect()
    layout.refresh()
    return True
