# -*- coding: utf-8 -*-
"""Advanced, workflow-specific layouts for the 02CartoLab template gallery."""
from __future__ import annotations

import datetime
from typing import List, Optional, Tuple

try:
    from qgis.core import QgsPrintLayout, QgsProject, QgsRectangle
except ImportError:
    QgsPrintLayout = QgsProject = QgsRectangle = None

from ..core.layout_math import page_size_mm
from .grid_presets import apply_grid_preset
from .paper_themes import apply_paper_theme
from .template_gallery import (
    _add_north_arrow,
    _create_base_layout,
    _create_card_shape,
    _create_label,
    _create_legend,
    _create_map_frame,
    _create_scalebar,
    _resolve_crs,
    _resolve_extent,
    _resolve_layers,
)
from .typography_engine import apply_typography_hierarchy


def _context(iface, project, layers, extent, crs):
    proj = project or (QgsProject.instance() if QgsProject else None)
    resolved_layers = layers if layers is not None else _resolve_layers(iface, proj)
    resolved_crs = crs or _resolve_crs(iface, proj, resolved_layers)
    resolved_extent = extent if extent is not None else _resolve_extent(
        iface, resolved_layers, target_crs=resolved_crs, project=proj
    )
    return proj, resolved_layers, resolved_extent, resolved_crs


def _finish(layout, project, theme):
    if theme and theme != "swiss_modern":
        apply_paper_theme(layout, theme)
    apply_typography_hierarchy(layout, preset=theme or "swiss_modern")
    if project is not None and hasattr(project, "layoutManager"):
        project.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


def _project_meta(crs, credits: str) -> str:
    authid = crs.authid() if crs is not None and crs.isValid() else "Project CRS"
    return f"{credits}  ·  {authid}  ·  {datetime.date.today():%Y-%m-%d}"


def _metric_cards(layout, cards: List[Tuple[str, str]], x, y, width, height, gap=4.0):
    card_w = (width - gap * (len(cards) - 1)) / max(1, len(cards))
    for index, (label, value) in enumerate(cards):
        cx = x + index * (card_w + gap)
        _create_card_shape(layout, cx, y, card_w, height, bg_color="#f8fafc",
                           border_color="#dbe4ee", border_width_mm=0.25)
        _create_label(layout, label.upper(), cx + 3, y + 2.5, card_w - 6, 4,
                      font_size=6.8, bold=True, color="#64748b")
        _create_label(layout, value, cx + 3, y + 7, card_w - 6, height - 9,
                      font_size=11, bold=True, color="#0f172a")


def create_utm_field_sheet_layout(
    iface=None, *, layers: Optional[List] = None, extent: Optional[QgsRectangle] = None,
    crs=None, title="UTM Field Reference Sheet", subtitle="Metric navigation and site documentation",
    credits="02CartoLab · Field Operations", page_size="A4", landscape=True,
    theme="swiss_modern", layout_name="UTM Field Sheet", project=None, **kwargs,
) -> Optional[QgsPrintLayout]:
    """Create a dependency-free UTM field sheet inspired by responsive QPT grids."""
    proj, resolved_layers, resolved_extent, resolved_crs = _context(
        iface, project, layers, extent, crs
    )
    page_w, page_h = page_size_mm(page_size, landscape)
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None
    margin, gap, header_h, footer_h = 12.0, 5.0, 25.0, 18.0
    side_w = max(48.0, (page_w - 2 * margin) * 0.19)
    map_x, map_y = margin, margin + header_h
    map_w = page_w - 2 * margin - side_w - gap
    map_h = page_h - map_y - margin - footer_h

    _create_label(layout, "FIELD MAP · PROJECTED COORDINATES", margin, margin, page_w - 2 * margin,
                  4.5, font_size=7, bold=True, color="#2563eb")
    _create_label(layout, title, margin, margin + 4.5, page_w - 2 * margin, 8,
                  font_size=14, bold=True, color="#0f172a", item_id="cartolab_title")
    _create_label(layout, subtitle, margin, margin + 12.5, page_w - 2 * margin, 5,
                  font_size=8, color="#64748b", item_id="cartolab_subtitle")
    map_item = _create_map_frame(layout, "cartolab_utm_map", map_x, map_y, map_w, map_h,
                                 layers=resolved_layers, extent=resolved_extent, crs=resolved_crs,
                                 frame_color="#0f172a", frame_width_mm=0.35)
    if map_item is not None:
        projected = resolved_crs is not None and resolved_crs.isValid() and not resolved_crs.isGeographic()
        # Label inside the frame: the sidebar, header and footer leave no
        # margin around the map for outside coordinate labels.
        apply_grid_preset(layout, "utm_field" if projected else "graticule", map_item,
                          annotations_inside=True, annotation_sides="left_bottom")
        _add_north_arrow(layout, map_x + map_w - 15, map_y + 4, size=11)

    side_x = map_x + map_w + gap
    _create_card_shape(layout, side_x, map_y, side_w, map_h, bg_color="#ffffff",
                       border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "MAP REFERENCE", side_x + 4, map_y + 4, side_w - 8, 5,
                  font_size=7, bold=True, color="#2563eb")
    if map_item is not None:
        _create_legend(layout, map_item, side_x + 4, map_y + 11, side_w - 8, map_h * 0.43,
                       title="Layers")
        _create_scalebar(layout, map_item, side_x + 4, map_y + map_h - 20,
                         segments=2, max_width_mm=side_w - 10)
    reference = (
        "Coordinate reference\n"
        f"{resolved_crs.authid() if resolved_crs and resolved_crs.isValid() else 'Project CRS'}\n\n"
        "Grid system\nMetric working grid\n\n"
        "Field notes\n________________\n________________\n________________"
    )
    _create_label(layout, reference, side_x + 4, map_y + map_h * 0.56, side_w - 8,
                  map_h * 0.27, font_size=7.2, color="#334155")
    _create_label(layout, _project_meta(resolved_crs, credits), margin,
                  page_h - margin - footer_h + 5, page_w - 2 * margin, 5,
                  font_size=6.8, color="#64748b", item_id="cartolab_footer")
    return _finish(layout, proj, theme)


def create_planning_board_layout(
    iface=None, *, layers=None, extent=None, crs=None,
    title="Planning Review Board", subtitle="Spatial framework, key indicators and decision record",
    credits="02CartoLab · Planning Studio", page_size="A3", landscape=True,
    theme="swiss_modern", layout_name="Planning Review Board", project=None, **kwargs,
) -> Optional[QgsPrintLayout]:
    """Create a review-board composition with a hero map, metrics and decision sidebar."""
    proj, resolved_layers, resolved_extent, resolved_crs = _context(iface, project, layers, extent, crs)
    page_w, page_h = page_size_mm(page_size, landscape)
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None
    margin, gap, header_h, metrics_h = 14.0, 6.0, 24.0, 25.0
    content_y = margin + header_h
    content_h = page_h - content_y - margin - metrics_h - gap
    sidebar_w = max(78.0, (page_w - 2 * margin) * 0.24)
    map_w = page_w - 2 * margin - sidebar_w - gap
    _create_label(layout, "URBAN PLANNING · REVIEW PACKAGE", margin, margin, page_w - 2 * margin,
                  5, font_size=7.5, bold=True, color="#2563eb")
    _create_label(layout, title, margin, margin + 5, page_w - 2 * margin, 9,
                  font_size=16, bold=True, color="#0f172a", item_id="cartolab_title")
    _create_label(layout, subtitle, margin, margin + 14, page_w - 2 * margin, 5,
                  font_size=8.5, color="#64748b", item_id="cartolab_subtitle")
    map_item = _create_map_frame(layout, "cartolab_board_map", margin, content_y, map_w, content_h,
                                 layers=resolved_layers, extent=resolved_extent, crs=resolved_crs,
                                 frame_color="#0f172a", frame_width_mm=0.35)
    if map_item:
        _add_north_arrow(layout, margin + map_w - 17, content_y + 5, size=12)
        _create_card_shape(layout, margin + 4, content_y + content_h - 20, 86, 18,
                           bg_color="#ffffff", border_color="#e2e8f0", border_width_mm=0.2)
        _create_scalebar(layout, map_item, margin + 7, content_y + content_h - 15,
                         max_width_mm=min(80, map_w * 0.35))
    sx = margin + map_w + gap
    _create_card_shape(layout, sx, content_y, sidebar_w, content_h, bg_color="#f8fafc",
                       border_color="#cbd5e1", border_width_mm=0.3)
    _create_label(layout, "DECISION SUPPORT", sx + 5, content_y + 5, sidebar_w - 10, 5,
                  font_size=7.5, bold=True, color="#2563eb")
    if map_item:
        _create_legend(layout, map_item, sx + 5, content_y + 12, sidebar_w - 10,
                       content_h * 0.48, title="Plan layers")
    notes = "Review status\n□ Draft   □ Technical review   □ Approved\n\nKey decision\n________________________________\n________________________________\n\nConditions / actions\n• ______________________________\n• ______________________________"
    _create_label(layout, notes, sx + 5, content_y + content_h * 0.57,
                  sidebar_w - 10, content_h * 0.38, font_size=7.6, color="#334155")
    cards_y = content_y + content_h + gap
    _metric_cards(layout, [("Study area", "— km²"), ("Population", "—"),
                           ("Development", "— ha"), ("Review stage", "Draft")],
                  margin, cards_y, page_w - 2 * margin, metrics_h)
    return _finish(layout, proj, theme)


def create_data_story_layout(
    iface=None, *, layers=None, extent=None, crs=None,
    title="Spatial Data Story", subtitle="From geographic pattern to planning implication",
    credits="02CartoLab · Spatial Narrative", page_size="A3", landscape=False,
    theme="warm_editorial", layout_name="Spatial Data Story", project=None, **kwargs,
) -> Optional[QgsPrintLayout]:
    """Create a portrait editorial page with map, findings and methods blocks."""
    proj, resolved_layers, resolved_extent, resolved_crs = _context(iface, project, layers, extent, crs)
    page_w, page_h = page_size_mm(page_size, landscape)
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None
    margin, gap, header_h = 14.0, 6.0, 27.0
    _create_label(layout, "SPATIAL NARRATIVE · ISSUE 01", margin, margin, page_w - 2 * margin,
                  5, font_size=7.2, bold=True, color="#b45309")
    _create_label(layout, title, margin, margin + 5, page_w - 2 * margin, 10,
                  font_size=18, bold=True, color="#1c1917", item_id="cartolab_title")
    _create_label(layout, subtitle, margin, margin + 16, page_w - 2 * margin, 6,
                  font_size=9, color="#78716c", item_id="cartolab_subtitle")
    map_y = margin + header_h
    map_h = page_h * 0.49
    map_item = _create_map_frame(layout, "cartolab_story_map", margin, map_y,
                                 page_w - 2 * margin, map_h, layers=resolved_layers,
                                 extent=resolved_extent, crs=resolved_crs,
                                 frame_color="#292524", frame_width_mm=0.3)
    if map_item:
        _add_north_arrow(layout, page_w - margin - 16, map_y + 5, size=11)
        _create_card_shape(layout, margin + 4, map_y + map_h - 19, 88, 17,
                           bg_color="#ffffff", border_color="#e7e5e4", border_width_mm=0.2)
        _create_scalebar(layout, map_item, margin + 7, map_y + map_h - 14,
                         max_width_mm=min(80, (page_w - 2 * margin) * 0.4))
    body_y = map_y + map_h + gap
    body_h = page_h - body_y - margin
    col_w = (page_w - 2 * margin - gap) / 2
    _create_card_shape(layout, margin, body_y, col_w, body_h, bg_color="#fffdf8",
                       border_color="#e7e5e4", border_width_mm=0.25)
    _create_label(layout, "WHAT THE MAP REVEALS", margin + 5, body_y + 5, col_w - 10, 5,
                  font_size=7.5, bold=True, color="#b45309")
    _create_label(layout, "1  Core pattern\nDescribe the principal concentration or corridor.\n\n2  Spatial contrast\nExplain the most important difference between places.\n\n3  Planning implication\nConnect the observed pattern to an actionable decision.",
                  margin + 5, body_y + 12, col_w - 10, body_h - 17,
                  font_size=8.2, color="#44403c")
    rx = margin + col_w + gap
    _create_card_shape(layout, rx, body_y, col_w, body_h, bg_color="#f8fafc",
                       border_color="#e2e8f0", border_width_mm=0.25)
    _create_label(layout, "LEGEND & METHOD", rx + 5, body_y + 5, col_w - 10, 5,
                  font_size=7.5, bold=True, color="#2563eb")
    if map_item:
        _create_legend(layout, map_item, rx + 5, body_y + 12, col_w - 10,
                       body_h * 0.55, title="Map variables")
    _create_label(layout, _project_meta(resolved_crs, credits), rx + 5,
                  body_y + body_h - 12, col_w - 10, 7, font_size=6.8, color="#64748b")
    return _finish(layout, proj, theme)


def create_atlas_production_layout(
    iface=None, *, layers=None, extent=None, crs=None,
    title="District Map Book", subtitle="Atlas-ready standardized production sheet",
    credits="02CartoLab · Atlas Production", page_size="A4", landscape=False,
    theme="swiss_modern", layout_name="Atlas Production Sheet", project=None, **kwargs,
) -> Optional[QgsPrintLayout]:
    """Create an atlas-ready sheet with consistent marginalia and page expressions."""
    proj, resolved_layers, resolved_extent, resolved_crs = _context(iface, project, layers, extent, crs)
    page_w, page_h = page_size_mm(page_size, landscape)
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None
    margin, header_h, footer_h = 12.0, 24.0, 18.0
    _create_card_shape(layout, margin, margin, page_w - 2 * margin, header_h,
                       bg_color="#0f172a", border_color="#0f172a", border_width_mm=0)
    _create_label(layout, "MAP BOOK · [% @atlas_featurenumber %] / [% @atlas_totalfeatures %]",
                  margin + 5, margin + 4, page_w - 2 * margin - 10, 4,
                  font_size=7, bold=True, color="#93c5fd", item_id="cartolab_atlas_banner")
    _create_label(layout, title, margin + 5, margin + 8, page_w - 2 * margin - 10, 8,
                  font_size=14, bold=True, color="#ffffff", item_id="cartolab_title")
    _create_label(layout, subtitle, margin + 5, margin + 16, page_w - 2 * margin - 10, 5,
                  font_size=7.5, color="#cbd5e1", item_id="cartolab_subtitle")
    map_y = margin + header_h + 5
    map_h = page_h - map_y - margin - footer_h - 5
    map_item = _create_map_frame(layout, "cartolab_atlas_map", margin, map_y,
                                 page_w - 2 * margin, map_h, layers=resolved_layers,
                                 extent=resolved_extent, crs=resolved_crs,
                                 frame_color="#0f172a", frame_width_mm=0.4)
    if map_item:
        _add_north_arrow(layout, page_w - margin - 16, map_y + 5, size=11)
        _create_card_shape(layout, margin + 4, map_y + 4, 54, min(62, map_h * 0.34),
                           bg_color="#ffffff", border_color="#e2e8f0", border_width_mm=0.2)
        _create_legend(layout, map_item, margin + 5, map_y + 5, 50, min(58, map_h * 0.31),
                       title="Legend")
        _create_scalebar(layout, map_item, margin + 5, map_y + map_h - 15,
                         max_width_mm=65)
    footer_y = page_h - margin - footer_h
    _create_card_shape(layout, margin, footer_y, page_w - 2 * margin, footer_h,
                       bg_color="#f8fafc", border_color="#cbd5e1", border_width_mm=0.25)
    _create_label(layout, "AREA: [% coalesce(@atlas_feature, 'Coverage feature') %]",
                  margin + 4, footer_y + 3, (page_w - 2 * margin) * 0.55, 5,
                  font_size=7, bold=True, color="#0f172a", item_id="cartolab_atlas_area")
    _create_label(layout, _project_meta(resolved_crs, credits), margin + 4, footer_y + 9,
                  page_w - 2 * margin - 8, 5, font_size=6.5, color="#64748b")
    return _finish(layout, proj, theme)


def create_emergency_brief_layout(
    iface=None, *, layers=None, extent=None, crs=None,
    title="Operational Situation Map", subtitle="Current extent, access and response priorities",
    credits="02CartoLab · Operations", page_size="A4", landscape=True,
    theme="swiss_modern", layout_name="Emergency Operations Brief", project=None, **kwargs,
) -> Optional[QgsPrintLayout]:
    """Create a high-clarity operational map with status and action panels."""
    proj, resolved_layers, resolved_extent, resolved_crs = _context(iface, project, layers, extent, crs)
    page_w, page_h = page_size_mm(page_size, landscape)
    layout = _create_base_layout(proj, layout_name, page_w, page_h)
    if layout is None:
        return None
    margin, gap, header_h = 11.0, 5.0, 22.0
    _create_card_shape(layout, margin, margin, page_w - 2 * margin, header_h,
                       bg_color="#991b1b", border_color="#7f1d1d", border_width_mm=0.3)
    _create_label(layout, "OPERATIONAL BRIEF · CURRENT SITUATION", margin + 5, margin + 3,
                  page_w - 2 * margin - 10, 4, font_size=7, bold=True, color="#fecaca")
    _create_label(layout, title, margin + 5, margin + 7, page_w - 2 * margin - 10, 8,
                  font_size=15, bold=True, color="#ffffff", item_id="cartolab_title")
    _create_label(layout, subtitle, margin + 5, margin + 15, page_w - 2 * margin - 10, 4,
                  font_size=7.5, color="#fee2e2", item_id="cartolab_subtitle")
    content_y = margin + header_h + gap
    content_h = page_h - content_y - margin
    sidebar_w = max(64.0, (page_w - 2 * margin) * 0.25)
    map_w = page_w - 2 * margin - sidebar_w - gap
    map_item = _create_map_frame(layout, "cartolab_operations_map", margin, content_y,
                                 map_w, content_h, layers=resolved_layers, extent=resolved_extent,
                                 crs=resolved_crs, frame_color="#7f1d1d", frame_width_mm=0.45)
    if map_item:
        projected = resolved_crs is not None and resolved_crs.isValid() and not resolved_crs.isGeographic()
        # Inside labels on the free edges (the scale-bar card sits bottom-left).
        apply_grid_preset(layout, "survey_crosshair" if projected else "graticule", map_item,
                          annotations_inside=True, annotation_sides="left_top")
        _add_north_arrow(layout, margin + map_w - 16, content_y + 5, size=11)
        _create_card_shape(layout, margin + 4, content_y + content_h - 20, 80, 18,
                           bg_color="#ffffff", border_color="#fecaca", border_width_mm=0.2)
        _create_scalebar(layout, map_item, margin + 7, content_y + content_h - 15,
                         max_width_mm=70)
    sx = margin + map_w + gap
    _create_card_shape(layout, sx, content_y, sidebar_w, content_h, bg_color="#fff7ed",
                       border_color="#fdba74", border_width_mm=0.3)
    _create_label(layout, "STATUS & PRIORITIES", sx + 5, content_y + 5, sidebar_w - 10, 5,
                  font_size=7.5, bold=True, color="#9a3412")
    _create_label(layout, "STATUS  □ WATCH  □ ACTIVE  □ CLOSED\n\nPriority locations\n1. ____________________\n2. ____________________\n3. ____________________\n\nAccess constraints\n• _____________________\n• _____________________\n\nNext update  ____ : ____",
                  sx + 5, content_y + 13, sidebar_w - 10, content_h * 0.54,
                  font_size=7.4, color="#431407")
    if map_item:
        _create_legend(layout, map_item, sx + 5, content_y + content_h * 0.60,
                       sidebar_w - 10, content_h * 0.34, title="Operational layers")
    return _finish(layout, proj, theme)
