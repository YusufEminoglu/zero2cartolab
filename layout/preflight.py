# -*- coding: utf-8 -*-
"""Pre-export quality checks for QGIS print layouts."""
from __future__ import annotations

from collections import Counter
from contextlib import suppress
import re
from typing import Any, Dict, List

try:
    from qgis.core import (
        QgsExpression,
        QgsLayout,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemMap,
        QgsLayoutItemPage,
        QgsLayoutItemPicture,
        QgsLayoutItemScaleBar,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
    )
    from qgis.PyQt.QtGui import QColor
except ImportError:
    QgsExpression = QgsLayout = QgsLayoutItemLabel = QgsLayoutItemLegend = None
    QgsLayoutItemMap = QgsLayoutItemPage = QgsLayoutItemPicture = QgsLayoutItemScaleBar = None
    QgsLayoutPoint = QgsLayoutSize = QgsUnitTypes = QColor = None

from ..core.color_accessibility import suggest_accessible_color
from ..core.layout_math import nice_interval
from .layout_utils import main_map_item
from .pixel_qa import contrast_ratio

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0
_EXPR_BLOCK_RE = re.compile(r"\[%(.*?)%\]", re.DOTALL)


def _issue(severity: str, code: str, message: str, item_id: str = "") -> Dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "item_id": item_id,
    }


def validate_label_expressions(text: str) -> List[str]:
    """Return parser error strings for any invalid `[% ... %]` expression blocks in ``text``."""
    raw = text or ""
    if "[%" not in raw and "%]" not in raw:
        return []
    errors: List[str] = []
    if raw.count("[%") != raw.count("%]"):
        errors.append("Unbalanced '[%' / '%]' expression delimiters.")
    for match in _EXPR_BLOCK_RE.finditer(raw):
        body = (match.group(1) or "").strip()
        if not body:
            errors.append("Empty '[% %]' expression block.")
            continue
        if QgsExpression is not None:
            with suppress(Exception):
                exp = QgsExpression(body)
                if hasattr(exp, "hasParserError") and exp.hasParserError():
                    err_msg = exp.parserErrorString() if hasattr(exp, "parserErrorString") else "syntax error"
                    errors.append(f"Invalid expression '{body[:36]}': {err_msg}")
    return errors



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
            with suppress(Exception):
                fits_prop = item.customProperty("cartolab/legend_fits")
                if fits_prop in (False, "false", "False", 0, "0"):
                    issues.append(_issue(
                        "warning", "legend_overflow",
                        "Legend items exceed the allocated legend box height; enable Auto-Fit or increase columns.",
                        item_id,
                    ))
        elif isinstance(item, QgsLayoutItemLabel):
            raw_text = item.text() or ""
            if not raw_text.strip():
                issues.append(_issue(
                    "warning", "empty_label", "Text label is empty.", item_id
                ))
            else:
                expr_errors = validate_label_expressions(raw_text)
                for err_msg in expr_errors:
                    issues.append(_issue(
                        "error", "broken_expression", err_msg, item_id
                    ))
                with suppress(Exception):
                    is_html = bool(
                        item.customProperty("cartolab/is_html_card")
                        or (hasattr(item, "mode") and int(item.mode()) == 1)
                    )
                    if not is_html and hasattr(item, "hasBackground") and item.hasBackground():
                        bg_col = item.backgroundColor()
                        fg_col = item.fontColor()
                        if bg_col.alpha() >= 180:
                            ratio = contrast_ratio(fg_col.name(), bg_col.name())
                            if ratio < 3.0:
                                issues.append(_issue(
                                    "warning", "low_label_contrast",
                                    f"Label text has low contrast ({ratio:.1f}:1 < 3.0:1) against its background.",
                                    item_id,
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

    # Atlas readiness checks when Atlas is enabled on the layout
    with suppress(Exception):
        atlas = layout.atlas() if hasattr(layout, "atlas") else None
        if atlas is not None and atlas.enabled():
            cov = atlas.coverageLayer()
            if cov is None or (hasattr(cov, "isValid") and not cov.isValid()):
                issues.append(_issue(
                    "error", "atlas_no_coverage",
                    "Atlas is enabled, but no valid coverage layer is assigned.", "atlas",
                ))
            elif hasattr(cov, "featureCount") and int(cov.featureCount()) == 0:
                issues.append(_issue(
                    "warning", "atlas_empty_coverage",
                    "Atlas coverage layer has 0 features.", "atlas",
                ))
            if hasattr(atlas, "filterFeatures") and atlas.filterFeatures():
                f_expr = (atlas.filterExpression() or "").strip()
                if f_expr and QgsExpression is not None:
                    exp = QgsExpression(f_expr)
                    if hasattr(exp, "hasParserError") and exp.hasParserError():
                        issues.append(_issue(
                            "error", "atlas_invalid_filter",
                            f"Atlas filter expression error: {exp.parserErrorString()}", "atlas",
                        ))
            has_driven_map = any(
                isinstance(it, QgsLayoutItemMap) and hasattr(it, "atlasDriven") and it.atlasDriven()
                for it in items
            )
            if not has_driven_map:
                issues.append(_issue(
                    "error", "atlas_no_driven_map",
                    "Atlas is enabled, but no map item has 'Controlled by Atlas' enabled.", "atlas",
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

    # General furniture overlap check (Legend, ScaleBar, HTML cards)
    furniture_items = [
        item for item in items
        if isinstance(item, (QgsLayoutItemLegend, QgsLayoutItemScaleBar))
        or (isinstance(item, QgsLayoutItemLabel) and bool(item.customProperty("cartolab/is_html_card")))
    ]
    for idx_a, item_a in enumerate(furniture_items):
        id_a = item_a.id() if hasattr(item_a, "id") else ""
        with suppress(Exception):
            rect_a = item_a.sceneBoundingRect()
            for item_b in furniture_items[idx_a + 1 :]:
                id_b = item_b.id() if hasattr(item_b, "id") else ""
                if id_a and id_b and id_a.startswith("cartolab_scale_combo") and id_b.startswith("cartolab_scale_combo"):
                    continue
                overlap = rect_a.intersected(item_b.sceneBoundingRect())
                if overlap.width() * overlap.height() > 6.0:
                    issues.append(_issue(
                        "warning", "furniture_overlap",
                        f"Layout furniture '{id_a or type(item_a).__name__}' overlaps '{id_b or type(item_b).__name__}'.",
                        id_a,
                    ))
                    break
    return issues


def autofix_layout(layout: QgsLayout) -> Dict[str, Any]:
    """Automatically repair common layout preflight errors and warnings in-place.

    Repairs:
      - ``duplicate_id``: Assigns unique suffixes to duplicate item IDs.
      - ``zero_size``: Restores minimum positive dimensions `(25 x 10 mm)`.
      - ``outside_page``: Clamps off-page items inside the printable page bounds.
      - ``unlinked_scalebar`` / ``invalid_scalebar_segment`` / ``oversize_scalebar``:
        Links scalebar to primary map and recalculates clean segment widths.
      - ``unlinked_legend`` / ``small_legend`` / ``legend_overflow``:
        Links legend to primary map and auto-fits columns/typography.
      - ``invalid_grid_interval`` / ``dense_grid`` / ``sparse_grid``:
        Computes a balanced `nice_interval` for enabled map grids.
      - ``empty_label``: Removes accidental blank labels.
      - ``low_label_contrast``: Adjusts label text color to meet WCAG AA contrast.
      - ``atlas_no_driven_map``: Enables `atlasDriven` on the primary map item.
    """
    before_issues = preflight_layout(layout)
    before_summary = summarize_preflight(before_issues)
    fixes: List[str] = []

    if layout is None or QgsLayoutItemMap is None:
        return {
            "fixed_count": 0,
            "fixes": fixes,
            "before": before_summary,
            "after": before_summary,
            "issues": before_issues,
        }

    pages = list(layout.pageCollection().pages()) if layout.pageCollection() else []
    page_rect = pages[0].sceneBoundingRect() if pages else None
    primary_map = main_map_item(layout)

    items = [
        item for item in list(layout.items())
        if QgsLayoutItemPage is None or not isinstance(item, QgsLayoutItemPage)
    ]

    # 1. Deduplicate item IDs
    seen_ids: Dict[str, int] = {}
    for item in items:
        if not hasattr(item, "id") or not hasattr(item, "setId"):
            continue
        cid = item.id() or ""
        if not cid:
            continue
        if cid in seen_ids:
            seen_ids[cid] += 1
            new_id = f"{cid}_{seen_ids[cid]}"
            item.setId(new_id)
            fixes.append(f"Renamed duplicate item ID '{cid}' -> '{new_id}'")
        else:
            seen_ids[cid] = 1

    # 2. Inspect and repair individual items
    for item in list(items):
        item_id = item.id() if hasattr(item, "id") else ""

        # Remove empty non-HTML labels
        if isinstance(item, QgsLayoutItemLabel):
            raw_txt = (item.text() or "").strip()
            if not raw_txt:
                with suppress(Exception):
                    layout.removeLayoutItem(item)
                    fixes.append(f"Removed empty label '{item_id or 'unnamed'}'")
                continue

            # Fix low contrast against solid label background
            with suppress(Exception):
                is_html = bool(
                    item.customProperty("cartolab/is_html_card")
                    or (hasattr(item, "mode") and int(item.mode()) == 1)
                )
                if not is_html and hasattr(item, "hasBackground") and item.hasBackground():
                    bg_col = item.backgroundColor()
                    fg_col = item.fontColor()
                    if bg_col.alpha() >= 180 and contrast_ratio(fg_col.name(), bg_col.name()) < 3.0:
                        better_hex = suggest_accessible_color(fg_col.name(), bg_col.name(), target_ratio=4.5)
                        if QColor is not None:
                            item.setFontColor(QColor(better_hex))
                            fixes.append(f"Improved text contrast on label '{item_id}' -> {better_hex}")

        # Fix zero-size items
        with suppress(Exception):
            rect = item.sceneBoundingRect()
            if (rect.width() <= 0 or rect.height() <= 0) and QgsLayoutSize is not None:
                item.attemptResize(QgsLayoutSize(max(25.0, float(rect.width())), max(10.0, float(rect.height())), _MM))
                fixes.append(f"Resized zero-dimension item '{item_id}'")

        # Clamp outside-page items back onto the first page
        if page_rect is not None and QgsLayoutPoint is not None and QgsLayoutSize is not None:
            with suppress(Exception):
                rect = item.sceneBoundingRect()
                px, py = float(page_rect.left()), float(page_rect.top())
                pw, ph = float(page_rect.width()), float(page_rect.height())
                ix, iy = float(rect.left()), float(rect.top())
                iw, ih = float(rect.width()), float(rect.height())
                if ix < px - 0.75 or iy < py - 0.75 or (ix + iw) > (px + pw + 0.75) or (iy + ih) > (py + ph + 0.75):
                    margin = 5.0
                    new_w = min(iw, max(15.0, pw - 2 * margin))
                    new_h = min(ih, max(10.0, ph - 2 * margin))
                    new_x = min(max(px + margin, ix), px + pw - new_w - margin)
                    new_y = min(max(py + margin, iy), py + ph - new_h - margin)
                    if abs(new_w - iw) > 0.5 or abs(new_h - ih) > 0.5:
                        item.attemptResize(QgsLayoutSize(new_w, new_h, _MM))
                    item.attemptMove(QgsLayoutPoint(new_x, new_y, _MM))
                    fixes.append(f"Clamped off-page item '{item_id}' into printable area")

        # Fix map grids
        if isinstance(item, QgsLayoutItemMap):
            ext = item.extent()
            if ext is not None and not ext.isEmpty() and hasattr(item, "grids"):
                for grid in list(item.grids().asList()):
                    if not grid.enabled():
                        continue
                    ix_val = float(grid.intervalX())
                    iy_val = float(grid.intervalY())
                    w_ext = float(ext.width())
                    h_ext = float(ext.height())
                    has_ann = bool(hasattr(grid, "annotationEnabled") and grid.annotationEnabled())
                    max_d = 14 if has_ann else 30
                    div_x = (w_ext / ix_val) if ix_val > 0 else 0.0
                    div_y = (h_ext / iy_val) if iy_val > 0 else 0.0
                    if ix_val <= 0 or iy_val <= 0 or div_x > max_d or div_y > max_d or (0 < div_x < 2) or (0 < div_y < 2):
                        clean_x = nice_interval(w_ext, 5)
                        clean_y = nice_interval(h_ext, 5)
                        if clean_x > 0 and clean_y > 0:
                            grid.setIntervalX(clean_x)
                            grid.setIntervalY(clean_y)
                            fixes.append(f"Calibrated coordinate grid interval on '{item_id}'")

        # Fix scalebars
        elif isinstance(item, QgsLayoutItemScaleBar):
            linked = item.linkedMap() if hasattr(item, "linkedMap") else None
            if linked is None and primary_map is not None:
                item.setLinkedMap(primary_map)
                linked = primary_map
                fixes.append(f"Linked scale bar '{item_id}' to primary map")
            if linked is not None:
                needs_reconfig = False
                with suppress(Exception):
                    if float(item.unitsPerSegment()) <= 0:
                        needs_reconfig = True
                    segs = int(item.numberOfSegments()) + int(item.numberOfSegmentsLeft())
                    if segs < 2 or segs > 6:
                        needs_reconfig = True
                    if float(item.rect().width()) > float(linked.rect().width()) * 0.55:
                        needs_reconfig = True
                if needs_reconfig:
                    with suppress(Exception):
                        from .map_sheet import _configure_scalebar
                        max_sb_w = min(float(linked.rect().width()) * 0.45, max(35.0, float(item.rect().width())))
                        _configure_scalebar(item, linked, max_width_mm=max_sb_w)
                        fixes.append(f"Recalibrated scale bar segments on '{item_id}'")

        # Fix legends
        elif isinstance(item, QgsLayoutItemLegend):
            linked = item.linkedMap() if hasattr(item, "linkedMap") else None
            if linked is None and primary_map is not None:
                item.setLinkedMap(primary_map)
                fixes.append(f"Linked legend '{item_id}' to primary map")
            with suppress(Exception):
                w_leg = float(item.rect().width())
                h_leg = float(item.rect().height())
                if (w_leg < 18.0 or h_leg < 12.0) and QgsLayoutSize is not None:
                    w_leg = max(36.0, w_leg)
                    h_leg = max(24.0, h_leg)
                    item.attemptResize(QgsLayoutSize(w_leg, h_leg, _MM))
                    fixes.append(f"Expanded small legend frame '{item_id}'")
                from .map_sheet import _fit_legend_to_box
                _fit_legend_to_box(item, w_leg, h_leg)

    # 3. Fix Atlas driven map if Atlas is enabled
    with suppress(Exception):
        atlas = layout.atlas() if hasattr(layout, "atlas") else None
        if atlas is not None and atlas.enabled() and primary_map is not None:
            has_driven = any(
                isinstance(it, QgsLayoutItemMap) and hasattr(it, "atlasDriven") and it.atlasDriven()
                for it in items
            )
            if not has_driven:
                primary_map.setAtlasDriven(True)
                fixes.append(f"Enabled 'Controlled by Atlas' on primary map '{primary_map.id()}'")

    with suppress(Exception):
        layout.invalidateCache()
        layout.refresh()

    after_issues = preflight_layout(layout)
    after_summary = summarize_preflight(after_issues)
    return {
        "fixed_count": len(fixes),
        "fixes": fixes,
        "before": before_summary,
        "after": after_summary,
        "issues": after_issues,
    }


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
