# -*- coding: utf-8 -*-
"""Choropleth Normalization & Rates — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGraduatedSymbolRenderer,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber, QgsRendererRange, QgsSymbol,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..core import normalize as nm
from ..core import palettes as pal
from ._help_mixin import CartoLabHelpMixin


class NormalizeFieldAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "style.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    METHOD = "METHOD"
    DENOMINATOR = "DENOMINATOR"
    SCALE = "SCALE"
    PALETTE = "PALETTE"
    CLASSES = "CLASSES"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "normalize_field"

    def displayName(self) -> str:
        return "Choropleth Normalization & Rates"

    def group(self) -> str:
        return "Data Preparation"

    def groupId(self) -> str:
        return "data_preparation"

    def createInstance(self):
        return NormalizeFieldAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Turn a raw field into a map-ready value before choropleth "
            "classification. Mapping a raw count as colour is the classic error "
            "(it just redraws population); normalise first.\n\n"
            "  - Rate: numerator / denominator x scale (e.g. cases per 100k)\n"
            "  - Location Quotient (LQ): specialisation index relative to benchmark base\n"
            "  - Z-score / Robust z (median-MAD) / Robust IQR (median-IQR): standardise for comparison\n"
            "  - Min-max / Winsorized min-max: rescale to 0-1 with optional outlier clamping\n"
            "  - Percentile / Decile rank / Tukey Hinge: distribution position and box-plot binning\n"
            "  - Log / Sigmoid / Power (Box-Cox): tame heavy right tails and stabilize variance\n\n"
            "Writes 'norm_value' and 'norm_method' fields, and graduates the output layer automatically."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input layer", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD, "Value field (numerator)", parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD, "Method", options=[m[0] for m in nm.METHODS], defaultValue=0))
        self.addParameter(QgsProcessingParameterField(
            self.DENOMINATOR, "Denominator field (Rate / LQ only)",
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric, optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.SCALE, "Rate scale (e.g. 1000, 100000)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=1.0, minValue=1e-12))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Color ramp for output styling",
            options=pal.ordered_names(), defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CLASSES, "Number of classes for graduated style",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=5, minValue=2, maxValue=20))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Normalized output"))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        field_name = self.parameterAsString(parameters, self.FIELD, context)
        method_idx = self.parameterAsEnum(parameters, self.METHOD, context)
        method = nm.METHODS[method_idx][1] if 0 <= method_idx < len(nm.METHODS) else "rate"
        denom_field = self.parameterAsString(parameters, self.DENOMINATOR, context)
        scale = self.parameterAsDouble(parameters, self.SCALE, context)
        palette_names = pal.ordered_names()
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context) if self.PALETTE in parameters else 0
        pal_name = palette_names[pal_idx] if 0 <= pal_idx < len(palette_names) else "Viridis"
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context) if self.CLASSES in parameters else 5

        if method in ("rate", "lq") and not denom_field:
            raise QgsProcessingException(
                f"The {method.upper()} method needs a denominator field (e.g. total population / employment).")

        features_raw = list(source.getFeatures())
        numerators = [f[field_name] for f in features_raw]

        if method == "rate":
            denominators = [f[denom_field] for f in features_raw]
            norm = nm.rate(numerators, denominators, scale)
        elif method == "lq":
            denominators = [f[denom_field] for f in features_raw]
            norm = nm.location_quotient(numerators, denominators)
        elif method == "zscore":
            norm = nm.z_scores(numerators)
        elif method == "robust_z":
            norm = nm.robust_z(numerators)
        elif method == "robust_iqr":
            norm = nm.robust_iqr(numerators)
        elif method == "minmax":
            norm = nm.min_max(numerators)
        elif method == "winsorized":
            norm = nm.winsorized_min_max(numerators, lower_pct=5.0, upper_pct=95.0)
        elif method == "percentile":
            norm = nm.percentile_rank(numerators)
        elif method == "decile":
            norm = nm.decile_rank(numerators)
        elif method == "tukey_hinge":
            norm = nm.tukey_hinge_rank(numerators)
        elif method == "sigmoid":
            norm = nm.sigmoid_scale(numerators)
        elif method == "power":
            norm = nm.power_transform(numerators)
        elif method == "quantile_norm":
            norm = nm.quantile_normalize(numerators)
        elif method == "log":
            norm = nm.log_scale(numerators)
        else:
            raise QgsProcessingException(f"Unknown method: {method}")

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(QgsField(f.name(), f.type()))
        out_fields.append(QgsField("norm_value", QVariant.Double))
        out_fields.append(QgsField("norm_method", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs(),
        )

        valid_values = []
        total = len(features_raw) or 1
        for i, feat in enumerate(features_raw):
            if feedback.isCanceled():
                break
            val = norm[i]
            attrs = feat.attributes()[:]
            attrs.append(float(val) if val is not None else None)
            attrs.append(method)
            nf = QgsFeature(out_fields)
            nf.setGeometry(feat.geometry())
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
            if val is not None:
                valid_values.append(float(val))
            feedback.setProgress(int(100 * i / total))

        n_null = len(features_raw) - len(valid_values)
        feedback.pushInfo(
            f"Normalised {len(valid_values)} features via '{method}'. "
            f"{n_null} left null (missing / zero denominator)."
        )

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer and valid_values:
                _apply_graduated(out_layer, "norm_value", min(valid_values), max(valid_values), pal_name, n_classes)

        return {self.OUTPUT: dest_id}


def _apply_graduated(layer, field, vmin, vmax, pal_name="Viridis", n_classes=5):
    from qgis.core import QgsClassificationCustom
    colours = pal.get_palette(pal_name, n_classes)
    n = len(colours)
    span = (vmax - vmin) or 1.0
    ranges = []
    for i in range(n):
        lo = vmin + span * i / n
        hi = vmin + span * (i + 1) / n
        sym = QgsSymbol.defaultSymbol(layer.geometryType())
        if sym:
            sym.setColor(QColor(colours[i]))
            sym.setOpacity(0.9)
            ranges.append(QgsRendererRange(lo, hi, sym, f"{lo:.3f} – {hi:.3f}"))
    if ranges:
        renderer = QgsGraduatedSymbolRenderer(field, ranges)
        renderer.setClassificationMethod(QgsClassificationCustom())
        layer.setRenderer(renderer)
        layer.triggerRepaint()

