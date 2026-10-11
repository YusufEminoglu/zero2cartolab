# -*- coding: utf-8 -*-
"""
Bivariate colour-matrix legend for QGIS print layouts.

Renders the legend as *native* layout items (rectangles or diamonds plus
text), grouped so it drags as one unit. Unlike an embedded SVG this leaves
no temporary files behind and stays fully editable in the Layout Designer.
"""
from __future__ import annotations

from contextlib import suppress
from typing import List

try:
    from qgis.PyQt.QtCore import QPointF, QRectF
    from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemGroup,
        QgsLayoutItemLabel,
        QgsLayoutItemPolygon,
        QgsLayoutItemShape,
        QgsLayoutItemScaleBar,
        QgsLayoutItemPicture,
        QgsLayoutItemMap,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
        QgsFillSymbol,
    )
    _MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except ImportError:
    QPointF = QRectF = QColor = QFont = QPolygonF = QgsLayout = QgsLayoutItemGroup = QgsLayoutItemLabel = QgsLayoutItemPolygon = QgsLayoutItemShape = QgsLayoutItemScaleBar = QgsLayoutItemPicture = QgsLayoutItemMap = QgsLayoutPoint = QgsLayoutSize = QgsUnitTypes = QgsFillSymbol = None
    _MM = 0



from ..core.bivariate_engine import BIVARIATE_PALETTE_PRESETS, bivariate_colour_matrix
from .layout_utils import main_map_item
from .map_sheet import _configure_scalebar



def add_bivariate_legend_to_layout(
    layout: QgsLayout,
    x_label: str = "Variable X",
    y_label: str = "Variable Y",
    grid_size: int = 4,
    position: tuple = (12.0, 12.0),
    size_mm: tuple = (40.0, 40.0),
    color_ll: str = "#e8e8e8",
    color_lh: str = "#d8b365",
    color_hl: str = "#5ab4ac",
    color_hh: str = "#8c510a",
    legend_type: str = "diamond",
    add_card: bool = True,
) -> QgsLayoutItemGroup:
    """
    Insert a bivariate colour-matrix legend built from native layout items.

    Returns the :class:`QgsLayoutItemGroup` holding the legend so callers can
    reposition or delete it as a whole.
    """
    matrix = bivariate_colour_matrix(grid_size, color_ll, color_lh, color_hl, color_hh)
    if legend_type == "square":
        items = _build_square(layout, matrix, position, size_mm, x_label, y_label, add_card=add_card)
    else:
        items = _build_diamond(layout, matrix, position, size_mm, x_label, y_label, add_card=add_card)

    _align_items_top_left(items, position)
    if hasattr(layout, "groupItems") and items:
        grp = layout.groupItems(items)
        if grp:
            return grp
    return items


def _items_bounds(items):
    """Union of the items' frames in scene (layout) units.

    Uses the geometric frame (``rect()`` mapped to the scene, rotation
    included) without stroke bleed, which is what a layout group reports as
    its position.
    """
    bounds = None
    for item in items:
        rect = item.mapRectToScene(item.rect())
        bounds = QRectF(rect) if bounds is None else bounds.united(rect)
    return bounds


def _align_items_top_left(items, position) -> None:
    """Shift built items so their joint top-left corner sits at ``position``.

    The card, rotated labels and the outer diamond labels extend left/above
    the anchor the builders draw from, so without this the legend starts
    off-page and each in-place update drifts it further.
    """
    bounds = _items_bounds(items) if items else None
    if bounds is None:
        return
    dx = float(position[0]) - bounds.left()
    dy = float(position[1]) - bounds.top()
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return
    for item in items:
        pos = item.positionWithUnits()
        item.attemptMove(QgsLayoutPoint(pos.x() + dx, pos.y() + dy, pos.units()))


def replace_bivariate_legend(layout: QgsLayout, selected, **kwargs):
    """Rebuild a selected bivariate legend group in place.

    ``selected`` is the designer selection (the group or any of its member
    items). The old group and all its members are removed and the new legend
    is placed at the old group's top-left corner, so repeated updates do not
    move it.
    """
    members = []
    for item in selected or []:
        group = item if isinstance(item, QgsLayoutItemGroup) else None
        if group is None:
            with suppress(Exception):
                group = item.parentGroup()
        if group is not None:
            for child in [group] + list(group.items()):
                if child not in members:
                    members.append(child)
        elif item not in members:
            members.append(item)
    drawn = [m for m in members if not isinstance(m, QgsLayoutItemGroup)] or members
    bounds = _items_bounds(drawn)
    position = (bounds.left(), bounds.top()) if bounds is not None else (12.0, 12.0)
    for group in [m for m in members if isinstance(m, QgsLayoutItemGroup)]:
        with suppress(Exception):
            layout.ungroupItems(group)
    for item in members:
        if isinstance(item, QgsLayoutItemGroup):
            continue
        with suppress(Exception):
            layout.removeLayoutItem(item)
    kwargs["position"] = position
    return add_bivariate_legend(layout, **kwargs)


def add_bivariate_legend(
    layout: QgsLayout,
    colors: tuple = None,
    legend_type: str = "diamond",
    title: str = "Bivariate Legend",
    x_label: str = "Variable X",
    y_label: str = "Variable Y",
    add_card: bool = True,
    **kwargs,
) -> QgsLayoutItemGroup:
    """Convenience wrapper for add_bivariate_legend_to_layout."""
    if colors and len(colors) >= 4:
        cll, clh, chl, chh = colors[0], colors[1], colors[2], colors[3]
    else:
        # Default = teal_brown preset ("lh" = low X / high Y, "hl" = high X / low Y).
        preset = BIVARIATE_PALETTE_PRESETS.get("teal_brown", {})
        cll, clh, chl, chh = (preset.get("ll", "#e8e8e8"), preset.get("lh", "#d8b365"),
                              preset.get("hl", "#5ab4ac"), preset.get("hh", "#8c510a"))
    return add_bivariate_legend_to_layout(
        layout,
        x_label=x_label,
        y_label=y_label,
        color_ll=cll,
        color_lh=clh,
        color_hl=chl,
        color_hh=chh,
        legend_type=legend_type,
        add_card=add_card,
        **kwargs,
    )


def _fill(color: QColor) -> QgsFillSymbol:
    return QgsFillSymbol.createSimple({
        "color": color.name(),
        "outline_color": "#ffffff",
        "outline_width": "0.25",
    })


def _label(layout, text: str, x: float, y: float, size: float = 8.0,
           bold: bool = False, rotation: float = 0.0, color: str = "#0f172a") -> QgsLayoutItemLabel:
    lbl = QgsLayoutItemLabel(layout)
    lbl.setText(text)
    lbl.setBackgroundEnabled(False)
    lbl.setFrameEnabled(False)
    f = QFont("Segoe UI")
    hint = getattr(getattr(QFont, "StyleHint", QFont), "SansSerif", getattr(QFont, "SansSerif", None))
    if hint is not None and hasattr(f, "setStyleHint"):
        with suppress(Exception):
            f.setStyleHint(hint)
    if hasattr(f, "setFamilies"):
        f.setFamilies(["Segoe UI", "Arial", "sans-serif"])
    if hasattr(f, "setPointSizeF"):
        f.setPointSizeF(float(size))
    else:
        f.setPointSize(int(round(size)))
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setFontColor(QColor(color))
    lbl.adjustSizeToText()
    if rotation:
        lbl.setItemRotation(rotation)
    lbl.attemptMove(QgsLayoutPoint(x, y, _MM))
    layout.addLayoutItem(lbl)
    return lbl


def _build_square(layout, matrix, position, size_mm, x_label, y_label, add_card: bool = True) -> List:
    n = len(matrix)
    x0, y0 = position
    cell = min(size_mm[0], size_mm[1]) / float(n)
    grid_w = n * cell
    grid_h = n * cell
    items: List = []

    if add_card and QgsLayoutItemShape is not None:
        card_w = grid_w + 26.0
        card_h = grid_h + 20.0
        card = QgsLayoutItemShape(layout)
        shape_type = getattr(getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape), "Rectangle", getattr(QgsLayoutItemShape, "Rectangle", 0))
        card.setShapeType(shape_type)
        card.attemptResize(QgsLayoutSize(card_w, card_h, _MM))
        card.attemptMove(QgsLayoutPoint(x0 - 12.0, y0 - 6.0, _MM))
        if QgsFillSymbol:
            card_sym = QgsFillSymbol.createSimple({
                "color": "255,255,255,245",
                "outline_color": "#cbd5e1",
                "outline_width": "0.3",
            })
            if card_sym:
                card.setSymbol(card_sym)
        layout.addLayoutItem(card)
        items.append(card)

    for ri, row in enumerate(matrix):
        for ci, col in enumerate(row):
            shape = QgsLayoutItemShape(layout)
            shape_type = getattr(getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape), "Rectangle", getattr(QgsLayoutItemShape, "Rectangle", 0))
            shape.setShapeType(shape_type)
            shape.attemptResize(QgsLayoutSize(cell, cell, _MM))
            shape.attemptMove(QgsLayoutPoint(x0 + ci * cell, y0 + ri * cell, _MM))
            shape.setSymbol(_fill(col))
            layout.addLayoutItem(shape)
            items.append(shape)

    # High-contrast X & Y axis labels and directional indicators
    items.append(_label(layout, f"{x_label} ->", x0, y0 + grid_h + 2.0, size=7.5, bold=True, color="#0f172a"))
    items.append(_label(layout, f"{y_label} ^", x0 - 2.0, y0 + grid_h - 2.0, size=7.5, bold=True, rotation=270.0, color="#0f172a"))
    items.append(_label(layout, "Low", x0 - 2.0, y0 + grid_h + 1.0, size=6.5, bold=False, color="#64748b"))
    items.append(_label(layout, "High", x0 + grid_w - 6.0, y0 + grid_h + 1.0, size=6.5, bold=False, color="#64748b"))
    return items


def _build_diamond(layout, matrix, position, size_mm, x_label, y_label, add_card: bool = True) -> List:
    n = len(matrix)
    half_w = size_mm[0] / (2.0 * n)
    half_h = size_mm[1] / (2.0 * n)
    x0, y0 = position
    items: List = []

    if add_card and QgsLayoutItemShape is not None:
        card_w = size_mm[0] + 32.0
        card_h = size_mm[1] + 24.0
        card = QgsLayoutItemShape(layout)
        shape_type = getattr(getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape), "Rectangle", getattr(QgsLayoutItemShape, "Rectangle", 0))
        card.setShapeType(shape_type)
        card.attemptResize(QgsLayoutSize(card_w, card_h, _MM))
        card.attemptMove(QgsLayoutPoint(x0 - 16.0, y0 - 10.0, _MM))
        if QgsFillSymbol:
            card_sym = QgsFillSymbol.createSimple({
                "color": "255,255,255,245",
                "outline_color": "#cbd5e1",
                "outline_width": "0.3",
            })
            if card_sym:
                card.setSymbol(card_sym)
        layout.addLayoutItem(card)
        items.append(card)

    offset_x = x0 + (n - 1) * half_w + half_w
    offset_y = y0 + half_h + 4.0

    for ri in range(n):
        for ci in range(n):
            col = matrix[ri][ci]
            cx = offset_x + (ci - ri) * half_w
            cy = offset_y + ((n - 1) - (ci + ri)) * half_h
            poly = QPolygonF([
                QPointF(cx, cy - half_h),
                QPointF(cx + half_w, cy),
                QPointF(cx, cy + half_h),
                QPointF(cx - half_w, cy),
            ])
            diamond = QgsLayoutItemPolygon(poly, layout)
            diamond.setSymbol(_fill(col))
            layout.addLayoutItem(diamond)
            items.append(diamond)

    cx_mid = offset_x
    # Top/bottom/left/right axis labels
    items.append(_label(layout, f"High {y_label} ^", cx_mid - 12.0, offset_y - (n * half_h) - 4.0, size=7, bold=True, color="#0f172a"))
    items.append(_label(layout, f"Low {y_label}", cx_mid - 10.0, offset_y + (n * half_h) + 2.0, size=6.5, bold=False, color="#64748b"))
    items.append(_label(layout, f"{x_label} ->", offset_x + (n * half_w) + 1.0, offset_y - 2.0, size=7.5, bold=True, color="#0f172a"))
    items.append(_label(layout, f"Low {x_label}", x0 - 12.0, offset_y - 2.0, size=6.5, bold=False, color="#64748b"))
    return items


def add_scalebar_to_layout(
    layout: QgsLayout,
    map_item: QgsLayoutItemMap = None,
    position: tuple = (15.0, 15.0),
    style_name: str = "Clean Line (Ticks Up)",
    segments: int = 3,
    units_per_segment: float = 1.0,
    unit_label: str = "km",
    max_width_mm: float = 65.0,
) -> QgsLayoutItemScaleBar:
    """Add an executive publication-ready scalebar to the layout."""
    if layout is None or QgsLayoutItemScaleBar is None:
        return None

    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setId("cartolab_scalebar")
    if map_item is None:
        map_item = main_map_item(layout)

    if map_item is not None:
        scalebar.setLinkedMap(map_item)
    scalebar.applyDefaultSettings()

    # Style mapping: "Single Box", "Double Box", "Line Ticks", "Stepped Box", "Line Ticks Up", "Line Ticks Down"
    STYLE_MAP = {
        "Single Box": "Single Box",
        "Single Box (Modern)": "Single Box",
        "Double Box": "Double Box",
        "Double Box (Classic)": "Double Box",
        "Line Ticks": "Line Ticks Middle",
        "Line Ticks Middle": "Line Ticks Middle",
        "Line Ticks Up": "Line Ticks Up",
        "Clean Line (Ticks Up)": "Line Ticks Up",
        "Line Ticks Down": "Line Ticks Down",
        "Clean Line (Ticks Down)": "Line Ticks Down",
        "Stepped Box": "Stepped Line",
        "Stepped Line": "Stepped Line",
        "Stepped Line (Academic)": "Stepped Line",
        "Hollow": "Hollow",
    }
    target_style = STYLE_MAP.get(style_name, "Single Box")
    scalebar.setStyle(target_style)

    # Units — safe for both QGIS 3.x (unscoped) and 4.x (scoped)
    _DistKm = getattr(getattr(QgsUnitTypes, "DistanceUnit", QgsUnitTypes), "DistanceKilometers", getattr(QgsUnitTypes, "DistanceKilometers", None))
    if _DistKm is not None:
        scalebar.setUnits(_DistKm)

    n_segs = max(3, segments)
    scalebar.setNumberOfSegments(n_segs)
    scalebar.setNumberOfSegmentsLeft(0)

    if map_item is not None and units_per_segment == 1.0:
        project = None
        with suppress(Exception):
            project = map_item.layout().project()
        if not _configure_scalebar(
            scalebar,
            map_item,
            project,
            max_width_mm=max_width_mm,
            target_segments=n_segs,
        ):
            scalebar.setUnitsPerSegment(units_per_segment)
            scalebar.setUnitLabel(unit_label)
    else:
        scalebar.setUnitsPerSegment(units_per_segment)
        scalebar.setUnitLabel(unit_label)

    scalebar.attemptMove(QgsLayoutPoint(position[0], position[1], _MM))
    layout.addLayoutItem(scalebar)
    layout.refresh()
    return scalebar


def scale_ratio_expression(map_item) -> str:
    """Label text whose ratio follows ``map_item``'s live scale.

    The map id is assigned when missing so the expression can address the
    frame through ``item_variables``.
    """
    if map_item is None:
        return "Scale 1:25,000"
    if not map_item.id():
        layout = map_item.layout()
        base, n = "cartolab_scale_map", 1
        candidate = base
        while layout is not None and layout.itemById(candidate) is not None:
            n += 1
            candidate = f"{base}_{n}"
        map_item.setId(candidate)
    map_id = map_item.id().replace("'", "''")
    return f"Scale 1:[% format_number(map_get(item_variables('{map_id}'), 'map_scale'), 0) %]"


def add_scale_combo_to_layout(
    layout: QgsLayout,
    map_item: QgsLayoutItemMap = None,
    position: tuple = (15.0, 15.0),
    style_name: str = "Clean Line (Ticks Up)",
) -> QgsLayoutItemGroup:
    """
    Insert a combined scale indicator: dynamic ratio text (e.g. 1:25,000) + graphical bar.
    """
    if layout is None or QgsLayoutItemScaleBar is None:
        return None

    if map_item is None:
        map_item = main_map_item(layout)

    sb = add_scalebar_to_layout(
        layout,
        map_item=map_item,
        position=(position[0], position[1] + 6.0),
        style_name=style_name,
    )

    lbl = QgsLayoutItemLabel(layout)
    lbl.setText(scale_ratio_expression(map_item))
    if QFont is not None:
        lbl.setFont(QFont("Inter, Segoe UI", 8, QFont.Weight.Bold))
    if QColor is not None:
        lbl.setFontColor(QColor("#0f172a"))
    lbl.attemptMove(QgsLayoutPoint(position[0], position[1], _MM))
    lbl.attemptResize(QgsLayoutSize(60.0, 5.0, _MM))
    layout.addLayoutItem(lbl)

    items = [lbl]
    if sb is not None:
        items.append(sb)

    if hasattr(layout, "groupItems") and items:
        grp = layout.groupItems(items)
        if grp:
            return grp
    return items


def add_north_arrow_to_layout(
    layout: QgsLayout,
    position: tuple = (15.0, 15.0),
    size_mm: tuple = (16.0, 22.0),
    preset: str = "compass_rose",
) -> QgsLayoutItemGroup:
    """
    Insert a publication-ready north arrow motif (Compass Rose, Swiss Minimalist, Nautical Star).
    Returns the grouped layout item containing the compass components.
    """
    if layout is None:
        return None

    x0, y0 = position
    w, h = size_mm
    cx = x0 + w / 2.0
    cy = y0 + h / 2.0
    items = []

    if preset == "swiss_minimal":
        # Ultra-clean thin needle arrow
        poly_l = QPolygonF([QPointF(cx, y0 + 6.0), QPointF(cx - w / 4.0, y0 + h), QPointF(cx, y0 + h * 0.75)])
        poly_r = QPolygonF([QPointF(cx, y0 + 6.0), QPointF(cx + w / 4.0, y0 + h), QPointF(cx, y0 + h * 0.75)])
        p_l = QgsLayoutItemPolygon(poly_l, layout)
        p_l.setSymbol(_fill(QColor("#0f172a")))
        p_r = QgsLayoutItemPolygon(poly_r, layout)
        p_r.setSymbol(_fill(QColor("#94a3b8")))
        layout.addLayoutItem(p_l)
        layout.addLayoutItem(p_r)
        items.extend([p_l, p_r])
        lbl = _label(layout, "N", cx - 2.5, y0, size=9, bold=True)
        items.append(lbl)

    elif preset == "nautical_star":
        # 4-point Nautical Star Compass
        poly_top = QPolygonF([QPointF(cx, y0 + 6.0), QPointF(cx + w / 5.0, cy), QPointF(cx, cy)])
        poly_right = QPolygonF([QPointF(x0 + w, cy), QPointF(cx, cy + h / 5.0), QPointF(cx, cy)])
        poly_bottom = QPolygonF([QPointF(cx, y0 + h), QPointF(cx - w / 5.0, cy), QPointF(cx, cy)])
        poly_left = QPolygonF([QPointF(x0, cy), QPointF(cx, cy - h / 5.0), QPointF(cx, cy)])
        for poly, col in [(poly_top, "#0f172a"), (poly_right, "#475569"), (poly_bottom, "#0f172a"), (poly_left, "#475569")]:
            item = QgsLayoutItemPolygon(poly, layout)
            item.setSymbol(_fill(QColor(col)))
            layout.addLayoutItem(item)
            items.append(item)
        lbl = _label(layout, "N", cx - 2.5, y0, size=9, bold=True)
        items.append(lbl)

    elif preset == "modern_arrow":
        # Contemporary architectural & urban planning chevron needle
        tip_y = y0 + 6.0
        poly_chevron = QPolygonF([
            QPointF(cx, tip_y),
            QPointF(cx + w * 0.35, y0 + h * 0.65),
            QPointF(cx, y0 + h * 0.5),
            QPointF(cx - w * 0.35, y0 + h * 0.65),
        ])
        p_chev = QgsLayoutItemPolygon(poly_chevron, layout)
        p_chev.setSymbol(_fill(QColor("#0f172a")))
        layout.addLayoutItem(p_chev)
        items.append(p_chev)

        poly_tail = QPolygonF([
            QPointF(cx - 0.4, y0 + h * 0.5),
            QPointF(cx + 0.4, y0 + h * 0.5),
            QPointF(cx + 0.4, y0 + h),
            QPointF(cx - 0.4, y0 + h),
        ])
        p_tail = QgsLayoutItemPolygon(poly_tail, layout)
        p_tail.setSymbol(_fill(QColor("#475569")))
        layout.addLayoutItem(p_tail)
        items.append(p_tail)

        lbl = _label(layout, "N", cx - 2.5, y0, size=9, bold=True)
        items.append(lbl)

    else:
        # Classic 8-Point Compass Rose with dual-facet shading
        facet_left = QPolygonF([QPointF(cx, y0 + 6.0), QPointF(x0, y0 + h), QPointF(cx, y0 + h * 0.8)])
        facet_right = QPolygonF([QPointF(cx, y0 + 6.0), QPointF(x0 + w, y0 + h), QPointF(cx, y0 + h * 0.8)])
        p1 = QgsLayoutItemPolygon(facet_left, layout)
        p1.setSymbol(_fill(QColor("#0f172a")))
        p2 = QgsLayoutItemPolygon(facet_right, layout)
        p2.setSymbol(_fill(QColor("#cbd5e1")))
        layout.addLayoutItem(p1)
        layout.addLayoutItem(p2)
        items.extend([p1, p2])
        lbl = _label(layout, "N", cx - 2.5, y0, size=9, bold=True)
        items.append(lbl)

    if hasattr(layout, "groupItems") and items:
        grp = layout.groupItems(items)
        if grp:
            return grp
    return items
