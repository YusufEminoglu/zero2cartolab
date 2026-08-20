# -*- coding: utf-8 -*-
"""Apply native QGIS 2.5D building styling."""
from __future__ import annotations

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorLayer,
)

from ..core.qgis_25d_style import (
    FLOOR_BAND_PALETTES,
    HEIGHT_MODE_FLOOR_COUNT,
    HEIGHT_MODE_HEIGHT,
    RENDER_MODE_FLOOR_BANDS,
    RENDER_MODE_NATIVE,
    STYLE_25D_PRESETS,
    Style25DConfig,
    apply_25d_renderer,
    preset_config,
)
from ._help_mixin import CartoLabHelpMixin


class Building25DStyleAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "isometric.png"
    INPUT = "INPUT"
    HEIGHT_FIELD = "HEIGHT_FIELD"
    HEIGHT_MODE = "HEIGHT_MODE"
    FLOOR_HEIGHT = "FLOOR_HEIGHT"
    RENDER_MODE = "RENDER_MODE"
    FLOOR_PALETTE = "FLOOR_PALETTE"
    MAX_FLOORS = "MAX_FLOORS"
    PRESET = "PRESET"
    ANGLE = "ANGLE"
    HEIGHT_SCALE = "HEIGHT_SCALE"
    MAX_HEIGHT = "MAX_HEIGHT"
    STEPPED = "STEPPED"
    STEP_HEIGHT = "STEP_HEIGHT"
    SHADOW_ENABLED = "SHADOW_ENABLED"
    SHADOW_SPREAD = "SHADOW_SPREAD"
    WALL_SHADING = "WALL_SHADING"
    SUMMARY = "SUMMARY"

    PRESET_KEYS = list(STYLE_25D_PRESETS.keys())
    FLOOR_PALETTE_KEYS = list(FLOOR_BAND_PALETTES.keys())
    HEIGHT_MODE_OPTIONS = [
        ("Height field is already in metres/map units", HEIGHT_MODE_HEIGHT),
        ("Floor count field (floors x floor height)", HEIGHT_MODE_FLOOR_COUNT),
    ]
    RENDER_MODE_OPTIONS = [
        ("Native 2.5D material", RENDER_MODE_NATIVE),
        ("Per-floor colour bands", RENDER_MODE_FLOOR_BANDS),
    ]

    def name(self) -> str:
        return "building_25d_style"

    def displayName(self) -> str:
        return "Apply 2.5D Building Style"

    def group(self) -> str:
        return "2.5D Styling"

    def groupId(self) -> str:
        return "25d_styling"

    def createInstance(self):
        return Building25DStyleAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Apply a polished native QGIS 2.5D renderer to a loaded polygon layer. "
            "The selected field can be a real height or a floor-count field. CartoLab controls "
            "the roof colour, wall colour, shadow, viewing angle, optional height "
            "clamp, optional stepped extrusion, and sample-QML-style per-floor colour bands."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, "Polygon layer", [QgsProcessing.SourceType.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.HEIGHT_FIELD,
            "Height field",
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.DataType.Numeric,
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.HEIGHT_MODE,
            "Height source",
            options=[m[0] for m in self.HEIGHT_MODE_OPTIONS],
            defaultValue=0,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.FLOOR_HEIGHT,
            "Floor height, used only when height source is floor count",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=3.5,
            minValue=0.01,
            maxValue=100.0,
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.RENDER_MODE,
            "Renderer style",
            options=[m[0] for m in self.RENDER_MODE_OPTIONS],
            defaultValue=0,
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.FLOOR_PALETTE,
            "Floor colour palette, used by per-floor bands",
            options=[FLOOR_BAND_PALETTES[k]["label"] for k in self.FLOOR_PALETTE_KEYS],
            defaultValue=0,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_FLOORS,
            "Maximum floor bands, 0 scans the layer automatically",
            type=QgsProcessingParameterNumber.Type.Integer,
            defaultValue=0,
            minValue=0,
            maxValue=80,
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.PRESET,
            "Visual preset",
            options=[STYLE_25D_PRESETS[k]["label"] for k in self.PRESET_KEYS],
            defaultValue=0,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.ANGLE,
            "Projection angle in degrees",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=110.0,
            minValue=0.0,
            maxValue=359.0,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.HEIGHT_SCALE,
            "Height scale multiplier",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=1.0,
            minValue=0.01,
            maxValue=100.0,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_HEIGHT,
            "Maximum rendered height, 0 for no clamp",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=0.0,
            minValue=0.0,
            maxValue=1000000.0,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.STEPPED,
            "Snap heights to stepped floors",
            defaultValue=False,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.STEP_HEIGHT,
            "Step height in map units",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=3.5,
            minValue=0.01,
            maxValue=100000.0,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SHADOW_ENABLED,
            "Enable soft shadow",
            defaultValue=True,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.SHADOW_SPREAD,
            "Shadow spread in map units",
            type=QgsProcessingParameterNumber.Type.Double,
            defaultValue=3.5,
            minValue=0.0,
            maxValue=100000.0,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WALL_SHADING,
            "Enable directional wall shading",
            defaultValue=True,
        ))
        self.addOutput(QgsProcessingOutputString(self.SUMMARY, "Style summary"))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        height_field = self.parameterAsString(parameters, self.HEIGHT_FIELD, context)
        mode_idx = self.parameterAsEnum(parameters, self.HEIGHT_MODE, context)
        height_mode = self.HEIGHT_MODE_OPTIONS[mode_idx][1] if 0 <= mode_idx < len(self.HEIGHT_MODE_OPTIONS) else HEIGHT_MODE_HEIGHT
        render_idx = self.parameterAsEnum(parameters, self.RENDER_MODE, context)
        render_mode = self.RENDER_MODE_OPTIONS[render_idx][1] if 0 <= render_idx < len(self.RENDER_MODE_OPTIONS) else RENDER_MODE_NATIVE
        palette_idx = self.parameterAsEnum(parameters, self.FLOOR_PALETTE, context)
        floor_palette = self.FLOOR_PALETTE_KEYS[palette_idx] if 0 <= palette_idx < len(self.FLOOR_PALETTE_KEYS) else "civic_spectrum"
        preset_idx = self.parameterAsEnum(parameters, self.PRESET, context)
        preset_key = self.PRESET_KEYS[preset_idx] if 0 <= preset_idx < len(self.PRESET_KEYS) else "warm_civic"

        base = preset_config(height_field, preset_key)
        config = Style25DConfig(
            height_field=height_field,
            preset=preset_key,
            roof_color=base.roof_color,
            wall_color=base.wall_color,
            shadow_color=base.shadow_color,
            angle=self.parameterAsDouble(parameters, self.ANGLE, context),
            height_scale=self.parameterAsDouble(parameters, self.HEIGHT_SCALE, context),
            max_height=self.parameterAsDouble(parameters, self.MAX_HEIGHT, context),
            stepped=self.parameterAsBool(parameters, self.STEPPED, context),
            step_height=self.parameterAsDouble(parameters, self.STEP_HEIGHT, context),
            shadow_enabled=self.parameterAsBool(parameters, self.SHADOW_ENABLED, context),
            shadow_spread=self.parameterAsDouble(parameters, self.SHADOW_SPREAD, context),
            wall_shading=self.parameterAsBool(parameters, self.WALL_SHADING, context),
            height_mode=height_mode,
            floor_height=self.parameterAsDouble(parameters, self.FLOOR_HEIGHT, context),
            render_mode=render_mode,
            floor_palette=floor_palette,
            max_floors=self.parameterAsInt(parameters, self.MAX_FLOORS, context),
        )

        try:
            summary = apply_25d_renderer(layer, config)
        except Exception as exc:
            raise QgsProcessingException(str(exc))

        feedback.pushInfo(summary)
        return {self.SUMMARY: summary}
