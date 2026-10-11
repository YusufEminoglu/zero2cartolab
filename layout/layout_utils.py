# -*- coding: utf-8 -*-
"""
Shared helpers for PlanX CartoLab print-layout automation.

Small, dependency-light utilities used by the map-sheet generator and the
individual decorators (grid, legend, typography, isometric stack): locating
map items, finding a bundled north-arrow SVG, and exporting to PNG/PDF.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import suppress
from typing import List, Optional

try:
    from qgis.core import (
        QgsApplication,
        QgsLayout,
        QgsLayoutExporter,
        QgsLayoutItemMap,
        QgsMapSettings,
        QgsProject,
    )
except ImportError:
    QgsApplication = QgsLayout = QgsLayoutExporter = QgsLayoutItemMap = QgsMapSettings = QgsProject = None

from ..core.layout_math import unique_name


def unique_layout_name(project: QgsProject, base: str) -> str:
    """Return a layout name not already present in the project's manager."""
    existing = [lay.name() for lay in project.layoutManager().layouts()]
    return unique_name(existing, base)


_LOCATOR_MAP_IDS = ("cartolab_locator_inset",)


def _is_auxiliary_map(item) -> bool:
    """True for generated overview/locator frames that are never the main map."""
    item_id = (item.id() or "").lower()
    return item_id in _LOCATOR_MAP_IDS or "locator" in item_id or "inset" in item_id


def _map_area(item) -> float:
    with suppress(Exception):
        rect = item.sceneBoundingRect()
        return float(rect.width()) * float(rect.height())
    return 0.0


def main_map_item(layout: QgsLayout) -> Optional[QgsLayoutItemMap]:
    """
    Return the layout's main map frame.

    Preference order: the CartoLab main map id ``cartolab_map``; then the
    largest ``cartolab_*_map*`` frame (template archetypes); then the largest
    map that is not a locator/inset; finally the largest map of any kind.
    Draw order is never used, so an inset added later (and drawn on top) is
    not mistaken for the main map.
    """
    if layout is None:
        return None
    maps = map_items(layout)
    if not maps:
        return None
    for item in maps:
        if item.id() == "cartolab_map":
            return item
    named = [m for m in maps
             if (m.id() or "").startswith("cartolab_") and "_map" in (m.id() or "")
             and not _is_auxiliary_map(m)]
    pool = named or [m for m in maps if not _is_auxiliary_map(m)] or maps
    return max(pool, key=_map_area)


def find_map_item(layout: QgsLayout, map_id: str = "") -> Optional[QgsLayoutItemMap]:
    """
    Return a map item from ``layout``.

    Prefers the item whose id matches ``map_id``; otherwise the main map (see
    :func:`main_map_item`), or ``None`` when the layout has no map frame.
    """
    if layout is None:
        return None
    if map_id:
        item = layout.itemById(map_id)
        if isinstance(item, QgsLayoutItemMap):
            return item
    return main_map_item(layout)


def map_items(layout: QgsLayout) -> List[QgsLayoutItemMap]:
    """Return every map item in the layout (draw order not guaranteed)."""
    return [it for it in layout.items() if isinstance(it, QgsLayoutItemMap)]


def clear_layout_render_cache(layout: QgsLayout) -> None:
    """
    Clear render caches before/after layout export.

    Large atlas exports can retain rasterised layer/map images between pages.
    QGIS exposes cache invalidation through slightly different methods across
    versions, so this helper probes supported APIs and silently skips missing
    ones.
    """
    if layout is None:
        return

    if QgsMapSettings is not None:
        with suppress(Exception):
            clear_cache = getattr(QgsMapSettings, "clearCache", None)
            if callable(clear_cache):
                clear_cache()

    for item in map_items(layout):
        for method_name in ("clearCache", "invalidateCache", "clearCachedImage"):
            with suppress(Exception):
                method = getattr(item, method_name, None)
                if callable(method):
                    method()
        with suppress(Exception):
            item.refresh()


def north_arrow_svg_path() -> Optional[str]:
    """
    Locate a north-arrow SVG shipped with QGIS.

    Searches :func:`QgsApplication.svgPaths` for the standard
    ``arrows/NorthArrow_*.svg`` set. Returns the first match, or ``None`` so
    callers can fall back to a drawn arrow.
    """
    candidates: List[str] = []
    for base in QgsApplication.svgPaths():
        arrows = os.path.join(base, "arrows")
        if not os.path.isdir(arrows):
            continue
        for fn in sorted(os.listdir(arrows)):
            if fn.lower().startswith("northarrow") and fn.lower().endswith(".svg"):
                candidates.append(os.path.join(arrows, fn))
    # NorthArrow_02 is the clean filled compass; prefer it when present.
    for path in candidates:
        if path.lower().endswith("northarrow_02.svg"):
            return path
    return candidates[0] if candidates else None


_LAST_EXPORT_ERROR = ""


def last_export_error() -> str:
    """Human-readable reason for the most recent failed :func:`export_layout`."""
    return _LAST_EXPORT_ERROR


def _export_result_name(result) -> str:
    for name in ("Canceled", "MemoryError", "FileError", "PrintError", "SvgLayerError", "IteratorError"):
        value = getattr(QgsLayoutExporter.ExportResult, name, getattr(QgsLayoutExporter, name, None))
        if value is not None and result == value:
            return name
    return str(result)


def export_layout(layout: QgsLayout, path: str, dpi: int = 300) -> bool:
    """
    Export ``layout`` to PNG, PDF or SVG (chosen by the ``path`` extension).

    PDF and SVG are vector formats (``dpi`` affects only rasterised effects);
    any other extension is treated as a raster image at ``dpi``. Returns
    ``True`` on success; on failure returns ``False`` and
    :func:`last_export_error` explains why. QGIS renders into a private
    temporary folder next to the destination; every page it produces
    (``map.png``, ``map_2.png`` ... for multi-page image/SVG exports) is then
    moved to its final name, so a failed render never destroys a previous
    export and no temporary files are left behind.
    """
    global _LAST_EXPORT_ERROR
    _LAST_EXPORT_ERROR = ""
    if layout is None or QgsLayoutExporter is None:
        _LAST_EXPORT_ERROR = "No layout to export."
        return False
    path = os.path.abspath(path)
    out_dir = os.path.dirname(path)
    try:
        os.makedirs(out_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix=".cartolab-export-", dir=out_dir)
    except OSError as exc:
        _LAST_EXPORT_ERROR = f"Cannot write to {out_dir}: {exc}"
        return False
    exporter = QgsLayoutExporter(layout)
    ext = os.path.splitext(path)[1].lower()
    # Raster exports pick the image format from the suffix; default to PNG.
    temp_path = os.path.join(temp_dir, os.path.basename(path) + ("" if ext else ".png"))

    clear_layout_render_cache(layout)
    try:
        if ext == ".pdf":
            settings = QgsLayoutExporter.PdfExportSettings()
            settings.dpi = dpi
            result = exporter.exportToPdf(temp_path, settings)
        elif ext == ".svg":
            settings = QgsLayoutExporter.SvgExportSettings()
            settings.dpi = dpi
            result = exporter.exportToSvg(temp_path, settings)
        else:
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = dpi
            # Publication PNGs are self-contained; do not create world-file
            # sidecars next to the temporary destination.
            with suppress(Exception):
                settings.generateWorldFile = False
            result = exporter.exportToImage(temp_path, settings)
        success = result == QgsLayoutExporter.ExportResult.Success and os.path.exists(temp_path)
        if success:
            for name in sorted(os.listdir(temp_dir)):
                produced = os.path.join(temp_dir, name)
                os.replace(produced, path if produced == temp_path else os.path.join(out_dir, name))
        else:
            detail = ""
            with suppress(Exception):
                detail = exporter.errorMessage()
            _LAST_EXPORT_ERROR = (
                f"QGIS could not export the layout to {path} "
                f"({_export_result_name(result)}){': ' + detail if detail else ''}."
            )
        return success
    except Exception as exc:
        _LAST_EXPORT_ERROR = f"Export to {path} failed: {exc}"
        raise
    finally:
        clear_layout_render_cache(layout)
        shutil.rmtree(temp_dir, ignore_errors=True)


def copy_layout_to_clipboard(layout: QgsLayout, dpi: int = 300) -> bool:
    """
    Render first page of ``layout`` at ``dpi`` and copy directly to system clipboard.
    """
    if layout is None or QgsLayoutExporter is None:
        return False
    try:
        from qgis.PyQt.QtCore import QSize
        from qgis.PyQt.QtWidgets import QApplication
        exporter = QgsLayoutExporter(layout)
        clear_layout_render_cache(layout)
        try:
            # renderPageToImage(page, imageSize, dpi): an invalid QSize lets
            # QGIS derive the pixel size from the page size and dpi.
            img = exporter.renderPageToImage(0, QSize(), float(dpi))
            if not img.isNull():
                cb = QApplication.clipboard()
                if cb:
                    cb.setImage(img)
                    return True
        finally:
            clear_layout_render_cache(layout)
    except Exception:
        return False
    return False


def set_legend_style_text(legend, style_enum, font, color=None) -> None:
    """Set a legend style's font (and colour) on QGIS 3.28 to 4.x.

    ``QgsLegendStyle.textFormat()`` arrived in QGIS 3.30; older releases only
    have ``setFont`` on the style and one font colour for the whole legend.
    """
    style = legend.rstyle(style_enum)
    if hasattr(style, "textFormat"):
        text_format = style.textFormat()
        text_format.setFont(font)
        if font.pointSizeF() > 0:
            text_format.setSize(font.pointSizeF())
        if color is not None:
            text_format.setColor(color)
        style.setTextFormat(text_format)
        return
    style.setFont(font)
    if color is not None and hasattr(legend, "setFontColor"):
        legend.setFontColor(color)


def zoom_map_to_extent(map_item, extent) -> None:
    """``zoomToExtent`` that also works on a fresh map item in QGIS 3.28.

    QGIS 3.28 derives the new extent from the current one, so a map item that
    still has its initial empty extent ends up Empty with a NaN scale. Seeding
    the extent first makes the aspect-fitted zoom work on every version.
    """
    if map_item.extent().isEmpty():
        # setExtent() also reshapes the frame to the extent's aspect ratio;
        # put the frame back to its planned size before the real zoom.
        size = map_item.sizeWithUnits()
        map_item.setExtent(extent)
        map_item.attemptResize(size)
    map_item.zoomToExtent(extent)
