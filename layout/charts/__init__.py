"""Native, dependency-free charts for QGIS Print Layouts."""

from .spec import ChartSpec, CHART_TYPES, AGGREGATIONS, PALETTES
from .datasource import extract_columns
from .transform import build_chart_data
from .renderer import add_chart_to_layout, list_charts, remove_chart
from .placement import best_position
from .theme_adapter import discover_zero2viz_themes

__all__ = [
    "ChartSpec", "CHART_TYPES", "AGGREGATIONS", "PALETTES", "extract_columns",
    "build_chart_data", "add_chart_to_layout", "list_charts", "remove_chart", "best_position",
    "discover_zero2viz_themes",
]
