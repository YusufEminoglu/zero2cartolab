# -*- coding: utf-8 -*-
"""Quick Style — one-click graduated or categorized renderer with a good palette."""
from __future__ import annotations

from contextlib import suppress

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorLayer,
    QgsSymbol,
    QgsRendererRange,
    QgsRendererCategory,
    QgsGraduatedSymbolRenderer,
    QgsCategorizedSymbolRenderer,
)

from ..core import palettes as pal
from ..core import quick_style as qs
from ..core.utils import safe_float
from ..core.bivariate_engine import geometric_interval_breaks
from ._help_mixin import CartoLabHelpMixin

_MODE_AUTO, _MODE_GRAD, _MODE_CAT = 0, 1, 2
_MAX_CATS = 100


class QuickStyleAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "style.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    MODE = "MODE"
    CLASSES = "CLASSES"
    METHOD = "METHOD"
    PALETTE = "PALETTE"
    REVERSE = "REVERSE"
    OUTLINE = "OUTLINE"
    SUMMARY = "SUMMARY"

    MODES = [("Auto (detect field type)", "auto"),
             ("Graduated (numeric)", "graduated"),
             ("Categorized (unique values)", "categorized")]
    METHODS = [
        ("Quantile (equal count)", qs.QUANTILE),
        ("Equal interval", qs.EQUAL),
        ("Geometric interval", qs.GEOMETRIC),
        ("Natural Breaks (Fisher-Jenks)", qs.JENKS),
        ("Head/Tail Breaks (power-law)", qs.HEAD_TAIL),
        ("Standard Deviation", qs.STD_DEV),
        ("Box Plot / Tukey Outliers", qs.BOX_PLOT),
        ("Equal Area (Quantile)", qs.EQUAL_AREA),
        ("Maximum Breaks (largest gaps)", qs.MAXIMUM),
        ("Pretty Breaks (nice round numbers)", qs.PRETTY),
    ]

    def name(self) -> str:
        return "quick_style"

    def displayName(self) -> str:
        return "Quick Style (auto choropleth / categories)"

    def group(self) -> str:
        return "Quick Style"

    def groupId(self) -> str:
        return "quick_style"

    def createInstance(self):
        return QuickStyleAlgorithm()

    def flags(self):
        f = super().flags()
        if hasattr(QgsProcessingAlgorithm, "FlagNoExecutionResults"):
            f |= QgsProcessingAlgorithm.FlagNoExecutionResults
        if hasattr(QgsProcessingAlgorithm, "FlagSupportsInPlaceEdits"):
            f |= QgsProcessingAlgorithm.FlagSupportsInPlaceEdits
        return f

    def shortHelpString(self) -> str:
        return (
            "Style an existing vector layer in place without creating a copy.\n\n"
            "Pick a field and a palette name: numeric fields become a graduated "
            "choropleth with ColorBrewer / colour-blind-safe palettes; string fields "
            "become a categorized map.\n\n"
            "In 'Auto' mode the layer field type decides whether graduated or "
            "categorized is applied."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, "Vector layer", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, "Field to style", parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODE, "Style as", options=[m[0] for m in self.MODES], defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes (graduated)",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=5, minValue=2, maxValue=12))
        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD, "Class break method (graduated)",
            options=[m[0] for m in self.METHODS], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Colour palette", options=pal.ordered_names(), defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.REVERSE, "Reverse palette", defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(
            self.OUTLINE, "Thin white outline", defaultValue=True))
        self.addOutput(QgsProcessingOutputString(self.SUMMARY, "Summary of changes"))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field = self.parameterAsString(parameters, self.FIELD, context)
        mode_idx = self.parameterAsEnum(parameters, self.MODE, context)
        classes = self.parameterAsInt(parameters, self.CLASSES, context)
        method_idx = self.parameterAsEnum(parameters, self.METHOD, context)
        palette_idx = self.parameterAsEnum(parameters, self.PALETTE, context)
        reverse = self.parameterAsBool(parameters, self.REVERSE, context)
        outline = self.parameterAsBool(parameters, self.OUTLINE, context)

        mode = self.MODES[mode_idx][1]
        method = self.METHODS[method_idx][1]
        palette_names = pal.ordered_names()
        palette = palette_names[palette_idx] if palette_idx < len(palette_names) else palette_names[0]

        field_idx = layer.fields().indexOf(field)
        if field_idx < 0:
            raise QgsProcessingException(f"Field '{field}' not found in layer '{layer.name()}'.")
        is_numeric = layer.fields()[field_idx].isNumeric()

        if mode == "auto":
            target_mode = "graduated" if is_numeric else "categorized"
        else:
            target_mode = mode

        if target_mode == "graduated":
            summary = self._graduated(layer, field, classes, method, palette, reverse, outline)
        else:
            summary = self._categorized(layer, field, palette, reverse, outline, feedback)

        layer.triggerRepaint()
        return {self.SUMMARY: summary}

    # -- helpers ----------------------------------------------------------

    def _symbol(self, layer, hex_color, outline):
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        sym.setColor(QColor(hex_color))
        if outline:
            with suppress(Exception):
                sl = sym.symbolLayer(0)
                if hasattr(sl, "setStrokeColor"):
                    sl.setStrokeColor(QColor("#ffffff"))
                if hasattr(sl, "setStrokeWidth"):
                    sl.setStrokeWidth(0.2)
        return sym

    def _colors(self, palette, n, reverse):
        cols = pal.get_palette(palette, n)
        return list(reversed(cols)) if reverse else cols

    def _graduated(self, layer, field, classes, method, palette, reverse, outline):
        values = [safe_float(f[field]) for f in layer.getFeatures() if safe_float(f[field]) is not None]
        if not values:
            raise QgsProcessingException(f"Field '{field}' has no numeric values.")
        edges = qs.compute_breaks(values, method=method, n=classes)
        ranges_lh = qs.edges_to_ranges(edges)
        if not ranges_lh:
            # Degenerate field (a single distinct value): one class is still
            # a valid, if plain, map — better than failing outright.
            v = values[0]
            ranges_lh = [(v, v)]
        colors = self._colors(palette, len(ranges_lh), reverse)
        ranges = []
        for (lo, hi), col in zip(ranges_lh, colors):
            label = f"{lo:.4g} - {hi:.4g}"
            ranges.append(QgsRendererRange(lo, hi, self._symbol(layer, col, outline), label))
        layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))
        return (f"Quick Style: graduated '{field}' into {len(ranges)} classes "
                f"({method}) with palette '{palette}'"
                f"{' (colour-blind safe)' if pal.is_colorblind_safe(palette) else ''}.")

    def _categorized(self, layer, field, palette, reverse, outline, feedback):
        seen = []
        for f in layer.getFeatures():
            v = f[field]
            if v is not None and v not in seen:
                seen.append(v)
                if len(seen) > _MAX_CATS:
                    break
        cats = sorted(seen, key=lambda x: str(x))
        if not cats:
            raise QgsProcessingException(f"Field '{field}' has no values.")
        if len(cats) >= _MAX_CATS:
            feedback.pushInfo(
                f"Field has many unique values; styling the first {_MAX_CATS}.")
        colors = self._colors(palette, len(cats), reverse)
        categories = []
        for value, col in zip(cats, colors):
            categories.append(
                QgsRendererCategory(value, self._symbol(layer, col, outline), str(value)))
        layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
        return (f"Quick Style: categorized '{field}' into {len(categories)} "
                f"classes with palette '{palette}'.")
