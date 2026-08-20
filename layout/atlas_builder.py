# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Automated Multi-Page Map Book & Atlas Builder.

Configures QGIS Print Layout Atlas engine for automatic serial map sheet production:
coverage layer binding, dynamic title expressions, page counters, auto-centering map frames,
custom header banners, configurable page margins, and overview locator inset maps.

Author: Yusuf Eminoğlu
"""
from __future__ import annotations

from contextlib import suppress
from typing import Optional, Tuple

try:
    from qgis.core import (
        QgsFillSymbol,
        QgsLayout,
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
    QgsFillSymbol = QFont = QColor = None
    _MM = 0

from .locator_map import add_locator_inset_map


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
) -> bool:
    """
    Configure the layout's Atlas engine with dynamic titles, page counters, and auto-framing.

    Enhancements:
      - Custom styled top header banner card with dynamic title and subtitle.
      - Adaptive page margins and map frame positioning.
      - Overview locator inset map linked to atlas coverage features.
      - Filter and sort expressions for ordered atlas generation.
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
        with suppress(Exception):
            atlas.setFilterExpression(filter_expression)
            atlas.setFilterFeatures(True)

    if sort_field and sort_field in [f.name() for f in coverage_layer.fields()]:
        with suppress(Exception):
            atlas.setSortKeyAttributeName(sort_field)
            atlas.setSortAscending(sort_ascending)

    # 2. Page Dimensions & Geometry Budget
    page = layout.pageCollection().page(0) if layout.pageCollection() else None
    page_w = page.pageSize().width() if page else 297.0
    page_h = page.pageSize().height() if page else 210.0

    banner_h = 22.0 if add_header_banner else 0.0
    top_offset = page_margin_mm + (banner_h + 4.0 if add_header_banner else 14.0)

    # 3. Find and link primary map frame
    main_map: Optional[QgsLayoutItemMap] = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap) and item.id() != "cartolab_locator_inset":
            main_map = item
            break

    if main_map is not None:
        main_map.setAtlasDriven(True)
        _AutoScaling = getattr(
            getattr(QgsLayoutItemMap, "AtlasScalingMode", QgsLayoutItemMap),
            "Auto",
            getattr(QgsLayoutItemMap, "Auto", 0),
        )
        main_map.setAtlasScalingMode(_AutoScaling)
        main_map.setAtlasMargin(margin_percent / 100.0)

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
            if hasattr(QgsLayoutItemShape, "Shape") and hasattr(QgsLayoutItemShape.Shape, "Rectangle"):
                banner_card.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
            elif hasattr(QgsLayoutItemShape, "Rectangle"):
                banner_card.setShapeType(QgsLayoutItemShape.Rectangle)
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
        if not has_atlas_title:
            lbl_title = QgsLayoutItemLabel(layout)
            lbl_title.setText(f"Map Series: {atlas_title_expr}")
            if QFont is not None:
                lbl_title.setFont(QFont("Inter, Segoe UI", 16, QFont.Weight.Bold))
            if QColor is not None:
                lbl_title.setFontColor(QColor("#0f172a"))
            lbl_title.attemptMove(QgsLayoutPoint(page_margin_mm, page_margin_mm - 2.0, _MM))
            lbl_title.attemptResize(QgsLayoutSize(page_w - 90.0, 12.0, _MM))
            layout.addLayoutItem(lbl_title)

        has_counter = any(isinstance(it, QgsLayoutItemLabel) and "@atlas_featurenumber" in it.text() for it in layout.items())
        if not has_counter:
            lbl_counter = QgsLayoutItemLabel(layout)
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

    layout.refresh()
    return True
