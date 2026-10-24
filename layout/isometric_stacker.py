# -*- coding: utf-8 -*-
"""
Isometric Layout Stacker — Axonometric explosion of map layers.

Creates a QGIS Print Layout where multiple map layers are rendered as
floating 2.5D isometric planes stacked vertically, revealing their
spatial relationships.
"""
from __future__ import annotations

from typing import List, Optional

try:
    from qgis.PyQt.QtGui import QFont, QPolygonF
    from qgis.PyQt.QtCore import QPointF
    from qgis.core import (
        QgsPrintLayout,
        QgsLayoutItemMap,
        QgsLayoutItemLabel,
        QgsLayoutItemPolyline,
        QgsLineSymbol,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsProject,
        QgsRectangle,
        QgsUnitTypes,
        QgsMapLayer,
    )
except ImportError:
    QFont = QPolygonF = QPointF = None
    QgsPrintLayout = QgsLayoutItemMap = QgsLayoutItemLabel = QgsLayoutItemPolyline = QgsLineSymbol = None
    QgsLayoutPoint = QgsLayoutSize = QgsProject = QgsRectangle = QgsUnitTypes = QgsMapLayer = None

from .layout_utils import unique_layout_name, zoom_map_to_extent


def create_isometric_stack_layout(
    layers: List[QgsMapLayer],
    layout_name: str = "Isometric Stack",
    page_width_mm: float = 420.0,
    page_height_mm: float = 297.0,
    base_spacing_mm: float = 18.0,
    angle_deg: float = 30.0,
    elevation_deg: float = 35.264,
    map_scale: Optional[float] = None,
) -> QgsPrintLayout:
    """
    Create an isometric-stacked map layout.

    Each layer appears offset diagonally (simulating a 2.5D explosion),
    with the bottom layer at z=0 and each subsequent layer shifted upward
    and slightly to the right.

    Parameters
    ----------
    layers : list[QgsMapLayer]
        Layers to stack (bottom → top order).
    layout_name : str
        Name for the layout in the layout manager.
    page_width_mm, page_height_mm : float
        Page dimensions in millimetres.
    base_spacing_mm : float
        Vertical offset between stacked maps.
    angle_deg, elevation_deg : float
        Isometric projection angles.
    map_scale : float, optional
        Fixed scale denominator; by default each plane is zoomed to fit
        the combined layer extent.

    Returns
    -------
    QgsPrintLayout
        The configured print layout with isometric map items.
    """
    if not layers:
        raise ValueError("Isometric stack needs at least one layer.")

    project = QgsProject.instance()
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(unique_layout_name(project, layout_name))

    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(page_width_mm, page_height_mm, QgsUnitTypes.LayoutUnit.LayoutMillimeters))

    # precompute isometric offsets from our affine engine
    from ..core.affine_matrix import compute_isometric_layer_offsets
    offsets = compute_isometric_layer_offsets(
        len(layers), base_spacing_mm, angle_deg, elevation_deg)

    # Size the planes so the whole stack (sideways drift from the tilt angle,
    # rise from the elevation, plus the layer captions) fits on the page.
    margin, caption_h = 10.0, 8.0
    min_dx = min(dx for dx, _ in offsets)
    max_dx = max(dx for dx, _ in offsets)
    max_dy = max(dy for _, dy in offsets)
    span_x, span_y = max_dx - min_dx, max_dy + caption_h
    map_width = max(20.0, min(page_width_mm * 0.55, page_width_mm - 2 * margin - span_x))
    map_height = max(15.0, min(page_height_mm * 0.55, page_height_mm - 2 * margin - span_y))

    # determine a common extent from all layers
    extent = None
    for layer in layers:
        if extent is None:
            extent = QgsRectangle(layer.extent())
        else:
            extent.combineExtentWith(layer.extent())
    if extent is None or extent.isEmpty():
        extent = QgsRectangle(0, 0, 1000, 1000)
    extent.scale(1.15)

    # Top-left of the bottom (i = 0) plane, centring the stack's bounding box.
    center_x = (page_width_mm - (map_width + span_x)) / 2.0 - min_dx
    center_y = (page_height_mm - (map_height + span_y)) / 2.0 + span_y

    _mm = QgsUnitTypes.LayoutUnit.LayoutMillimeters
    labels = []
    for i, (layer, (dx, dy)) in enumerate(zip(layers, offsets)):
        map_item = QgsLayoutItemMap(layout)
        map_item.setId(f"cartolab_iso_map_{i + 1}")
        map_item.attemptResize(QgsLayoutSize(map_width, map_height, _mm))
        map_item.attemptMove(QgsLayoutPoint(center_x + dx, center_y - dy, _mm))
        # Fit the data instead of forcing a fixed scale that clips it.
        zoom_map_to_extent(map_item, extent)
        if map_scale:
            map_item.setScale(map_scale)
        # Transparent planes: lower layers and their captions stay visible.
        map_item.setBackgroundEnabled(False)

        # set which layers are visible: only the current one
        map_item.setLayers([layer])
        map_item.setKeepLayerSet(True)
        layout.addLayoutItem(map_item)

        # caption above each plane; added after every map so it draws on top
        label = QgsLayoutItemLabel(layout)
        label.setText(layer.name())
        font = QFont()
        font.setFamilies(["Inter", "Segoe UI", "Arial", "sans-serif"])
        font.setPointSize(9)
        font.setBold(True)
        label.setFont(font)
        label.adjustSizeToText()
        label.attemptMove(QgsLayoutPoint(center_x + dx, center_y - dy - caption_h, _mm))
        labels.append(label)

    for label in labels:
        layout.addLayoutItem(label)

    # Draw connector lines between adjacent map layers
    for i in range(len(layers) - 1):
        dx1, dy1 = offsets[i]
        dx2, dy2 = offsets[i + 1]

        corners1 = [
            (center_x + dx1, center_y - dy1),
            (center_x + dx1 + map_width, center_y - dy1),
            (center_x + dx1, center_y - dy1 + map_height),
            (center_x + dx1 + map_width, center_y - dy1 + map_height),
        ]
        corners2 = [
            (center_x + dx2, center_y - dy2),
            (center_x + dx2 + map_width, center_y - dy2),
            (center_x + dx2, center_y - dy2 + map_height),
            (center_x + dx2 + map_width, center_y - dy2 + map_height),
        ]

        for pt1, pt2 in zip(corners1, corners2):
            polygon = QPolygonF([QPointF(pt1[0], pt1[1]), QPointF(pt2[0], pt2[1])])
            line_item = QgsLayoutItemPolyline(polygon, layout)
            symbol = QgsLineSymbol.createSimple({
                "color": "#9ebbca",
                "width": "0.3",
                "style": "dash"
            })
            line_item.setSymbol(symbol)
            layout.addLayoutItem(line_item)

    # Captions above every plane and connector (QGIS does not always append new items on top).
    for label in labels:
        layout.moveItemToTop(label, True)
    layout.updateZValues()

    project.layoutManager().addLayout(layout)
    return layout


def stack_layers_isometrically(
    layout: QgsPrintLayout,
    layers: List[QgsMapLayer],
    tilt_angle: float = 30.0,
    heading: float = 100.0,
    **kwargs,
) -> QgsPrintLayout:
    """Alias for create_isometric_stack_layout."""
    return create_isometric_stack_layout(
        layers=layers,
        angle_deg=tilt_angle,
        **kwargs,
    )

