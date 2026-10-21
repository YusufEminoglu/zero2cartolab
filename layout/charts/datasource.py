"""Bounded QGIS layer extraction for Print Layout charts."""
from __future__ import annotations

try:
    from qgis.core import NULL as _QGIS_NULL
except Exception:  # headless unit-test runs without QGIS
    _QGIS_NULL = None


MAX_ROWS = 50_000


def _is_null(value) -> bool:
    """QGIS-NULL-aware check; ``repr`` kept as a provider-wrapper fallback."""
    if value is None:
        return True
    if _QGIS_NULL is not None and value is _QGIS_NULL:
        return True
    return repr(value) == "NULL"


def extract_columns(layer, field_names, selected_only: bool = False, max_rows: int = MAX_ROWS):
    """Return row-aligned columns without importing or depending on zero2viz."""
    if layer is None:
        raise ValueError("Select a vector layer first.")
    names = [name for name in dict.fromkeys(field_names) if name]
    indices = {name: layer.fields().lookupField(name) for name in names}
    missing = [name for name, index in indices.items() if index < 0]
    if missing:
        raise ValueError(f"Field(s) not found: {', '.join(missing)}")
    out = {name: [] for name in names}
    features = layer.selectedFeatures() if selected_only else layer.getFeatures()
    for row, feature in enumerate(features):
        if row >= max(1, int(max_rows)):
            break
        attrs = feature.attributes()
        for name, index in indices.items():
            value = attrs[index]
            out[name].append(None if _is_null(value) else value)
    return out
