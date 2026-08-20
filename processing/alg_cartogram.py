# -*- coding: utf-8 -*-
"""Continuous-Area Cartogram — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.core import (
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingOutputNumber,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsFeature,
)
from qgis import processing

from ..core.cartogram_engine import CartogramEngine
from ._help_mixin import CartoLabHelpMixin


class CartogramAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "cartogram.png"
    INPUT = "INPUT"
    FIELD = "FIELD"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    MAX_ERROR = "MAX_ERROR"
    PALETTE = "PALETTE"
    ITERATIONS = "ITERATIONS"
    RESIDUAL_ERROR = "RESIDUAL_ERROR"
    OUTPUT = "OUTPUT"

    PALETTES_LIST = [
        "Plasma", "Viridis", "Inferno", "Magma", "Cividis",
        "Turbo", "Mako", "Rocket", "Blues", "Oranges", "YlOrRd", "Purples", "Greens"
    ]

    def name(self) -> str:
        return "compute_cartogram"

    def displayName(self) -> str:
        return "Continuous-Area Cartogram (Diffusion)"

    def group(self) -> str:
        return "Cartogram"

    def groupId(self) -> str:
        return "cartogram"

    def createInstance(self):
        return CartogramAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Distort polygon areas to be proportional to a numeric field "
            "using the diffusion method (Gastner & Newman).\n\n"
            "The algorithm iteratively displaces polygon boundaries until "
            "each region's area represents its field value. A zero-width "
            "buffer is applied to fix topology issues on exit.\n\n"
            "• Color ramp: Automatically styles the resulting distorted polygons.\n"
            "Requires at least 2 valid polygon features."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, "Input polygon layer",
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterField(self.FIELD, "Area-representation field",
                                         parentLayerParameterName=self.INPUT,
                                         type=QgsProcessingParameterField.DataType.Numeric)
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.MAX_ITERATIONS, "Max iterations",
                                          type=QgsProcessingParameterNumber.Type.Integer,
                                          defaultValue=30, minValue=1, maxValue=200)
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.MAX_ERROR, "Max average error (%)",
                                          type=QgsProcessingParameterNumber.Type.Double,
                                          defaultValue=5.0, minValue=0.1, maxValue=100.0)
        )
        self.addParameter(
            QgsProcessingParameterEnum(self.PALETTE, "Color ramp for cartogram styling",
                                       options=self.PALETTES_LIST, defaultValue=0)
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "Cartogram output")
        )
        self.addOutput(
            QgsProcessingOutputNumber(self.ITERATIONS, "Iterations run")
        )
        self.addOutput(
            QgsProcessingOutputNumber(self.RESIDUAL_ERROR, "Residual average error (%)")
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        field_name = self.parameterAsString(parameters, self.FIELD, context)
        max_iter = self.parameterAsInt(parameters, self.MAX_ITERATIONS, context)
        max_error = self.parameterAsDouble(parameters, self.MAX_ERROR, context)
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context) if self.PALETTE in parameters else 0
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "Plasma"

        feedback.pushInfo(f"Loading input layer with {source.featureCount()} features...")

        # fix geometry with zero-buffer
        feedback.pushInfo("Fixing geometries (zero-width buffer)...")
        buffered_result = processing.run(
            "native:buffer",
            {"INPUT": parameters[self.INPUT], "DISTANCE": 0.0, "OUTPUT": "memory:"},
            context=context, is_child_algorithm=True,
        )
        memory_layer = context.getMapLayer(buffered_result["OUTPUT"])

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            source.fields(), source.wkbType(), source.sourceCrs(),
        )

        # run cartogram engine
        engine = CartogramEngine(memory_layer, field_name, max_iter, max_error)
        iterations, avg_error = engine.run(feedback)

        engine.write_to_layer(memory_layer)

        # final zero-buffer to fix slithers
        feedback.pushInfo("Final cleanup (zero-width buffer)...")
        cleaned = processing.run(
            "native:buffer",
            {"INPUT": memory_layer, "DISTANCE": 0.0, "OUTPUT": "memory:"},
            context=context, is_child_algorithm=True,
        )
        cleaned_layer = context.getMapLayer(cleaned["OUTPUT"])

        for feat in cleaned_layer.getFeatures():
            sink.addFeature(feat, QgsFeatureSink.Flag.FastInsert)

        error_pct = (avg_error - 1.0) * 100.0
        feedback.pushInfo(
            f"Cartogram finished: {iterations} iterations, "
            f"residual error: {error_pct:.2f}%"
        )

        out_layer = context.getMapLayer(dest_id)
        if out_layer:
            with suppress(Exception):
                from ..core.publication_styler import auto_style_layer
                auto_style_layer(out_layer, style_type="cartogram", field_name=field_name, palette_name=pal_name)

        return {
            self.OUTPUT: dest_id,
            self.ITERATIONS: iterations,
            self.RESIDUAL_ERROR: error_pct,
        }

