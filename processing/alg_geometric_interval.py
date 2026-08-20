# -*- coding: utf-8 -*-
"""Adaptive Geometric Interval & Advanced Classification — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.core import (
    QgsClassificationCustom, QgsFeature, QgsFeatureSink, QgsField, QgsFields,
    QgsGraduatedSymbolRenderer, QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingException, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber, QgsProcessingParameterEnum,
    QgsRendererRange, QgsSymbol,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..core.utils import safe_float
from ..core.bivariate_engine import (
    geometric_interval_breaks, head_tail_breaks, fisher_jenks_breaks,
    standard_deviation_breaks, box_plot_breaks,
)
from ..core.quick_style import maximum_breaks, pretty_breaks
from ..core import palettes as pal
from ._help_mixin import CartoLabHelpMixin


class GeometricIntervalAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "bivariate.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    CLASSES = "CLASSES"
    METHOD = "METHOD"
    PALETTE = "PALETTE"
    OUTPUT = "OUTPUT"

    METHODS = [
        ("Adaptive Geometric Interval (GIC)", "geometric"),
        ("Head/Tail Breaks", "head_tail"),
        ("Fisher-Jenks Natural Breaks", "fisher_jenks"),
        ("Standard Deviation", "std_dev"),
        ("Box Plot / Tukey Breaks", "box_plot"),
        ("Maximum Distribution Breaks", "maximum_breaks"),
        ("Pretty Nice-Round Breaks", "pretty_breaks"),
    ]

    PALETTES_LIST = pal.ordered_names()

    def name(self) -> str:
        return "geometric_interval_classification"

    def displayName(self) -> str:
        return "Advanced Classification (GIC / Head-Tail / Jenks / StdDev / BoxPlot / Max / Pretty)"

    def group(self) -> str:
        return "Classification"

    def groupId(self) -> str:
        return "classification"

    def createInstance(self):
        return GeometricIntervalAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Classify a numeric field using advanced cartographic algorithms.\n\n"
            "• Adaptive GIC: Optimal for skewed continuous and geometric growth data.\n"
            "• Head/Tail Breaks: Optimal for heavy-tailed / power-law spatial distributions.\n"
            "• Fisher-Jenks: Natural breaks minimising within-class variance.\n"
            "• Standard Deviation: Symmetrical interval breaks centered at the sample mean.\n"
            "• Box Plot / Tukey: Outlier-resistant quartile and fence boundaries.\n"
            "• Maximum Breaks: Splits data at the largest natural distribution gaps.\n"
            "• Pretty Breaks: Heckbert algorithm for clean rounded interval boundaries.\n\n"
            "Output carries 'gic_class' (0-based integer index) and 'gic_label' fields, "
            "and is styled automatically with the chosen color ramp."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input layer", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, "Field to classify", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes", type=QgsProcessingParameterNumber.Type.Integer,
            minValue=2, defaultValue=5, maxValue=20))
        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD, "Classification method",
            options=[m[0] for m in self.METHODS], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Color ramp",
            options=self.PALETTES_LIST, defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Classified output"))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field_name = self.parameterAsString(parameters, self.FIELD, context)
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context)
        method_idx = self.parameterAsEnum(parameters, self.METHOD, context)
        method = self.METHODS[method_idx][1]
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context) if self.PALETTE in parameters else 0
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "Viridis"

        values = []
        features_raw = []
        for feat in source.getFeatures():
            fv = safe_float(feat[field_name])
            if fv is not None:
                values.append(fv)
                features_raw.append(feat)

        if not values:
            raise QgsProcessingException(f"No valid numeric values in field '{field_name}'.")

        feedback.pushInfo(f"Classifying {len(values)} values using {method} into {n_classes} classes.")

        if method == "geometric":
            breaks = geometric_interval_breaks(values, n_classes)
        elif method == "head_tail":
            breaks = head_tail_breaks(values)
        elif method == "fisher_jenks":
            breaks = fisher_jenks_breaks(values, n_classes)
        elif method == "std_dev":
            breaks = standard_deviation_breaks(values, n_classes)
        elif method == "box_plot":
            breaks = box_plot_breaks(values)
        elif method == "maximum_breaks":
            breaks = maximum_breaks(values, n_classes)
        elif method == "pretty_breaks":
            breaks = pretty_breaks(values, n_classes)
        else:
            raise QgsProcessingException(f"Unknown method: {method}")

        feedback.pushInfo(f"Breaks: {[round(b, 4) for b in breaks]}")

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(QgsField(f.name(), f.type()))
        out_fields.append(QgsField("gic_class", QVariant.Int))
        out_fields.append(QgsField("gic_label", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs(),
        )

        labels = ["Very Low", "Low", "Medium", "High", "Very High"]
        total = len(features_raw)
        for current, feat in enumerate(features_raw):
            if feedback.isCanceled():
                break
            val = safe_float(feat[field_name], 0.0)
            class_idx = 0
            for i in range(len(breaks) - 1):
                if breaks[i] <= val <= breaks[i + 1]:
                    class_idx = i
                    break
            attrs = feat.attributes()[:]
            attrs.append(class_idx)
            label = labels[class_idx] if class_idx < len(labels) else f"Class {class_idx + 1}"
            attrs.append(label)

            new_feat = QgsFeature(out_fields)
            new_feat.setGeometry(feat.geometry())
            new_feat.setAttributes(attrs)
            sink.addFeature(new_feat, QgsFeatureSink.Flag.FastInsert)
            feedback.setProgress(int(100 * current / total))

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer:
                num_classes = max(1, len(breaks) - 1)
                colours = pal.get_palette(pal_name, num_classes)
                ranges = []
                for i in range(num_classes):
                    sym = QgsSymbol.defaultSymbol(out_layer.geometryType())
                    if sym:
                        col = colours[min(i, len(colours) - 1)]
                        sym.setColor(QColor(col))
                        sym.setOpacity(0.88)
                        label = f"{breaks[i]:.2f} – {breaks[i+1]:.2f}"
                        ranges.append(QgsRendererRange(breaks[i], breaks[i+1], sym, label))
                if ranges:
                    renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
                    renderer.setClassificationMethod(QgsClassificationCustom())
                    out_layer.setRenderer(renderer)
                    out_layer.triggerRepaint()

        return {self.OUTPUT: dest_id}
