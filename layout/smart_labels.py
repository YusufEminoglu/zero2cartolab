# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Smart Cartographic Labeling & Layout Callout Engine.

Provides:
  1. 1-Click Vector Layer Smart Labeling (`apply_smart_layer_labels`) with
     publication typography presets, halo buffers, pill badges, polygon
     interior ("polylabel" / centroidInside) placement, and leader-line
     callouts (`QgsSimpleLineCallout`).
  2. Print Layout Callout Annotation Badges (`add_layout_callout_badge`) with
     numbered HTML callout cards, leader polylines, and focal target markers.

Author: Yusuf Eminoğlu
"""
from __future__ import annotations

from contextlib import suppress
from typing import Any, Dict, List, Optional, Tuple

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsLayoutItemPolyline,
        QgsLayoutItemShape,
        QgsLayoutMeasurement,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLineSymbol,
        QgsFillSymbol,
        QgsPalLayerSettings,
        QgsTextBackgroundSettings,
        QgsTextBufferSettings,
        QgsTextFormat,
        QgsUnitTypes,
        QgsVectorLayer,
        QgsVectorLayerSimpleLabeling,
        QgsWkbTypes,
    )
    from qgis.PyQt.QtCore import QPointF, QSizeF
    from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
except ImportError:
    QgsLayout = QgsLayoutItemLabel = QgsLayoutItemMap = QgsLayoutItemPolyline = QgsLayoutItemShape = None
    QgsLayoutMeasurement = QgsLayoutPoint = QgsLayoutSize = QgsLineSymbol = QgsFillSymbol = None
    QgsPalLayerSettings = QgsTextBackgroundSettings = QgsTextBufferSettings = QgsTextFormat = None
    QgsUnitTypes = QgsVectorLayer = QgsVectorLayerSimpleLabeling = QgsWkbTypes = None
    QPointF = QSizeF = QColor = QFont = QPolygonF = None

try:
    from qgis.core import QgsSimpleLineCallout
except ImportError:
    QgsSimpleLineCallout = None

from ..core.html_graph_factory import HTML_CARD_THEMES, _esc
from .layout_utils import main_map_item

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0


SMART_LABEL_PRESETS: Dict[str, Dict[str, Any]] = {
    "swiss_halo": {
        "name": "Swiss Modern Halo",
        "font_family": "Segoe UI",
        "font_size": 8.5,
        "bold": True,
        "italic": False,
        "text_color": "#0f172a",
        "halo_enabled": True,
        "halo_color": "#ffffff",
        "halo_size_mm": 1.0,
        "halo_opacity": 0.92,
        "bg_enabled": False,
        "callout": False,
    },
    "dark_glow": {
        "name": "Dark Matter / Obsidian Glow",
        "font_family": "Segoe UI",
        "font_size": 8.5,
        "bold": True,
        "italic": False,
        "text_color": "#f8fafc",
        "halo_enabled": True,
        "halo_color": "#0f172a",
        "halo_size_mm": 1.2,
        "halo_opacity": 0.94,
        "bg_enabled": False,
        "callout": False,
    },
    "academic_serif": {
        "name": "Academic Classical Serif",
        "font_family": "Georgia",
        "font_size": 8.5,
        "bold": False,
        "italic": True,
        "text_color": "#1c1917",
        "halo_enabled": True,
        "halo_color": "#fdfbf7",
        "halo_size_mm": 0.9,
        "halo_opacity": 0.90,
        "bg_enabled": False,
        "callout": False,
    },
    "technical_badge": {
        "name": "Technical Code Pill Badge",
        "font_family": "Consolas",
        "font_size": 7.8,
        "bold": True,
        "italic": False,
        "text_color": "#0f172a",
        "halo_enabled": False,
        "halo_color": "#ffffff",
        "halo_size_mm": 0.0,
        "halo_opacity": 0.0,
        "bg_enabled": True,
        "bg_color": "#ffffff",
        "bg_stroke": "#475569",
        "callout": False,
    },
    "callout_leader": {
        "name": "Leader-Line Callout Label",
        "font_family": "Segoe UI",
        "font_size": 8.2,
        "bold": True,
        "italic": False,
        "text_color": "#0f172a",
        "halo_enabled": True,
        "halo_color": "#ffffff",
        "halo_size_mm": 1.0,
        "halo_opacity": 0.95,
        "bg_enabled": False,
        "callout": True,
        "callout_color": "#334155",
    },
}


def detect_best_label_field(layer: Any) -> str:
    """Choose the most human-readable attribute field on a vector layer for labeling."""
    if layer is None or not hasattr(layer, "fields"):
        return ""
    fields = layer.fields()
    if len(fields) == 0:
        return ""

    preferred_tokens = ("name", "ad", "adi", "title", "label", "district", "ilce", "mahalle", "code", "kod", "type", "tur")
    for tok in preferred_tokens:
        for fld in fields:
            if tok in fld.name().lower():
                return fld.name()

    for fld in fields:
        if not fld.isNumeric():
            return fld.name()

    return fields[0].name()


def apply_smart_layer_labels(
    layer: Any,
    field_name: str = "",
    preset: str = "swiss_halo",
    use_callouts: bool = False,
    use_polylabel: bool = True,
    font_size: Optional[float] = None,
    min_scale: float = 0.0,
) -> bool:
    """
    Configure publication-ready PAL smart labeling on a ``QgsVectorLayer``.
    Supports halo buffers, pill badges, polygon interior placement, and leader-line callouts.
    """
    if (
        layer is None
        or QgsPalLayerSettings is None
        or QgsTextFormat is None
        or QgsVectorLayerSimpleLabeling is None
        or not hasattr(layer, "setLabeling")
    ):
        return False

    cfg = dict(SMART_LABEL_PRESETS.get(preset, SMART_LABEL_PRESETS["swiss_halo"]))
    target_field = field_name.strip() if field_name else ""
    is_expression = "[%" in target_field or "(" in target_field or "||" in target_field
    if not target_field:
        target_field = detect_best_label_field(layer)
    if not target_field:
        return False

    settings = QgsPalLayerSettings()
    settings.fieldName = target_field
    settings.isExpression = bool(is_expression)

    # Configure typography & halo
    pt_size = float(font_size) if font_size is not None and font_size > 0 else float(cfg.get("font_size", 8.5))
    tf = QgsTextFormat()
    font = QFont(str(cfg.get("font_family", "Segoe UI")), int(round(pt_size)))
    if hasattr(font, "setPointSizeF"):
        font.setPointSizeF(pt_size)
    font.setBold(bool(cfg.get("bold", True)))
    font.setItalic(bool(cfg.get("italic", False)))
    tf.setFont(font)
    tf.setSize(pt_size)
    if QColor is not None:
        tf.setColor(QColor(str(cfg.get("text_color", "#0f172a"))))

    if cfg.get("halo_enabled", True) and QgsTextBufferSettings is not None:
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(float(cfg.get("halo_size_mm", 1.0)))
        if QColor is not None:
            buf.setColor(QColor(str(cfg.get("halo_color", "#ffffff"))))
        buf.setOpacity(float(cfg.get("halo_opacity", 0.92)))
        tf.setBuffer(buf)

    if cfg.get("bg_enabled", False) and QgsTextBackgroundSettings is not None:
        bg = QgsTextBackgroundSettings()
        bg.setEnabled(True)
        shape_enum = getattr(QgsTextBackgroundSettings, "ShapeType", QgsTextBackgroundSettings)
        rect_shape = getattr(shape_enum, "ShapeRectangle", 0)
        with suppress(Exception):
            bg.setType(rect_shape)
        if QSizeF is not None:
            with suppress(Exception):
                bg.setSize(QSizeF(1.2, 0.7))
        if QColor is not None:
            with suppress(Exception):
                bg.setFillColor(QColor(str(cfg.get("bg_color", "#ffffff"))))
                bg.setStrokeColor(QColor(str(cfg.get("bg_stroke", "#475569"))))
                bg.setStrokeWidth(0.2)
        with suppress(Exception):
            bg.setRadii(QSizeF(0.8, 0.8))
        tf.setBackground(bg)

    settings.setFormat(tf)

    # Geometry-aware placement
    geom_type = layer.geometryType() if hasattr(layer, "geometryType") else -1
    placement_enum = getattr(QgsPalLayerSettings, "Placement", QgsPalLayerSettings)
    if QgsWkbTypes is not None:
        poly_geom = getattr(
            getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes),
            "PolygonGeometry",
            2,
        )
        line_geom = getattr(
            getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes),
            "LineGeometry",
            1,
        )
        if geom_type == poly_geom:
            with suppress(Exception):
                over_pt = getattr(placement_enum, "OverPoint", getattr(placement_enum, "AroundPoint", 0))
                settings.placement = over_pt
                if hasattr(settings, "centroidInside"):
                    settings.centroidInside = bool(use_polylabel)
                if hasattr(settings, " centroidWhole"):
                    settings.centroidWhole = True
        elif geom_type == line_geom:
            with suppress(Exception):
                 settings.placement = getattr(placement_enum, "Line", getattr(placement_enum, "Curved", 2))

    # Optional Callout Leader Lines
    enable_callout = bool(use_callouts or cfg.get("callout", False))
    if enable_callout and QgsSimpleLineCallout is not None and hasattr(settings, "setCallout"):
        with suppress(Exception):
            callout = QgsSimpleLineCallout()
            callout.setEnabled(True)
            if hasattr(callout, "setMinimumLength"):
                callout.setMinimumLength(1.5)
            if QgsLineSymbol is not None and hasattr(callout, "setLineSymbol"):
                line_sym = QgsLineSymbol.createSimple({
                    "color": str(cfg.get("callout_color", "#334155")),
                    "width": "0.3",
                })
                if line_sym is not None:
                    callout.setLineSymbol(line_sym)
            settings.setCallout(callout)
            if hasattr(settings, "dist"):
                settings.dist = 2.5

    if min_scale and float(min_scale) > 0:
        with suppress(Exception):
            settings.scaleVisibility = True
            settings.minimumScale = float(min_scale)

    labeling = QgsVectorLayerSimpleLabeling(settings)
    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)
    with suppress(Exception):
        layer.triggerRepaint()
    return True


def add_layout_callout_badge(
    layout: QgsLayout,
    text: str,
    subtitle: str = "",
    badge_number: Optional[int] = 1,
    position: Optional[Tuple[float, float]] = None,
    target_pos: Optional[Tuple[float, float]] = None,
    theme: str = "swiss_modern",
    size_mm: Tuple[float, float] = (58.0, 18.0),
    item_id: str = "cartolab_callout_badge",
) -> Optional[QgsLayoutItemLabel]:
    """
    Insert a styled HTML callout annotation badge with a leader line and focal
    target dot onto a Print Layout.
    """
    if layout is None or QgsLayoutItemLabel is None:
        return None

    for suffix in ("", "_line", "_dot"):
        with suppress(Exception):
            existing = layout.itemById(f"{item_id}{suffix}")
            if existing is not None:
                layout.removeLayoutItem(existing)

    primary_map = main_map_item(layout)
    w_mm = max(32.0, float(size_mm[0]))
    h_mm = max(12.0, float(size_mm[1]))

    if position is None:
        if primary_map is not None:
            mp = primary_map.pos()
            x_mm = float(mp.x()) + 8.0
            y_mm = float(mp.y()) + 8.0
        else:
            x_mm, y_mm = 18.0, 22.0
    else:
        x_mm, y_mm = float(position[0]), float(position[1])

    if target_pos is None:
        if primary_map is not None:
            mp = primary_map.pos()
            mr = primary_map.rect()
            tx_mm = float(mp.x()) + min(float(mr.width()) * 0.48, w_mm + 26.0)
            ty_mm = float(mp.y()) + min(float(mr.height()) * 0.45, h_mm + 24.0)
            target_pos = (tx_mm, ty_mm)
        else:
            target_pos = (x_mm + w_mm + 16.0, y_mm + h_mm + 12.0)

    pal = HTML_CARD_THEMES.get(theme, HTML_CARD_THEMES["swiss_modern"])
    badge_html = ""
    if badge_number is not None:
        badge_html = (
            f"<td width='20' valign='middle' align='center' bgcolor='{pal['accent']}' "
            f"style='color:#ffffff;font-size:7.5pt;font-weight:700;padding:2px 4px;'>"
            f"{int(badge_number)}</td>"
        )

    sub_div = (
        f"<div style='font-size:6.5pt;color:{pal['muted']};margin-top:1px;'>{_esc(subtitle)}</div>"
        if subtitle
        else ""
    )
    html_str = (
        f"<div style='font-family:{pal['font']};background-color:{pal['bg']};color:{pal['text']};"
        f"padding:3px 5px;border:1px solid {pal['accent']};'>"
        f"<table width='100%' cellspacing='0' cellpadding='0'><tr>"
        f"{badge_html}"
        f"<td valign='middle' style='padding-left:5px;'>"
        f"<div style='font-size:7.8pt;font-weight:700;color:{pal['text']};'>{_esc(text or 'Focal Area Callout')}</div>"
        f"{sub_div}"
        f"</td></tr></table></div>"
    )

    # 1. Leader polyline from callout card corner to target point
    tx, ty = float(target_pos[0]), float(target_pos[1])
    anchor_x = x_mm + w_mm if tx >= x_mm + w_mm * 0.5 else x_mm
    anchor_y = y_mm + h_mm * 0.5
    elbow_x = anchor_x + (6.0 if tx >= anchor_x else -6.0)

    if QgsLayoutItemPolyline is not None and QPolygonF is not None and QPointF is not None:
        with suppress(Exception):
            poly = QPolygonF([
                QPointF(anchor_x, anchor_y),
                QPointF(elbow_x, anchor_y),
                QPointF(tx, ty),
            ])
            line_item = QgsLayoutItemPolyline(poly, layout)
            line_item.setId(f"{item_id}_line")
            if QgsLineSymbol is not None:
                sym = QgsLineSymbol.createSimple({
                    "color": pal["accent"],
                    "width": "0.4",
                })
                if sym is not None:
                    line_item.setSymbol(sym)
            line_item.setCustomProperty("cartolab/is_callout_badge", True)
            layout.addLayoutItem(line_item)
            line_item.setZValue(48)

    # 2. Target focal marker dot
    if QgsLayoutItemShape is not None:
        with suppress(Exception):
            dot = QgsLayoutItemShape(layout)
            dot.setId(f"{item_id}_dot")
            shape_enum = getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape)
            ellipse_val = getattr(shape_enum, "Ellipse", 0)
            dot.setShapeType(ellipse_val)
            dot.attemptMove(QgsLayoutPoint(tx - 1.5, ty - 1.5, _MM))
            dot.attemptResize(QgsLayoutSize(3.0, 3.0, _MM))
            if QgsFillSymbol is not None:
                dsym = QgsFillSymbol.createSimple({
                    "color": pal["accent"],
                    "outline_color": "#ffffff",
                    "outline_width": "0.4",
                })
                if dsym is not None:
                    dot.setSymbol(dsym)
            dot.setCustomProperty("cartolab/is_callout_badge", True)
            layout.addLayoutItem(dot)
            dot.setZValue(49)

    # 3. Callout badge label
    lbl = QgsLayoutItemLabel(layout)
    lbl.setId(item_id)
    mode_enum = getattr(QgsLayoutItemLabel, "Mode", None)
    html_mode = getattr(mode_enum, "ModeHtml", getattr(QgsLayoutItemLabel, "ModeHtml", 1))
    with suppress(Exception):
        lbl.setMode(html_mode)
    lbl.setText(html_str)
    lbl.attemptMove(QgsLayoutPoint(x_mm, y_mm, _MM))
    lbl.attemptResize(QgsLayoutSize(w_mm, h_mm, _MM))
    if QColor is not None:
        with suppress(Exception):
            lbl.setBackgroundEnabled(True)
            lbl.setBackgroundColor(QColor(pal["bg"]))
            lbl.setFrameEnabled(True)
            if hasattr(lbl, "setFrameStrokeColor"):
                lbl.setFrameStrokeColor(QColor(pal["accent"]))
            if hasattr(lbl, "setFrameStrokeWidth") and QgsLayoutMeasurement is not None:
                lbl.setFrameStrokeWidth(QgsLayoutMeasurement(0.35, _MM))
    with suppress(Exception):
        lbl.setCustomProperty("cartolab/is_callout_badge", True)
        lbl.setCustomProperty("cartolab/is_html_card", True)
        lbl.setCustomProperty("cartolab/html_card_type", "callout_badge")
        lbl.setCustomProperty("cartolab/html_card_theme", theme)
    layout.addLayoutItem(lbl)
    with suppress(Exception):
        lbl.setZValue(50)
        layout.refresh()
    return lbl
