# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Paper Themes & Canvas Styling Engine.

Applies artistic paper background colors, border styles, grid color palettes,
and font color schemes directly to QgsLayout pages and layout items.
"""
from __future__ import annotations

from contextlib import suppress
from typing import Dict, Any

try:
    import sip
except ImportError:
    try:
        from qgis.PyQt import sip
    except ImportError:
        sip = None

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemPage,
        QgsLayoutItemLabel,
        QgsLayoutItemShape,
        QgsLayoutItemMap,
        QgsLayoutItemLegend,
        QgsLayoutItemScaleBar,
        QgsLayoutItemPicture,
        QgsLegendStyle,
        QgsFillSymbol,
    )
    from qgis.PyQt.QtGui import QColor, QFont
except ImportError:
    QgsLayout = QgsLayoutItemPage = QgsLayoutItemLabel = QgsLayoutItemShape = QgsLayoutItemMap = None
    QgsLayoutItemLegend = QgsLayoutItemScaleBar = QgsLayoutItemPicture = QgsLegendStyle = QgsFillSymbol = QColor = QFont = None


PAPER_THEMES: Dict[str, Dict[str, Any]] = {
    "swiss_modern": {
        "name": "Modern Swiss Minimalist",
        "bg_color": "#ffffff",
        "text_color": "#18181b",
        "grid_color": "#e4e4e7",
        "frame_color": "#27272a",
    },
    "blueprint": {
        "name": "Architectural Blueprint",
        "bg_color": "#0b2545",
        "text_color": "#e0f2fe",
        "grid_color": "#134074",
        "frame_color": "#38bdf8",
    },
    "dark_matter": {
        "name": "Dark Matter / Obsidian Urban",
        "bg_color": "#0f172a",
        "text_color": "#f8fafc",
        "grid_color": "#1e293b",
        "frame_color": "#475569",
    },
    "sepia_atlas": {
        "name": "Vintage Sepia Atlas",
        "bg_color": "#f4ebd9",
        "text_color": "#3d2612",
        "grid_color": "#d4c5b9",
        "frame_color": "#6e473b",
    },
    "warm_editorial": {
        "name": "Warm Editorial Newsprint",
        "bg_color": "#fdfbf7",
        "text_color": "#292524",
        "grid_color": "#e7e5e4",
        "frame_color": "#78716c",
    },
    "japanese_washi": {
        "name": "Japanese Washi Minimal",
        "bg_color": "#f7f6f2",
        "text_color": "#1c1917",
        "grid_color": "#e2e0d8",
        "frame_color": "#a8a29e",
    },
}


def apply_paper_theme(layout: QgsLayout, theme_key: str = "blueprint") -> bool:
    """
    Apply paper background color, label text colors, and grid colors to a layout.
    Returns True if successfully applied. Safe against C++ access violations.
    """
    if layout is None or QgsLayoutItemPage is None:
        return False

    theme = PAPER_THEMES.get(theme_key, PAPER_THEMES["swiss_modern"])
    text_qcolor = QColor(theme["text_color"]) if QColor else None
    frame_qcolor = QColor(theme["frame_color"]) if QColor else None
    bg_qcolor = QColor(theme["bg_color"]) if QColor else None

    # 1. Update Page Item background color safely using new fill symbol
    page_collection = layout.pageCollection()
    if page_collection:
        for page in page_collection.pages():
            if sip and sip.isdeleted(page):
                continue
            if QgsFillSymbol:
                sym = QgsFillSymbol.createSimple({"color": theme["bg_color"], "outline_style": "no"})
                if sym:
                    page.setPageStyleSymbol(sym)

    # 2. Update all layout items safely
    items = list(layout.items())
    for item in items:
        if sip and sip.isdeleted(item):
            continue
        with suppress(Exception):
            if isinstance(item, QgsLayoutItemLabel) and text_qcolor:
                item.setFontColor(text_qcolor)
                f_lbl = item.font()
                f_lbl.setFamily("Segoe UI")
                item.setFont(f_lbl)
                item.setBackgroundEnabled(False)
                if hasattr(item, "id") and item.id() == "cartolab_north_arrow_label":
                    with suppress(Exception):
                        tf_na = item.textFormat()
                        tf_na.setFont(f_lbl)
                        tf_na.setColor(text_qcolor)
                        buf_na = tf_na.buffer()
                        buf_na.setEnabled(True)
                        buf_na.setSize(0.75)
                        buf_na.setColor(QColor(theme["bg_color"] if theme_key in ("dark_matter", "blueprint") else "#ffffff"))
                        buf_na.setOpacity(0.90)
                        tf_na.setBuffer(buf_na)
                        item.setTextFormat(tf_na)
            elif isinstance(item, QgsLayoutItemMap):
                item.setFrameEnabled(True)
                if hasattr(item, "setFrameStrokeColor") and frame_qcolor:
                    item.setFrameStrokeColor(frame_qcolor)
                elif hasattr(item, "setFrameColor") and frame_qcolor:
                    item.setFrameColor(frame_qcolor)
                if theme_key in ("dark_matter", "blueprint") and bg_qcolor:
                    item.setBackgroundColor(bg_qcolor)
                    item.setBackgroundEnabled(True)
                # Update map grids font
                if hasattr(item, "grids"):
                    halo_color = QColor(theme["bg_color"] if theme_key in ("dark_matter", "blueprint") else "#ffffff")
                    for grid in list(item.grids().asList()):
                        f_grid = QFont("Segoe UI", 8)
                        f_grid.setFamily("Segoe UI")
                        grid.setAnnotationFont(f_grid)
                        if text_qcolor:
                            grid.setAnnotationFontColor(text_qcolor)
                        if hasattr(grid, "annotationTextFormat") and hasattr(grid, "setAnnotationTextFormat"):
                            with suppress(Exception):
                                tf_g = grid.annotationTextFormat()
                                tf_g.setFont(f_grid)
                                if text_qcolor:
                                    tf_g.setColor(text_qcolor)
                                buf_g = tf_g.buffer()
                                buf_g.setEnabled(True)
                                buf_g.setSize(0.85)
                                buf_g.setColor(halo_color)
                                buf_g.setOpacity(0.90)
                                tf_g.setBuffer(buf_g)
                                grid.setAnnotationTextFormat(tf_g)
            elif QgsLayoutItemLegend and isinstance(item, QgsLayoutItemLegend):
                if theme_key in ("dark_matter", "blueprint") and bg_qcolor:
                    item.setBackgroundColor(bg_qcolor)
                    item.setBackgroundEnabled(True)
                else:
                    item.setBackgroundEnabled(False)
                if hasattr(item, "setFontColor") and text_qcolor:
                    item.setFontColor(text_qcolor)
                with suppress(Exception):
                    w_leg = float(item.rect().width())
                    h_leg = float(item.rect().height())
                    if w_leg > 0 and h_leg > 0:
                        from .map_sheet import _fit_legend_to_box
                        _fit_legend_to_box(item, w_leg, h_leg)
                if hasattr(item, "rstyle") and QgsLegendStyle:
                    from .layout_utils import set_legend_style_text
                    fit_pt = float(item.customProperty("cartolab/legend_fit_font_pt", 8.5) or 8.5)
                    style_sizes = {
                        "Title": min(10.0, fit_pt + 1.2),
                        "Group": min(9.5, fit_pt + 0.8),
                        "Subgroup": min(9.0, fit_pt + 0.4),
                        "SymbolLabel": fit_pt,
                    }
                    for style_attr, sz in style_sizes.items():
                        with suppress(Exception):
                            style_enum = getattr(QgsLegendStyle, style_attr, getattr(getattr(QgsLegendStyle, "Style", None), style_attr, None))
                            if style_enum is not None:
                                f_leg = QFont("Segoe UI", int(round(sz)))
                                f_leg.setFamily("Segoe UI")
                                if hasattr(f_leg, "setPointSizeF"):
                                    f_leg.setPointSizeF(float(sz))
                                f_leg.setBold(style_attr in ("Title", "Group"))
                                set_legend_style_text(item, style_enum, f_leg, text_qcolor or None)
                with suppress(Exception):
                    item.setAutoUpdateModel(False)
                    item.updateLegend()
            elif QgsLayoutItemScaleBar and isinstance(item, QgsLayoutItemScaleBar):
                with suppress(Exception):
                    tf_sb = item.textFormat()
                    f_sb = QFont("Segoe UI", 8)
                    f_sb.setFamily("Segoe UI")
                    tf_sb.setFont(f_sb)
                    if text_qcolor:
                        tf_sb.setColor(text_qcolor)
                        item.setFontColor(text_qcolor)
                        item.setLineColor(text_qcolor)
                        item.setFillColor(text_qcolor)
                    if bg_qcolor:
                        item.setFillColor2(bg_qcolor)
                    item.setTextFormat(tf_sb)
            elif isinstance(item, QgsLayoutItemPicture):
                with suppress(Exception):
                    item.setBackgroundEnabled(False)
                    item.setFrameEnabled(False)
                    if hasattr(item, "setSvgFillColor") and text_qcolor:
                        item.setSvgFillColor(text_qcolor)
                    if hasattr(item, "setSvgStrokeColor") and text_qcolor:
                        item.setSvgStrokeColor(text_qcolor)
            elif isinstance(item, QgsLayoutItemShape):
                with suppress(Exception):
                    if theme_key in ("dark_matter", "blueprint") and QgsFillSymbol:
                        sym = QgsFillSymbol.createSimple({
                            "color": theme["bg_color"],
                            "outline_color": theme["frame_color"],
                            "outline_width": "0.3",
                        })
                        if sym:
                            item.setSymbol(sym)
            elif hasattr(item, "id") and item.id() == "cartolab_north_arrow":
                with suppress(Exception):
                    if text_qcolor and QgsFillSymbol and hasattr(item, "setSymbol"):
                        outline_col = theme["bg_color"] if theme_key in ("dark_matter", "blueprint") else "#ffffff"
                        sym = QgsFillSymbol.createSimple({
                            "color": text_qcolor.name(),
                            "outline_color": outline_col,
                            "outline_width": "0.35",
                        })
                        item.setSymbol(sym)
            elif hasattr(item, "id") and item.id() == "cartolab_north_arrow_label":
                with suppress(Exception):
                    if text_qcolor and hasattr(item, "setFontColor"):
                        item.setFontColor(text_qcolor)

    with suppress(Exception):
        layout.invalidateCache()
        layout.refresh()
    return True
