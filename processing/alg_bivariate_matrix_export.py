# -*- coding: utf-8 -*-
"""
Export Bivariate 2D Legend Matrix — Processing algorithm.

Generates a standalone NxN (2x2, 3x3, 4x4) vector layer representing the
bivariate colour legend matrix in standard square or 45-degree diamond orientation,
with full attributes and automatic categorized styling.
"""
from __future__ import annotations

import math
from contextlib import suppress

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputHtml,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterColor,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsRendererCategory,
    QgsSymbol,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from ..core.bivariate_engine import (
    BIVARIATE_PALETTE_PRESETS,
    bivariate_colour_matrix,
)
from ._help_mixin import CartoLabHelpMixin


class BivariateMatrixExportAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "bivariate.png"
    CLASSES = "CLASSES"
    PALETTE_PRESET = "PALETTE_PRESET"
    COLOR_LL = "COLOR_LL"
    COLOR_LH = "COLOR_LH"
    COLOR_HL = "COLOR_HL"
    COLOR_HH = "COLOR_HH"
    DIAMOND = "DIAMOND"
    CELL_SIZE = "CELL_SIZE"
    ORIGIN_X = "ORIGIN_X"
    ORIGIN_Y = "ORIGIN_Y"
    LABEL_X = "LABEL_X"
    LABEL_Y = "LABEL_Y"
    OUTPUT = "OUTPUT"
    OUTPUT_HTML = "OUTPUT_HTML"

    PRESETS = [
        ("Teal - Brown (Environment & Resilience)", "teal_brown"),
        ("Stevens Pink - Cyan (Demographics & Social)", "stevens_pink_cyan"),
        ("Blue - Orange (Density & Economy)", "blue_orange"),
        ("Purple - Green (Land Use & Canopy)", "purple_green"),
        ("Night Neon (Dark Theme Visuals)", "night_neon"),
        ("Custom Corner Colours", "custom"),
    ]

    def name(self) -> str:
        return "bivariate_matrix_export"

    def displayName(self) -> str:
        return "Export Bivariate 2D Legend Matrix"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return BivariateMatrixExportAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Generate a standalone vector polygon layer and HTML preview of an NxN "
            "bivariate colour legend matrix (2x2, 3x3, or 4x4).\n\n"
            "• Supports standard square grid or 45-degree diamond cartographic layout.\n"
            "• Built-in curated palettes (Stevens Pink-Cyan, Teal-Brown, Blue-Orange, "
            "Purple-Green, Night Neon) or custom corner colours.\n"
            "• Each cell carries col, row, class code, label, and hex colour code.\n"
            "• Automatically styled with categorized renderer and crisp white borders."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CLASSES, "Number of classes per axis (N x N)",
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=3, minValue=2, maxValue=4,
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
            QgsProcessingParameterBoolean(
                self.DIAMOND, "Rotate 45 degrees (Diamond Legend)",
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CELL_SIZE, "Cell size (map units / mm)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=100.0, minValue=0.01,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ORIGIN_X, "Origin X coordinate (grid corner/center)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ORIGIN_Y, "Origin Y coordinate (grid corner/center)",
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.LABEL_X, "Horizontal axis variable name (X)",
                defaultValue="Variable X", optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.LABEL_Y, "Vertical axis variable name (Y)",
                defaultValue="Variable Y", optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT, "Bivariate Matrix Layer",
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )
        self.addOutput(
            QgsProcessingOutputHtml(self.OUTPUT_HTML, "HTML Legend Matrix Preview")
        )

    def processAlgorithm(self, parameters, context, feedback):
        n_classes = self.parameterAsInt(parameters, self.CLASSES, context)
        preset_idx = self.parameterAsEnum(parameters, self.PALETTE_PRESET, context)
        preset_key = self.PRESETS[preset_idx][1] if 0 <= preset_idx < len(self.PRESETS) else "teal_brown"
        diamond = self.parameterAsBool(parameters, self.DIAMOND, context)
        cell_size = self.parameterAsDouble(parameters, self.CELL_SIZE, context)
        origin_x = self.parameterAsDouble(parameters, self.ORIGIN_X, context)
        origin_y = self.parameterAsDouble(parameters, self.ORIGIN_Y, context)
        label_x = self.parameterAsString(parameters, self.LABEL_X, context) or "Variable X"
        label_y = self.parameterAsString(parameters, self.LABEL_Y, context) or "Variable Y"

        if preset_key != "custom" and preset_key in BIVARIATE_PALETTE_PRESETS:
            p_info = BIVARIATE_PALETTE_PRESETS[preset_key]
            c_ll = p_info["ll"]
            c_lh = p_info["lh"]
            c_hl = p_info["hl"]
            c_hh = p_info["hh"]
        else:
            q_ll = self.parameterAsColor(parameters, self.COLOR_LL, context)
            q_lh = self.parameterAsColor(parameters, self.COLOR_LH, context)
            q_hl = self.parameterAsColor(parameters, self.COLOR_HL, context)
            q_hh = self.parameterAsColor(parameters, self.COLOR_HH, context)
            c_ll = q_ll.name() if hasattr(q_ll, "name") else str(q_ll)
            c_lh = q_lh.name() if hasattr(q_lh, "name") else str(q_lh)
            c_hl = q_hl.name() if hasattr(q_hl, "name") else str(q_hl)
            c_hh = q_hh.name() if hasattr(q_hh, "name") else str(q_hh)

        matrix = bivariate_colour_matrix(n_classes, c_ll, c_lh, c_hl, c_hh)

        out_fields = QgsFields()
        out_fields.append(QgsField("col", QVariant.Int))
        out_fields.append(QgsField("row", QVariant.Int))
        out_fields.append(QgsField("bivar_class", QVariant.String))
        out_fields.append(QgsField("label", QVariant.String))
        out_fields.append(QgsField("hex_color", QVariant.String))
        out_fields.append(QgsField("x_label", QVariant.String))
        out_fields.append(QgsField("y_label", QVariant.String))

        # Output in project CRS or default 3857
        crs = context.project().crs() if context.project() else None

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Type.Polygon, crs,
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Center for optional 45-degree diamond rotation
        center_x = origin_x + (n_classes * cell_size) / 2.0
        center_y = origin_y + (n_classes * cell_size) / 2.0
        rot_angle = math.radians(45.0) if diamond else 0.0
        cos_a = math.cos(rot_angle)
        sin_a = math.sin(rot_angle)

        def _rotate(px: float, py: float) -> QgsPointXY:
            if not diamond:
                return QgsPointXY(px, py)
            dx, dy = px - center_x, py - center_y
            rx = center_x + dx * cos_a - dy * sin_a
            ry = center_y + dx * sin_a + dy * cos_a
            return QgsPointXY(rx, ry)

        def _tier_name(idx: int, total: int) -> str:
            if total == 2:
                return "Low" if idx == 0 else "High"
            if total == 3:
                return ["Low", "Medium", "High"][idx]
            return ["Low", "Mid-Low", "Mid-High", "High"][idx]

        categories = []
        total_cells = n_classes * n_classes

        # HTML Table builder
        html_rows = []

        for r in range(n_classes):
            html_cells = []
            for c in range(n_classes):
                col_color = matrix[r][c]
                hex_str = col_color.name()
                val = f"({c},{r})"

                x_desc = _tier_name(c, n_classes)
                y_desc = _tier_name(r, n_classes)

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
                label_str = " ".join(label_parts)

                # Cell polygon coordinates
                x0 = origin_x + c * cell_size
                y0 = origin_y + r * cell_size
                x1 = x0 + cell_size
                y1 = y0 + cell_size

                ring = [
                    _rotate(x0, y0),
                    _rotate(x1, y0),
                    _rotate(x1, y1),
                    _rotate(x0, y1),
                    _rotate(x0, y0),
                ]

                feat = QgsFeature(out_fields)
                feat.setGeometry(QgsGeometry.fromPolygonXY([ring]))
                feat.setAttributes([c, r, val, label_str, hex_str, f"{label_x}: {x_desc}", f"{label_y}: {y_desc}"])
                sink.addFeature(feat, QgsFeatureSink.Flag.FastInsert)

                # Category symbol for styling
                sym = QgsSymbol.defaultSymbol(QgsWkbTypes.GeometryType.Polygon)
                if sym:
                    sym.setColor(col_color)
                    with suppress(Exception):
                        for sl_idx in range(sym.symbolLayerCount()):
                            sl = sym.symbolLayer(sl_idx)
                            if hasattr(sl, "setStrokeColor"):
                                sl.setStrokeColor(QColor(255, 255, 255, 200))
                            if hasattr(sl, "setStrokeWidth"):
                                sl.setStrokeWidth(0.3)
                    categories.append(QgsRendererCategory(val, sym, label_str))

                html_cells.append(
                    f'<td style="background-color:{hex_str}; width:60px; height:60px; '
                    f'text-align:center; color:#ffffff; font-family:sans-serif; font-size:10px; '
                    f'font-weight:bold; text-shadow:0 1px 2px rgba(0,0,0,0.8); border:1px solid #ffffff;">'
                    f'{c+1},{r+1}</td>'
                )

            html_rows.insert(0, f'<tr><td style="font-weight:bold; padding-right:6px; font-size:11px; color:#333;">{_tier_name(r, n_classes)}</td>' + "".join(html_cells) + '</tr>')

        feedback.pushInfo(f"Emitted {total_cells} bivariate legend matrix cells (Diamond={diamond}).")

        # HTML Matrix preview
        html_table = (
            '<div style="padding:12px; font-family:sans-serif;">'
            f'<h3 style="margin-bottom:8px; color:#0f172a;">Bivariate Legend Matrix ({n_classes}x{n_classes})</h3>'
            f'<p style="margin-top:0; font-size:12px; color:#64748b;"><b>Y:</b> {label_y} &nbsp;|&nbsp; <b>X:</b> {label_x}</p>'
            '<table style="border-collapse:collapse; margin:12px 0;">'
            + "".join(html_rows)
            + '</table>'
            '</div>'
        )

        with suppress(Exception):
            out_layer = context.getMapLayer(dest_id)
            if out_layer:
                renderer = QgsCategorizedSymbolRenderer("bivar_class", categories)
                out_layer.setRenderer(renderer)
                out_layer.triggerRepaint()

        return {
            self.OUTPUT: dest_id,
            self.OUTPUT_HTML: html_table,
        }
