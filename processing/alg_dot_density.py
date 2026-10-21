# -*- coding: utf-8 -*-
"""Dot-Density Map — Processing algorithm."""
from __future__ import annotations


from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterColor, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber, QgsWkbTypes, QgsMarkerSymbol, QgsSingleSymbolRenderer,
)

from ..core.dot_density import dots_for_value, generate_dots_in_parts
from ._help_mixin import CartoLabHelpMixin
from ._styling import style_output


def _parts_from_geometry(geom):
    """Split a (multi)polygon geometry into parts, each a list of (x, y) rings.

    Parts are kept separate so dots can be shared out by part area and sampled
    inside each part's own bounding box (islands far apart would otherwise
    waste most rejection-sampling draws on the empty sea between them).
    """
    if geom is None or geom.isEmpty():
        return []
    if geom.isMultipart():
        polygons = geom.asMultiPolygon()
    else:
        polygons = [geom.asPolygon()]
    return [[[(p.x(), p.y()) for p in ring] for ring in poly] for poly in polygons if poly]


def _rings_from_geometry(geom):
    """Flatten a (multi)polygon geometry into one list of (x, y) rings."""
    return [ring for part in _parts_from_geometry(geom) for ring in part]


class DotDensityAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "dot_density.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    VALUE_PER_DOT = "VALUE_PER_DOT"
    DOT_SIZE = "DOT_SIZE"
    DOT_COLOR = "DOT_COLOR"
    SEED = "SEED"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "dot_density"

    def displayName(self) -> str:
        return "Dot-Density Map"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return DotDensityAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Scatter dots inside each polygon, one dot per N units of a count "
            "field, so density reads as visual texture rather than colour.\n\n"
            "Placement is seeded (re-runs are identical) and hole-aware. Each dot "
            "inherits the source polygon's attributes, so you can colour dots by "
            "category for a multi-group dot map.\n\n"
            "• Value per dot: Choose so the busiest polygon shows a few hundred dots.\n"
            "• Marker size & color: Configured directly in millimeters and RGBA."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input polygon layer", [QgsProcessing.SourceType.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, "Count field", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.VALUE_PER_DOT, "Value represented by one dot",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=100.0, minValue=1e-9))
        self.addParameter(QgsProcessingParameterNumber(
            self.DOT_SIZE, "Dot marker size (mm)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1.0, minValue=0.1, maxValue=20.0))
        self.addParameter(QgsProcessingParameterColor(
            self.DOT_COLOR, "Dot marker color", defaultValue=QColor(33, 102, 131, 200)))
        self.addParameter(QgsProcessingParameterNumber(
            self.SEED, "Random seed", type=QgsProcessingParameterNumber.Type.Integer,
            defaultValue=42, minValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Dot-density output", QgsProcessing.SourceType.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field_name = self.parameterAsString(parameters, self.FIELD, context)
        per_dot = self.parameterAsDouble(parameters, self.VALUE_PER_DOT, context)
        dot_size = self.parameterAsDouble(parameters, self.DOT_SIZE, context) if self.DOT_SIZE in parameters else 1.0
        dot_color = self.parameterAsColor(parameters, self.DOT_COLOR, context) if self.DOT_COLOR in parameters else QColor(33, 102, 131, 200)
        seed = self.parameterAsInt(parameters, self.SEED, context)

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(QgsField(f.name(), f.type()))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Type.Point, source.sourceCrs(),
        )

        total = source.featureCount() or 1
        dots_written = 0
        dots_requested = 0
        short_features = 0
        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            n_dots = dots_for_value(feat[field_name], per_dot)
            if n_dots > 0:
                parts = _parts_from_geometry(feat.geometry())
                if parts:
                    dots_requested += n_dots
                    coords = generate_dots_in_parts(
                        parts, n_dots, seed=seed * 1000003 + current,
                    )
                    if len(coords) < n_dots:
                        short_features += 1
                    attrs = feat.attributes()[:]
                    for (x, y) in coords:
                        nf = QgsFeature(out_fields)
                        nf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                        nf.setAttributes(attrs)
                        sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
                        dots_written += 1
            feedback.setProgress(int(100 * current / total))

        feedback.pushInfo(f"Placed {dots_written} dots (1 dot = {per_dot:g} units).")
        if dots_written < dots_requested:
            feedback.pushWarning(
                f"Only {dots_written} of {dots_requested} dots could be placed: "
                f"{short_features} polygon(s) are too thin / degenerate to hold all their dots.")

        def _style(out_layer):
            c_str = f"{dot_color.red()},{dot_color.green()},{dot_color.blue()},{dot_color.alpha()}"
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle", "size": str(dot_size),
                "color": c_str, "outline_style": "no",
            })
            out_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            out_layer.triggerRepaint()

        style_output(context, dest_id, _style, feedback)

        return {self.OUTPUT: dest_id}
