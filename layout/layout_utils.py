# -*- coding: utf-8 -*-
"""
Shared helpers for PlanX CartoLab print-layout automation.

Small, dependency-light utilities used by the map-sheet generator and the
individual decorators (grid, legend, typography, isometric stack): locating
map items, finding a bundled north-arrow SVG, and exporting to PNG/PDF.
"""
from __future__ import annotations

import os
from contextlib import suppress
from typing import List, Optional

try:
    from qgis.core import (
        QgsApplication,
        QgsLayout,
        QgsLayoutExporter,
        QgsLayoutItemMap,
        QgsProject,
    )
except ImportError:
    QgsApplication = QgsLayout = QgsLayoutExporter = QgsLayoutItemMap = QgsProject = None

from ..core.layout_math import unique_name


def unique_layout_name(project: QgsProject, base: str) -> str:
    """Return a layout name not already present in the project's manager."""
    existing = [lay.name() for lay in project.layoutManager().layouts()]
    return unique_name(existing, base)


def find_map_item(layout: QgsLayout, map_id: str = "") -> Optional[QgsLayoutItemMap]:
    """
    Return a map item from ``layout``.

    Prefers the item whose id matches ``map_id``; otherwise returns the
    first :class:`QgsLayoutItemMap` found, or ``None`` when the layout has no
    map frame.
    """
    if map_id:
        item = layout.itemById(map_id)
        if isinstance(item, QgsLayoutItemMap):
            return item
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            return item
    return None


def map_items(layout: QgsLayout) -> List[QgsLayoutItemMap]:
    """Return every map item in the layout (draw order not guaranteed)."""
    return [it for it in layout.items() if isinstance(it, QgsLayoutItemMap)]


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


def export_layout(layout: QgsLayout, path: str, dpi: int = 300) -> bool:
    """
    Export ``layout`` to PNG, PDF or SVG (chosen by the ``path`` extension).

    PDF and SVG are vector formats (``dpi`` affects only rasterised effects);
    any other extension is treated as a raster image at ``dpi``. Returns
    ``True`` on success. A pre-existing target file is removed first so raster
    drivers do not refuse to overwrite.
    """
    if layout is None or QgsLayoutExporter is None:
        return False
    exporter = QgsLayoutExporter(layout)
    ext = os.path.splitext(path)[1].lower()
    with suppress(OSError):
        if os.path.exists(path):
            os.remove(path)

    if ext == ".pdf":
        settings = QgsLayoutExporter.PdfExportSettings()
        settings.dpi = dpi
        result = exporter.exportToPdf(path, settings)
    elif ext == ".svg":
        settings = QgsLayoutExporter.SvgExportSettings()
        settings.dpi = dpi
        result = exporter.exportToSvg(path, settings)
    elif ext in (".tif", ".tiff"):
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi
        result = exporter.exportToImage(path, settings)
    else:
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi
        result = exporter.exportToImage(path, settings)
    return result == QgsLayoutExporter.ExportResult.Success


def copy_layout_to_clipboard(layout: QgsLayout, dpi: int = 300) -> bool:
    """
    Render first page of ``layout`` at ``dpi`` and copy directly to system clipboard.
    """
    if layout is None:
        return False
    try:
        from qgis.PyQt.QtWidgets import QApplication
        exporter = QgsLayoutExporter(layout)
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi
        img = exporter.renderPageToImage(0, settings)
        if not img.isNull():
            cb = QApplication.clipboard()
            if cb:
                cb.setImage(img)
                return True
    except Exception:
        return False
    return False

