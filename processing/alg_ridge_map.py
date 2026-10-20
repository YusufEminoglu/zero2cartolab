# -*- coding: utf-8 -*-
"""Ridge Map (Joyplot) — Processing algorithm."""
from __future__ import annotations


from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterColor,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsRasterLayer,
    QgsLineSymbol,
    QgsSingleSymbolRenderer,
)

from ..core.style_transformer import generate_ridge_lines
from ._help_mixin import CartoLabHelpMixin
from ._styling import style_output


class RidgeMapAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "ridge.png"
    RASTER = "RASTER"
    N_LINES = "N_LINES"
    VERTICAL_SCALE = "VERTICAL_SCALE"
    LINE_SPACING = "LINE_SPACING"
    SMOOTH = "SMOOTH"
    EXTENT = "EXTENT"
    LINE_COLOR = "LINE_COLOR"
    LINE_WIDTH = "LINE_WIDTH"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "ridge_map"

    def displayName(self) -> str:
        return "Ridge Map (Joy Division Style)"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return RidgeMapAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Generate a ridge-line (joy division style) vector layer from a "
            "single-band raster. The raster values deform scanlines vertically, "
            "producing overlapping wave profiles.\n\n"
            "• Vertical exaggeration & Line spacing: Control wave crest height and frequency.\n"
            "• Line color & width: Configured directly for publication rendering.\n"
            "Best raster inputs: DEM elevation, population density surfaces, LST, urban heat index.\n\n"
            "The input raster must use a projected CRS: the vertical exaggeration multiplies "
            "the raw raster value and adds it to the scanline position, so in a geographic "
            "CRS (degrees) a 100 m elevation would move the ridge thousands of degrees. "
            "Reproject the raster first (Vector ▸ Raster Tools ▸ Reproject)."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.RASTER, "Input raster (single-band)")
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.N_LINES, "Number of scanlines",
                                          type=QgsProcessingParameterNumber.Type.Integer,
                                          defaultValue=60, minValue=5, maxValue=500)
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.VERTICAL_SCALE, "Vertical exaggeration",
                                          type=QgsProcessingParameterNumber.Type.Double,
                                          defaultValue=1.0, minValue=0.01, maxValue=100.0)
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.LINE_SPACING, "Line spacing (map units)",
                                          type=QgsProcessingParameterNumber.Type.Double,
                                          defaultValue=1.0, minValue=0.0)
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.SMOOTH, "Smoothing passes (0 = raw)",
                                          type=QgsProcessingParameterNumber.Type.Integer,
                                          defaultValue=2, minValue=0, maxValue=20)
        )
        self.addParameter(
            QgsProcessingParameterExtent(self.EXTENT, "Clip extent (optional = raster extent)",
                                          optional=True)
        )
        self.addParameter(
            QgsProcessingParameterColor(self.LINE_COLOR, "Ridge line color",
                                        defaultValue=QColor(255, 255, 255, 240))
        )
        self.addParameter(
            QgsProcessingParameterNumber(self.LINE_WIDTH, "Ridge line width (mm)",
                                         type=QgsProcessingParameterNumber.Type.Double,
                                         defaultValue=0.35, minValue=0.05, maxValue=5.0)
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, "Ridge lines output")
        )

    def processAlgorithm(self, parameters, context, feedback):
        raster: QgsRasterLayer = self.parameterAsRasterLayer(parameters, self.RASTER, context)
        if raster is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.RASTER))

        # The vertical exaggeration multiplies the raw raster value and adds it
        # to the scanline position. In a geographic CRS the unit is the degree,
        # so a 100 m elevation would displace the ridge thousands of degrees
        # and the output would collapse into an unreadable line. Require a
        # projected CRS, exactly like the cartogram engine does.
        if raster.crs().isGeographic():
            raise QgsProcessingException(
                "The ridge map engine displaces the scanlines by the raw raster value, "
                "so the raster must use a projected CRS (metres or feet). In a geographic "
                "CRS (degrees) the displacement would be meaningless and the ridges "
                "would collapse into a single line. Reproject the raster first "
                "(Raster ▸ Reproject) and run the algorithm again."
            )

        n_lines = self.parameterAsInt(parameters, self.N_LINES, context)
        v_scale = self.parameterAsDouble(parameters, self.VERTICAL_SCALE, context)
        spacing = self.parameterAsDouble(parameters, self.LINE_SPACING, context)
        smooth = self.parameterAsInt(parameters, self.SMOOTH, context)
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        line_color = self.parameterAsColor(parameters, self.LINE_COLOR, context) if self.LINE_COLOR in parameters else QColor(255, 255, 255, 240)
        line_width = self.parameterAsDouble(parameters, self.LINE_WIDTH, context) if self.LINE_WIDTH in parameters else 0.35

        feedback.pushInfo(f"Generating {n_lines} ridge lines from {raster.name()}...")

        ridge_layer = generate_ridge_lines(
            raster, n_lines, v_scale, spacing, smooth, extent,
        )

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            ridge_layer.fields(), ridge_layer.wkbType(), ridge_layer.sourceCrs(),
        )

        total = ridge_layer.featureCount() or 1
        for current, feat in enumerate(ridge_layer.getFeatures()):
            if feedback.isCanceled():
                break
            sink.addFeature(feat, QgsFeatureSink.Flag.FastInsert)
            feedback.setProgress(int(100 * current / total))

        feedback.pushInfo(f"Ridge map ready: {total} scanlines.")

        def _style(out_layer):
            c_str = f"{line_color.red()},{line_color.green()},{line_color.blue()},{line_color.alpha()}"
            symbol = QgsLineSymbol.createSimple({
                "line_style": "solid",
                "line_color": c_str,
                "line_width": str(line_width),
            })
            out_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            out_layer.triggerRepaint()

        style_output(context, dest_id, _style, feedback)

        return {self.OUTPUT: dest_id}
