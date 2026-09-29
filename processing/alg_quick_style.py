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
    QgsWkbTypes,
)

from ..core import palettes as pal
from ..core import quick_style as qs
from ..core import hatch_patterns as hp
from ..core.utils import safe_float
from ._help_mixin import CartoLabHelpMixin

_MODE_AUTO, _MODE_GRAD, _MODE_CAT = 0, 1, 2
_MAX_CATS = 100


def hatch_fill_symbol(pattern, outline: bool = True):
    """Black-on-white fill symbol for a ``core.hatch_patterns`` pattern."""
    from qgis.core import (
        QgsFillSymbol, QgsLinePatternFillSymbolLayer, QgsLineSymbol,
        QgsMarkerSymbol, QgsPointPatternFillSymbolLayer, QgsSimpleFillSymbolLayer,
    )
    kind = pattern["kind"]
    # bottom to top: opaque ground, pattern, outline (so patterns never cover it)
    base = QgsFillSymbol.createSimple({
        "color": "0,0,0,255" if kind == "solid" else "255,255,255,255",
        "outline_style": "no",
    })
    if kind in ("lines", "cross"):
        angles = [pattern["angle"]]
        if kind == "cross":
            angles.append(pattern["angle"] + 90.0)
        for angle in angles:
            layer = QgsLinePatternFillSymbolLayer()
            layer.setLineAngle(float(angle))
            layer.setDistance(float(pattern["spacing"]))
            layer.setLineWidth(float(pattern["width"]))
            layer.setSubSymbol(QgsLineSymbol.createSimple({
                "line_color": "0,0,0,255", "line_width": str(pattern["width"]),
            }))
            base.appendSymbolLayer(layer)
    elif kind == "dots":
        layer = QgsPointPatternFillSymbolLayer()
        spacing = float(pattern["spacing"])
        layer.setDistanceX(spacing)
        layer.setDistanceY(spacing)
        layer.setDisplacementX(spacing / 2.0)  # staggered rows read as texture, not a grid
        layer.setSubSymbol(QgsMarkerSymbol.createSimple({
            "name": "circle", "color": "0,0,0,255", "outline_style": "no",
            "size": str(pattern["size"]),
        }))
        base.appendSymbolLayer(layer)
    if outline:
        border = QgsSimpleFillSymbolLayer.create({
            "style": "no", "outline_color": "35,35,35,255", "outline_width": "0.26",
        })
        base.appendSymbolLayer(border)
    return base


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
    MONOCHROME = "MONOCHROME"
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
        if hasattr(QgsProcessingAlgorithm.Flag, "FlagNoExecutionResults"):
            f |= QgsProcessingAlgorithm.Flag.FlagNoExecutionResults
        if hasattr(QgsProcessingAlgorithm.Flag, "FlagSupportsInPlaceEdits"):
            f |= QgsProcessingAlgorithm.Flag.FlagSupportsInPlaceEdits
        return f

    def shortHelpString(self) -> str:
        return (
            "Style an existing vector layer in place without creating a copy.\n\n"
            "Pick a field and a palette name: numeric fields become a graduated "
            "choropleth with ColorBrewer / colour-blind-safe palettes; string fields "
            "become a categorized map.\n\n"
            "In 'Auto' mode the layer field type decides whether graduated or "
            "categorized is applied.\n\n"
            "Monochrome print-safe: polygon layers get black-and-white hatch and "
            "dot patterns instead of colours, so the map survives greyscale "
            "printing and photocopies. Graduated classes darken strictly with "
            "the value (up to 10 classes); categories differ by texture and "
            "orientation (up to 16 before patterns repeat)."
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
        self.addParameter(QgsProcessingParameterBoolean(
            self.MONOCHROME, "Monochrome print-safe patterns (polygons)", defaultValue=False))
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
        monochrome = self.parameterAsBool(parameters, self.MONOCHROME, context)

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

        if monochrome and layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            feedback.pushWarning(
                "Monochrome patterns need a polygon layer; using the 'Greys' palette instead.")
            monochrome, palette = False, "Greys"
        if monochrome and target_mode == "graduated" and classes > hp.MAX_GRADUATED:
            feedback.pushWarning(
                f"Monochrome ramps stay readable up to {hp.MAX_GRADUATED} classes; "
                f"using {hp.MAX_GRADUATED}.")
            classes = hp.MAX_GRADUATED

        if target_mode == "graduated":
            summary = self._graduated(layer, field, classes, method, palette, reverse, outline, monochrome)
        else:
            summary = self._categorized(layer, field, palette, reverse, outline, feedback, monochrome)

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

    def _graduated(self, layer, field, classes, method, palette, reverse, outline, monochrome=False):
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
        if monochrome:
            patterns = hp.graduated_patterns(len(ranges_lh))
            if reverse:
                patterns.reverse()
            symbols = [hatch_fill_symbol(p, outline) for p in patterns]
        else:
            symbols = [self._symbol(layer, c, outline)
                       for c in self._colors(palette, len(ranges_lh), reverse)]
        ranges = []
        for (lo, hi), sym in zip(ranges_lh, symbols):
            label = f"{lo:.4g} - {hi:.4g}"
            ranges.append(QgsRendererRange(lo, hi, sym, label))
        layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))
        if monochrome:
            return (f"Quick Style: graduated '{field}' into {len(ranges)} classes "
                    f"({method}) with monochrome print-safe patterns.")
        return (f"Quick Style: graduated '{field}' into {len(ranges)} classes "
                f"({method}) with palette '{palette}'"
                f"{' (colour-blind safe)' if pal.is_colorblind_safe(palette) else ''}.")

    def _categorized(self, layer, field, palette, reverse, outline, feedback, monochrome=False):
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
        if monochrome:
            if len(cats) > hp.MAX_CATEGORICAL:
                feedback.pushWarning(
                    f"{len(cats)} categories: monochrome patterns repeat after "
                    f"{hp.MAX_CATEGORICAL}. Consider grouping categories.")
            symbols = [hatch_fill_symbol(p, outline) for p in hp.categorical_patterns(len(cats))]
        else:
            symbols = [self._symbol(layer, c, outline)
                       for c in self._colors(palette, len(cats), reverse)]
        categories = []
        for value, sym in zip(cats, symbols):
            categories.append(QgsRendererCategory(value, sym, str(value)))
        layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
        style = "monochrome print-safe patterns" if monochrome else f"palette '{palette}'"
        return (f"Quick Style: categorized '{field}' into {len(categories)} "
                f"classes with {style}.")
