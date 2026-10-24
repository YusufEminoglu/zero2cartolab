# -*- coding: utf-8 -*-
"""Pre-export quality checks for QGIS print layouts."""
from __future__ import annotations

from collections import Counter
from contextlib import suppress
from typing import Dict, List

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemPage,
        QgsLayoutItemScaleBar,
    )
except ImportError:
    QgsLayout = QgsLayoutItemLabel = QgsLayoutItemLegend = None
    QgsLayoutItemMap = QgsLayoutItemPage = QgsLayoutItemScaleBar = None


def _issue(severity: str, code: str, message: str, item_id: str = "") -> Dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "item_id": item_id,
    }


def preflight_layout(layout: QgsLayout, tolerance: float = 0.75) -> List[Dict[str, str]]:
    """Inspect a layout for common failures before PDF/image export.

    Checks are intentionally deterministic and non-mutating. Coordinates are
    compared in layout scene units, which avoids assuming that user-created
    items were positioned in millimetres.
    """
    if layout is None or QgsLayoutItemMap is None:
        return [_issue("error", "layout_missing", "No print layout is available.")]

    pages = list(layout.pageCollection().pages()) if layout.pageCollection() else []
    if not pages:
        return [_issue("error", "page_missing", "The layout has no pages.")]

    items = [
        item for item in layout.items()
        if QgsLayoutItemPage is None or not isinstance(item, QgsLayoutItemPage)
    ]
    issues: List[Dict[str, str]] = []

    item_ids = [item.id() for item in items if hasattr(item, "id") and item.id()]
    for item_id, count in Counter(item_ids).items():
        if count > 1:
            issues.append(_issue(
                "warning", "duplicate_id",
                f"{count} items use the same ID; Designer actions may target the wrong item.",
                item_id,
            ))

    page_rects = [page.sceneBoundingRect() for page in pages]
    item_by_id = {
        item.id(): item for item in items
        if hasattr(item, "id") and item.id()
    }
    for item in items:
        item_id = item.id() if hasattr(item, "id") else ""
        with suppress(RuntimeError):
            rect = item.sceneBoundingRect()
            if rect.width() <= 0 or rect.height() <= 0:
                issues.append(_issue(
                    "error", "zero_size", "Item has zero width or height.", item_id
                ))
                continue
            on_page = any(
                rect.left() >= page.left() - tolerance
                and rect.top() >= page.top() - tolerance
                and rect.right() <= page.right() + tolerance
                and rect.bottom() <= page.bottom() + tolerance
                for page in page_rects
            )
            if not on_page:
                issues.append(_issue(
                    "error", "outside_page",
                    (
                        "Item extends beyond the printable page boundary "
                        f"(item {rect.left():.1f},{rect.top():.1f}–{rect.right():.1f},{rect.bottom():.1f}; "
                        f"page {page_rects[0].left():.1f},{page_rects[0].top():.1f}–"
                        f"{page_rects[0].right():.1f},{page_rects[0].bottom():.1f})."
                    ),
                    item_id,
                ))

        if isinstance(item, QgsLayoutItemMap):
            extent = item.extent()
            if extent is None or extent.isEmpty():
                issues.append(_issue(
                    "error", "empty_map_extent", "Map frame has an empty extent.", item_id
                ))
            if float(item.rect().width()) < 25.0 or float(item.rect().height()) < 20.0:
                issues.append(_issue(
                    "warning", "small_map_frame",
                    "Map frame is very small and may not be legible in print.", item_id,
                ))
            for grid in list(item.grids().asList()) if hasattr(item, "grids") else []:
                if not grid.enabled():
                    continue
                interval_x = float(grid.intervalX())
                interval_y = float(grid.intervalY())
                if interval_x <= 0 or interval_y <= 0:
                    issues.append(_issue(
                        "error", "invalid_grid_interval",
                        "Enabled coordinate grid has a zero or negative interval.", item_id,
                    ))
                    continue
                width = float(extent.width()) if extent is not None else 0.0
                height = float(extent.height()) if extent is not None else 0.0
                divisions_x = width / interval_x if interval_x else 0.0
                divisions_y = height / interval_y if interval_y else 0.0
                has_annotations = bool(hasattr(grid, "annotationEnabled") and grid.annotationEnabled())
                max_divs = 14 if has_annotations else 30
                if divisions_x > max_divs or divisions_y > max_divs:
                    issues.append(_issue(
                        "warning", "dense_grid",
                        "Coordinate grid is too dense for a publication layout; increase its interval.", item_id,
                    ))
                elif (divisions_x and divisions_x < 2) or (divisions_y and divisions_y < 2):
                    issues.append(_issue(
                        "warning", "sparse_grid",
                        "Coordinate grid has fewer than two divisions on an axis.", item_id,
                    ))
        elif isinstance(item, QgsLayoutItemScaleBar):
            linked_map = item.linkedMap() if hasattr(item, "linkedMap") else None
            if linked_map is None:
                issues.append(_issue(
                    "error", "unlinked_scalebar", "Scale bar is not linked to a map.", item_id
                ))
            else:
                with suppress(Exception):
                    if float(item.unitsPerSegment()) <= 0:
                        issues.append(_issue(
                            "error", "invalid_scalebar_segment",
                            "Scale bar segment distance must be positive.", item_id,
                        ))
                with suppress(Exception):
                    segments = int(item.numberOfSegments()) + int(item.numberOfSegmentsLeft())
                    if segments < 2 or segments > 6:
                        issues.append(_issue(
                            "warning", "scalebar_segment_count",
                            "Scale bar should normally contain 2–6 readable segments.", item_id,
                        ))
                with suppress(Exception):
                    if float(item.rect().width()) > float(linked_map.rect().width()) * 0.55:
                        issues.append(_issue(
                            "warning", "oversize_scalebar",
                            "Scale bar occupies more than half of its linked map width.", item_id,
                        ))
        elif isinstance(item, QgsLayoutItemLegend):
            linked_map = item.linkedMap() if hasattr(item, "linkedMap") else None
            if linked_map is None:
                issues.append(_issue(
                    "warning", "unlinked_legend", "Legend is not linked to a map frame.", item_id
                ))
            with suppress(Exception):
                if float(item.rect().width()) < 18 or float(item.rect().height()) < 12:
                    issues.append(_issue(
                        "warning", "small_legend",
                        "Legend frame is too small for reliably readable symbols and labels.", item_id,
                    ))
        elif isinstance(item, QgsLayoutItemLabel):
            if not (item.text() or "").strip():
                issues.append(_issue(
                    "warning", "empty_label", "Text label is empty.", item_id
                ))

        if item_id.endswith("_frame") and item_id.startswith("cartolab_chart_"):
            with suppress(Exception):
                rect = item.sceneBoundingRect()
                containing = next((page for page in page_rects if page.contains(rect.center())), None)
                if containing is not None:
                    inset = 3.0
                    if (rect.left() < containing.left() + inset or
                            rect.top() < containing.top() + inset or
                            rect.right() > containing.right() - inset or
                            rect.bottom() > containing.bottom() - inset):
                        issues.append(_issue(
                            "warning", "chart_safe_margin",
                            "Chart is inside the page but violates the 3 mm print-safe margin.", item_id,
                        ))

    if not any(isinstance(item, QgsLayoutItemMap) for item in items):
        issues.append(_issue("error", "map_missing", "The layout contains no map frame."))
    if "cartolab_map" in item_by_id:
        has_north = any(
            item_id == "cartolab_north_arrow" or item_id.startswith("cartolab_north_arrow_")
            for item_id in item_by_id
        )
        if not has_north:
            issues.append(_issue(
                "warning", "north_arrow_missing",
                "CartoLab map sheet has no north arrow; add one unless orientation is self-evident.",
                "cartolab_map",
            ))
    chart_frames = [
        item for item in items
        if hasattr(item, "id")
        and item.id().startswith("cartolab_chart_")
        and item.id().endswith("_frame")
    ]
    for frame in chart_frames:
        with suppress(Exception):
            frame_rect = frame.sceneBoundingRect()
            for other in items:
                if other is frame or isinstance(other, QgsLayoutItemMap):
                    continue
                other_id = other.id() if hasattr(other, "id") else ""
                if other_id.startswith("cartolab_chart_"):
                    continue
                overlap = frame_rect.intersected(other.sceneBoundingRect())
                if overlap.width() * overlap.height() > 4.0:
                    issues.append(_issue(
                        "warning", "chart_furniture_overlap",
                        f"Chart overlaps layout furniture '{other_id or type(other).__name__}'.",
                        frame.id(),
                    ))
                    break
    return issues


def summarize_preflight(issues: List[Dict[str, str]]) -> Dict[str, int]:
    """Return error/warning counts and a simple readiness score."""
    errors = sum(issue.get("severity") == "error" for issue in issues)
    warnings = sum(issue.get("severity") == "warning" for issue in issues)
    score = max(0, 100 - errors * 25 - warnings * 5)
    return {"errors": errors, "warnings": warnings, "score": score}


def format_preflight_report(layout: QgsLayout, issues: List[Dict[str, str]]) -> str:
    """Build compact plain text suitable for a Designer dialog."""
    summary = summarize_preflight(issues)
    name = layout.name() if layout is not None and hasattr(layout, "name") else "Layout"
    lines = [
        f"{name} — Print Preflight",
        f"Readiness: {summary['score']}/100 | Errors: {summary['errors']} | Warnings: {summary['warnings']}",
    ]
    if not issues:
        lines.append("No blocking or advisory issues found.")
    else:
        for issue in issues:
            item = f" [{issue['item_id']}]" if issue.get("item_id") else ""
            lines.append(f"{issue['severity'].upper()}: {issue['message']}{item}")
    return "\n".join(lines)
