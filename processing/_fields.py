# -*- coding: utf-8 -*-
"""Output-schema helpers shared by the attribute-appending algorithms.

``QgsFields.append`` refuses a field whose name already exists and returns
``False`` silently. Appending computed values positionally after the source
attributes therefore breaks when an algorithm is re-run on its own output:
the new value lands past the end of the schema and the stale value from the
previous run is kept. These helpers reuse the existing column instead.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

from qgis.core import QgsField, QgsFields


def extend_fields(source_fields, specs: Iterable[Tuple[str, object]]) -> Tuple[QgsFields, Dict[str, int]]:
    """Copy ``source_fields`` and add each ``(name, QVariant type)`` not already present.

    Returns the output fields and a ``{name: index}`` map for the computed columns.
    Existing columns of the same name (case-insensitive, as QGIS providers treat
    them) are reused rather than duplicated.
    """
    out_fields = QgsFields(source_fields)
    index = {}
    for name, vtype in specs:
        idx = out_fields.lookupField(name)
        if idx < 0:
            out_fields.append(QgsField(name, vtype))
            idx = out_fields.indexFromName(name)
        index[name] = idx
    return out_fields, index


def output_attributes(feat, out_fields: QgsFields, index: Dict[str, int], values: Dict[str, object]) -> list:
    """Source attributes padded to ``out_fields`` with ``values`` written at their columns."""
    attrs = list(feat.attributes())
    count = out_fields.count()
    if len(attrs) < count:
        attrs.extend([None] * (count - len(attrs)))
    else:
        attrs = attrs[:count]
    for name, value in values.items():
        attrs[index[name]] = value
    return attrs
