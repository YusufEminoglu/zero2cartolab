# -*- coding: utf-8 -*-
"""Native QGIS 2.5D styling helpers for 0202CartoLab."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import re
from typing import Dict, Optional


POLYGON_GEOMETRY = 2
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
HEIGHT_MODE_HEIGHT = "height"
HEIGHT_MODE_FLOOR_COUNT = "floor_count"
HEIGHT_MODES = (HEIGHT_MODE_HEIGHT, HEIGHT_MODE_FLOOR_COUNT)
RENDER_MODE_NATIVE = "native"
RENDER_MODE_FLOOR_BANDS = "floor_bands"
RENDER_MODES = (RENDER_MODE_NATIVE, RENDER_MODE_FLOOR_BANDS)
FLOOR_FIELD_TOKENS = ("kat", "floor", "storey", "story", "level")
AUTO_MAX_FLOORS = 0
DEFAULT_MAX_FLOORS = 16
MAX_FLOOR_BANDS = 80


STYLE_25D_PRESETS: Dict[str, dict] = {
    "warm_civic": {
        "label": "Warm Civic",
        "roof": "#f2cf96",
        "wall": "#b36f43",
        "shadow": "#202833",
        "shadow_spread": 3.5,
    },
    "cool_slate": {
        "label": "Cool Slate",
        "roof": "#d7e4e8",
        "wall": "#607d8b",
        "shadow": "#14242b",
        "shadow_spread": 4.0,
    },
    "limestone_teal": {
        "label": "Limestone and Teal",
        "roof": "#eadfc8",
        "wall": "#4f8f8a",
        "shadow": "#1f2933",
        "shadow_spread": 3.0,
    },
    "night_copper": {
        "label": "Night Copper",
        "roof": "#d89b6a",
        "wall": "#6f4a58",
        "shadow": "#090d16",
        "shadow_spread": 5.0,
    },
    "urban_gold": {
        "label": "Urban Core Gold",
        "roof": "#d4af37",
        "wall": "#1a1a24",
        "shadow": "#0d1b2a",
        "shadow_spread": 4.5,
    },
    "suburban_pastoral": {
        "label": "Suburban Pastoral",
        "roof": "#c06c84",
        "wall": "#f8b195",
        "shadow": "#355c7d",
        "shadow_spread": 3.0,
    },
    "cyberpunk_night": {
        "label": "Cyberpunk Night",
        "roof": "#00f5d4",
        "wall": "#7b2cbf",
        "shadow": "#ff007f",
        "shadow_spread": 6.0,
    },
    "nordic_minimalist": {
        "label": "Nordic Minimalist",
        "roof": "#f8f9fa",
        "wall": "#6c757d",
        "shadow": "#212529",
        "shadow_spread": 3.5,
    },
    "emerald_metropolis": {
        "label": "Emerald Metropolis",
        "roof": "#52b788",
        "wall": "#1b4332",
        "shadow": "#081c15",
        "shadow_spread": 4.0,
    },
    "terracotta_mediterranean": {
        "label": "Terracotta Mediterranean",
        "roof": "#f4a261",
        "wall": "#b34233",
        "shadow": "#4a121a",
        "shadow_spread": 3.5,
    },
}


def estimate_building_height(floor_count: float, default_floor_height: float = 3.2) -> float:
    """Calculate building height in map units from floor count."""
    return max(0.0, float(floor_count)) * max(0.1, float(default_floor_height))


FLOOR_BAND_PALETTES: Dict[str, dict] = {
    "civic_spectrum": {
        "label": "Civic Spectrum",
        "colors": (
            "#f4d35e", "#ee964b", "#f95738", "#d7263d",
            "#9b5de5", "#00bbf9", "#00f5d4", "#80ed99",
            "#ffd166", "#06d6a0", "#118ab2", "#ef476f",
            "#f4a261", "#2a9d8f", "#e76f51", "#457b9d",
        ),
    },
    "planning_bands": {
        "label": "Planning Bands",
        "colors": (
            "#f2cc8f", "#e07a5f", "#81b29a", "#3d405b",
            "#8ecae6", "#219ebc", "#ffb703", "#fb8500",
            "#a7c957", "#6a994e", "#bc4749", "#9d4edd",
            "#4cc9f0", "#4895ef", "#4361ee", "#3a0ca3",
        ),
    },
    "soft_atlas": {
        "label": "Soft Atlas",
        "colors": (
            "#b8e0d2", "#95b8d1", "#809bce", "#b8b8ff",
            "#ffc8dd", "#ffafcc", "#ffd6a5", "#fdffb6",
            "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff",
            "#d8e2dc", "#ffe5d9", "#ffcad4", "#f4acb7",
        ),
    },
    "turbo_height": {
        "label": "Turbo Height Spectrum",
        "colors": (
            "#30123b", "#4662d8", "#35abf8", "#1ae4b6",
            "#72fe5e", "#c8ef34", "#faba39", "#f66c19",
            "#cb2a04", "#7a0403", "#5c015b", "#2a0845",
            "#00b4d8", "#0077b6", "#023e8a", "#03045e",
        ),
    },
    "viridis_height": {
        "label": "Viridis Height Spectrum",
        "colors": (
            "#440154", "#482878", "#3e4989", "#31688e",
            "#26828e", "#1f9e89", "#35b779", "#6ece58",
            "#b5de2b", "#fde725", "#80ed99", "#38b000",
            "#007200", "#004b23", "#132a13", "#001a00",
        ),
    },
}


@dataclass(frozen=True)
class Style25DConfig:
    """Serializable configuration for one 02CartoLab 2.5D renderer."""

    height_field: str
    preset: str = "warm_civic"
    roof_color: str = "#f2cf96"
    wall_color: str = "#b36f43"
    shadow_color: str = "#202833"
    angle: float = 110.0
    height_scale: float = 1.0
    max_height: float = 0.0
    stepped: bool = False
    step_height: float = 3.5
    shadow_enabled: bool = True
    shadow_spread: float = 3.5
    wall_shading: bool = True
    height_mode: str = HEIGHT_MODE_HEIGHT
    floor_height: float = 3.5
    render_mode: str = RENDER_MODE_NATIVE
    floor_palette: str = "civic_spectrum"
    max_floors: int = DEFAULT_MAX_FLOORS


def preset_config(height_field: str, preset_key: str = "warm_civic") -> Style25DConfig:
    preset = STYLE_25D_PRESETS.get(preset_key, STYLE_25D_PRESETS["warm_civic"])
    return Style25DConfig(
        height_field=height_field,
        preset=preset_key if preset_key in STYLE_25D_PRESETS else "warm_civic",
        roof_color=preset["roof"],
        wall_color=preset["wall"],
        shadow_color=preset["shadow"],
        shadow_spread=float(preset["shadow_spread"]),
    )


def normalise_hex_color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if HEX_COLOR_RE.match(value):
        return value.lower()
    return fallback.lower()


def _hex_rgb(value: str) -> tuple[int, int, int]:
    color = normalise_hex_color(value, "#000000").lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def hex_to_rgba(value: str, alpha: int = 255) -> str:
    r, g, b = _hex_rgb(value)
    a = max(0, min(255, int(alpha)))
    return f"{r},{g},{b},{a}"


def adjust_hex_color(value: str, factor: float) -> str:
    r, g, b = _hex_rgb(value)
    factor = max(0.0, float(factor))
    rr = max(0, min(255, int(round(r * factor))))
    gg = max(0, min(255, int(round(g * factor))))
    bb = max(0, min(255, int(round(b * factor))))
    return f"#{rr:02x}{gg:02x}{bb:02x}"


def quote_field_name(field_name: str) -> str:
    if not field_name or not field_name.strip():
        raise ValueError("A height field is required.")
    return '"' + field_name.replace('"', '""') + '"'


def looks_like_floor_count_field(field_name: str) -> bool:
    clean = (field_name or "").strip().lower().replace(" ", "_")
    return any(token in clean for token in FLOOR_FIELD_TOKENS)


def format_number(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def floor_band_height(config: Style25DConfig) -> float:
    return max(float(config.floor_height), 0.01) * max(float(config.height_scale), 0.01)


def is_auto_max_floors(config: Style25DConfig) -> bool:
    return int(round(float(config.max_floors))) <= AUTO_MAX_FLOORS


def sanitised_max_floors(config: Style25DConfig) -> int:
    if is_auto_max_floors(config):
        return DEFAULT_MAX_FLOORS
    return max(1, min(MAX_FLOOR_BANDS, int(round(float(config.max_floors)))))


def normalise_floor_count_value(value) -> int:
    if value is None:
        return 0
    try:
        floor_count = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, floor_count)


def estimate_layer_max_floor_count(layer, field_name: str) -> int:
    """Scan a QGIS layer and return a safe maximum floor-band count."""
    if layer is None:
        return DEFAULT_MAX_FLOORS
    fields = layer.fields()
    idx = fields.lookupField(field_name) if hasattr(fields, "lookupField") else fields.indexOf(field_name)
    if idx < 0:
        return DEFAULT_MAX_FLOORS

    from qgis.core import QgsFeatureRequest

    max_floor = 0
    request = QgsFeatureRequest()
    if hasattr(request, "setSubsetOfAttributes"):
        request.setSubsetOfAttributes([field_name], fields)
    for feature in layer.getFeatures(request):
        max_floor = max(max_floor, normalise_floor_count_value(feature.attribute(idx)))
    if max_floor <= 0:
        return DEFAULT_MAX_FLOORS
    return max(1, min(MAX_FLOOR_BANDS, max_floor))


def resolve_max_floors(layer, config: Style25DConfig) -> int:
    if is_auto_max_floors(config):
        return estimate_layer_max_floor_count(layer, config.height_field)
    return sanitised_max_floors(config)


def floor_band_color(floor_index: int, palette_key: str, wall: bool = False) -> str:
    palette = FLOOR_BAND_PALETTES.get(palette_key, FLOOR_BAND_PALETTES["civic_spectrum"])
    colors = palette["colors"]
    color = colors[(max(1, int(floor_index)) - 1) % len(colors)]
    return adjust_hex_color(color, 0.76) if wall else normalise_hex_color(color, "#f4d35e")


def build_floor_band_legend_label(config: Style25DConfig, floor_index: int, max_floors: int) -> str:
    floor_index = max(1, int(floor_index))
    max_floor = max(1, int(max_floors))
    label = f"Floor {floor_index}"
    if floor_index >= max_floor:
        label += "+"
    top_height = format_number(floor_index * floor_band_height(config))
    return f"{label} ({top_height} units)"


def build_height_expression(config: Style25DConfig) -> str:
    """Build the expression evaluated by QGIS as @qgis_25d_height."""
    field_expr = f"coalesce(to_real({quote_field_name(config.height_field)}), 0)"
    scale_parts = []
    if config.height_mode == HEIGHT_MODE_FLOOR_COUNT:
        scale_parts.append(max(float(config.floor_height), 0.01))
    scale_parts.append(max(float(config.height_scale), 0.01))

    expr = field_expr
    for factor in scale_parts:
        expr = f"({expr}) * {format_number(factor)}"

    if config.stepped:
        step = max(float(config.step_height), 0.01)
        expr = f"round(({expr}) / {format_number(step)}) * {format_number(step)}"

    expr = f"(CASE WHEN ({expr}) < 0 THEN 0 ELSE ({expr}) END)"
    if config.max_height and config.max_height > 0:
        max_height = format_number(config.max_height)
        expr = f"(CASE WHEN ({expr}) > {max_height} THEN {max_height} ELSE ({expr}) END)"
    return expr


def build_floor_count_expression(config: Style25DConfig) -> str:
    """Build a non-negative integer floor-count expression."""
    field_expr = f"coalesce(to_int(round(to_real({quote_field_name(config.height_field)}))), 0)"
    return f"(CASE WHEN ({field_expr}) < 0 THEN 0 ELSE ({field_expr}) END)"


def build_order_by_expression(angle_variable: str = "@qgis_25d_angle", geometry_variable: str = "@geometry") -> str:
    return (
        f"distance({geometry_variable}, translate(@map_extent_center, "
        f"1000 * @map_extent_width * cos(radians({angle_variable} + 180)), "
        f"1000 * @map_extent_width * sin(radians({angle_variable} + 180))))"
    )


def build_floor_band_roof_expression(config: Style25DConfig, floor_index: int, max_floors: Optional[int] = None) -> str:
    floor_index = max(1, int(floor_index))
    max_floor = sanitised_max_floors(config) if max_floors is None else max(1, int(max_floors))
    floor_count = build_floor_count_expression(config)
    band_top = format_number(floor_index * floor_band_height(config))
    angle = "eval(@qgis_25d_angle)"
    if floor_index >= max_floor:
        condition = f"({floor_count}) >= {floor_index}"
    else:
        condition = f"({floor_count}) = {floor_index}"
    return (
        f"CASE WHEN {condition} THEN "
        f"translate($geometry, cos(radians({angle})) * {band_top}, "
        f"sin(radians({angle})) * {band_top}) END"
    )


def build_floor_band_wall_expression(config: Style25DConfig, floor_index: int) -> str:
    floor_index = max(1, int(floor_index))
    floor_count = build_floor_count_expression(config)
    band = floor_band_height(config)
    band_bottom = format_number((floor_index - 1) * band)
    band_height = format_number(band)
    angle = "eval(@qgis_25d_angle)"
    order_expr = build_order_by_expression("@qgis_25d_angle", "$geometry").replace("'", "''")
    return (
        f"CASE WHEN ({floor_count}) >= {floor_index} THEN "
        "order_parts("
        "extrude("
        f"segments_to_lines(translate($geometry, cos(radians({angle})) * {band_bottom}, "
        f"sin(radians({angle})) * {band_bottom})), "
        f"cos(radians({angle})) * {band_height}, "
        f"sin(radians({angle})) * {band_height}"
        "), "
        f"'{order_expr}', false"
        ") END"
    )


def build_floor_band_shadow_expression(config: Style25DConfig) -> str:
    height_expr = build_height_expression(config)
    spread = format_number(max(float(config.shadow_spread), 0.0))
    angle = "eval(@qgis_25d_angle)"
    return (
        "translate($geometry, "
        f"cos(radians({angle})) * (({height_expr}) + {spread}), "
        f"sin(radians({angle})) * (({height_expr}) + {spread}))"
    )


def build_wall_shading_expression() -> str:
    return (
        "set_color_part(@symbol_color, 'value', "
        "40 + 19 * abs($pi - azimuth("
        "point_n(geometry_n($geometry, @geometry_part_num), 1), "
        "point_n(geometry_n($geometry, @geometry_part_num), 2))))"
    )


def build_style_summary(layer_name: str, config: Style25DConfig, resolved_max_floors: Optional[int] = None) -> str:
    preset_label = STYLE_25D_PRESETS.get(config.preset, {}).get("label", config.preset)
    mode_label = "floor count" if config.height_mode == HEIGHT_MODE_FLOOR_COUNT else "height"
    render_label = "per-floor colour bands" if config.render_mode == RENDER_MODE_FLOOR_BANDS else "native 2.5D"
    palette_label = FLOOR_BAND_PALETTES.get(config.floor_palette, FLOOR_BAND_PALETTES["civic_spectrum"])["label"]
    lines = [
        "0202CartoLab 2.5D style applied",
        f"Layer: {layer_name}",
        f"Height field: {config.height_field}",
        f"Height source: {mode_label}",
        f"Renderer: {render_label}",
        f"Height expression: {build_height_expression(config)}",
        f"Preset: {preset_label}",
        f"Angle: {format_number(config.angle)} degrees",
        f"Roof color: {config.roof_color}",
        f"Wall color: {config.wall_color}",
        f"Shadow: {'enabled' if config.shadow_enabled else 'disabled'}",
    ]
    if config.height_mode == HEIGHT_MODE_FLOOR_COUNT:
        lines.append(f"Floor height: {format_number(config.floor_height)} map units")
    if config.render_mode == RENDER_MODE_FLOOR_BANDS:
        lines.append(f"Floor palette: {palette_label}")
        if is_auto_max_floors(config):
            if resolved_max_floors:
                lines.append(f"Maximum floor bands: auto ({int(resolved_max_floors)} resolved)")
            else:
                lines.append("Maximum floor bands: auto from layer")
        else:
            lines.append(f"Maximum floor bands: {sanitised_max_floors(config)}")
        lines.append("Legend: one rule per floor band")
    if config.height_scale != 1.0:
        lines.append(f"Vertical scale: {format_number(config.height_scale)}x")
    if config.stepped:
        lines.append(f"Stepped extrusion: {format_number(config.step_height)} map units")
    if config.max_height and config.max_height > 0:
        lines.append(f"Maximum height clamp: {format_number(config.max_height)} map units")
    return "\n".join(lines)


def field_is_numeric(field) -> bool:
    if hasattr(field, "isNumeric"):
        with suppress(Exception):
            return bool(field.isNumeric())
    type_name = ""
    if hasattr(field, "typeName"):
        try:
            type_name = str(field.typeName()).lower()
        except Exception:
            type_name = ""
    return any(token in type_name for token in ("int", "real", "double", "float", "decimal", "numeric"))


def _make_fill_symbol(fill_color: str, outline_color: str, outline_width: float = 0.2, wall_shading: bool = False):
    from qgis.core import QgsFillSymbol, QgsProperty, QgsSymbolLayer

    symbol = QgsFillSymbol.createSimple({
        "color": fill_color,
        "outline_color": outline_color,
        "outline_style": "solid",
        "outline_width": format_number(outline_width),
        "outline_width_unit": "MM",
        "joinstyle": "bevel",
    })
    if wall_shading and symbol and symbol.symbolLayerCount():
        symbol.symbolLayer(0).setDataDefinedProperty(
            QgsSymbolLayer.Property.FillColor,
            QgsProperty.fromExpression(build_wall_shading_expression()),
        )
    return symbol


def _make_geometry_generator_layer(expression: str, fill_symbol, rendering_pass: int):
    from qgis.core import QgsGeometryGeneratorSymbolLayer

    layer = QgsGeometryGeneratorSymbolLayer.create({
        "geometryModifier": expression,
        "SymbolType": "Fill",
        "units": "MapUnit",
    })
    if layer is None:
        raise RuntimeError("QGIS could not create the floor-band geometry generator symbol layer.")
    layer.setSubSymbol(fill_symbol)
    layer.setRenderingPass(int(rendering_pass))
    return layer


def _empty_fill_symbol():
    from qgis.core import QgsFillSymbol

    symbol = QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_style": "no"})
    while symbol.symbolLayerCount():
        symbol.deleteSymbolLayer(0)
    return symbol


def _set_layer_25d_properties(layer, config: Style25DConfig) -> None:
    from qgis.core import QgsExpressionContextUtils

    QgsExpressionContextUtils.setLayerVariable(layer, "qgis_25d_angle", format_number(config.angle))
    QgsExpressionContextUtils.setLayerVariable(layer, "qgis_25d_height", build_height_expression(config))
    QgsExpressionContextUtils.setLayerVariable(layer, "zero2cartolab_25d_preset", config.preset)
    QgsExpressionContextUtils.setLayerVariable(layer, "zero2cartolab_25d_render_mode", config.render_mode)

    layer.setCustomProperty("zero2cartolab/25d_height_field", config.height_field)
    layer.setCustomProperty("zero2cartolab/25d_preset", config.preset)
    layer.setCustomProperty("zero2cartolab/25d_angle", float(config.angle))
    layer.setCustomProperty("zero2cartolab/25d_height_scale", float(config.height_scale))
    layer.setCustomProperty("zero2cartolab/25d_height_mode", config.height_mode)
    layer.setCustomProperty("zero2cartolab/25d_floor_height", float(config.floor_height))
    layer.setCustomProperty("zero2cartolab/25d_render_mode", config.render_mode)
    layer.setCustomProperty("zero2cartolab/25d_floor_palette", config.floor_palette)
    layer.setCustomProperty("zero2cartolab/25d_max_floors", int(sanitised_max_floors(config)))
    layer.setCustomProperty("zero2cartolab/25d_max_floors_mode", "auto" if is_auto_max_floors(config) else "manual")
    layer.setCustomProperty("zero2cartolab/25d_floor_legend", "one_rule_per_floor")
    layer.setCustomProperty("zero2cartolab/25d_step_height", float(config.step_height))
    layer.setCustomProperty("zero2cartolab/25d_max_height", float(config.max_height))


def _apply_floor_band_renderer(layer, config: Style25DConfig) -> str:
    if config.height_mode != HEIGHT_MODE_FLOOR_COUNT:
        raise ValueError("Per-floor colour bands require Height source = Floor count field.")

    from qgis.core import QgsFeatureRequest, QgsRuleBasedRenderer

    _set_layer_25d_properties(layer, config)
    max_floors = resolve_max_floors(layer, config)
    layer.setCustomProperty("zero2cartolab/25d_resolved_max_floors", int(max_floors))

    root = QgsRuleBasedRenderer.Rule(None)
    for floor_index in range(1, max_floors + 1):
        symbol = _empty_fill_symbol()
        if floor_index == 1 and config.shadow_enabled:
            shadow_symbol = _make_fill_symbol(
                hex_to_rgba(config.shadow_color, 72),
                hex_to_rgba(config.shadow_color, 0),
                outline_width=0.0,
            )
            symbol.appendSymbolLayer(
                _make_geometry_generator_layer(build_floor_band_shadow_expression(config), shadow_symbol, 0)
            )

        roof_color = floor_band_color(floor_index, config.floor_palette, wall=False)
        wall_color = floor_band_color(floor_index, config.floor_palette, wall=True)
        outline = hex_to_rgba(adjust_hex_color(wall_color, 0.72), 96)

        wall_symbol = _make_fill_symbol(
            hex_to_rgba(wall_color, 255),
            outline,
            outline_width=0.22,
            wall_shading=bool(config.wall_shading),
        )
        roof_symbol = _make_fill_symbol(
            hex_to_rgba(roof_color, 255),
            hex_to_rgba(adjust_hex_color(roof_color, 0.72), 112),
            outline_width=0.18,
        )

        symbol.appendSymbolLayer(
            _make_geometry_generator_layer(
                build_floor_band_wall_expression(config, floor_index),
                wall_symbol,
                floor_index * 2 - 1,
            )
        )
        symbol.appendSymbolLayer(
            _make_geometry_generator_layer(
                build_floor_band_roof_expression(config, floor_index, max_floors),
                roof_symbol,
                floor_index * 2,
            )
        )

        root.appendChild(
            QgsRuleBasedRenderer.Rule(
                symbol,
                0,
                0,
                "",
                build_floor_band_legend_label(config, floor_index, max_floors),
            )
        )

    renderer = QgsRuleBasedRenderer(root)
    renderer.setUsingSymbolLevels(True)
    renderer.setOrderByEnabled(True)
    renderer.setOrderBy(QgsFeatureRequest.OrderBy([
        QgsFeatureRequest.OrderByClause(build_order_by_expression("@qgis_25d_angle", "$geometry"), False, True)
    ]))

    layer.setRenderer(renderer)
    layer.triggerRepaint()
    return build_style_summary(layer.name(), config, resolved_max_floors=max_floors)


def apply_25d_renderer(layer, config: Style25DConfig) -> str:
    """Apply a 02CartoLab 2.5D renderer to a loaded polygon layer."""
    if layer is None:
        raise ValueError("Select a polygon layer before applying the 2.5D style.")
    if not hasattr(layer, "geometryType") or layer.geometryType() != POLYGON_GEOMETRY:
        raise ValueError("The 2.5D style requires a polygon layer.")

    fields = layer.fields()
    lookup = fields.lookupField(config.height_field) if hasattr(fields, "lookupField") else fields.indexOf(config.height_field)
    if lookup < 0:
        raise ValueError(f"Height field not found: {config.height_field}")

    if config.render_mode == RENDER_MODE_FLOOR_BANDS:
        return _apply_floor_band_renderer(layer, config)

    from qgis.core import Qgs25DRenderer
    from qgis.PyQt.QtGui import QColor

    renderer = Qgs25DRenderer()
    renderer.setRoofColor(QColor(config.roof_color))
    renderer.setWallColor(QColor(config.wall_color))

    if hasattr(renderer, "setShadowColor"):
        renderer.setShadowColor(QColor(config.shadow_color))
    if hasattr(renderer, "setShadowEnabled"):
        renderer.setShadowEnabled(bool(config.shadow_enabled))
    if hasattr(renderer, "setShadowSpread"):
        renderer.setShadowSpread(float(config.shadow_spread))
    if hasattr(renderer, "setWallShadingEnabled"):
        renderer.setWallShadingEnabled(bool(config.wall_shading))

    _set_layer_25d_properties(layer, config)

    layer.setRenderer(renderer)
    layer.triggerRepaint()
    return build_style_summary(layer.name(), config)
