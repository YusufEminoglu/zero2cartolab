# -*- coding: utf-8 -*-
"""Dorling Circle Cartogram — Processing algorithm."""
from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingOutputNumber, QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber, QgsWkbTypes,
)

from ..core import dorling
from ..core.utils import safe_float
from ..core.palettes import get_palette
from ..core.quick_style import quantile_breaks
from ._help_mixin import CartoLabHelpMixin
from ._styling import style_output


def apply_dorling_renderer(layer, breaks, colours) -> None:
    from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol

    ranges = []
    for i in range(len(breaks) - 1):
        lo, hi = breaks[i], breaks[i + 1]
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        if sym is None:
            continue
        sym.setColor(QColor(colours[min(i, len(colours) - 1)]))
        for idx in range(sym.symbolLayerCount()):
            sl = sym.symbolLayer(idx)
            if hasattr(sl, "setStrokeColor"):
                sl.setStrokeColor(QColor(255, 255, 255, 230))
            if hasattr(sl, "setStrokeWidth"):
                sl.setStrokeWidth(0.25)
        ranges.append(QgsRendererRange(lo, hi, sym, f"{lo:,.2f} – {hi:,.2f}"))
    if ranges:
        layer.setRenderer(QgsGraduatedSymbolRenderer("dor_value", ranges))


class DorlingCartogramAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "dorling.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    SIZE_FACTOR = "SIZE_FACTOR"
    ATTRACTION = "ATTRACTION"
    GAP = "GAP"
    ITERATIONS = "ITERATIONS"
    PALETTE = "PALETTE"
    OUTPUT = "OUTPUT"
    ROUNDS = "ROUNDS"
    RESIDUAL = "RESIDUAL"

    PALETTES_LIST = ["Viridis", "YlGnBu", "YlOrRd", "Plasma", "Magma", "Blues", "Purples"]

    def name(self) -> str:
        return "dorling_cartogram"

    def displayName(self) -> str:
        return "Dorling Circle Cartogram"

    def group(self) -> str:
        return "Cartogram Engine"

    def groupId(self) -> str:
        return "cartogram_engine"

    def createInstance(self):
        return DorlingCartogramAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Replace every areal unit with a circle whose area is proportional "
            "to a value, then move the circles apart until none overlap "
            "(Dorling 1996).\n\n"
            "Unlike a continuous cartogram, shapes are not deformed: each unit "
            "is an honest, directly comparable circle, and small units with "
            "large values stay visible.\n\n"
            "• Size factor: the circles' total area as a share of the input "
            "layer's area. Lower values give more space between circles and "
            "smaller displacements.\n"
            "• Attraction: how strongly circles are pulled back toward their "
            "home position while they separate (fades to zero, so the result "
            "never overlaps).\n"
            "• Gap: extra spacing between circles, in layer units.\n"
            "• Units with a missing, zero or negative value are omitted.\n\n"
            "Output fields: every input field plus dor_value, dor_radius and "
            "dor_shift (distance moved from the unit's interior point). Use a "
            "projected CRS: circles are built in layer units."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Areal units (polygons)", [QgsProcessing.SourceType.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, "Value field", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.SIZE_FACTOR, "Size factor (total circle area / layer area)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.5,
            minValue=0.01, maxValue=2.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.ATTRACTION, "Attraction toward home position (0-1)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.1,
            minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.GAP, "Gap between circles (layer units)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.ITERATIONS, "Settling iterations",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=150,
            minValue=1, maxValue=5000))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Colour ramp", options=self.PALETTES_LIST, defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Dorling cartogram", QgsProcessing.SourceType.TypeVectorPolygon))
        self.addOutput(QgsProcessingOutputNumber(self.ROUNDS, "Iterations used"))
        self.addOutput(QgsProcessingOutputNumber(
            self.RESIDUAL, "Residual overlap (fraction of mean radius, <= 0 = none)"))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field = self.parameterAsString(parameters, self.FIELD, context)
        size_factor = self.parameterAsDouble(parameters, self.SIZE_FACTOR, context)
        attraction = self.parameterAsDouble(parameters, self.ATTRACTION, context)
        gap = self.parameterAsDouble(parameters, self.GAP, context)
        iterations = self.parameterAsInt(parameters, self.ITERATIONS, context)
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context)
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "Viridis"

        if source.sourceCrs().isValid() and source.sourceCrs().isGeographic():
            feedback.pushWarning(
                "The layer uses a geographic CRS: circles are built in degrees and will look "
                "stretched away from the equator. Reproject to a projected CRS for true circles.")

        feats, centers, values = [], [], []
        total_area = 0.0
        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            total_area += geom.area()
            value = safe_float(feat[field])
            if value is None or value <= 0:
                continue
            pt = geom.pointOnSurface()
            if pt is None or pt.isEmpty():
                continue
            p = pt.asPoint()
            feats.append(feat)
            centers.append((p.x(), p.y()))
            values.append(value)
        if not feats:
            raise QgsProcessingException(f"No features with a positive value in '{field}'.")

        radii = dorling.dorling_radii(values, size_factor * total_area)
        budget = iterations + 2000

        def _tick(done, _phase):
            feedback.setProgress(min(95, int(95 * done / budget)))
            return feedback.isCanceled()

        positions, rounds, residual = dorling.dorling_layout(
            centers, radii, iterations=iterations, attraction=attraction,
            gap=gap, callback=_tick,
        )
        if feedback.isCanceled():
            return {}

        out_fields = QgsFields(source.fields())
        for name, vtype in (("dor_value", QVariant.Double), ("dor_radius", QVariant.Double),
                            ("dor_shift", QVariant.Double)):
            if out_fields.indexFromName(name) < 0:
                out_fields.append(QgsField(name, vtype))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            QgsWkbTypes.Type.Polygon, source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        extra = {"dor_value": 0, "dor_radius": 1, "dor_shift": 2}
        for feat, home, pos, r, v in zip(feats, centers, positions, radii, values):
            circle = QgsGeometry.fromPointXY(QgsPointXY(*pos)).buffer(r, 24)
            nf = QgsFeature(out_fields)
            nf.setGeometry(circle)
            attrs = list(feat.attributes()) + [None] * (out_fields.count() - len(feat.attributes()))
            computed = (v, r, dorling.displacement(home, pos))
            for name, k in extra.items():
                attrs[out_fields.indexFromName(name)] = computed[k]
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
        feedback.setProgress(100)

        feedback.pushInfo(
            f"Placed {len(feats)} circles in {rounds} iterations; residual overlap "
            f"{max(0.0, residual) * 100:.2f}% of the mean radius.")
        if residual > 0.01:
            feedback.pushWarning(
                "Some circles still overlap. Lower the size factor or raise the iterations.")

        n_classes = min(5, max(1, len(set(values))))
        breaks = sorted(set(quantile_breaks(values, n_classes))) if n_classes > 1 else []
        if len(breaks) < 2:
            breaks = [min(values), max(values)]
        colours = get_palette(pal_name, max(1, len(breaks) - 1))
        style_output(context, dest_id, lambda layer: apply_dorling_renderer(layer, breaks, colours), feedback)

        return {self.OUTPUT: dest_id, self.ROUNDS: rounds, self.RESIDUAL: residual}
