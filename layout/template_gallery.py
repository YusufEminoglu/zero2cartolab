# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Template Gallery & Publication Archetypes.

Provides distinct, publication-grade print layout templates:
  - "report_figure": 16:9 widescreen landscape for slide decks & executive presentations.
  - "academic_journal": A4 portrait 2-column scientific format with formal caption & citation blocks.
  - "poster_exhibition": Large-format A1/A2 landscape presentation poster with bold banner & insets.
  - "fact_sheet": A4 portrait executive 1-pager with top KPI metric cards & analytical narrative.
  - "side_by_side_diptych": A4/A3 landscape comparative layout with paired synchronized map frames.

Author: Yusuf Eminoğlu
"""
from __future__ import annotations

import datetime
from contextlib import suppress
from typing import Any, Dict, List, Optional, Tuple

try:
    from qgis.PyQt.QtCore import QPointF, Qt
    from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
    from qgis.core import (
        QgsFillSymbol,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemPicture,
        QgsLayoutItemPolygon,
        QgsLayoutItemScaleBar,
        QgsLayoutItemShape,
        QgsLayoutMeasurement,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsPrintLayout,
        QgsProject,
        QgsRectangle,
        QgsUnitTypes,
    )
    _MM = getattr(
        getattr(QgsUnitTypes, "LayoutUnit", QgsUnitTypes),
        "LayoutMillimeters",
        getattr(QgsUnitTypes, "LayoutMillimeters", 0),
    )
except ImportError:
    QPointF = Qt = QColor = QFont = QPolygonF = None
    QgsFillSymbol = QgsLayoutItemLabel = QgsLayoutItemLegend = QgsLayoutItemMap = None
    QgsLayoutItemPicture = QgsLayoutItemPolygon = QgsLayoutItemScaleBar = QgsLayoutItemShape = None
    QgsLayoutMeasurement = QgsLayoutPoint = QgsLayoutSize = QgsPrintLayout = QgsProject = QgsRectangle = QgsUnitTypes = None
    _MM = 0

from ..core.layout_math import page_size_mm, nice_scalebar_segments
from .layout_utils import north_arrow_svg_path, unique_layout_name
from .locator_map import add_locator_inset_map
from .map_sheet import _add_north_arrow, _font, _resolve_extent, _resolve_layers
from .paper_themes import apply_paper_theme
from .typography_engine import apply_typography_hierarchy


# ===========================================================================
# Helper Functions
# ===========================================================================

def _create_base_layout(
    project: Optional[QgsProject],
    layout_name: str,
    page_w: float,
    page_h: float,
) -> Optional[QgsPrintLayout]:
    """Initialize a QgsPrintLayout with given page dimensions."""
    if QgsPrintLayout is None:
        return None
    proj = project or (QgsProject.instance() if QgsProject else None)
    if proj is None:
        return None

    layout = QgsPrintLayout(proj)
    layout.initializeDefaults()
    layout.setName(unique_layout_name(proj, layout_name))

    page_col = layout.pageCollection()
    if page_col and page_col.pageCount() > 0:
        page = page_col.page(0)
        if page is not None and QgsLayoutSize is not None:
            page.setPageSize(QgsLayoutSize(page_w, page_h, _MM))

    return layout


def _create_map_frame(
    layout: QgsPrintLayout,
    map_id: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    frame_color: str = "#1e293b",
    frame_width_mm: float = 0.35,
    add_frame: bool = True,
) -> Optional[QgsLayoutItemMap]:
    """Create and configure a primary or secondary map frame item."""
    if layout is None or QgsLayoutItemMap is None:
        return None

    map_item = QgsLayoutItemMap(layout)
    map_item.setId(map_id)
    map_item.attemptMove(QgsLayoutPoint(x, y, _MM))
    map_item.attemptResize(QgsLayoutSize(w, h, _MM))

    if crs is not None and hasattr(crs, "isValid") and crs.isValid():
        map_item.setCrs(crs)
    if extent is not None and hasattr(extent, "isEmpty") and not extent.isEmpty():
        map_item.zoomToExtent(extent)
    if layers:
        map_item.setLayers(list(layers))
        map_item.setKeepLayerSet(True)

    if add_frame:
        map_item.setFrameEnabled(True)
        if hasattr(map_item, "setFrameStrokeColor") and QColor is not None:
            map_item.setFrameStrokeColor(QColor(frame_color))
            map_item.setFrameStrokeWidth(QgsLayoutMeasurement(frame_width_mm, _MM))
        elif hasattr(map_item, "setFrameColor") and QColor is not None:
            map_item.setFrameColor(QColor(frame_color))

    layout.addLayoutItem(map_item)
    return map_item


def _create_card_shape(
    layout: QgsPrintLayout,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    bg_color: str = "#ffffff",
    border_color: str = "#cbd5e1",
    border_width_mm: float = 0.3,
) -> Optional[QgsLayoutItemShape]:
    """Create a rectangular background card/panel shape."""
    if layout is None or QgsLayoutItemShape is None:
        return None

    shape = QgsLayoutItemShape(layout)
    if hasattr(QgsLayoutItemShape, "Shape") and hasattr(QgsLayoutItemShape.Shape, "Rectangle"):
        shape.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
    elif hasattr(QgsLayoutItemShape, "Rectangle"):
        shape.setShapeType(QgsLayoutItemShape.Rectangle)

    shape.attemptMove(QgsLayoutPoint(x, y, _MM))
    shape.attemptResize(QgsLayoutSize(w, h, _MM))

    if QgsFillSymbol is not None:
        sym = QgsFillSymbol.createSimple({
            "color": bg_color,
            "outline_color": border_color,
            "outline_width": str(border_width_mm),
        })
        if sym:
            shape.setSymbol(sym)

    layout.addLayoutItem(shape)
    return shape


def _create_label(
    layout: QgsPrintLayout,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    font_size: float = 10.0,
    bold: bool = False,
    color: str = "#0f172a",
    family: Optional[str] = None,
    h_align: str = "left",
) -> Optional[QgsLayoutItemLabel]:
    """Create and position a text label item."""
    if layout is None or QgsLayoutItemLabel is None:
        return None

    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    label.setBackgroundEnabled(False)
    label.setFrameEnabled(False)
    fam = family or "Segoe UI"
    f = QFont(fam, int(round(font_size)))
    hint = getattr(getattr(QFont, "StyleHint", QFont), "SansSerif", getattr(QFont, "SansSerif", None))
    if hint is not None and hasattr(f, "setStyleHint"):
        with suppress(Exception):
            f.setStyleHint(hint)
    if hasattr(f, "setFamilies"):
        f.setFamilies([fam, "Segoe UI", "Arial", "sans-serif"])
    if hasattr(f, "setPointSizeF"):
        f.setPointSizeF(float(font_size))
    f.setBold(bold)
    label.setFont(f)
    if QColor is not None:
        label.setFontColor(QColor(color))

    label.attemptMove(QgsLayoutPoint(x, y, _MM))
    label.attemptResize(QgsLayoutSize(w, h, _MM))

    if hasattr(label, "setHAlign") and Qt is not None:
        align_flag = getattr(Qt, "AlignmentFlag", Qt)
        if h_align == "center":
            label.setHAlign(getattr(align_flag, "AlignHCenter", getattr(align_flag, "AlignCenter", 0x0004)))
        elif h_align == "right":
            label.setHAlign(getattr(align_flag, "AlignRight", 0x0002))

    layout.addLayoutItem(label)
    return label


def _create_legend(
    layout: QgsPrintLayout,
    linked_map: QgsLayoutItemMap,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str = "",
) -> Optional[QgsLayoutItemLegend]:
    """Create a map-filtered legend item."""
    if layout is None or QgsLayoutItemLegend is None:
        return None

    legend = QgsLayoutItemLegend(layout)
    if linked_map is not None:
        legend.setLinkedMap(linked_map)
        legend.setLegendFilterByMapEnabled(True)
    legend.setAutoUpdateModel(True)
    legend.setResizeToContents(True)
    legend.setBackgroundEnabled(False)
    legend.setFrameEnabled(False)
    legend.setTitle(title)
    if hasattr(legend, "rstyle"):
        with suppress(Exception):
            from qgis.core import QgsLegendStyle
            for style_attr in ("Title", "Group", "Subgroup", "SymbolLabel"):
                style_enum = getattr(QgsLegendStyle, style_attr, getattr(getattr(QgsLegendStyle, "Style", None), style_attr, None))
                if style_enum is not None:
                    tf = legend.rstyle(style_enum).textFormat()
                    f = _font(8.5 if style_attr == "SymbolLabel" else 9.5)
                    tf.setFont(f)
                    tf.setColor(QColor("#0f172a"))
                    legend.rstyle(style_enum).setTextFormat(tf)
    legend.attemptMove(QgsLayoutPoint(x, y, _MM))
    legend.attemptResize(QgsLayoutSize(w, h, _MM))
    layout.addLayoutItem(legend)
    return legend


def _create_scalebar(
    layout: QgsPrintLayout,
    linked_map: QgsLayoutItemMap,
    x: float,
    y: float,
    style: str = "Line Ticks Up",
    segments: int = 2,
) -> Optional[QgsLayoutItemScaleBar]:
    """Create and position an executive scale bar."""
    if layout is None or QgsLayoutItemScaleBar is None:
        return None

    scalebar = QgsLayoutItemScaleBar(layout)
    if linked_map is not None:
        scalebar.setLinkedMap(linked_map)
    scalebar.applyDefaultSettings()
    scalebar.setStyle(style)
    scalebar.applyDefaultSize()

    unit_km = getattr(QgsUnitTypes, "DistanceKilometers", getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceKilometers", 1))
    scalebar.setUnits(unit_km)
    scalebar.setUnitLabel("km")
    num_segs = max(3, segments)
    scalebar.setNumberOfSegments(num_segs)
    scalebar.setNumberOfSegmentsLeft(0)
    if linked_map is not None:
        ext = linked_map.extent()
        if ext and not ext.isEmpty():
            map_w_km = ext.width() / 1000.0 if (hasattr(linked_map, "crs") and linked_map.crs().isValid() and not linked_map.crs().isGeographic()) else 10.0
            seg_km, n_right, n_left = nice_scalebar_segments(map_w_km, target_segments=num_segs)
            scalebar.setNumberOfSegments(n_right)
            scalebar.setNumberOfSegmentsLeft(n_left)
            scalebar.setUnitsPerSegment(seg_km)
    scalebar.setBackgroundEnabled(False)
    scalebar.setFrameEnabled(False)
    with suppress(Exception):
        tf_sb = scalebar.textFormat()
        tf_sb.setFont(_font(8.0))
        tf_sb.setColor(QColor("#0f172a"))
        scalebar.setTextFormat(tf_sb)
    scalebar.attemptMove(QgsLayoutPoint(x, y, _MM))
    layout.addLayoutItem(scalebar)
    return scalebar


# ===========================================================================
# 1. Report Figure Archetype (16:9 Landscape)
# ===========================================================================

def create_report_figure_layout(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "Figure 1.0 — Spatial Distribution Analysis",
    subtitle: str = "Widescreen executive summary and geographic pattern synthesis",
    credits: str = "Cartography: Yusuf Eminoğlu · PlanX CartoLab",
    page_size: str = "16:9",
    landscape: bool = True,
    theme: str = "swiss_modern",
    layout_name: str = "Report Figure (16:9)",
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Build a 16:9 widescreen presentation figure layout.

    Optimized for executive slide decks and digital reports with a prominent figure title,
    hero map frame, and compact right-hand HUD sidebar with metric highlights.
    """
    proj = project or (QgsProject.instance() if QgsProject else None)
    res_layers = layers if layers is not None else _resolve_layers(iface, proj)
    res_extent = extent if extent is not None else _resolve_extent(iface, res_layers)

    if crs is None and iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
    if crs is None and proj is not None:
        crs = proj.crs()

    if page_size == "16:9":
        page_w, page_h = (338.7, 190.5) if landscape else (190.5, 338.7)
    else:
        page_w, page_h = page_size_mm(page_size, landscape)

    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None

    margin = 12.0
    gap = 6.0
    header_h = 20.0

    # 1. Prominent Figure Title Header
    tag_text = "FIGURE 1.0"
    _create_label(layout, tag_text, margin, margin, 50.0, 5.0, font_size=8.0, bold=True, color="#2563eb")
    _create_label(layout, title, margin, margin + 4.5, page_w - 2 * margin, 9.0, font_size=15.0, bold=True, color="#0f172a")
    if subtitle:
        _create_label(layout, subtitle, margin, margin + 13.5, page_w - 2 * margin, 5.5, font_size=8.5, color="#64748b")

    # 2. Geometry partitioning: Hero Map (Left/Center ~72%) + HUD Sidebar (Right ~28%)
    hud_w = 84.0
    map_x = margin
    map_y = margin + header_h + gap
    map_w = page_w - 2 * margin - hud_w - gap
    map_h = page_h - map_y - margin - 8.0  # reserve space for footer

    # Hero Map Frame
    map_item = _create_map_frame(
        layout, "cartolab_report_map", map_x, map_y, map_w, map_h,
        layers=res_layers, extent=res_extent, crs=crs, frame_color="#0f172a", frame_width_mm=0.35
    )

    # 3. Compact Right HUD Sidebar Card
    hud_x = map_x + map_w + gap
    hud_y = map_y
    hud_h = map_h

    _create_card_shape(layout, hud_x, hud_y, hud_w, hud_h, bg_color="#ffffff", border_color="#e2e8f0", border_width_mm=0.3)

    # HUD Section Title
    _create_label(layout, "EXECUTIVE HUD & METRICS", hud_x + 4.0, hud_y + 4.0, hud_w - 8.0, 5.0, font_size=7.5, bold=True, color="#2563eb")

    # Legend inside HUD
    leg_y = hud_y + 10.0
    leg_h = hud_h * 0.45
    if map_item is not None:
        _create_legend(layout, map_item, hud_x + 4.0, leg_y, hud_w - 8.0, leg_h, title="")

    # Key Takeaways Box
    callout_y = hud_y + 12.0 + leg_h
    callout_h = hud_h - (12.0 + leg_h) - 22.0
    _create_card_shape(layout, hud_x + 4.0, callout_y, hud_w - 8.0, callout_h, bg_color="#f8fafc", border_color="#cbd5e1", border_width_mm=0.2)
    takeaway_text = "Key Spatial Insights:\n• Concentrated core density\n• High peripheral connectivity\n• Balanced accessibility"
    _create_label(layout, takeaway_text, hud_x + 6.0, callout_y + 2.0, hud_w - 12.0, callout_h - 4.0, font_size=7.5, color="#334155")

    # Scale Bar in HUD Bottom & North Arrow inside Map Frame
    if map_item is not None:
        _create_scalebar(layout, map_item, hud_x + 4.0, hud_y + hud_h - 18.0, style="Line Ticks Up")
    _add_north_arrow(layout, map_x + map_w - 16.0, map_y + 4.0, size=12.0)

    # 4. Bottom Footer Metadata Strip
    footer_y = page_h - margin
    now_str = datetime.date.today().strftime("%Y-%m-%d")
    meta_text = f"{credits}  ·  Date: {now_str}  ·  PlanX CartoLab Widescreen Suite"
    _create_label(layout, meta_text, margin, footer_y, page_w - 2 * margin, 5.0, font_size=7.0, color="#94a3b8")

    if theme and theme != "swiss_modern":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "swiss_modern")

    if proj is not None and hasattr(proj, "layoutManager"):
        proj.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


# ===========================================================================
# 2. Academic Journal Archetype (A4 Portrait - 2-Column Scientific)
# ===========================================================================

def create_academic_journal_layout(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "Fig. 1. Spatial morphology and accessibility patterns in the study area.",
    subtitle: str = "Analysis of urban form, network centrality, and spatial variance.",
    credits: str = "Sources: Municipal Open Data & OpenStreetMap contributors. Cartography: Yusuf Eminoğlu.",
    citation: str = "Eminoğlu, Y. (2026). Spatial Morphology Synthesis. PlanX CartoLab Academic Series, 4(2), 112–128.",
    page_size: str = "A4",
    landscape: bool = False,
    theme: str = "academic_serif",
    layout_name: str = "Academic Journal Figure (A4)",
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Build an A4 portrait 2-column academic journal layout.

    Follows formal Nature/Elsevier scientific publication guidelines:
    top journal header, high-resolution full-width hero map frame with neatline,
    formal figure caption, methodology description, and citation block.
    """
    proj = project or (QgsProject.instance() if QgsProject else None)
    res_layers = layers if layers is not None else _resolve_layers(iface, proj)
    res_extent = extent if extent is not None else _resolve_extent(iface, res_layers)

    if crs is None and iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
    if crs is None and proj is not None:
        crs = proj.crs()

    page_w, page_h = page_size_mm(page_size, landscape)  # A4 Portrait: 210 x 297 mm
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None

    margin = 14.0
    gutter = 8.0
    col_w = (page_w - (2 * margin) - gutter) / 2.0  # ~87 mm each column

    # 1. Top Journal Figure Header
    _create_label(layout, "RESEARCH ARTICLE — SPATIAL ANALYSIS & MORPHOLOGY", margin, margin, page_w - 2 * margin, 5.0, font_size=7.5, bold=True, color="#64748b")
    _create_label(layout, title, margin, margin + 5.0, page_w - 2 * margin, 10.0, font_size=11.0, bold=True, color="#1e293b")

    # 2. Main Hero Map Frame (Double Column Width)
    map_x = margin
    map_y = margin + 17.0
    map_w = page_w - 2 * margin  # 182 mm
    map_h = 142.0

    map_item = _create_map_frame(
        layout, "cartolab_academic_map", map_x, map_y, map_w, map_h,
        layers=res_layers, extent=res_extent, crs=crs, frame_color="#0f172a", frame_width_mm=0.35
    )

    # 3. 2-Column Scientific Content below map
    col1_x = margin
    col2_x = margin + col_w + gutter
    body_y = map_y + map_h + 6.0
    body_h = page_h - body_y - margin

    # Column 1 (Left): Formal Caption, Methodology & Scale
    caption_text = (
        f"{title}\n\n"
        "Methodology: Multi-criteria spatial classification and geometric interval scaling. "
        f"{subtitle}\n\n"
        f"{credits}"
    )
    _create_label(layout, caption_text, col1_x, body_y, col_w, body_h - 22.0, font_size=8.0, color="#334155")

    # Stepped Line Scale bar in Column 1 & North Arrow inside Map Frame
    if map_item is not None:
        _create_scalebar(layout, map_item, col1_x, page_h - margin - 16.0, style="Stepped Line")
    _add_north_arrow(layout, map_x + map_w - 14.0, map_y + 4.0, size=11.0)

    # Column 2 (Right): Filtered Academic Legend & Formal Citation Box
    if map_item is not None:
        _create_legend(layout, map_item, col2_x, body_y, col_w, body_h * 0.55, title="")

    # Citation & Coordinate System Box
    cite_y = page_h - margin - 28.0
    _create_card_shape(layout, col2_x, cite_y, col_w, 24.0, bg_color="#f8fafc", border_color="#e2e8f0", border_width_mm=0.2)
    cite_text = f"Citation:\n{citation}\nCoordinate System: [% @project_crs %]"
    _create_label(layout, cite_text, col2_x + 3.0, cite_y + 2.0, col_w - 6.0, 20.0, font_size=6.8, color="#475569")

    if theme and theme != "academic_serif":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "academic_serif")

    if proj is not None and hasattr(proj, "layoutManager"):
        proj.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


# ===========================================================================
# 3. Poster Exhibition Archetype (A1/A2 Landscape)
# ===========================================================================

def create_poster_exhibition_layout(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "METROPOLITAN SPATIAL RESILIENCE & MORPHOLOGY",
    subtitle: str = "Comprehensive Cartographic & Urban Analytics Exhibition Masterplan",
    credits: str = "PlanX CartoLab Studio · Yusuf Eminoğlu",
    page_size: str = "A1",
    landscape: bool = True,
    theme: str = "swiss_modern",
    layout_name: str = "Exhibition Poster (Large Format)",
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Build a large-format A1/A2 landscape presentation poster layout.

    Designed for urban design competitions, exhibitions, and public masterplans:
    bold high-impact banner, dominant hero map frame, regional locator inset card,
    and thematic legend & statistic callouts.
    """
    proj = project or (QgsProject.instance() if QgsProject else None)
    res_layers = layers if layers is not None else _resolve_layers(iface, proj)
    res_extent = extent if extent is not None else _resolve_extent(iface, res_layers)

    if crs is None and iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
    if crs is None and proj is not None:
        crs = proj.crs()

    page_w, page_h = page_size_mm(page_size, landscape)  # A1: 841 x 594 mm or A2: 594 x 420 mm
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None

    margin = 18.0
    gap = 10.0
    banner_h = max(42.0, page_h * 0.10)

    # 1. Bold Exhibition Top Banner Card
    banner_w = page_w - 2 * margin
    _create_card_shape(layout, margin, margin, banner_w, banner_h, bg_color="#0f172a", border_color="#2563eb", border_width_mm=0.6)

    # Banner Title & Subtitle (White / Ice-blue)
    _create_label(layout, title.upper(), margin + 10.0, margin + 6.0, banner_w * 0.72, banner_h * 0.50, font_size=20.0, bold=True, color="#ffffff")
    _create_label(layout, subtitle, margin + 10.0, margin + banner_h * 0.55, banner_w * 0.72, banner_h * 0.35, font_size=10.5, color="#94a3b8")

    # Author / Institution badge on banner right
    _create_label(
        layout,
        f"{credits}\nSpatial Analytics & Design Series",
        margin + banner_w * 0.74, margin + 8.0, banner_w * 0.24, banner_h - 16.0,
        font_size=9.5, bold=True, color="#38bdf8", h_align="right"
    )

    # 2. Central Layout Partitioning: Hero Map (Left ~70%) + Side Inset Cards (Right ~30%)
    content_y = margin + banner_h + gap
    content_h = page_h - content_y - margin - 22.0  # reserve space for bottom metadata bar
    side_w = max(160.0, (page_w - 2 * margin) * 0.28)
    hero_w = page_w - 2 * margin - side_w - gap

    # Hero Map Frame
    hero_map = _create_map_frame(
        layout, "cartolab_poster_hero_map", margin, content_y, hero_w, content_h,
        layers=res_layers, extent=res_extent, crs=crs, frame_color="#0f172a", frame_width_mm=0.5
    )

    # 3. Dual Right-Hand Inset Cards
    side_x = margin + hero_w + gap
    card_h = (content_h - gap) / 2.0

    # Inset Card 1: Regional Overview Locator Inset Map
    _create_card_shape(layout, side_x, content_y, side_w, card_h, bg_color="#ffffff", border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "REGIONAL CONTEXT & LOCATOR", side_x + 6.0, content_y + 4.0, side_w - 12.0, 6.0, font_size=8.5, bold=True, color="#0f172a")

    if hero_map is not None:
        add_locator_inset_map(
            layout,
            main_map=hero_map,
            position=(side_x + 6.0, content_y + 12.0),
            size_mm=(side_w - 12.0, card_h - 18.0),
            zoom_factor=4.5,
            add_header=False,
        )

    # Inset Card 2: Thematic Legend & Key Metrics
    card2_y = content_y + card_h + gap
    _create_card_shape(layout, side_x, card2_y, side_w, card_h, bg_color="#ffffff", border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "THEMATIC LEGEND & INDICATORS", side_x + 6.0, card2_y + 4.0, side_w - 12.0, 6.0, font_size=8.5, bold=True, color="#0f172a")

    if hero_map is not None:
        _create_legend(layout, hero_map, side_x + 6.0, card2_y + 12.0, side_w - 12.0, card_h - 18.0, title="")

    # 4. Bottom Control Bar (Scale Bar, North Arrow, Projection Info)
    bottom_y = page_h - margin - 18.0
    bottom_h = 18.0
    _create_card_shape(layout, margin, bottom_y, banner_w, bottom_h, bg_color="#f8fafc", border_color="#e2e8f0", border_width_mm=0.3)

    if hero_map is not None:
        _create_scalebar(layout, hero_map, margin + 8.0, bottom_y + 2.0, style="Double Box")
    _add_north_arrow(layout, margin + 95.0, bottom_y + 2.0, size=14.0)

    now_str = datetime.date.today().strftime("%Y-%m-%d")
    bottom_meta = f"Projection: [% @project_crs %]  ·  Datum: WGS 84  ·  Date: {now_str}  ·  {credits}"
    _create_label(layout, bottom_meta, margin + 120.0, bottom_y + 4.0, banner_w - 130.0, 10.0, font_size=8.0, color="#475569", h_align="right")

    if theme and theme != "swiss_modern":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "swiss_modern")

    if proj is not None and hasattr(proj, "layoutManager"):
        proj.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


# ===========================================================================
# 4. Fact Sheet Archetype (A4 Portrait Executive Summary)
# ===========================================================================

def create_fact_sheet_layout(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "Urban Resilience & Spatial Analytics",
    subtitle: str = "Executive Briefing & Strategic Spatial Indicator Summary",
    credits: str = "PlanX CartoLab · Yusuf Eminoğlu",
    page_size: str = "A4",
    landscape: bool = False,
    theme: str = "swiss_modern",
    layout_name: str = "Executive Fact Sheet (A4)",
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Build an A4 portrait executive fact sheet layout.

    Designed for municipal decision-makers and executive summaries:
    document header, top KPI metric summary cards, central thematic map frame,
    and bottom analytical narrative block.
    """
    proj = project or (QgsProject.instance() if QgsProject else None)
    res_layers = layers if layers is not None else _resolve_layers(iface, proj)
    res_extent = extent if extent is not None else _resolve_extent(iface, res_layers)

    if crs is None and iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
    if crs is None and proj is not None:
        crs = proj.crs()

    page_w, page_h = page_size_mm(page_size, landscape)  # A4 Portrait: 210 x 297 mm
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None

    margin = 12.0
    gap = 4.0
    content_w = page_w - 2 * margin  # 186 mm

    # 1. Executive Document Header
    _create_label(layout, "EXECUTIVE BRIEFING · SPATIAL FACT SHEET", margin, margin, content_w, 4.5, font_size=7.5, bold=True, color="#2563eb")
    _create_label(layout, title, margin, margin + 4.5, content_w, 8.5, font_size=15.0, bold=True, color="#0f172a")
    if subtitle:
        now_str = datetime.date.today().strftime("%Y-%m-%d")
        _create_label(layout, f"{subtitle}  ·  {now_str}", margin, margin + 13.0, content_w, 4.5, font_size=8.0, color="#64748b")

    # 2. Top 4 KPI Metric Summary Cards
    cards_y = margin + 19.0
    cards_h = 18.0
    n_cards = 4
    card_w = (content_w - (n_cards - 1) * gap) / float(n_cards)

    kpi_data = [
        ("TOTAL EXTENT", "48.5 km²", "#0f172a"),
        ("DENSITY INDEX", "4,820 /km²", "#2563eb"),
        ("ACCESSIBILITY", "0.86 (High)", "#059669"),
        ("PRIORITY TIER", "Tier 1 Priority", "#dc2626"),
    ]

    for i, (kpi_title, kpi_val, kpi_color) in enumerate(kpi_data):
        cx = margin + i * (card_w + gap)
        _create_card_shape(layout, cx, cards_y, card_w, cards_h, bg_color="#f8fafc", border_color="#e2e8f0", border_width_mm=0.25)
        _create_label(layout, kpi_title, cx + 3.0, cards_y + 2.5, card_w - 6.0, 4.0, font_size=6.5, bold=True, color="#64748b")
        _create_label(layout, kpi_val, cx + 3.0, cards_y + 7.5, card_w - 6.0, 7.5, font_size=10.0, bold=True, color=kpi_color)

    # 3. Central Thematic Map Frame
    map_x = margin
    map_y = cards_y + cards_h + gap
    map_w = content_w
    map_h = 135.0

    map_item = _create_map_frame(
        layout, "cartolab_factsheet_map", map_x, map_y, map_w, map_h,
        layers=res_layers, extent=res_extent, crs=crs, frame_color="#0f172a", frame_width_mm=0.35
    )

    # In-map Scale bar & North Arrow
    if map_item is not None:
        _create_scalebar(layout, map_item, map_x + 4.0, map_y + map_h - 14.0, style="Line Ticks Up")
    _add_north_arrow(layout, map_x + map_w - 16.0, map_y + 4.0, size=12.0)

    # 4. Bottom Analytical Narrative Block (Split: 60% Narrative + 40% Legend)
    narrative_y = map_y + map_h + gap
    narrative_h = page_h - narrative_y - margin
    narrative_w = content_w * 0.60
    legend_col_w = content_w - narrative_w - gap
    legend_col_x = margin + narrative_w + gap

    # Left Narrative Card
    _create_card_shape(layout, margin, narrative_y, narrative_w, narrative_h, bg_color="#ffffff", border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "KEY OBSERVATIONS & POLICY ACTIONS", margin + 4.0, narrative_y + 3.0, narrative_w - 8.0, 5.0, font_size=8.0, bold=True, color="#0f172a")

    findings = (
        "• Core urban areas exhibit high spatial integration and optimal transit access.\n"
        "• Peripheral zones show moderate vulnerability to infrastructure deficits.\n"
        "• Recommended Intervention: Targeted transit expansion & green corridor links.\n"
        f"• {credits}"
    )
    _create_label(layout, findings, margin + 4.0, narrative_y + 9.0, narrative_w - 8.0, narrative_h - 12.0, font_size=7.5, color="#334155")

    # Right Legend Card
    _create_card_shape(layout, legend_col_x, narrative_y, legend_col_w, narrative_h, bg_color="#ffffff", border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "THEMATIC LEGEND", legend_col_x + 4.0, narrative_y + 3.0, legend_col_w - 8.0, 5.0, font_size=8.0, bold=True, color="#0f172a")
    if map_item is not None:
        _create_legend(layout, map_item, legend_col_x + 4.0, narrative_y + 9.0, legend_col_w - 8.0, narrative_h - 12.0, title="")

    if theme and theme != "swiss_modern":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "swiss_modern")

    if proj is not None and hasattr(proj, "layoutManager"):
        proj.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


# ===========================================================================
# 5. Side-by-Side Diptych Archetype (A4/A3 Landscape Comparative)
# ===========================================================================

def create_side_by_side_diptych_layout(
    iface=None,
    *,
    layers: Optional[List] = None,
    layers_a: Optional[List] = None,
    layers_b: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "Comparative Scenario Evaluation",
    subtitle: str = "Side-by-side spatial comparison: Baseline (Left) vs. Proposed Intervention (Right)",
    label_a: str = "SCENARIO A — BASELINE",
    label_b: str = "SCENARIO B — PROPOSED PLAN",
    credits: str = "PlanX CartoLab · Yusuf Eminoğlu",
    page_size: str = "A4",
    landscape: bool = True,
    theme: str = "swiss_modern",
    layout_name: str = "Side-by-Side Diptych",
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Build an A4/A3 landscape comparative diptych layout.

    Features two synchronized or paired map frames for before/after, baseline/scenario,
    or temporal change analysis with synchronized extent, badges, and shared legend.
    """
    proj = project or (QgsProject.instance() if QgsProject else None)
    res_layers = layers if layers is not None else _resolve_layers(iface, proj)
    res_layers_a = layers_a if layers_a is not None else kwargs.get("scenario_a_layers", res_layers)
    res_layers_b = layers_b if layers_b is not None else kwargs.get("scenario_b_layers", res_layers)
    lbl_a = kwargs.get("scenario_a_title", label_a)
    lbl_b = kwargs.get("scenario_b_title", label_b)
    res_extent = extent if extent is not None else _resolve_extent(iface, res_layers_a or res_layers)

    if crs is None and iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
    if crs is None and proj is not None:
        crs = proj.crs()

    page_w, page_h = page_size_mm(page_size, landscape)  # A4 Landscape: 297 x 210 mm
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None

    margin = 12.0
    gap = 6.0
    header_h = 16.0

    # 1. Top Comparison Header
    _create_label(layout, "COMPARATIVE SPATIAL ANALYSIS", margin, margin, page_w - 2 * margin, 4.5, font_size=7.5, bold=True, color="#2563eb")
    _create_label(layout, title, margin, margin + 4.5, page_w - 2 * margin, 7.5, font_size=13.0, bold=True, color="#0f172a")
    if subtitle:
        _create_label(layout, subtitle, margin, margin + 11.5, page_w - 2 * margin, 4.5, font_size=7.5, color="#64748b")

    # 2. Dual Map Frames (Paired Side-by-Side)
    map_y = margin + header_h + gap
    bottom_h = 24.0
    map_h = page_h - map_y - margin - bottom_h - gap
    single_w = (page_w - 2 * margin - gap) / 2.0

    # Map A (Left)
    map_a_x = margin
    _create_card_shape(layout, map_a_x, map_y, single_w, 6.0, bg_color="#dbeafe", border_color="#93c5fd", border_width_mm=0.2)
    _create_label(layout, lbl_a, map_a_x + 4.0, map_y + 1.0, single_w - 8.0, 4.5, font_size=7.5, bold=True, color="#1e40af")

    map_a = _create_map_frame(
        layout, "cartolab_diptych_map_a", map_a_x, map_y + 6.0, single_w, map_h - 6.0,
        layers=res_layers_a, extent=res_extent, crs=crs, frame_color="#2563eb", frame_width_mm=0.35
    )

    # Map B (Right)
    map_b_x = margin + single_w + gap
    _create_card_shape(layout, map_b_x, map_y, single_w, 6.0, bg_color="#dcfce7", border_color="#86efac", border_width_mm=0.2)
    _create_label(layout, lbl_b, map_b_x + 4.0, map_y + 1.0, single_w - 8.0, 4.5, font_size=7.5, bold=True, color="#166534")

    map_b = _create_map_frame(
        layout, "cartolab_diptych_map_b", map_b_x, map_y + 6.0, single_w, map_h - 6.0,
        layers=res_layers_b, extent=res_extent, crs=crs, frame_color="#16a34a", frame_width_mm=0.35
    )

    # 3. Bottom Shared Synthesis & Legend Bar
    bar_y = map_y + map_h + gap
    bar_w = page_w - 2 * margin
    _create_card_shape(layout, margin, bar_y, bar_w, bottom_h, bg_color="#f8fafc", border_color="#e2e8f0", border_width_mm=0.3)

    # Comparative summary on left
    comp_note = "Evaluation: Scenario B achieves +28% spatial integration and 40% reduction in peripheral isolation."
    _create_label(layout, comp_note, margin + 6.0, bar_y + 3.0, bar_w * 0.45, bottom_h - 6.0, font_size=7.5, color="#334155")

    # Center Scale Bar & North Arrow
    if map_a is not None:
        _create_scalebar(layout, map_a, margin + bar_w * 0.48, bar_y + 4.0, style="Line Ticks Up")
    _add_north_arrow(layout, margin + bar_w * 0.70, bar_y + 3.0, size=12.0)

    # Right metadata
    now_str = datetime.date.today().strftime("%Y-%m-%d")
    right_text = f"{credits}\nCRS: [% @project_crs %]  ·  {now_str}"
    _create_label(layout, right_text, margin + bar_w * 0.76, bar_y + 3.0, bar_w * 0.22, bottom_h - 6.0, font_size=7.0, color="#64748b", h_align="right")

    if theme and theme != "swiss_modern":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "swiss_modern")

    if proj is not None and hasattr(proj, "layoutManager"):
        proj.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


# ===========================================================================
# Template Registry & Factory
# ===========================================================================

TEMPLATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "report_figure": {
        "id": "report_figure",
        "name": "Report & Slide Figure (16:9 / A4)",
        "tagline": "Widescreen presentation & executive report figure",
        "description": "Widescreen 16:9 layout with prominent figure title, hero map frame, and compact right HUD card with key takeaways and filtered legend.",
        "features": ["16:9 Widescreen Landscape", "Hero Map Frame (~72% width)", "Right HUD Sidebar Card", "Metric Takeaway Callouts", "Filtered Legend & Scale Bar"],
        "page_size": "A4",
        "default_page": "A4",
        "landscape": True,
        "default_landscape": True,
        "preset": "swiss_modern",
        "theme": "swiss_modern",
        "category": "Presentation & Reporting",
        "icon": "layout.png",
        "builder": create_report_figure_layout,
    },
    "academic_journal": {
        "id": "academic_journal",
        "name": "Academic Journal Figure (A4 2-Column)",
        "tagline": "Formal peer-reviewed journal figure & scientific report",
        "description": "Formal 2-column scientific layout with double-column map, caption box, methodology note, academic legend, and formal citation block.",
        "features": ["A4 Portrait 2-Column Format", "Full-Width Hero Map with Neatline", "Formal Figure Caption & Methodology", "Stepped Line Scale Bar", "Standardized Citation Block"],
        "page_size": "A4",
        "default_page": "A4",
        "landscape": False,
        "default_landscape": False,
        "preset": "academic_serif",
        "theme": "academic_serif",
        "category": "Scientific & Academic",
        "icon": "layout.png",
        "builder": create_academic_journal_layout,
    },
    "exhibition_poster": {
        "id": "exhibition_poster",
        "name": "Exhibition & Competition Poster (A1/A2)",
        "tagline": "Large-format presentation poster for competitions & exhibitions",
        "description": "Large-format presentation poster with bold dark banner, dominant hero map frame, regional locator map, and thematic legend cards.",
        "features": ["A1/A2 Large-Format Landscape", "Bold High-Contrast Header Banner", "Dominant Hero Map Frame (~70%)", "Regional Locator Inset Map Card", "Thematic Legend & Metric Cards"],
        "page_size": "A1",
        "default_page": "A1",
        "landscape": True,
        "default_landscape": True,
        "preset": "swiss_modern",
        "theme": "swiss_modern",
        "category": "Exhibition & Posters",
        "icon": "layout.png",
        "builder": create_poster_exhibition_layout,
    },
    "fact_sheet": {
        "id": "fact_sheet",
        "name": "Executive Fact Sheet (A4 Portrait)",
        "tagline": "Executive 1-page briefing with summary metrics & findings",
        "description": "Executive summary with top 4 KPI metric cards, central thematic map, and bottom analytical narrative & policy recommendation block.",
        "features": ["A4 Portrait Executive 1-Pager", "4 Top KPI Metric Summary Cards", "Central Thematic Map Frame", "Analytical Narrative & Callouts", "Thematic Legend & Action Points"],
        "page_size": "A4",
        "default_page": "A4",
        "landscape": False,
        "default_landscape": False,
        "preset": "swiss_modern",
        "theme": "swiss_modern",
        "category": "Executive & Briefing",
        "icon": "layout.png",
        "builder": create_fact_sheet_layout,
    },
    "diptych": {
        "id": "diptych",
        "name": "Side-by-Side Diptych (Comparative A/B)",
        "tagline": "Comparative dual-map layout for scenario or before/after analysis",
        "description": "Comparative dual-map layout with paired synchronized map frames for before/after or scenario comparison with badges and shared legend.",
        "features": ["A4/A3 Comparative Landscape", "Paired Synchronized Map Frames", "Scenario A & B Header Badges", "Shared Extent, Scale & CRS", "Bottom Comparative Synthesis Bar"],
        "page_size": "A4",
        "default_page": "A4",
        "landscape": True,
        "default_landscape": True,
        "preset": "swiss_modern",
        "theme": "swiss_modern",
        "category": "Comparative & Scenarios",
        "icon": "layout.png",
        "builder": create_side_by_side_diptych_layout,
    },
}

TEMPLATE_GALLERY = TEMPLATE_REGISTRY

_ALIASES: Dict[str, str] = {
    "poster_exhibition": "exhibition_poster",
    "side_by_side_diptych": "diptych",
}


def list_templates() -> List[Dict[str, Any]]:
    """Return list of all available layout archetype template definitions."""
    return list(TEMPLATE_REGISTRY.values())


def get_template_info(template_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve template definition metadata by archetype ID."""
    canonical_id = _ALIASES.get(template_id.lower(), template_id.lower())
    return TEMPLATE_REGISTRY.get(canonical_id)


def create_template_layout(
    template_id: str,
    iface=None,
    *,
    project: Optional[QgsProject] = None,
    **kwargs,
) -> Optional[QgsPrintLayout]:
    """
    Instantiate a layout from a named template archetype.

    Supported archetype IDs:
      - 'report_figure'
      - 'academic_journal'
      - 'poster_exhibition' (or 'exhibition_poster')
      - 'fact_sheet'
      - 'side_by_side_diptych' (or 'diptych')
    """
    canonical_id = _ALIASES.get(template_id.lower(), template_id.lower())
    meta = TEMPLATE_REGISTRY.get(canonical_id)
    if not meta:
        valid_keys = list(TEMPLATE_REGISTRY.keys()) + list(_ALIASES.keys())
        raise ValueError(f"Unknown template archetype: '{template_id}'. Available: {valid_keys}")

    builder_func = meta["builder"]
    return builder_func(iface=iface, project=project, **kwargs)


# Convenience aliases for layout automation package
create_report_figure = create_report_figure_layout
create_academic_journal = create_academic_journal_layout
create_exhibition_poster = create_poster_exhibition_layout
create_fact_sheet = create_fact_sheet_layout
create_diptych = create_side_by_side_diptych_layout
