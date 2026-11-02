# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Print Layout HTML Display & KPI Card Engine.

Creates publication-ready HTML cards, KPI summary blocks, ranked attribute
tables, dynamic Atlas feature dossiers, and metadata blocks inside QGIS Print
Layouts. Uses ``QgsLayoutItemLabel`` in HTML mode (`ModeHtml`) so expressions
(`[% ... %]`) evaluate natively and exports render deterministically in
headless/offscreen environments without WebEngine dependencies.

Author: Yusuf Eminoğlu
"""
from __future__ import annotations

from contextlib import suppress
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemLabel,
        QgsLayoutItemMap,
        QgsLayoutItemPage,
        QgsLayoutMeasurement,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtGui import QColor, QFont
except ImportError:
    QgsLayout = QgsLayoutItemLabel = QgsLayoutItemMap = QgsLayoutItemPage = None
    QgsLayoutMeasurement = QgsLayoutPoint = QgsLayoutSize = QgsUnitTypes = QgsVectorLayer = None
    QColor = QFont = None

from ..core.html_graph_factory import (
    HTML_CARD_THEMES,
    build_atlas_profile_html,
    build_attribute_table_html,
    build_kpi_summary_html,
    build_metadata_badge_html,
)
from .charts.placement import best_position
from .layout_utils import layout_page_size_mm, main_map_item

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0


def _enable_label_html_mode(label_item: Any) -> None:
    """Enable HTML rendering mode on a QgsLayoutItemLabel across QGIS 3 & 4."""
    if label_item is None or not hasattr(label_item, "setMode"):
        return
    mode_enum = getattr(QgsLayoutItemLabel, "Mode", None)
    html_mode = getattr(mode_enum, "ModeHtml", getattr(QgsLayoutItemLabel, "ModeHtml", 1))
    with suppress(Exception):
        label_item.setMode(html_mode)


def _smart_html_card_position(
    layout: QgsLayout,
    width_mm: float,
    height_mm: float,
    explicit_pos: Optional[Tuple[float, float]] = None,
) -> Tuple[float, float]:
    """Compute a non-overlapping placement for an HTML card on the layout page."""
    if explicit_pos is not None:
        return float(explicit_pos[0]), float(explicit_pos[1])
    page_w, page_h = layout_page_size_mm(layout)
    occupied: List[Tuple[Tuple[float, float, float, float], float]] = []
    if layout is not None:
        for item in layout.items():
            if not hasattr(item, "id") or not hasattr(item, "pos"):
                continue
            if QgsLayoutItemPage is not None and isinstance(item, QgsLayoutItemPage):
                continue
            if QgsLayoutItemMap is not None and isinstance(item, QgsLayoutItemMap):
                if item.id() != "cartolab_locator_inset":
                    continue
            with suppress(Exception):
                pos = item.pos()
                rect = item.rect()
                w = float(rect.width())
                h = float(rect.height())
                if w > 1.0 and h > 1.0:
                    occupied.append(((float(pos.x()), float(pos.y()), w, h), 4.0))
    return best_position(page_w, page_h, width_mm, height_mm, occupied)


def _create_html_label_item(
    layout: QgsLayout,
    item_id: str,
    html_content: str,
    card_type: str,
    theme: str = "swiss_modern",
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (80.0, 44.0),
    replace_existing: bool = True,
) -> Optional[QgsLayoutItemLabel]:
    """Create or replace a styled HTML card item in a Print Layout."""
    if layout is None or QgsLayoutItemLabel is None:
        return None

    if replace_existing and item_id:
        with suppress(Exception):
            existing = layout.itemById(item_id)
            if existing is not None:
                layout.removeLayoutItem(existing)

    w_mm = max(28.0, float(size_mm[0]))
    h_mm = max(16.0, float(size_mm[1]))
    x_mm, y_mm = _smart_html_card_position(layout, w_mm, h_mm, position)

    pal = HTML_CARD_THEMES.get(theme, HTML_CARD_THEMES["swiss_modern"])
    lbl = QgsLayoutItemLabel(layout)
    lbl.setId(item_id)
    _enable_label_html_mode(lbl)
    lbl.setText(html_content)
    lbl.attemptMove(QgsLayoutPoint(x_mm, y_mm, _MM))
    lbl.attemptResize(QgsLayoutSize(w_mm, h_mm, _MM))

    if hasattr(lbl, "setMarginX") and hasattr(lbl, "setMarginY"):
        with suppress(Exception):
            lbl.setMarginX(1.2)
            lbl.setMarginY(1.2)

    if QColor is not None:
        with suppress(Exception):
            lbl.setBackgroundEnabled(True)
            lbl.setBackgroundColor(QColor(pal["bg"]))
            lbl.setFrameEnabled(True)
            if hasattr(lbl, "setFrameStrokeColor"):
                lbl.setFrameStrokeColor(QColor(pal["border"]))
            if hasattr(lbl, "setFrameStrokeWidth") and QgsLayoutMeasurement is not None:
                lbl.setFrameStrokeWidth(QgsLayoutMeasurement(0.25, _MM))

    with suppress(Exception):
        lbl.setCustomProperty("cartolab/is_html_card", True)
        lbl.setCustomProperty("cartolab/html_card_type", card_type)
        lbl.setCustomProperty("cartolab/html_card_theme", theme)

    layout.addLayoutItem(lbl)
    with suppress(Exception):
        lbl.setZValue(45)
        layout.refresh()
    return lbl


def _format_number(val: float) -> str:
    if not math.isfinite(val):
        return "—"
    abs_v = abs(val)
    if abs_v >= 1_000_000:
        return f"{val / 1_000_000:,.2f}M"
    if abs_v >= 10_000:
        return f"{val:,.0f}"
    if abs_v >= 100 or abs(val - round(val)) < 1e-6:
        return f"{val:,.1f}".rstrip("0").rstrip(".")
    return f"{val:.2f}"


def _extract_numeric_stats(layer: Any, value_field: str = "") -> Tuple[str, List[float]]:
    """Extract numeric values from a QgsVectorLayer for KPI calculation."""
    if layer is None or not hasattr(layer, "fields") or not hasattr(layer, "getFeatures"):
        return "", []
    fields = layer.fields()
    chosen_field = value_field
    if not chosen_field or fields.indexFromName(chosen_field) < 0:
        for fld in fields:
            if fld.isNumeric() and fld.name().lower() not in ("id", "fid", "objectid", "gid"):
                chosen_field = fld.name()
                break
        if not chosen_field:
            for fld in fields:
                if fld.isNumeric():
                    chosen_field = fld.name()
                    break
    if not chosen_field or fields.indexFromName(chosen_field) < 0:
        return "", []

    vals: List[float] = []
    with suppress(Exception):
        for feat in layer.getFeatures():
            raw = feat[chosen_field]
            if raw is not None:
                v = float(raw)
                if math.isfinite(v):
                    vals.append(v)
    return chosen_field, vals


def add_html_kpi_card(
    layout: QgsLayout,
    layer: Optional[Any] = None,
    value_field: str = "",
    title: str = "",
    subtitle: str = "",
    metrics: Optional[Sequence[Dict[str, Any]]] = None,
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (82.0, 44.0),
    item_id: str = "cartolab_html_kpi_card",
) -> Optional[QgsLayoutItemLabel]:
    """
    Build and insert an Executive KPI Summary HTML Card into a Print Layout.
    Automatically computes summary statistics from ``layer`` if ``metrics`` is omitted.
    """
    computed_metrics: List[Dict[str, Any]] = list(metrics or [])
    resolved_title = title
    resolved_sub = subtitle

    if not computed_metrics and layer is not None:
        fld_name, nums = _extract_numeric_stats(layer, value_field)
        feat_count = int(layer.featureCount()) if hasattr(layer, "featureCount") else len(nums)
        if not resolved_title:
            resolved_title = f"{layer.name().upper()} — KPI SUMMARY"
        if nums:
            mean_v = sum(nums) / len(nums)
            min_v = min(nums)
            max_v = max(nums)
            span = max(1e-9, max_v - min_v)
            mean_pct = ((mean_v - min_v) / span) * 100.0
            if not resolved_sub:
                resolved_sub = f"Indicator: {fld_name} (n = {len(nums)})"
            computed_metrics = [
                {"label": "Features", "value": str(feat_count), "pct": 100.0},
                {"label": f"Mean {fld_name}", "value": _format_number(mean_v), "pct": mean_pct},
                {"label": f"Min {fld_name}", "value": _format_number(min_v), "pct": 20.0},
                {"label": f"Max {fld_name}", "value": _format_number(max_v), "pct": 95.0},
            ]
        else:
            crs_id = layer.crs().authid() if hasattr(layer, "crs") and layer.crs().isValid() else "EPSG:4326"
            computed_metrics = [
                {"label": "Feature Count", "value": str(feat_count), "pct": 100.0},
                {"label": "Layer CRS", "value": crs_id},
            ]

    if not resolved_title:
        resolved_title = "KEY SPATIAL INDICATORS"

    html_str = build_kpi_summary_html(
        title=resolved_title,
        metrics=computed_metrics,
        subtitle=resolved_sub,
        theme=theme,
        accent_color=accent_color,
    )
    return _create_html_label_item(
        layout=layout,
        item_id=item_id,
        html_content=html_str,
        card_type="kpi_summary",
        theme=theme,
        position=position,
        size_mm=size_mm,
    )


def add_html_attribute_table(
    layout: QgsLayout,
    layer: Optional[Any] = None,
    category_field: str = "",
    value_field: str = "",
    top_n: int = 5,
    title: str = "",
    subtitle: str = "",
    headers: Optional[Sequence[str]] = None,
    rows: Optional[Sequence[Sequence[Any]]] = None,
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (88.0, 50.0),
    item_id: str = "cartolab_html_table_card",
) -> Optional[QgsLayoutItemLabel]:
    """
    Build and insert a Top-N Attribute Summary HTML Table into a Print Layout.
    """
    table_headers: List[str] = list(headers or [])
    table_rows: List[Sequence[Any]] = list(rows or [])
    resolved_title = title
    resolved_sub = subtitle

    if not table_rows and layer is not None and hasattr(layer, "fields"):
        fields = layer.fields()
        field_names = [f.name() for f in fields]
        cat_f = category_field if category_field in field_names else ""
        if not cat_f:
            for f in fields:
                if not f.isNumeric():
                    cat_f = f.name()
                    break
            if not cat_f and field_names:
                cat_f = field_names[0]

        val_f, _ = _extract_numeric_stats(layer, value_field)
        records: List[Tuple[str, float]] = []
        with suppress(Exception):
            for idx, feat in enumerate(layer.getFeatures()):
                c_val = str(feat[cat_f]) if cat_f and feat[cat_f] is not None else f"Feature {idx + 1}"
                v_num = 0.0
                if val_f and feat[val_f] is not None:
                    with suppress(Exception):
                        v_num = float(feat[val_f])
                records.append((c_val, v_num))

        if val_f:
            records.sort(key=lambda r: r[1], reverse=True)
            total_val = sum(max(0.0, r[1]) for r in records) or 1.0
            table_headers = ["#", cat_f or "Name", val_f, "Share"]
            for rank, (c_name, v_num) in enumerate(records[: max(1, int(top_n))], start=1):
                share = f"{(max(0.0, v_num) / total_val) * 100.0:.1f}%"
                table_rows.append([str(rank), c_name[:22], _format_number(v_num), share])
        else:
            table_headers = ["#", cat_f or "Feature"]
            for rank, (c_name, _) in enumerate(records[: max(1, int(top_n))], start=1):
                table_rows.append([str(rank), c_name[:28]])

        if not resolved_title:
            resolved_title = f"TOP {min(len(table_rows), max(1, int(top_n)))} — {layer.name().upper()}"
        if not resolved_sub and val_f:
            resolved_sub = f"Ranked descending by {val_f}"

    if not table_headers:
        table_headers = ["Rank", "Category", "Value"]
    if not resolved_title:
        resolved_title = "ATTRIBUTE RANKING TABLE"

    html_str = build_attribute_table_html(
        title=resolved_title,
        headers=table_headers,
        rows=table_rows,
        subtitle=resolved_sub,
        theme=theme,
        accent_color=accent_color,
    )
    return _create_html_label_item(
        layout=layout,
        item_id=item_id,
        html_content=html_str,
        card_type="attribute_table",
        theme=theme,
        position=position,
        size_mm=size_mm,
    )


def add_html_atlas_profile_card(
    layout: QgsLayout,
    coverage_layer: Optional[Any] = None,
    fields: Optional[Sequence[Tuple[str, str]]] = None,
    title_expr: str = "[% @atlas_pagename %]",
    subtitle: str = "ATLAS FEATURE DOSSIER",
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (80.0, 46.0),
    item_id: str = "cartolab_html_atlas_profile",
) -> Optional[QgsLayoutItemLabel]:
    """
    Build and insert a dynamic `[% ... %]` expression-driven HTML Dossier Card
    that automatically updates for each `@atlas_feature` during Atlas rendering.
    """
    resolved_fields: List[Tuple[str, str]] = list(fields or [])
    if not resolved_fields and coverage_layer is not None and hasattr(coverage_layer, "fields"):
        for fld in coverage_layer.fields():
            fname = fld.name()
            label = fname.replace("_", " ").title()
            resolved_fields.append((label, fname))
            if len(resolved_fields) >= 4:
                break
        resolved_fields.append(("Area / Geometry", "[% round($area, 1) %]"))

    html_str = build_atlas_profile_html(
        title_expr=title_expr,
        fields=resolved_fields,
        subtitle=subtitle,
        theme=theme,
        accent_color=accent_color,
    )
    return _create_html_label_item(
        layout=layout,
        item_id=item_id,
        html_content=html_str,
        card_type="atlas_profile",
        theme=theme,
        position=position,
        size_mm=size_mm,
    )


def add_html_metadata_card(
    layout: QgsLayout,
    author: str = "Yusuf Eminoğlu",
    source: str = "PlanX CartoLab",
    title: str = "CARTOGRAPHIC METADATA",
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
    position: Optional[Tuple[float, float]] = None,
    size_mm: Tuple[float, float] = (74.0, 38.0),
    item_id: str = "cartolab_html_metadata_card",
) -> Optional[QgsLayoutItemLabel]:
    """
    Build and insert a structured publication metadata & citation HTML card.
    """
    crs_authid = "EPSG:4326"
    scale_text = "Auto"
    primary_map = main_map_item(layout) if layout is not None else None
    if primary_map is not None:
        with suppress(Exception):
            if primary_map.crs().isValid():
                crs_authid = primary_map.crs().authid()
            sc = float(primary_map.scale())
            if sc > 0 and math.isfinite(sc):
                scale_text = f"1:{int(round(sc)):,}"

    html_str = build_metadata_badge_html(
        title=title,
        author=author,
        crs_authid=crs_authid,
        scale_text=scale_text,
        source=source,
        theme=theme,
        accent_color=accent_color,
    )
    return _create_html_label_item(
        layout=layout,
        item_id=item_id,
        html_content=html_str,
        card_type="metadata_badge",
        theme=theme,
        position=position,
        size_mm=size_mm,
    )
