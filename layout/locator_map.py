# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Locator / Inset Map Decorator.

Provides automated locator map inset creation for QGIS Print Layouts with
contextual zoom-out extent, overview bounding extent styling, and smart corner placement.
"""
from __future__ import annotations

from contextlib import suppress
from typing import Optional, Tuple

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemMap,
        QgsLayoutItemMapOverview,
        QgsLayoutItemLabel,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLayoutMeasurement,
        QgsUnitTypes,
        QgsFillSymbol,
        QgsRectangle,
    )
    from qgis.PyQt.QtGui import QColor, QFont
except ImportError:
    QgsLayout = QgsLayoutItemMap = QgsLayoutItemMapOverview = QgsLayoutItemLabel = None
    QgsLayoutPoint = QgsLayoutSize = QgsLayoutMeasurement = QgsUnitTypes = QgsFillSymbol = QgsRectangle = None
    QColor = QFont = None

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0


def add_locator_inset_map(
    layout: QgsLayout,
    main_map: Optional[QgsLayoutItemMap] = None,
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (50.0, 45.0),
    zoom_factor: float = 4.0,
    corner: str = "bottom-right",  # "top-left", "top-right", "bottom-left", "bottom-right"
    overview_color: str = "#e11d48",
    overview_opacity: float = 0.25,
    border_color: str = "#0f172a",
    add_header: bool = True,
) -> Optional[QgsLayoutItemMap]:
    """
    Insert a secondary locator inset map frame into the layout linked to the primary map extent.
    """
    if layout is None or QgsLayoutItemMap is None:
        return None

    # Find primary map item if not provided
    if main_map is None:
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap) and item.id() != "cartolab_locator_inset":
                main_map = item
                break

    # Determine position
    if position is None:
        if main_map is not None:
            mp = main_map.pos()
            ms = main_map.sizeWithUnits()
            mx, my = mp.x(), mp.y()
            mw, mh = ms.width(), ms.height()
            pad = 5.0
            iw, ih = size_mm
            if corner == "top-left":
                pos_x, pos_y = mx + pad, my + pad
            elif corner == "top-right":
                pos_x, pos_y = mx + mw - iw - pad, my + pad
            elif corner == "bottom-left":
                pos_x, pos_y = mx + pad, my + mh - ih - pad
            else:  # "bottom-right"
                pos_x, pos_y = mx + mw - iw - pad, my + mh - ih - pad
        else:
            pos_x, pos_y = 15.0, 15.0
    else:
        pos_x, pos_y = position

    # Create secondary locator map item
    inset_map = QgsLayoutItemMap(layout)
    inset_map.setId("cartolab_locator_inset")
    inset_map.attemptMove(QgsLayoutPoint(pos_x, pos_y, _MM))
    inset_map.attemptResize(QgsLayoutSize(size_mm[0], size_mm[1], _MM))
    inset_map.setFrameEnabled(True)
    if hasattr(inset_map, "setFrameStrokeColor") and QColor:
        inset_map.setFrameStrokeColor(QColor(border_color))
        inset_map.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, _MM))
    if QColor:
        inset_map.setBackgroundColor(QColor("#ffffff"))
        inset_map.setBackgroundEnabled(True)

    if main_map is not None:
        if hasattr(main_map, "crs") and main_map.crs().isValid():
            inset_map.setCrs(main_map.crs())
        if hasattr(main_map, "layers") and main_map.layers():
            inset_map.setLayers(list(main_map.layers()))
            inset_map.setKeepLayerSet(True)

        # Scale inset map out for context
        ext = main_map.extent()
        if ext and not ext.isEmpty():
            inset_ext = QgsRectangle(ext)
            inset_ext.scale(max(1.5, zoom_factor))
            inset_map.setExtent(inset_ext)

        # Add extent overview rectangle linking inset map to main map
        if hasattr(inset_map, "overviews"):
            stack = inset_map.overviews()
            if hasattr(stack, "addOverview"):
                overview = QgsLayoutItemMapOverview("MainMapOverview", inset_map)
                overview.setLinkedMap(main_map)
                overview.setEnabled(True)
                if QgsFillSymbol:
                    alpha_255 = int(round(overview_opacity * 255))
                    qc = QColor(overview_color) if QColor else None
                    if qc and qc.isValid():
                        col_str = f"{qc.red()},{qc.green()},{qc.blue()},{alpha_255}"
                    else:
                        col_str = "239,68,68,90"
                    sym = QgsFillSymbol.createSimple({
                        "color": col_str,
                        "outline_color": overview_color,
                        "outline_width": "0.4",
                    })
                    if sym:
                        overview.setFrameSymbol(sym)
                stack.addOverview(overview)

    layout.addLayoutItem(inset_map)

    if add_header and QgsLayoutItemLabel:
        tag = QgsLayoutItemLabel(layout)
        tag.setText("LOCATOR OVERVIEW")
        tag.setBackgroundEnabled(False)
        tag.setFrameEnabled(False)
        f = QFont("Segoe UI", 7)
        if hasattr(f, "setFamilies"):
            f.setFamilies(["Segoe UI", "Arial", "sans-serif"])
        f.setBold(True)
        tag.setFont(f)
        if QColor:
            tag.setFontColor(QColor(border_color))
        tag.adjustSizeToText()
        tag.attemptMove(QgsLayoutPoint(pos_x, max(2.0, pos_y - 4.5), _MM))
        layout.addLayoutItem(tag)

    with suppress(Exception):
        layout.refresh()
    return inset_map
