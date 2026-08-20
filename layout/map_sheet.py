# -*- coding: utf-8 -*-
"""
Auto Map Sheet — one-click publication-ready print layout.

Assembles a complete :class:`QgsPrintLayout` from the current map view:
titled map frame at the current extent, filtered legend, scale bar,
north arrow, optional coordinate grid, neat-line and credits. The result
is added to the project's layout manager so it opens straight in the
Layout Designer.
"""
from __future__ import annotations

from contextlib import suppress
from typing import List, Optional

try:
    from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
    from qgis.PyQt.QtCore import QPointF
    from qgis.core import (
        QgsProject,
        QgsPrintLayout,
        QgsLayoutItemMap,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemScaleBar,
        QgsLayoutItemPicture,
        QgsLayoutItemPolygon,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLayoutMeasurement,
        QgsUnitTypes,
        QgsRectangle,
        QgsFillSymbol,
    )
    _MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except ImportError:
    QColor = QFont = QPolygonF = QPointF = None
    QgsProject = QgsPrintLayout = QgsLayoutItemMap = QgsLayoutItemLabel = QgsLayoutItemLegend = None
    QgsLayoutItemScaleBar = QgsLayoutItemPicture = QgsLayoutItemPolygon = QgsLayoutPoint = QgsLayoutSize = None
    _MM = 0

from ..core.layout_math import page_size_mm, nice_scalebar_segments
from .layout_utils import unique_layout_name, north_arrow_svg_path

# A real font fallback chain with standard installed Windows/Unix fonts
_FONT_FAMILIES = ["Segoe UI", "Arial", "Helvetica", "sans-serif"]


def _font(size: float, bold: bool = False, family: str = "Segoe UI") -> QFont:
    f = QFont(family, int(round(size)))
    hint = getattr(getattr(QFont, "StyleHint", QFont), "SansSerif", getattr(QFont, "SansSerif", None))
    if hint is not None and hasattr(f, "setStyleHint"):
        with suppress(Exception):
            f.setStyleHint(hint)
    if hasattr(f, "setFamilies"):
        f.setFamilies([family] + _FONT_FAMILIES)
    if hasattr(f, "setPointSizeF"):
        f.setPointSizeF(float(size))
    f.setBold(bold)
    return f


def _resolve_layers(iface, project: QgsProject) -> List:
    """Visible canvas layers if a canvas is available, else all project layers."""
    if iface is not None:
        with suppress(Exception):
            canvas_layers = iface.mapCanvas().layers()
            if canvas_layers:
                return list(canvas_layers)
    return [
        node.layer()
        for node in project.layerTreeRoot().findLayers()
        if node.isVisible() and node.layer() is not None
    ] or list(project.mapLayers().values())


def _resolve_extent(iface, layers) -> Optional[QgsRectangle]:
    """Current canvas extent if possible, else the combined extent of layers."""
    if iface is not None:
        with suppress(Exception):
            ext = iface.mapCanvas().extent()
            if ext is not None and not ext.isEmpty():
                return QgsRectangle(ext)
    extent = None
    for layer in layers:
        with suppress(Exception):
            le = layer.extent()
            if le is None or le.isEmpty():
                continue
            if extent is None:
                extent = QgsRectangle(le)
            else:
                extent.combineExtentWith(le)
    return extent


def create_map_sheet(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "",
    subtitle: str = "",
    credits: str = "",
    page_size: str = "A4",
    landscape: bool = True,
    add_title: bool = True,
    add_legend: bool = True,
    add_scalebar: bool = True,
    add_north_arrow: bool = True,
    add_grid: bool = False,
    add_frame: bool = True,
    preset: str = "swiss_modern",
    layout_name: str = "CartoLab Map Sheet",
    project: Optional[QgsProject] = None,
    template: Optional[str] = None,
) -> QgsPrintLayout:
    """
    Build and register a finished publication-ready map sheet or template archetype.

    Every element is optional via the ``add_*`` switches. Inputs left as
    ``None`` are resolved from ``iface`` (canvas layers / extent / CRS).
    Supports typography and styling presets ('swiss_modern', 'academic_serif', 'technical_blueprint', 'editorial_warm').
    If ``template`` is specified ('report_figure', 'academic_journal', 'poster_exhibition', 'fact_sheet', 'side_by_side_diptych'),
    delegates directly to the corresponding Template Gallery builder.

    Returns the :class:`QgsPrintLayout`, already added to the project's
    layout manager.
    """
    if template:
        from .template_gallery import create_template_layout
        return create_template_layout(
            template,
            iface=iface,
            layers=layers,
            extent=extent,
            crs=crs,
            title=title or "CartoLab Map Sheet",
            subtitle=subtitle,
            credits=credits or "Cartography: Yusuf Eminoğlu · PlanX CartoLab",
            layout_name=layout_name,
            project=project,
        )

    project = project or QgsProject.instance()
    layers = layers if layers is not None else _resolve_layers(iface, project)
    extent = extent if extent is not None else _resolve_extent(iface, layers)
    if crs is None:
        if iface is not None:
            try:
                crs = iface.mapCanvas().mapSettings().destinationCrs()
            except Exception:
                crs = project.crs()
        else:
            crs = project.crs()

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(unique_layout_name(project, layout_name))

    page_w, page_h = page_size_mm(page_size, landscape)
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(page_w, page_h, _MM))

    # --- geometry budget (millimetres) -----------------------------------
    margin = 12.0
    gap = 4.0
    title_h = 16.0 if add_title else 0.0
    legend_w = 58.0 if add_legend else 0.0
    bottom_h = 13.0 if (add_scalebar or credits) else 0.0

    map_x = margin
    map_y = margin + (title_h + gap if add_title else 0.0)
    right_reserve = (legend_w + gap) if add_legend else 0.0
    bottom_reserve = (bottom_h + gap) if bottom_h else 0.0
    map_w = page_w - 2 * margin - right_reserve
    map_h = page_h - map_y - margin - bottom_reserve

    # --- map frame -------------------------------------------------------
    map_item = QgsLayoutItemMap(layout)
    map_item.setId("cartolab_map")
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, _MM))
    map_item.attemptMove(QgsLayoutPoint(map_x, map_y, _MM))
    if crs is not None and crs.isValid():
        map_item.setCrs(crs)
    if extent is not None and not extent.isEmpty():
        map_item.zoomToExtent(extent)
    if layers:
        map_item.setLayers(list(layers))
        map_item.setKeepLayerSet(True)
    if add_frame:
        map_item.setFrameEnabled(True)
        map_item.setFrameStrokeColor(QColor("#333333"))
        map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, _MM))
    layout.addLayoutItem(map_item)

    if add_grid:
        with suppress(Exception):
            from .coordinate_grid import apply_coordinate_grid_decorator
            apply_coordinate_grid_decorator(
                layout,
                map_item=map_item,
                target_divisions_x=6,
                target_divisions_y=5,
                grid_style="Solid",
                frame_style="Zebra",
                show_annotations=True,
            )

    # --- title / subtitle ------------------------------------------------
    if add_title:
        text = title or project.title() or "Map"
        label = QgsLayoutItemLabel(layout)
        label.setText(text)
        label.setBackgroundEnabled(False)
        label.setFrameEnabled(False)
        label.setFont(_font(18, bold=True))
        label.setFontColor(QColor("#0f172a"))
        label.attemptMove(QgsLayoutPoint(margin, margin, _MM))
        label.attemptResize(QgsLayoutSize(page_w - 2 * margin, 9.0, _MM))
        layout.addLayoutItem(label)

        if subtitle:
            sub = QgsLayoutItemLabel(layout)
            sub.setText(subtitle)
            sub.setBackgroundEnabled(False)
            sub.setFrameEnabled(False)
            sub.setFont(_font(9.5))
            sub.setFontColor(QColor("#475569"))
            sub.attemptMove(QgsLayoutPoint(margin, margin + 9.5, _MM))
            sub.attemptResize(QgsLayoutSize(page_w - 2 * margin, 5.5, _MM))
            layout.addLayoutItem(sub)

    # --- legend ----------------------------------------------------------
    if add_legend:
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)
        legend.setResizeToContents(True)
        legend.setBackgroundEnabled(False)
        legend.setFrameEnabled(False)
        legend.setTitle("")
        if hasattr(legend, "rstyle"):
            with suppress(Exception):
                from qgis.core import QgsLegendStyle
                for style_attr in ("Title", "Group", "Subgroup", "SymbolLabel"):
                    style_enum = getattr(QgsLegendStyle, style_attr, getattr(getattr(QgsLegendStyle, "Style", None), style_attr, None))
                    if style_enum is not None:
                        tf = legend.rstyle(style_enum).textFormat()
                        f = _font(9.0 if style_attr == "SymbolLabel" else 10.0)
                        tf.setFont(f)
                        tf.setColor(QColor("#0f172a"))
                        legend.rstyle(style_enum).setTextFormat(tf)
        legend.setAutoUpdateModel(False)
        legend.attemptMove(QgsLayoutPoint(map_x + map_w + gap, map_y, _MM))
        legend.attemptResize(QgsLayoutSize(legend_w, map_h, _MM))
        layout.addLayoutItem(legend)

    # --- scale bar -------------------------------------------------------
    if add_scalebar:
        bar = QgsLayoutItemScaleBar(layout)
        bar.setLinkedMap(map_item)
        bar.applyDefaultSettings()
        bar.setStyle("Line Ticks Up" if preset == "swiss_modern" else "Single Box")
        bar.applyDefaultSize()

        unit_km = getattr(QgsUnitTypes, "DistanceKilometers", getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceKilometers", 1))
        bar.setUnits(unit_km)
        bar.setUnitLabel("km")
        bar.setNumberOfSegments(3)
        bar.setNumberOfSegmentsLeft(0)
        bar.setBackgroundEnabled(False)
        bar.setFrameEnabled(False)
        ext = map_item.extent()
        if ext and not ext.isEmpty():
            map_w_km = ext.width() / 1000.0 if (hasattr(map_item, "crs") and map_item.crs().isValid() and not map_item.crs().isGeographic()) else 10.0
            seg_km, n_right, n_left = nice_scalebar_segments(map_w_km, target_segments=3)
            bar.setNumberOfSegments(n_right)
            bar.setNumberOfSegmentsLeft(n_left)
            bar.setUnitsPerSegment(seg_km)
        with suppress(Exception):
            tf_sb = bar.textFormat()
            tf_sb.setFont(_font(8.0))
            tf_sb.setColor(QColor("#0f172a"))
            bar.setTextFormat(tf_sb)
        bar.attemptMove(
            QgsLayoutPoint(map_x, map_y + map_h + gap, _MM)
        )
        layout.addLayoutItem(bar)

    # --- north arrow -----------------------------------------------------
    if add_north_arrow:
        _add_north_arrow(layout, map_x + map_w - 16.0, map_y + 4.0)

    # --- credits ---------------------------------------------------------
    if credits:
        cred = QgsLayoutItemLabel(layout)
        cred.setText(credits)
        cred.setBackgroundEnabled(False)
        cred.setFrameEnabled(False)
        cred.setFont(_font(8))
        cred.setFontColor(QColor("#64748b"))
        cred.attemptResize(QgsLayoutSize(map_w * 0.6, bottom_h, _MM))
        cred.attemptMove(
            QgsLayoutPoint(map_x + map_w * 0.4, map_y + map_h + gap, _MM)
        )
        layout.addLayoutItem(cred)

    # Apply paper theme and typography hierarchy preset if specified
    if preset:
        with suppress(Exception):
            from .typography_engine import apply_typography_hierarchy
            apply_typography_hierarchy(layout, preset=preset)
        with suppress(Exception):
            from .paper_themes import apply_paper_theme
            apply_paper_theme(layout, theme_key=preset)

    project.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


def _add_north_arrow(layout, x: float, y: float, size: float = 12.0) -> None:
    """Add a crisp vector north arrow with Segoe UI typography."""
    _add_drawn_north_arrow(layout, x, y, size)


def _add_drawn_north_arrow(layout, x: float, y: float, size: float = 12.0, color: str = "#0f172a") -> None:
    """Vector north arrow: a filled triangle plus an 'N' label."""
    half = size / 2.0
    poly = QPolygonF([
        QPointF(x + half, y),
        QPointF(x + size, y + size),
        QPointF(x + half, y + size * 0.72),
        QPointF(x, y + size),
    ])
    arrow = QgsLayoutItemPolygon(poly, layout)
    arrow.setId("cartolab_north_arrow")
    arrow.setBackgroundEnabled(False)
    arrow.setFrameEnabled(False)
    if QgsFillSymbol:
        sym = QgsFillSymbol.createSimple({
            "color": color, "outline_color": color, "outline_width": "0.2",
        })
        if sym:
            arrow.setSymbol(sym)
    layout.addLayoutItem(arrow)

    label = QgsLayoutItemLabel(layout)
    label.setId("cartolab_north_arrow_label")
    label.setText("N")
    label.setBackgroundEnabled(False)
    label.setFrameEnabled(False)
    label.setFont(_font(8.5, bold=True))
    label.setFontColor(QColor(color))
    label.adjustSizeToText()
    label.attemptMove(QgsLayoutPoint(x + half - 2.5, y - 4.5, _MM))
    layout.addLayoutItem(label)
