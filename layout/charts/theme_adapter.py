"""Optional 02viz theme discovery with a dependency-free fallback path."""
from __future__ import annotations

import re


API_ID = "zero2viz.print_layout_themes"
SUPPORTED_API_VERSION = 1
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalise_theme(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    required = ("id", "label", "palette", "background", "text", "grid")
    if any(not value.get(key) for key in required):
        return None
    palette = value["palette"]
    colors = [str(color).lower() for color in palette]
    if not isinstance(palette, (list, tuple)) or not colors:
        return None
    if any(not _COLOR.fullmatch(color) for color in colors):
        return None
    surfaces = [str(value[key]).lower() for key in ("background", "text", "grid")]
    if any(not _COLOR.fullmatch(color) for color in surfaces):
        return None
    try:
        title_size = min(24.0, max(6.0, float(value.get("title_size_pt", 9.0))))
        label_size = min(16.0, max(4.0, float(value.get("label_size_pt", 5.6))))
        line_width = min(3.0, max(0.1, float(value.get("line_width_mm", 0.65))))
    except (TypeError, ValueError):
        return None
    return {
        "id": str(value["id"])[:80],
        "label": str(value["label"])[:100],
        "provider": "02viz",
        "palette": tuple(colors[:16]),
        "surface": tuple(surfaces),
        "font_family": str(value.get("font_family", "Segoe UI"))[:100],
        "title_size_pt": title_size,
        "label_size_pt": label_size,
        "line_width_mm": line_width,
    }


def discover_zero2viz_themes(plugin_registry=None) -> tuple[list[dict], str]:
    """Return validated 02viz themes and a user-facing availability status."""
    if plugin_registry is None:
        try:
            from qgis.utils import plugins
            plugin_registry = plugins
        except (ImportError, AttributeError):
            return [], "02viz not active · built-in themes available"
    plugin = plugin_registry.get("zero2viz") if hasattr(plugin_registry, "get") else None
    provider = getattr(plugin, "print_layout_theme_catalog", None)
    if not callable(provider):
        return [], "02viz not active · built-in themes available"
    try:
        catalog = provider()
    except Exception as exc:
        return [], f"02viz themes unavailable · {type(exc).__name__}"
    if (not isinstance(catalog, dict) or catalog.get("api") != API_ID
            or catalog.get("api_version") != SUPPORTED_API_VERSION):
        return [], "02viz theme API is incompatible · built-in themes available"
    themes = [_normalise_theme(theme) for theme in catalog.get("themes", [])]
    clean = [theme for theme in themes if theme is not None]
    if not clean:
        return [], "02viz returned no valid themes · built-in themes available"
    return clean, f"02viz connected · {len(clean)} studio themes"
