# -*- coding: utf-8 -*-
"""Hexbin Aggregation — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..core.utils import safe_float
from ..core.hexgrid import point_to_cell, cell_center, hex_vertices
from ._help_mixin import CartoLabHelpMixin


class HexbinAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "hexbin.png"
    INPUT = "INPUT"
    CELL_SIZE = "CELL_SIZE"
    WEIGHT = "WEIGHT"
    STAT = "STAT"
    PALETTE = "PALETTE"
    CLASSIFIER = "CLASSIFIER"
    CLASSES = "CLASSES"
    OUTPUT = "OUTPUT"

    STATS = [("Count", "count"), ("Sum of weight", "sum"), ("Mean of weight", "mean")]
    PALETTES_LIST = [
        "Viridis", "Plasma", "Inferno", "Magma", "Cividis",
        "Turbo", "Mako", "Rocket", "Blues", "Oranges", "YlOrRd", "Purples", "Greens"
    ]
    CLASSIFIERS = ["Quantile", "Equal Interval", "Natural Breaks (Jenks)", "Pretty Breaks"]

    def name(self) -> str:
        return "hexbin_aggregate"

    def displayName(self) -> str:
        return "Hexbin Aggregation"

    def group(self) -> str:
        return "Aggregation"

    def groupId(self) -> str:
        return "aggregation"

    def createInstance(self):
        return HexbinAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Aggregate a point layer into a pointy-top hexagonal grid. Only hexagons "
            "that actually contain points are emitted, so dense scatter plots become "
            "a clean, overplot-free density surface.\n\n"
            "• Statistic: Point count, sum of weight, or mean of weight.\n"
            "• Cell size: Hexagon radius in layer's map units.\n"
            "• Color Palette & Classifier: Direct styling with Quantile, Equal Interval, Jenks, or Pretty breaks.\n"
            "Output carries hex_count, hex_sum, hex_mean and is graduated automatically."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input point layer", [QgsProcessing.SourceType.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber(
            self.CELL_SIZE, "Hexagon radius (map units)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1000.0, minValue=1e-9))
        self.addParameter(QgsProcessingParameterField(
            self.WEIGHT, "Weight field (for sum / mean)", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.STAT, "Statistic", options=[s[0] for s in self.STATS], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Color ramp", options=self.PALETTES_LIST, defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.CLASSIFIER, "Classification method", options=self.CLASSIFIERS, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=5, minValue=2, maxValue=10))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Hexbin output", QgsProcessing.SourceType.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        size = self.parameterAsDouble(parameters, self.CELL_SIZE, context)
        weight_field = self.parameterAsString(parameters, self.WEIGHT, context)
        stat = self.STATS[self.parameterAsEnum(parameters, self.STAT, context)][1]
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context) if self.PALETTE in parameters else 0
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "Viridis"
        clf_idx = self.parameterAsEnum(parameters, self.CLASSIFIER, context) if self.CLASSIFIER in parameters else 0
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context) if self.CLASSES in parameters else 5

        ext = source.sourceExtent()
        extent_span = max(ext.width(), ext.height()) if ext and not ext.isEmpty() else 1000.0
        if size <= 0:
            size = extent_span / 40.0

        min_allowed = extent_span / 500.0
        if size < min_allowed:
            size = min_allowed
            feedback.pushInfo(f"Cell size adjusted to safeguard memory -> {size:.2f}")

        bins = {}
        total = source.featureCount() or 1
        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            pt = geom.centroid().asPoint()
            cell = point_to_cell(pt.x(), pt.y(), size)
            w = 1.0
            if weight_field:
                w = safe_float(feat[weight_field])
            entry = bins.setdefault(cell, [0, 0.0])
            entry[0] += 1
            if w is not None:
                entry[1] += w
            feedback.setProgress(int(50 * current / total))

        out_fields = QgsFields()
        out_fields.append(QgsField("hex_q", QVariant.Int))
        out_fields.append(QgsField("hex_r", QVariant.Int))
        out_fields.append(QgsField("hex_count", QVariant.Int))
        out_fields.append(QgsField("hex_sum", QVariant.Double))
        out_fields.append(QgsField("hex_mean", QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Type.Polygon, source.sourceCrs(),
        )

        stat_field = {"count": "hex_count", "sum": "hex_sum", "mean": "hex_mean"}[stat]
        stat_values = []
        n_cells = len(bins) or 1
        for idx, ((q, r), (count, wsum)) in enumerate(bins.items()):
            cx, cy = cell_center(q, r, size)
            ring = [QgsPointXY(x, y) for (x, y) in hex_vertices(cx, cy, size)]
            ring.append(ring[0])
            nf = QgsFeature(out_fields)
            nf.setGeometry(QgsGeometry.fromPolygonXY([ring]))
            mean = wsum / count if count else 0.0
            nf.setAttributes([q, r, count, wsum, mean])
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
            stat_values.append(count if stat == "count" else (wsum if stat == "sum" else mean))
            feedback.setProgress(50 + int(50 * idx / n_cells))

        feedback.pushInfo(f"Aggregated {total} points into {len(bins)} hexagons (statistic: {stat}).")

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer and stat_values:
                _apply_hex_graduated(out_layer, stat_field, stat_values, pal_name, n_classes, clf_idx)

        return {self.OUTPUT: dest_id}


def _apply_hex_graduated(layer, field, values, pal_name, n_classes, clf_idx):
    """Apply graduated renderer with chosen palette and classifier."""
    from qgis.core import (
        QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol,
    )
    from ..core.palettes import get_palette
    from ..core.quick_style import quantile_breaks, equal_interval_breaks, jenks_breaks, pretty_breaks

    colours = get_palette(pal_name, n_classes)
    if clf_idx == 0:
        breaks = quantile_breaks(values, n_classes)
    elif clf_idx == 1:
        breaks = equal_interval_breaks(values, n_classes)
    elif clf_idx == 2:
        breaks = jenks_breaks(values, n_classes)
    else:
        breaks = pretty_breaks(values, n_classes)

    ranges = []
    for i in range(len(breaks) - 1):
        lo = breaks[i]
        hi = breaks[i + 1]
        c = colours[min(i, len(colours) - 1)]
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        if sym:
            sym.setColor(QColor(c))
            sym.setOpacity(0.92)
            ranges.append(QgsRendererRange(lo, hi, sym, f"{lo:.2f} – {hi:.2f}"))
    if ranges:
        renderer = QgsGraduatedSymbolRenderer(field, ranges)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
