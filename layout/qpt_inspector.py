# -*- coding: utf-8 -*-
"""Safe, dependency-free structural inspection for QGIS QPT templates."""
from __future__ import annotations

import os
import re
from html import unescape
from collections import Counter
from typing import Any, Dict


_FUNCTION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_ATTR_RE = re.compile(r"([A-Za-z_:][\w:.-]*)\s*=\s*\"([^\"]*)\"")
_EXTERNAL_FUNCTIONS = {"mgrs_gzd", "mgrs_100km"}
_TYPE_NAMES = {65638: "page", 65639: "map", 65640: "picture", 65641: "label",
               65642: "legend", 65643: "shape", 65644: "scale_bar"}


def _attributes(fragment: str) -> Dict[str, str]:
    return {name: unescape(value) for name, value in _ATTR_RE.findall(fragment)}


def inspect_qpt(path: str) -> Dict[str, Any]:
    """Return a compact structural and compatibility report for a QPT file."""
    resolved = os.path.abspath(path)
    if os.path.splitext(resolved)[1].lower() != ".qpt":
        raise ValueError("Template must use the .qpt extension.")
    size = os.path.getsize(resolved)
    if size > 10 * 1024 * 1024:
        raise ValueError("QPT exceeds the 10 MB inspection limit.")
    with open(resolved, "r", encoding="utf-8-sig") as handle:
        source = handle.read()
    root_match = re.search(r"<Layout\b([^>]*)>", source)
    if root_match is None:
        raise ValueError("The file does not contain a QGIS Layout root element.")
    root = _attributes(root_match.group(1))

    items = [_attributes(match) for match in re.findall(r"<LayoutItem\b([^>]*)>", source)]
    grids = [_attributes(match) for match in re.findall(r"<ComposerMapGrid\b([^>]*)>", source)]
    item_types = Counter(_TYPE_NAMES.get(int(item.get("type", -1)), item.get("type", "unknown"))
                         for item in items)
    page_sizes = [item.get("size", "") for item in items if item.get("type") == "65638"]
    expressions = [grid.get("annotationExpression", "") for grid in grids]
    functions = sorted({fn for expr in expressions for fn in _FUNCTION_RE.findall(expr)})
    external = sorted(set(functions) & _EXTERNAL_FUNCTIONS)
    active_grids = [grid for grid in grids if grid.get("show", "1") == "1"]
    blank_ids = sum(1 for item in items if not item.get("id", "").strip())
    off_page = sum(
        1 for item in items
        if item.get("type") != "65638" and item.get("position", "").lstrip().startswith("-")
    )
    warnings = []
    if external:
        warnings.append("External expression functions required: " + ", ".join(external))
    if blank_ids:
        warnings.append(f"{blank_ids} layout item(s) have no stable ID.")
    if off_page:
        warnings.append(f"{off_page} item(s) are positioned outside the page.")
    if not any(item.get("type") == "65639" for item in items):
        warnings.append("No map frame was found.")

    return {
        "path": resolved,
        "name": root.get("name", "Untitled Layout"),
        "units": root.get("units", ""),
        "dpi": int(float(root.get("printResolution", "300"))),
        "size_bytes": size,
        "page_sizes": page_sizes,
        "item_count": len(items),
        "item_types": dict(item_types),
        "grid_count": len(grids),
        "active_grid_count": len(active_grids),
        "grid_names": [grid.get("name", "Unnamed grid") for grid in grids],
        "expression_functions": functions,
        "external_functions": external,
        "safe_to_import": not external,
        "warnings": warnings,
    }


def format_qpt_report(report: Dict[str, Any]) -> str:
    """Format :func:`inspect_qpt` output for the dashboard."""
    types = ", ".join(f"{name}: {count}" for name, count in report["item_types"].items())
    warning_text = "\n".join(f"- {warning}" for warning in report["warnings"]) or "- None"
    grid_text = "\n".join(f"- {name}" for name in report["grid_names"]) or "- None"
    return (
        f"Template: {report['name']}\n"
        f"Page: {', '.join(report['page_sizes']) or 'unknown'} | {report['dpi']} DPI\n"
        f"Items: {report['item_count']} ({types})\n"
        f"Grids: {report['active_grid_count']} active / {report['grid_count']} total\n\n"
        f"Grid stack:\n{grid_text}\n\nCompatibility notes:\n{warning_text}"
    )
