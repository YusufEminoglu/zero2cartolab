# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Visual Balance & Margin Optimizer.

Automatically inspects and adjusts print layout items (Map frame, Title block, Legend,
Scale bar, North arrow) to follow Swiss/National Geographic visual hierarchy principles:
consistent margins, non-overlapping items, balanced whitespace, and aligned anchors.
Supports multiple layout archetypes: Editorial Bottom Bar, Right Sidebar, and Left Sidebar.
"""
from __future__ import annotations

from typing import Optional

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItem,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsLayoutItemPolygon,
        QgsLayoutItemScaleBar,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
        QgsRectangle,
    )
except ImportError:
    QgsLayout = QgsLayoutItem = QgsLayoutItemLabel = QgsLayoutItemLegend = QgsLayoutItemMap = QgsLayoutItemPicture = QgsLayoutItemPolygon = QgsLayoutItemScaleBar = QgsLayoutPoint = QgsLayoutSize = QgsUnitTypes = QgsRectangle = None

from .layout_utils import main_map_item


def _move_item_cluster(items, x: float, y: float, unit) -> None:
    """Move related layout items together while preserving their offsets."""
    positioned = []
    for item in items:
        try:
            pos = item.positionWithUnits()
            positioned.append((item, float(pos.x()), float(pos.y())))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    if not positioned:
        return
    min_x = min(pos_x for _, pos_x, _ in positioned)
    min_y = min(pos_y for _, _, pos_y in positioned)
    for item, pos_x, pos_y in positioned:
        item.attemptMove(QgsLayoutPoint(x + pos_x - min_x, y + pos_y - min_y, unit))


def _cluster_size(items):
    """Width/height (layout units) of the joint bounding box of ``items``."""
    rect = None
    for item in items:
        try:
            r = item.sceneBoundingRect()
        except (AttributeError, RuntimeError):
            continue
        rect = r if rect is None else rect.united(r)
    if rect is None:
        return 0.0, 0.0
    return float(rect.width()), float(rect.height())


def optimize_layout_visual_balance(
    layout: QgsLayout,
    margin_mm: float = 12.0,
    bottom_bar_height_mm: float = 24.0,
    title_height_mm: float = 16.0,
    archetype: str = "editorial_bottom",
) -> bool:
    """
    Auto-arrange and align layout elements for optimal publication balance and readability.
    
    Archetypes:
      - 'editorial_bottom': Title at top, full map in center, metadata & legend row at bottom.
      - 'sidebar_right': Primary map on left, dedicated vertical title/legend/scale sidebar on right.
      - 'sidebar_left': Dedicated vertical title/legend/scale sidebar on left, primary map on right.
    """
    if layout is None or QgsLayoutItemMap is None:
        return False

    page = layout.pageCollection().page(0)
    if page is None:
        return False

    page_w = page.pageSize().width()
    page_h = page.pageSize().height()

    main_map: Optional[QgsLayoutItemMap] = main_map_item(layout)
    title_item: Optional[QgsLayoutItemLabel] = None
    subtitle_item: Optional[QgsLayoutItemLabel] = None
    credits_item: Optional[QgsLayoutItemLabel] = None
    legend_item: Optional[QgsLayoutItemLegend] = None
    scalebar_item: Optional[QgsLayoutItemScaleBar] = None
    north_items = []

    def _label_by_id(*ids):
        for wanted in ids:
            found = layout.itemById(wanted)
            if isinstance(found, QgsLayoutItemLabel):
                return found
        return None

    title_item = _label_by_id("cartolab_title")
    subtitle_item = _label_by_id("cartolab_subtitle")
    credits_item = _label_by_id("cartolab_credits", "cartolab_footer")
    known = {title_item, subtitle_item, credits_item}

    for item in layout.items():
        item_id = item.id() if hasattr(item, "id") else ""
        if item_id in ("cartolab_locator_inset",):
            continue
        if item_id.startswith("cartolab_north_arrow"):
            north_items.append(item)
        elif (isinstance(item, QgsLayoutItemLabel) and title_item is None and item not in known
              and item.rect().width() > 50):
            title_item = item
        elif isinstance(item, QgsLayoutItemLegend) and legend_item is None:
            legend_item = item
        elif isinstance(item, QgsLayoutItemScaleBar) and scalebar_item is None:
            scalebar_item = item
        elif isinstance(item, QgsLayoutItemPicture) and not north_items:
            north_items.append(item)

    if main_map is None:
        return False

    _Mm = getattr(getattr(QgsUnitTypes, "LayoutUnit", QgsUnitTypes), "LayoutMillimeters", getattr(QgsUnitTypes, "LayoutMillimeters", 0))
    original_extent = QgsRectangle(main_map.extent())
    if legend_item is not None:
        # A legend that resizes to its contents would grow out of its slot.
        legend_item.setResizeToContents(False)
    north_w, north_h = _cluster_size(north_items)
    credits_h = 6.0

    if archetype in ("sidebar_right", "sidebar_left"):
        sidebar_w = max(55.0, page_w * 0.28)
        gap = 6.0
        map_w = page_w - (2 * margin_mm) - sidebar_w - gap
        map_h = page_h - (2 * margin_mm)

        if archetype == "sidebar_right":
            map_x = margin_mm
            sidebar_x = page_w - margin_mm - sidebar_w
        else:
            sidebar_x = margin_mm
            map_x = margin_mm + sidebar_w + gap

        # Main Map
        main_map.attemptMove(QgsLayoutPoint(map_x, margin_mm, _Mm))
        main_map.attemptResize(QgsLayoutSize(map_w, map_h, _Mm))
        main_map.zoomToExtent(original_extent)

        # Sidebar, top down: title, subtitle, legend ...
        curr_y = margin_mm
        if title_item is not None:
            title_item.attemptMove(QgsLayoutPoint(sidebar_x, curr_y, _Mm))
            title_item.attemptResize(QgsLayoutSize(sidebar_w, title_height_mm, _Mm))
            curr_y += title_height_mm + 2.0
        if subtitle_item is not None:
            subtitle_item.attemptMove(QgsLayoutPoint(sidebar_x, curr_y, _Mm))
            subtitle_item.attemptResize(QgsLayoutSize(sidebar_w, 9.0, _Mm))
            curr_y += 9.0
        curr_y += gap

        # ... and bottom up: credits, scale bar, north arrow.
        bottom = page_h - margin_mm
        if credits_item is not None:
            credits_item.attemptMove(QgsLayoutPoint(sidebar_x, bottom - credits_h, _Mm))
            credits_item.attemptResize(QgsLayoutSize(sidebar_w, credits_h, _Mm))
            bottom -= credits_h + 2.0
        try:
            sb_h = max(12.0, float(scalebar_item.sceneBoundingRect().height())) if scalebar_item is not None else 12.0
        except (AttributeError, RuntimeError, TypeError, ValueError):
            sb_h = 12.0
        sb_y = bottom - sb_h
        furniture_top = sb_y
        if scalebar_item is not None:
            scalebar_item.attemptMove(QgsLayoutPoint(sidebar_x, sb_y, _Mm))
            if north_items:
                _move_item_cluster(north_items, sidebar_x + sidebar_w - north_w, sb_y - north_h - 2.0, _Mm)
                furniture_top = sb_y - north_h - 2.0
        elif north_items:
            _move_item_cluster(north_items, sidebar_x, bottom - north_h, _Mm)
            furniture_top = bottom - north_h

        # Sidebar Legend fills the space in between
        if legend_item is not None:
            legend_item.attemptMove(QgsLayoutPoint(sidebar_x, curr_y, _Mm))
            legend_item.attemptResize(QgsLayoutSize(sidebar_w, max(10.0, furniture_top - curr_y - gap), _Mm))

    else:
        # Default: Editorial Bottom Bar
        # 1. Top Section (Title Block)
        top_offset = margin_mm
        if title_item is not None:
            title_w = page_w - (2 * margin_mm)
            title_h = title_height_mm * (0.6 if subtitle_item is not None else 1.0)
            title_item.attemptResize(QgsLayoutSize(title_w, title_h, _Mm))
            title_item.attemptMove(QgsLayoutPoint(margin_mm, margin_mm, _Mm))
            top_offset = margin_mm + title_h + 4.0
        if subtitle_item is not None:
            sub_y = top_offset - 4.0 if title_item is not None else margin_mm
            sub_h = title_height_mm * 0.4 if title_item is not None else 6.0
            subtitle_item.attemptMove(QgsLayoutPoint(margin_mm, sub_y, _Mm))
            subtitle_item.attemptResize(QgsLayoutSize(page_w - 2 * margin_mm, sub_h, _Mm))
            top_offset = sub_y + sub_h + 4.0

        # 2. Bottom Bar (Legend, Credits, North Arrow, Scale bar)
        bottom_y = page_h - margin_mm - bottom_bar_height_mm
        map_h = bottom_y - top_offset - 4.0
        map_w = page_w - (2 * margin_mm)

        if map_h < 40.0:
            map_h = page_h - (2 * margin_mm)
            bottom_y = page_h - margin_mm - 18.0

        # 3. Main Map Frame
        main_map.attemptMove(QgsLayoutPoint(margin_mm, top_offset, _Mm))
        main_map.attemptResize(QgsLayoutSize(map_w, map_h, _Mm))
        main_map.zoomToExtent(original_extent)

        # 4. Position Bottom Elements (Clean Aligned Row)
        bar_bottom = page_h - margin_mm
        curr_x = margin_mm
        right_x = page_w - margin_mm

        # Scale bar on bottom right
        if scalebar_item is not None:
            sb_w = scalebar_item.rect().width()
            sb_x = right_x - sb_w
            scalebar_item.attemptMove(QgsLayoutPoint(sb_x, bottom_y + 8.0, _Mm))
            right_x = sb_x - 4.0
        # North Arrow beside the scale bar
        if north_items:
            north_x = right_x - north_w
            _move_item_cluster(north_items, north_x, bottom_y + 3.0, _Mm)
            right_x = north_x - 4.0

        # Legend on left
        if legend_item is not None:
            legend_w = max(35.0, min(map_w * 0.42, right_x - curr_x - 4.0))
            legend_item.attemptMove(QgsLayoutPoint(curr_x, bottom_y + 2.0, _Mm))
            legend_item.attemptResize(QgsLayoutSize(legend_w, bar_bottom - bottom_y - 2.0, _Mm))
            curr_x += legend_w + 4.0

        # Credits fill the free middle of the bar, on its baseline
        if credits_item is not None:
            credits_w = max(20.0, right_x - curr_x)
            credits_item.attemptMove(QgsLayoutPoint(curr_x, bar_bottom - credits_h, _Mm))
            credits_item.attemptResize(QgsLayoutSize(credits_w, credits_h, _Mm))

    layout.refresh()
    return True
