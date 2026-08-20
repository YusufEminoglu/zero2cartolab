# -*- coding: utf-8 -*-
"""Value-by-Alpha — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber,
)

from ..core.utils import safe_float
from ..core.bivariate_engine import compute_alpha_values
from ._help_mixin import CartoLabHelpMixin


class ValueByAlphaAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "vba.png"
    INPUT = "INPUT"
    FIELD_COLOUR = "FIELD_COLOUR"
    FIELD_ALPHA = "FIELD_ALPHA"
    ALPHA_MIN = "ALPHA_MIN"
    ALPHA_MAX = "ALPHA_MAX"
    PALETTE = "PALETTE"
    CLASSES = "CLASSES"
    OUTPUT = "OUTPUT"

    PALETTES_LIST = [
        "Viridis", "Plasma", "Inferno", "Magma", "Cividis",
        "Turbo", "Mako", "Rocket", "Blues", "Oranges", "Purples", "Greens"
    ]

    def name(self) -> str:
        return "value_by_alpha"

    def displayName(self) -> str:
        return "Value-by-Alpha (VbA) Map"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return ValueByAlphaAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Encode uncertainty/reliability as opacity (alpha channel).\n\n"
            "• Primary variable drives color gradient.\n"
            "• Secondary reliability variable controls opacity (High reliability = opaque, Low = transparent).\n"
            "• Color Palette & Classes: Direct sequential ramp selection.\n"
            "Adds 'vba_alpha' (0-255) and 'vba_alpha_pct' (0-100) fields and sets up data-defined opacity renderer."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input layer", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_COLOUR, "Primary variable (colour)", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_ALPHA, "Reliability variable (opacity)", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.ALPHA_MIN, "Minimum opacity (least reliable)",
            type=QgsProcessingParameterNumber.Type.Integer,
            defaultValue=25, minValue=0, maxValue=255))
        self.addParameter(QgsProcessingParameterNumber(
            self.ALPHA_MAX, "Maximum opacity (most reliable)",
            type=QgsProcessingParameterNumber.Type.Integer,
            defaultValue=255, minValue=0, maxValue=255))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Color ramp (for primary variable)",
            options=self.PALETTES_LIST, defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes",
            type=QgsProcessingParameterNumber.Type.Integer,
            defaultValue=5, minValue=2, maxValue=10))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "VbA output"))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        colour_field = self.parameterAsString(parameters, self.FIELD_COLOUR, context)
        alpha_field = self.parameterAsString(parameters, self.FIELD_ALPHA, context)
        alpha_min = self.parameterAsInt(parameters, self.ALPHA_MIN, context)
        alpha_max = self.parameterAsInt(parameters, self.ALPHA_MAX, context)
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context) if self.PALETTE in parameters else 0
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "Viridis"
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context) if self.CLASSES in parameters else 5

        primary_vals = []
        reliability_vals = []
        features_raw = []
        for feat in source.getFeatures():
            pv = safe_float(feat[colour_field])
            rv = safe_float(feat[alpha_field])
            primary_vals.append(pv if pv is not None else 0.0)
            reliability_vals.append(rv if rv is not None else 0.0)
            features_raw.append(feat)

        if not features_raw:
            raise QgsProcessingException("No features in input layer.")

        alpha_values = compute_alpha_values(primary_vals, reliability_vals, alpha_min, alpha_max)

        # Build output schema
        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(QgsField(f.name(), f.type()))
        out_fields.append(QgsField("vba_alpha", QVariant.Int))
        out_fields.append(QgsField("vba_alpha_pct", QVariant.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs(),
        )

        total = len(features_raw)
        for i, feat in enumerate(features_raw):
            if feedback.isCanceled():
                break
            attrs = feat.attributes()[:]
            attrs.append(alpha_values[i])
            attrs.append(int(100 * alpha_values[i] / 255))

            new_feat = QgsFeature(out_fields)
            new_feat.setGeometry(feat.geometry())
            new_feat.setAttributes(attrs)
            sink.addFeature(new_feat, QgsFeatureSink.Flag.FastInsert)
            feedback.setProgress(int(100 * i / total))

        feedback.pushInfo(
            f"VbA complete. Alpha range [{alpha_min}, {alpha_max}]. "
            "Applied data-defined layer opacity on 'vba_alpha'."
        )

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer and out_layer.isSpatial():
                from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol, QgsProperty
                from ..core.quick_style import quantile_breaks
                from ..core.palettes import get_palette

                colors = get_palette(pal_name, n_classes)
                breaks = quantile_breaks(primary_vals, n_classes)
                ranges = []
                for i in range(len(breaks) - 1):
                    lo, hi = breaks[i], breaks[i + 1]
                    c = colors[min(i, len(colors) - 1)]
                    sym = QgsSymbol.defaultSymbol(out_layer.geometryType())
                    if sym:
                        sym.setColor(QColor(c))
                        sym.setDataDefinedProperty(
                            QgsSymbol.Property.PropertyOpacity,
                            QgsProperty.fromExpression("vba_alpha / 255.0 * 100.0")
                        )
                        label = f"{lo:.2f} - {hi:.2f}"
                        ranges.append(QgsRendererRange(lo, hi, sym, label))
                if ranges:
                    renderer = QgsGraduatedSymbolRenderer(colour_field, ranges)
                    renderer.setMode(QgsGraduatedSymbolRenderer.Mode.Quantile)
                    out_layer.setRenderer(renderer)
                    out_layer.triggerRepaint()

        return {self.OUTPUT: dest_id}
