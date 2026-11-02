# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Automated Multi-Page Map Book & Atlas Builder.

Configures QGIS Print Layout Atlas engine for automatic serial map sheet production:
coverage layer binding, dynamic title expressions, page counters, auto-centering map frames,
scaling modes (Auto margin, Predefined scales, Fixed scale), active feature highlight rules,
dynamic HTML feature dossiers, rule validation, and memory-safe batch export.

Author: Yusuf Eminoğlu
"""
from __future__ import annotations

from contextlib import suppress
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from qgis.core import (
        QgsExpression,
        QgsExpressionContext,
        QgsExpressionContextUtils,
        QgsFillSymbol,
        QgsLayout,
        QgsLayoutExporter,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemScaleBar,
        QgsLayoutItemShape,
        QgsLayoutMeasurement,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsPrintLayout,
        QgsProject,
        QgsProperty,
        QgsSymbolLayer,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtGui import QColor, QFont
    _MM = getattr(
        getattr(QgsUnitTypes, "LayoutUnit", QgsUnitTypes),
        "LayoutMillimeters",
        getattr(QgsUnitTypes, "LayoutMillimeters", 0),
    )
except ImportError:
    QgsLayout = QgsLayoutItemLabel = QgsLayoutItemLegend = QgsLayoutItemMap = QgsLayoutItemShape = QgsLayoutItemScaleBar = None
    QgsLayoutMeasurement = QgsLayoutPoint = QgsLayoutSize = QgsPrintLayout = QgsProject = QgsUnitTypes = QgsVectorLayer = None
    QgsFillSymbol = QgsExpression = QgsExpressionContext = QgsExpressionContextUtils = None
    QgsLayoutExporter = QgsProperty = QgsSymbolLayer = QFont = QColor = None
    _MM = 0

from .html_cards import add_html_atlas_profile_card
from .layout_utils import clear_layout_render_cache, main_map_item
from .locator_map import add_locator_inset_map


ATLAS_SCALING_MODES: Dict[str, str] = {
    "auto": "Auto Margin (% around feature)",
    "predefined": "Predefined Standard Scales (1:1k, 1:5k, 1:10k...)",
    "fixed": "Fixed Map Scale (Keep current scale)",
}


def validate_atlas_rules(
    coverage_layer: Any,
    filter_expression: str = "",
    name_field: str = "",
    sort_field: str = "",
) -> Dict[str, Any]:
    """
    Validate Atlas coverage layer, filter expression, and naming/sorting rules.
    Returns live feature counts and preview page names for GUI feedback.
    """
    if coverage_layer is None or (hasattr(coverage_layer, "isValid") and not coverage_layer.isValid()):
        return {
            "valid": False,
            "total_count": 0,
            "matching_count": 0,
            "error": "No valid coverage vector layer selected.",
            "preview_names": [],
        }

    total_count = int(coverage_layer.featureCount()) if hasattr(coverage_layer, "featureCount") else 0
    if total_count <= 0:
        return {
            "valid": False,
            "total_count": 0,
            "matching_count": 0,
            "error": "Coverage layer contains 0 features.",
            "preview_names": [],
        }

    field_names = [f.name() for f in coverage_layer.fields()] if hasattr(coverage_layer, "fields") else []
    clean_filter = (filter_expression or "").strip()
    exp = None
    if clean_filter and QgsExpression is not None:
        exp = QgsExpression(clean_filter)
        if exp.hasParserError():
            return {
                "valid": False,
                "total_count": total_count,
                "matching_count": 0,
                "error": f"Filter syntax error: {exp.parserErrorString()}",
                "preview_names": [],
            }

    ctx = None
    if exp is not None and QgsExpressionContext is not None:
        ctx = QgsExpressionContext()
        if QgsExpressionContextUtils is not None and hasattr(QgsExpressionContextUtils, "createFeatureBasedContext"):
            with suppress(Exception):
                ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(coverage_layer))
        with suppress(Exception):
            exp.prepare(ctx)

    matching = 0
    preview: List[str] = []
    use_name = name_field if name_field in field_names else ""
    with suppress(Exception):
        for idx, feat in enumerate(coverage_layer.getFeatures()):
            if exp is not None and ctx is not None:
                ctx.setFeature(feat)
                res = exp.evaluate(ctx)
                if not res:
                    continue
            matching += 1
            if len(preview) < 5:
                if use_name and feat[use_name] is not None:
                    preview.append(str(feat[use_name]))
                else:
                    preview.append(f"Sheet {matching}")

    if matching == 0:
        return {
            "valid": False,
            "total_count": total_count,
            "matching_count": 0,
            "error": "Filter expression matched 0 features.",
            "preview_names": [],
        }

    return {
        "valid": True,
        "total_count": total_count,
        "matching_count": matching,
        "error": "",
        "preview_names": preview,
        "sort_field": sort_field if sort_field in field_names else "",
    }


def apply_atlas_highlight_rule(
    coverage_layer: Any,
    accent_color: str = "#e11d48",
    stroke_width_mm: float = 0.85,
) -> bool:
    """
    Apply a non-destructive data-defined stroke highlight (`$id = @atlas_featureid`)
    onto the coverage layer's symbol layers so the active Atlas feature stands out.
    """
    if (
        coverage_layer is None
        or QgsProperty is None
        or QgsSymbolLayer is None
        or not hasattr(coverage_layer, "renderer")
    ):
        return False

    renderer = coverage_layer.renderer()
    if renderer is None:
        return False

    prop_enum = getattr(QgsSymbolLayer, "Property", QgsSymbolLayer)
    stroke_col_key = getattr(
        prop_enum,
        "StrokeColor",
        getattr(prop_enum, "PropertyStrokeColor", getattr(QgsSymbolLayer, "PropertyStrokeColor", None)),
    )
    stroke_w_key = getattr(
        prop_enum,
        "StrokeWidth",
        getattr(prop_enum, "PropertyStrokeWidth", getattr(QgsSymbolLayer, "PropertyStrokeWidth", None)),
    )
    if stroke_col_key is None or stroke_w_key is None:
        return False

    safe_accent = accent_color if isinstance(accent_color, str) and accent_color.startswith("#") else "#e11d48"
    col_expr = f"CASE WHEN $id = @atlas_featureid THEN '{safe_accent}' ELSE '#334155' END"
    width_expr = f"CASE WHEN $id = @atlas_featureid THEN {float(stroke_width_mm):.2f} ELSE 0.25 END"

    symbols = []
    with suppress(Exception):
        if hasattr(renderer, "symbol") and callable(renderer.symbol) and renderer.symbol() is not None:
            symbols = [renderer.symbol()]
        elif hasattr(renderer, "symbols") and QgsExpressionContext is not None:
            symbols = list(renderer.symbols(QgsExpressionContext()))

    applied = False
    for sym in symbols:
        if sym is None or not hasattr(sym, "symbolLayers"):
            continue
        for sl in sym.symbolLayers():
            with suppress(Exception):
                sl.setDataDefinedProperty(stroke_col_key, QgsProperty.fromExpression(col_expr))
                sl.setDataDefinedProperty(stroke_w_key, QgsProperty.fromExpression(width_expr))
                applied = True

    with suppress(Exception):
        coverage_layer.setCustomProperty("cartolab/atlas_highlight_enabled", "1")
        coverage_layer.setCustomProperty("cartolab/atlas_highlight_color", safe_accent)
        coverage_layer.triggerRepaint()
        applied = True
    return applied



def setup_layout_atlas(
    layout: QgsLayout,
    coverage_layer: QgsVectorLayer,
    name_field: str = "",
    margin_percent: float = 10.0,
    *,
    page_margin_mm: float = 12.0,
    add_header_banner: bool = False,
    banner_title: str = "",
    banner_subtitle: str = "",
    add_overview_locator: bool = False,
    locator_corner: str = "bottom-right",
    locator_size_mm: Tuple[float, float] = (48.0, 40.0),
    locator_zoom_factor: float = 4.5,
    page_counter_format: str = "Sheet [% @atlas_featurenumber %] of [% @atlas_totalfeatures %]",
    filter_expression: str = "",
    sort_field: str = "",
    sort_ascending: bool = True,
    scaling_mode: str = "auto",
    highlight_active_feature: bool = False,
    highlight_color: str = "#e11d48",
    add_html_profile: bool = False,
    profile_fields: Optional[Sequence[Tuple[str, str]]] = None,
) -> bool:
    """
    Configure the layout's Atlas engine with dynamic titles, page counters, scaling modes,
    active feature highlighting, dynamic HTML dossiers, and auto-framing.
    """
    if layout is None or coverage_layer is None or QgsLayoutItemMap is None:
        return False

    if not hasattr(layout, "atlas"):
        # If a base QgsLayout C++ wrapper was passed, resolve the actual QgsPrintLayout from project layoutManager
        with suppress(Exception):
            if hasattr(layout, "name") and QgsProject and QgsProject.instance():
                resolved = QgsProject.instance().layoutManager().layoutByName(layout.name())
                if resolved and hasattr(resolved, "atlas"):
                    layout = resolved

    if not hasattr(layout, "atlas"):
        return False

    atlas = layout.atlas()
    if atlas is None:
        return False

    if filter_expression and QgsExpression is not None:
        expression = QgsExpression(filter_expression)
        if expression.hasParserError():
            return False

    # An atlas over an empty coverage layer produces no pages: report it.
    with suppress(Exception):
        if coverage_layer.featureCount() == 0:
            return False

    # Generated atlas furniture is replaced on repeated runs instead of stacked.
    for item in list(layout.items()):
        with suppress(Exception):
            if (item.id() or "").startswith("cartolab_atlas_"):
                layout.removeLayoutItem(item)

    # 1. Configure Atlas Engine
    atlas.setEnabled(True)
    atlas.setCoverageLayer(coverage_layer)

    if name_field and name_field in [f.name() for f in coverage_layer.fields()]:
        atlas.setPageNameExpression(f'"{name_field}"')
        atlas_title_expr = f'[% "{name_field}" %]'
    else:
        atlas.setPageNameExpression("concat('Sheet ', @atlas_featurenumber)")
        atlas_title_expr = "[% @atlas_pagename %]"

    if filter_expression:
        atlas.setFilterExpression(filter_expression)
        atlas.setFilterFeatures(True)
    else:
        atlas.setFilterFeatures(False)

    if sort_field and sort_field in [f.name() for f in coverage_layer.fields()]:
        atlas.setSortExpression(f'"{sort_field}"')
        atlas.setSortAscending(sort_ascending)
        atlas.setSortFeatures(True)
    else:
        atlas.setSortFeatures(False)

    # The filter may still match nothing; an atlas without pages is a failure.
    try:
        feature_count = int(atlas.updateFeatures())
    except Exception:
        feature_count = -1
    if feature_count <= 0:
        # 0 = filter matched nothing; -1 = the update itself raised. Either way
        # the atlas must not stay enabled in a half-configured state.
        atlas.setEnabled(False)
        return False

    # 2. Page Dimensions & Geometry Budget
    page = layout.pageCollection().page(0) if layout.pageCollection() else None
    page_w = page.pageSize().width() if page else 297.0
    page_h = page.pageSize().height() if page else 210.0

    banner_h = 22.0 if add_header_banner else 0.0
    top_offset = page_margin_mm + (banner_h + 4.0 if add_header_banner else 14.0)

    # 3. Find and link primary map frame
    main_map: Optional[QgsLayoutItemMap] = main_map_item(layout)

    if main_map is not None:
        main_map.setAtlasDriven(True)
        mode_ns = getattr(QgsLayoutItemMap, "AtlasScalingMode", QgsLayoutItemMap)
        mode_key = (scaling_mode or "auto").strip().lower()
        if mode_key == "fixed":
            resolved_mode = getattr(mode_ns, "Fixed", getattr(QgsLayoutItemMap, "Fixed", 0))
        elif mode_key == "predefined":
            resolved_mode = getattr(mode_ns, "Predefined", getattr(QgsLayoutItemMap, "Predefined", 1))
        else:
            resolved_mode = getattr(mode_ns, "Auto", getattr(QgsLayoutItemMap, "Auto", 2))
        main_map.setAtlasScalingMode(resolved_mode)
        main_map.setAtlasMargin(max(0.0, float(margin_percent)) / 100.0)

        # Apply page margins if banner or custom margins requested
        if add_header_banner:
            map_w = page_w - (2 * page_margin_mm)
            map_h = page_h - top_offset - page_margin_mm - 12.0
            if map_h > 40.0:
                main_map.attemptMove(QgsLayoutPoint(page_margin_mm, top_offset, _MM))
                main_map.attemptResize(QgsLayoutSize(map_w, map_h, _MM))

                # Reposition scalebar, north arrow, and legend if present
                for it in layout.items():
                    if QgsLayoutItemScaleBar is not None and isinstance(it, QgsLayoutItemScaleBar):
                        it.attemptMove(QgsLayoutPoint(page_margin_mm, top_offset + map_h + 2.0, _MM))
                    elif hasattr(it, "id") and it.id() == "cartolab_north_arrow":
                        it.attemptMove(QgsLayoutPoint(page_margin_mm + map_w - 12.0, top_offset + 3.0, _MM))
                    elif hasattr(it, "id") and it.id() == "cartolab_north_arrow_label":
                        it.attemptMove(QgsLayoutPoint(page_margin_mm + map_w - 9.5, top_offset + 1.0, _MM))
                    elif QgsLayoutItemLegend is not None and isinstance(it, QgsLayoutItemLegend):
                        it.setBackgroundColor(QColor(255, 255, 255, 235))
                        it.setBackgroundEnabled(True)
                        it.setFrameEnabled(True)
                        it.setFrameStrokeColor(QColor("#cbd5e1"))
                        it.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, _MM))
                        it.attemptMove(QgsLayoutPoint(page_w - page_margin_mm - 48.0, top_offset + 3.0, _MM))

    # 4. Custom Top Header Banner or Standard Dynamic Labels
    if add_header_banner:
        # Background card across top
        banner_w = page_w - (2 * page_margin_mm)
        if QgsLayoutItemShape is not None:
            banner_card = QgsLayoutItemShape(layout)
            banner_card.setId("cartolab_atlas_banner")
            rectangle = getattr(
                getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape),
                "Rectangle", getattr(QgsLayoutItemShape, "Rectangle", 0),
            )
            banner_card.setShapeType(rectangle)
            banner_card.attemptMove(QgsLayoutPoint(page_margin_mm, page_margin_mm, _MM))
            banner_card.attemptResize(QgsLayoutSize(banner_w, banner_h, _MM))
            if QgsFillSymbol is not None:
                sym = QgsFillSymbol.createSimple({
                    "color": "#0f172a",
                    "outline_color": "#2563eb",
                    "outline_width": "0.4",
                })
                if sym:
                    banner_card.setSymbol(sym)
            layout.addLayoutItem(banner_card)

        # Header Title (Dynamic)
        title_text = banner_title if banner_title else f"Map Series: {atlas_title_expr}"
        lbl_b_title = QgsLayoutItemLabel(layout)
        lbl_b_title.setId("cartolab_atlas_title")
        lbl_b_title.setText(title_text)
        lbl_b_title.setBackgroundEnabled(False)
        lbl_b_title.setFrameEnabled(False)
        if QFont is not None:
            f_title = QFont("Segoe UI", 12)
            f_title.setBold(True)
            lbl_b_title.setFont(f_title)
        if QColor is not None:
            lbl_b_title.setFontColor(QColor("#ffffff"))
        lbl_b_title.attemptMove(QgsLayoutPoint(page_margin_mm + 4.0, page_margin_mm + 2.5, _MM))
        lbl_b_title.attemptResize(QgsLayoutSize(banner_w - 70.0, 8.0, _MM))
        layout.addLayoutItem(lbl_b_title)

        # Header Subtitle
        sub_text = banner_subtitle if banner_subtitle else "Automated Atlas Map Book · PlanX CartoLab"
        lbl_b_sub = QgsLayoutItemLabel(layout)
        lbl_b_sub.setId("cartolab_atlas_subtitle")
        lbl_b_sub.setText(sub_text)
        lbl_b_sub.setBackgroundEnabled(False)
        lbl_b_sub.setFrameEnabled(False)
        if QFont is not None:
            f_sub = QFont("Segoe UI", 8)
            lbl_b_sub.setFont(f_sub)
        if QColor is not None:
            lbl_b_sub.setFontColor(QColor("#94a3b8"))
        lbl_b_sub.attemptMove(QgsLayoutPoint(page_margin_mm + 4.0, page_margin_mm + 11.5, _MM))
        lbl_b_sub.attemptResize(QgsLayoutSize(banner_w - 70.0, 6.0, _MM))
        layout.addLayoutItem(lbl_b_sub)

        # Dynamic Page Counter on Right of Banner
        lbl_b_counter = QgsLayoutItemLabel(layout)
        lbl_b_counter.setId("cartolab_atlas_counter")
        lbl_b_counter.setText(page_counter_format)
        lbl_b_counter.setBackgroundEnabled(False)
        lbl_b_counter.setFrameEnabled(False)
        if QFont is not None:
            f_counter = QFont("Segoe UI", 9)
            f_counter.setBold(True)
            lbl_b_counter.setFont(f_counter)
        if QColor is not None:
            lbl_b_counter.setFontColor(QColor("#38bdf8"))
        lbl_b_counter.attemptMove(QgsLayoutPoint(page_w - page_margin_mm - 65.0, page_margin_mm + 6.0, _MM))
        lbl_b_counter.attemptResize(QgsLayoutSize(60.0, 8.0, _MM))
        layout.addLayoutItem(lbl_b_counter)

    else:
        # Standard Title & Page Counter labels if not already present
        has_atlas_title = any(isinstance(it, QgsLayoutItemLabel) and "atlas" in it.text().lower() for it in layout.items())
        has_counter = any(isinstance(it, QgsLayoutItemLabel) and "@atlas_featurenumber" in it.text() for it in layout.items())
        sheet_title = layout.itemById("cartolab_title")
        if isinstance(sheet_title, QgsLayoutItemLabel):
            # A map sheet already owns the title row: make that title
            # atlas-aware and fit the counter into the row's right end
            # instead of stacking new labels on top of it.
            if not has_atlas_title:
                sheet_title.setText(f"{sheet_title.text()} · {atlas_title_expr}")
            if not has_counter:
                title_pos = sheet_title.positionWithUnits()
                title_size = sheet_title.sizeWithUnits()
                # Repeated runs start from the title's pre-atlas width.
                full_w = sheet_title.customProperty("cartolab/pre_atlas_width")
                if full_w:
                    title_size = QgsLayoutSize(float(full_w), title_size.height(), title_size.units())
                else:
                    sheet_title.setCustomProperty("cartolab/pre_atlas_width", float(title_size.width()))
                counter_w = min(63.0, title_size.width() * 0.4)
                sheet_title.attemptResize(QgsLayoutSize(
                    title_size.width() - counter_w - 2.0, title_size.height(), title_size.units()))
                lbl_counter = QgsLayoutItemLabel(layout)
                lbl_counter.setId("cartolab_atlas_counter")
                lbl_counter.setText(page_counter_format)
                if QFont is not None:
                    lbl_counter.setFont(QFont("Inter, Segoe UI", 10, QFont.Weight.DemiBold))
                if QColor is not None:
                    lbl_counter.setFontColor(QColor("#64748b"))
                with suppress(Exception):
                    from qgis.PyQt.QtCore import Qt
                    lbl_counter.setHAlign(Qt.AlignmentFlag.AlignRight)
                lbl_counter.attemptMove(QgsLayoutPoint(
                    title_pos.x() + title_size.width() - counter_w, title_pos.y(), title_pos.units()))
                lbl_counter.attemptResize(QgsLayoutSize(counter_w, title_size.height(), title_size.units()))
                layout.addLayoutItem(lbl_counter)
            has_atlas_title = has_counter = True

        if not has_atlas_title:
            lbl_title = QgsLayoutItemLabel(layout)
            lbl_title.setId("cartolab_atlas_title")
            lbl_title.setText(f"Map Series: {atlas_title_expr}")
            if QFont is not None:
                lbl_title.setFont(QFont("Inter, Segoe UI", 16, QFont.Weight.Bold))
            if QColor is not None:
                lbl_title.setFontColor(QColor("#0f172a"))
            lbl_title.attemptMove(QgsLayoutPoint(page_margin_mm, page_margin_mm - 2.0, _MM))
            lbl_title.attemptResize(QgsLayoutSize(page_w - 90.0, 12.0, _MM))
            layout.addLayoutItem(lbl_title)

        if not has_counter:
            lbl_counter = QgsLayoutItemLabel(layout)
            lbl_counter.setId("cartolab_atlas_counter")
            lbl_counter.setText(page_counter_format)
            if QFont is not None:
                lbl_counter.setFont(QFont("Inter, Segoe UI", 10, QFont.Weight.DemiBold))
            if QColor is not None:
                lbl_counter.setFontColor(QColor("#64748b"))
            lbl_counter.attemptMove(QgsLayoutPoint(page_w - 75.0, page_margin_mm, _MM))
            lbl_counter.attemptResize(QgsLayoutSize(63.0, 8.0, _MM))
            layout.addLayoutItem(lbl_counter)

    # 5. Overview Locator Inset Map (Optional)
    if add_overview_locator and main_map is not None:
        add_locator_inset_map(
            layout,
            main_map=main_map,
            size_mm=locator_size_mm,
            zoom_factor=locator_zoom_factor,
            corner=locator_corner,
            add_header=True,
        )

    # 6. Active Feature Highlight Rule (Optional)
    if highlight_active_feature:
        apply_atlas_highlight_rule(coverage_layer, accent_color=highlight_color)

    # 7. Dynamic HTML Feature Profile Card (Optional)
    if add_html_profile:
        add_html_atlas_profile_card(
            layout,
            coverage_layer=coverage_layer,
            fields=profile_fields,
            title_expr=atlas_title_expr,
            item_id="cartolab_atlas_html_profile",
        )

    layout.refresh()
    return True


def export_atlas_series(
    layout: QgsLayout,
    output_dir: str,
    dpi: int = 300,
    max_pages: int = 0,
    file_prefix: str = "atlas_sheet",
) -> Dict[str, Any]:
    """
    Export each page of a configured Print Layout Atlas to PNG images while
    flushing the render cache between pages (`clear_layout_render_cache`) to
    prevent memory bloat across multi-page exports.
    """
    if layout is None or QgsLayoutExporter is None or not hasattr(layout, "atlas"):
        return {"exported_count": 0, "files": [], "error": "Atlas layout or exporter unavailable."}

    atlas = layout.atlas()
    if atlas is None or not atlas.enabled():
        return {"exported_count": 0, "files": [], "error": "Atlas is not enabled on this layout."}

    os.makedirs(output_dir, exist_ok=True)
    total = int(atlas.updateFeatures())
    if total <= 0:
        return {"exported_count": 0, "files": [], "error": "Atlas matched 0 features."}

    limit = min(total, int(max_pages)) if max_pages and int(max_pages) > 0 else total
    exported_files: List[str] = []
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = max(72, int(dpi))

    if not atlas.beginRender():
        return {"exported_count": 0, "files": [], "error": "Atlas beginRender() failed."}

    try:
        for idx in range(limit):
            if not atlas.seekTo(idx):
                continue
            raw_name = ""
            if hasattr(atlas, "nameForPage"):
                with suppress(Exception):
                    raw_name = str(atlas.nameForPage(idx) or "")
            safe_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_name).strip("_") or f"p{idx + 1:02d}"
            out_path = os.path.join(output_dir, f"{file_prefix}_{idx + 1:02d}_{safe_slug}.png")
            res = exporter.exportToImage(out_path, settings)
            ok_code = getattr(
                getattr(QgsLayoutExporter, "ExportResult", QgsLayoutExporter),
                "Success",
                0,
            )
            if res == ok_code and os.path.exists(out_path):
                exported_files.append(out_path)
            clear_layout_render_cache(layout)
    finally:
        with suppress(Exception):
            atlas.endRender()

    return {
        "exported_count": len(exported_files),
        "total_features": total,
        "files": exported_files,
        "error": "",
    }

