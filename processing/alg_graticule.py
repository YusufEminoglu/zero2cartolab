# -*- coding: utf-8 -*-
"""Graticule / Reference Grid — Processing algorithm."""
from __future__ import annotations

from contextlib import suppress

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterColor, QgsProcessingParameterEnum,
    QgsProcessingParameterExtent, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsWkbTypes,
    QgsLineSymbol, QgsSingleSymbolRenderer,
)

from ..core.graticule import nice_interval, graticule_lines
from ._help_mixin import CartoLabHelpMixin


class GraticuleAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "grid.png"
    EXTENT = "EXTENT"
    X_INTERVAL = "X_INTERVAL"
    Y_INTERVAL = "Y_INTERVAL"
    LINE_STYLE = "LINE_STYLE"
    LINE_COLOR = "LINE_COLOR"
    LINE_WIDTH = "LINE_WIDTH"
    OUTPUT = "OUTPUT"

    STYLES = ["Solid Line", "Dashed Line", "Dotted Line", "Dash-Dot Line"]
    STYLE_MAP = ["solid", "dash", "dot", "dash dot"]

    def name(self) -> str:
        return "graticule_grid"

    def displayName(self) -> str:
        return "Graticule / Reference Grid"

    def group(self) -> str:
        return "Map Reference"

    def groupId(self) -> str:
        return "map_reference"

    def createInstance(self):
        return GraticuleAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Generate a line layer of meridians and parallels across an extent, on "
            "'nice' round coordinate intervals. Each line carries its orientation, "
            "constant coordinate and a formatted label (label it with the 'label' "
            "field).\n\n"
            "• Auto-picks nice rounded step intervals (~8 lines across extent) if left at 0.\n"
            "• Direct styling control: Solid, Dashed, Dotted, or Dash-Dot with custom color and line width.\n"
            "The output uses the extent's CRS — set the extent in the CRS you want the grid drawn in."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(self.EXTENT, "Grid extent"))
        self.addParameter(QgsProcessingParameterNumber(
            self.X_INTERVAL, "Vertical line (meridian) interval, 0 = auto",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.Y_INTERVAL, "Horizontal line (parallel) interval, 0 = auto",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterEnum(
            self.LINE_STYLE, "Grid line style", options=self.STYLES, defaultValue=1))
        self.addParameter(QgsProcessingParameterColor(
            self.LINE_COLOR, "Grid line color", defaultValue=QColor(160, 160, 160, 180)))
        self.addParameter(QgsProcessingParameterNumber(
            self.LINE_WIDTH, "Grid line width (mm)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.25, minValue=0.05, maxValue=5.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Graticule output", QgsProcessing.SourceType.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):
        rect = self.parameterAsExtent(parameters, self.EXTENT, context)
        crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        if rect.isEmpty():
            raise QgsProcessingException("The supplied extent is empty.")
        x_interval = self.parameterAsDouble(parameters, self.X_INTERVAL, context)
        y_interval = self.parameterAsDouble(parameters, self.Y_INTERVAL, context)
        style_idx = self.parameterAsEnum(parameters, self.LINE_STYLE, context) if self.LINE_STYLE in parameters else 1
        line_style = self.STYLE_MAP[style_idx] if 0 <= style_idx < len(self.STYLE_MAP) else "dash"
        line_color = self.parameterAsColor(parameters, self.LINE_COLOR, context) if self.LINE_COLOR in parameters else QColor(160, 160, 160, 180)
        line_width = self.parameterAsDouble(parameters, self.LINE_WIDTH, context) if self.LINE_WIDTH in parameters else 0.25

        xmin, ymin = rect.xMinimum(), rect.yMinimum()
        xmax, ymax = rect.xMaximum(), rect.yMaximum()
        x_step = x_interval if x_interval > 0 else nice_interval(xmax - xmin)
        y_step = y_interval if y_interval > 0 else nice_interval(ymax - ymin)

        out_fields = QgsFields()
        out_fields.append(QgsField("orientation", QVariant.String))
        out_fields.append(QgsField("coord", QVariant.Double))
        out_fields.append(QgsField("label", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Type.LineString, crs,
        )

        lines = graticule_lines(xmin, ymin, xmax, ymax, x_step, y_step)
        for ln in lines:
            if feedback.isCanceled():
                break
            pts = [QgsPointXY(x, y) for (x, y) in ln["points"]]
            nf = QgsFeature(out_fields)
            nf.setGeometry(QgsGeometry.fromPolylineXY(pts))
            nf.setAttributes([ln["orientation"], ln["coord"], ln["label"]])
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)

        feedback.pushInfo(
            f"Graticule: {len(lines)} lines (x step {x_step:g}, y step {y_step:g})."
        )

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer:
                c_str = f"{line_color.red()},{line_color.green()},{line_color.blue()},{line_color.alpha()}"
                symbol = QgsLineSymbol.createSimple({
                    "line_style": line_style,
                    "line_color": c_str,
                    "line_width": str(line_width),
                })
                out_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
                out_layer.triggerRepaint()

        return {self.OUTPUT: dest_id}
