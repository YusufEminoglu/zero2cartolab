# -*- coding: utf-8 -*-
"""Bivariate Choropleth — Processing algorithm."""
from __future__ import annotations

from qgis.core import (
    QgsFeature, QgsFeatureSink,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterColor,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..core.utils import safe_float
from ..core.bivariate_engine import bivariate_colour_matrix, class_index
from ._fields import extend_fields, output_attributes
from ._help_mixin import CartoLabHelpMixin
from ._styling import style_output


def apply_bivariate_renderer(layer, n_classes: int, color_ll: str, color_lh: str,
                             color_hl: str, color_hh: str) -> None:
    """Apply the bivariate NxN categorized style keyed on ``bivar_class``.

    Corner colours are named X class first: ``color_lh`` colours LOW X /
    HIGH Y features (``bivar_class`` "(0,n-1)"), ``color_hl`` HIGH X / LOW Y.
    """
    from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol

    matrix = bivariate_colour_matrix(n_classes, color_ll, color_lh, color_hl, color_hh)
    categories = []

    for r in range(n_classes):
        for c in range(n_classes):
            val = f"({c},{r})"
            color = matrix[r][c]

            # Human-readable labels:
            label_parts = [f"X:{c+1}, Y:{r+1}"]
            if r == 0 and c == 0:
                label_parts.append("(Low-Low)")
            elif r == 0 and c == n_classes - 1:
                label_parts.append("(High-Low)")
            elif r == n_classes - 1 and c == 0:
                label_parts.append("(Low-High)")
            elif r == n_classes - 1 and c == n_classes - 1:
                label_parts.append("(High-High)")
            label = " ".join(label_parts)

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            if symbol:
                symbol.setColor(color)
                # For polygon layers, use clean semi-transparent white outlines
                if layer.geometryType() == 2:
                    for idx in range(symbol.symbolLayerCount()):
                        sl = symbol.symbolLayer(idx)
                        if hasattr(sl, 'setStrokeColor'):
                            sl.setStrokeColor(QColor(255, 255, 255, 140))
                        if hasattr(sl, 'setStrokeWidth'):
                            sl.setStrokeWidth(0.2)

                cat = QgsRendererCategory(val, symbol, label)
                categories.append(cat)

    renderer = QgsCategorizedSymbolRenderer("bivar_class", categories)
    layer.setRenderer(renderer)


class BivariateChoroplethAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "bivariate.png"
    INPUT = "INPUT"
    FIELD_X = "FIELD_X"
    FIELD_Y = "FIELD_Y"
    CLASSES = "CLASSES"
    METHOD = "METHOD"
    COLOR_LL = "COLOR_LL"
    COLOR_LH = "COLOR_LH"
    COLOR_HL = "COLOR_HL"
    COLOR_HH = "COLOR_HH"
    OUTPUT = "OUTPUT"

    PALETTE_PRESET = "PALETTE_PRESET"

    METHODS = [
        ("Quantile (Equal Count - Recommended)", "quantile"),
        ("Geometric Interval", "geometric"),
        ("Fisher-Jenks Natural Breaks", "fisher_jenks"),
        ("Equal Interval", "equal"),
    ]

    PRESETS = [
        ("Teal - Brown (Environment & Resilience)", "teal_brown"),
        ("Stevens Pink - Cyan (Demographics & Social)", "stevens_pink_cyan"),
        ("Blue - Orange (Density & Economy)", "blue_orange"),
        ("Purple - Green (Land Use & Canopy)", "purple_green"),
        ("Night Neon (Dark Theme Visuals)", "night_neon"),
        ("Custom Corner Colours", "custom"),
    ]

    def name(self) -> str:
        return "bivariate_choropleth"

    def displayName(self) -> str:
        return "Bivariate Choropleth Map"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return BivariateChoroplethAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Creates a 2D Bivariate Choropleth thematic map classifying two numeric fields "
            "simultaneously into an NxN colour matrix (2x2, 3x3, or 4x4).\n\n"
            "Supports 5 curated cartographic palette presets (Stevens Pink-Cyan, Teal-Brown, "
            "Blue-Orange, Purple-Green, Night Neon) or custom corner colours.\n\n"
            "Outputs an automatically styled layer with high-quality translucent outlines "
            "and human-readable class descriptions (e.g. Low-Low, High-High)."
        )

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, "Input vector layer",
                [QgsProcessing.SourceType.TypeVectorPolygon, QgsProcessing.SourceType.TypeVectorPoint],
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_X, "Horizontal axis field (X)",
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.DataType.Numeric,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_Y, "Vertical axis field (Y)",
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.DataType.Numeric,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CLASSES, "Number of classes per axis (N x N)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=3, minValue=2, maxValue=4,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD, "Classification method",
                options=[m[0] for m in self.METHODS],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PALETTE_PRESET, "Colour Palette Preset",
                options=[p[0] for p in self.PRESETS],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.COLOR_LL, "Bottom-Left colour (Low X, Low Y) [if Custom]",
                defaultValue=QColor("#e8e8e8"),
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.COLOR_LH, "Top-Left colour (Low X, High Y) [if Custom]",
                defaultValue=QColor("#5ab4ac"),
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.COLOR_HL, "Bottom-Right colour (High X, Low Y) [if Custom]",
                defaultValue=QColor("#d8b365"),
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.COLOR_HH, "Top-Right colour (High X, High Y) [if Custom]",
                defaultValue=QColor("#8c510a"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, "Bivariate Layer",
            )
        )

    def processAlgorithm(self, parameters, context, feedback) -> dict:
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Invalid input layer.")

        field_x = self.parameterAsString(parameters, self.FIELD_X, context)
        field_y = self.parameterAsString(parameters, self.FIELD_Y, context)
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context)
        method_idx = self.parameterAsEnum(parameters, self.METHOD, context)
        method = self.METHODS[method_idx][1]
        preset_idx = self.parameterAsEnum(parameters, self.PALETTE_PRESET, context)
        preset_key = self.PRESETS[preset_idx][1]

        from ..core.bivariate_engine import BIVARIATE_PALETTE_PRESETS

        if preset_key != "custom" and preset_key in BIVARIATE_PALETTE_PRESETS:
            p_info = BIVARIATE_PALETTE_PRESETS[preset_key]
            color_ll = p_info["ll"]
            color_lh = p_info["lh"]
            color_hl = p_info["hl"]
            color_hh = p_info["hh"]
        else:
            c_ll = self.parameterAsColor(parameters, self.COLOR_LL, context)
            c_lh = self.parameterAsColor(parameters, self.COLOR_LH, context)
            c_hl = self.parameterAsColor(parameters, self.COLOR_HL, context)
            c_hh = self.parameterAsColor(parameters, self.COLOR_HH, context)

            color_ll = c_ll.name() if hasattr(c_ll, "name") else str(c_ll)
            color_lh = c_lh.name() if hasattr(c_lh, "name") else str(c_lh)
            color_hl = c_hl.name() if hasattr(c_hl, "name") else str(c_hl)
            color_hh = c_hh.name() if hasattr(c_hh, "name") else str(c_hh)

        # collect paired values; features missing either value are still
        # written, with NULL class fields, instead of vanishing from the output
        x_vals, y_vals = [], []
        features_raw = []
        for feat in source.getFeatures():
            fx = safe_float(feat[field_x])
            fy = safe_float(feat[field_y])
            if fx is not None and fy is not None:
                x_vals.append(fx)
                y_vals.append(fy)
            features_raw.append(feat)

        if not x_vals:
            raise QgsProcessingException("No valid paired numeric values found.")

        from ..core.quick_style import compute_breaks
        req_method = "jenks" if method == "fisher_jenks" else method
        x_breaks = compute_breaks(x_vals, method=req_method, n=n_classes)
        y_breaks = compute_breaks(y_vals, method=req_method, n=n_classes)

        feedback.pushInfo(
            f"X breaks ({field_x}): {[round(b, 4) for b in x_breaks]}\n"
            f"Y breaks ({field_y}): {[round(b, 4) for b in y_breaks]}"
        )

        # Build output schema with bivariate fields
        out_fields, out_idx = extend_fields(source.fields(), (
            ("bivar_x_class", QVariant.Int),
            ("bivar_y_class", QVariant.Int),
            ("bivar_class", QVariant.String),
        ))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, source.wkbType(), source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        n_null = len(features_raw) - len(x_vals)
        if n_null:
            feedback.pushInfo(f"{n_null} feature(s) missing an X or Y value keep NULL class fields.")

        total = len(features_raw) or 1
        for current, feat in enumerate(features_raw):
            if feedback.isCanceled():
                break
            fx = safe_float(feat[field_x])
            fy = safe_float(feat[field_y])
            if fx is None or fy is None:
                col_idx = row_idx = bivar = None
            else:
                col_idx = _break_index(fx, x_breaks)
                row_idx = _break_index(fy, y_breaks)
                bivar = f"({col_idx},{row_idx})"

            attrs = output_attributes(feat, out_fields, out_idx, {
                "bivar_x_class": col_idx, "bivar_y_class": row_idx, "bivar_class": bivar})

            new_feat = QgsFeature(out_fields)
            new_feat.setGeometry(feat.geometry())
            new_feat.setAttributes(attrs)
            sink.addFeature(new_feat, QgsFeatureSink.Flag.FastInsert)
            feedback.setProgress(int(100 * current / total))

        style_output(
            context, dest_id,
            lambda layer: apply_bivariate_renderer(layer, n_classes, color_ll, color_lh, color_hl, color_hh),
            feedback,
        )

        return {self.OUTPUT: dest_id}


def _break_index(value: float, breaks: list) -> int:
    """Class of ``value`` using the QGIS range convention (lo < v <= hi)."""
    if not breaks or len(breaks) < 2:
        return 0
    return class_index(value, breaks)
