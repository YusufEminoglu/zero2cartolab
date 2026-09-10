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

import math
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
        QgsDistanceArea,
        QgsPointXY,
        QgsCoordinateTransform,
    )
    _MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except ImportError:
    QColor = QFont = QPolygonF = QPointF = None
    QgsProject = QgsPrintLayout = QgsLayoutItemMap = QgsLayoutItemLabel = QgsLayoutItemLegend = None
    QgsLayoutItemScaleBar = QgsLayoutItemPicture = QgsLayoutItemPolygon = QgsLayoutPoint = QgsLayoutSize = None
    QgsDistanceArea = QgsPointXY = QgsCoordinateTransform = None
    _MM = 0

from ..core.layout_math import fitted_scalebar_segments, map_width_to_km, page_size_mm
from .layout_utils import unique_layout_name

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


def _resolve_crs(iface, project: QgsProject, layers):
    """Resolve canvas/project CRS, preferring a valid input-layer CRS headlessly."""
    if iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
            if crs is not None and crs.isValid():
                return crs
    for layer in layers or []:
        with suppress(Exception):
            crs = layer.crs()
            if crs is not None and crs.isValid():
                return crs
    with suppress(Exception):
        crs = project.crs()
        if crs is not None and crs.isValid():
            return crs
    return None


def _resolve_extent(
    iface,
    layers,
    target_crs=None,
    project: Optional[QgsProject] = None,
) -> Optional[QgsRectangle]:
    """Current canvas extent, else layer extents transformed to one CRS."""
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
            layer_crs = layer.crs()
            if (
                target_crs is not None
                and target_crs.isValid()
                and layer_crs is not None
                and layer_crs.isValid()
                and layer_crs != target_crs
                and QgsCoordinateTransform is not None
            ):
                context = project.transformContext() if project is not None else QgsProject.instance().transformContext()
                le = QgsCoordinateTransform(layer_crs, target_crs, context).transformBoundingBox(le)
            if extent is None:
                extent = QgsRectangle(le)
            else:
                extent.combineExtentWith(le)
    return extent


def _distance_kilometres_unit():
    return getattr(
        QgsUnitTypes,
        "DistanceKilometers",
        getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceKilometers", 1),
    )


def _distance_metres_unit():
    return getattr(
        QgsUnitTypes,
        "DistanceMeters",
        getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceMeters", 0),
    )


def _crs_is_geographic(crs) -> bool:
    is_geographic = False
    with suppress(Exception):
        is_geographic = bool(crs is not None and crs.isValid() and crs.isGeographic())
    return is_geographic


def _crs_unit_to_km(crs) -> float:
    factor = 0.001
    with suppress(Exception):
        factor = float(QgsUnitTypes.fromUnitToUnitFactor(crs.mapUnits(), _distance_kilometres_unit()))
    return factor if factor > 0 else 0.001


def _fallback_geographic_width_km(extent: QgsRectangle) -> float:
    """Approximate longitude span in kilometres when QgsDistanceArea is unavailable."""
    lat = (float(extent.yMinimum()) + float(extent.yMaximum())) * 0.5
    km_per_degree_lon = 111.320 * max(0.01, abs(math.cos(math.radians(lat))))
    return map_width_to_km(float(extent.width()), km_per_degree_lon)


def _geodesic_extent_width_km(extent: QgsRectangle, crs, project: QgsProject) -> float:
    if QgsDistanceArea is None or QgsPointXY is None:
        return 0.0

    width_km = 0.0
    with suppress(Exception):
        distance = QgsDistanceArea()
        if project is not None and hasattr(project, "transformContext"):
            distance.setSourceCrs(crs, project.transformContext())
        if project is not None and hasattr(project, "ellipsoid"):
            ellipsoid = project.ellipsoid()
        else:
            ellipsoid = ""
        if not ellipsoid or str(ellipsoid).upper() == "NONE":
            with suppress(Exception):
                ellipsoid = crs.ellipsoidAcronym()
        distance.setEllipsoid(ellipsoid or "WGS84")
        mid_y = (float(extent.yMinimum()) + float(extent.yMaximum())) * 0.5
        width = distance.measureLine(
            QgsPointXY(float(extent.xMinimum()), mid_y),
            QgsPointXY(float(extent.xMaximum()), mid_y),
        )
        unit_to_km = QgsUnitTypes.fromUnitToUnitFactor(
            distance.lengthUnits(), _distance_kilometres_unit()
        )
        width_km = map_width_to_km(float(width), float(unit_to_km))
    return width_km


def _map_extent_width_km(map_item: QgsLayoutItemMap, project: QgsProject) -> float:
    """Return the linked map frame's real-world width in kilometres."""
    extent = map_item.extent()
    if extent is None or extent.isEmpty():
        return 0.0

    crs = None
    with suppress(Exception):
        crs = map_item.crs()

    if _crs_is_geographic(crs):
        width_km = _geodesic_extent_width_km(extent, crs, project)
        if width_km > 0:
            return width_km
        return _fallback_geographic_width_km(extent)

    return map_width_to_km(float(extent.width()), _crs_unit_to_km(crs))


def _configure_scalebar(
    bar: QgsLayoutItemScaleBar,
    map_item: QgsLayoutItemMap,
    project: QgsProject,
    *,
    max_width_mm: float,
    target_segments: int = 3,
) -> bool:
    """Configure a metric scale bar that stays inside its layout budget."""
    if bar is None or map_item is None:
        return False
    map_w_km = _map_extent_width_km(map_item, project)
    if map_w_km <= 0:
        return False

    map_frame_w_mm = 0.0
    with suppress(Exception):
        map_frame_w_mm = float(map_item.rect().width())
    if map_frame_w_mm <= 0:
        map_frame_w_mm = max_width_mm * 3.0

    seg_km, n_right, n_left = fitted_scalebar_segments(
        map_w_km,
        map_frame_w_mm,
        max_width_mm,
        target_segments=target_segments,
    )
    use_metres = map_w_km < 5.0
    bar.setUnits(_distance_metres_unit() if use_metres else _distance_kilometres_unit())
    bar.setUnitLabel("m" if use_metres else "km")
    # QgsLayoutItemScaleBar converts its selected distance unit against the
    # linked map CRS. A non-1 manual factor is an additional divisor and would
    # corrupt labels (for example 0.5 km becoming 0.0005 km).
    bar.setMapUnitsPerScaleBarUnit(1.0)
    bar.setNumberOfSegments(n_right)
    bar.setNumberOfSegmentsLeft(n_left)
    segment_display_units = seg_km * 1000.0 if use_metres else seg_km
    bar.setUnitsPerSegment(segment_display_units)
    with suppress(Exception):
        bar.setMaximumBarWidth(float(max_width_mm))
    with suppress(Exception):
        bar.resizeToMinimumWidth()
    return True


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
    if crs is None:
        crs = _resolve_crs(iface, project, layers)
    extent = extent if extent is not None else _resolve_extent(
        iface, layers, target_crs=crs, project=project
    )

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
        label.setId("cartolab_title")
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
            sub.setId("cartolab_subtitle")
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
        legend.setId("cartolab_legend")
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
        # Measure the natural legend, but never let a large layer tree push
        # furniture beyond its dedicated sidebar or page margin.
        with suppress(Exception):
            legend.adjustBoxSize()
            natural_w = float(legend.rect().width())
            natural_h = float(legend.rect().height())
            if natural_w > legend_w or natural_h > map_h:
                legend.setResizeToContents(False)
                legend.attemptResize(QgsLayoutSize(legend_w, map_h, _MM))

    # --- scale bar -------------------------------------------------------
    if add_scalebar:
        bar = QgsLayoutItemScaleBar(layout)
        bar.setId("cartolab_scalebar")
        bar.setLinkedMap(map_item)
        bar.applyDefaultSettings()
        bar.setStyle("Line Ticks Up" if preset == "swiss_modern" else "Single Box")
        bar.applyDefaultSize()

        bar.setNumberOfSegments(3)
        bar.setNumberOfSegmentsLeft(0)
        bar.setBackgroundEnabled(False)
        bar.setFrameEnabled(False)
        _configure_scalebar(
            bar,
            map_item,
            project,
            max_width_mm=max(32.0, map_w * 0.32),
            target_segments=3,
        )
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
        cred.setId("cartolab_credits")
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
