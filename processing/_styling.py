# -*- coding: utf-8 -*-
"""Deliver an algorithm's symbology to its output however the result is stored.

Styling ``context.getMapLayer(dest_id)`` inside ``processAlgorithm`` only
reaches the project for temporary (memory) outputs: that object *is* the layer
QGIS later adds. A GeoPackage or Shapefile output is re-read from disk when
QGIS loads it, so a style set during the run is silently lost. A layer
post-processor runs on the layer that is actually loaded, whatever its format.

QGIS keeps only a raw pointer to a Python post-processor, so the wrapper must
outlive ``processAlgorithm`` or it is garbage-collected before the load and
never runs (the QGIS documentation's own "sip bug" workaround). Batch runs
load every result at the end, so instances are kept rather than rotated.
"""
from __future__ import annotations

from typing import Callable

from qgis.core import QgsProcessingLayerPostProcessorInterface

_ALIVE: list = []


class _StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    def __init__(self, apply: Callable):
        super().__init__()
        self._apply = apply

    def postProcessLayer(self, layer, context, feedback) -> None:
        if layer is None:
            return
        try:
            self._apply(layer)
            layer.triggerRepaint()
        except Exception as exc:
            if feedback is not None:
                feedback.reportError(f"Could not apply 02CartoLab symbology: {exc}", False)


def style_output(context, dest_id: str, apply: Callable, feedback=None) -> bool:
    """Apply ``apply(layer)`` to the output identified by ``dest_id``.

    The style is applied at once when the output is a temporary layer held by
    the context, and it is registered to run again on the loaded layer when
    QGIS is going to add the result to a project. ``apply`` must capture only
    plain values (breaks, colours, field names), never a layer. Returns True
    when the style was applied or scheduled.
    """
    delivered = False
    layer = None
    store = context.temporaryLayerStore() if hasattr(context, "temporaryLayerStore") else None
    if store is not None and dest_id:
        layer = store.mapLayer(dest_id)
    if layer is not None:
        try:
            apply(layer)
            layer.triggerRepaint()
            delivered = True
        except Exception as exc:
            if feedback is not None:
                feedback.reportError(f"Could not apply 02CartoLab symbology: {exc}", False)

    if dest_id and context.willLoadLayerOnCompletion(dest_id):
        processor = _StylePostProcessor(apply)
        _ALIVE.append(processor)
        context.layerToLoadOnCompletionDetails(dest_id).setPostProcessor(processor)
        delivered = True
    return delivered
