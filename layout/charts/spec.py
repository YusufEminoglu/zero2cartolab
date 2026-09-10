"""Validated chart specification shared by the Designer GUI and renderer."""
from __future__ import annotations

from dataclasses import dataclass, field


CHART_TYPES = (
    "bar", "grouped_bar", "stacked_bar", "line", "multi_line", "area",
    "scatter", "pie", "donut", "histogram",
)
AGGREGATIONS = ("count", "sum", "mean", "median", "min", "max")
DEFAULT_PALETTE = (
    "#2563eb", "#0f766e", "#d97706", "#dc2626", "#7c3aed",
    "#0891b2", "#65a30d", "#c026d3", "#475569", "#ea580c",
)
PALETTES = {
    "Editorial": DEFAULT_PALETTE,
    "Ocean": ("#0c4a6e", "#0369a1", "#0284c7", "#38bdf8", "#7dd3fc", "#0f766e"),
    "Earth": ("#3f6212", "#65a30d", "#a16207", "#d97706", "#92400e", "#57534e"),
    "Colorblind Safe": ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"),
    "Monochrome": ("#0f172a", "#334155", "#475569", "#64748b", "#94a3b8", "#cbd5e1"),
}


@dataclass(frozen=True)
class ChartSpec:
    chart_type: str = "bar"
    category_field: str = ""
    value_field: str = ""
    series_field: str = ""
    aggregation: str = "count"
    title: str = "Chart"
    x: float = 15.0
    y: float = 15.0
    width: float = 90.0
    height: float = 60.0
    top_n: int = 10
    bins: int = 8
    show_legend: bool = True
    show_values: bool = True
    palette: tuple[str, ...] = field(default_factory=lambda: DEFAULT_PALETTE)
    background_color: str = "#ffffff"
    text_color: str = "#0f172a"
    grid_color: str = "#e2e8f0"
    theme_provider: str = "02CartoLab"
    theme_id: str = "editorial"
    font_family: str = "Segoe UI"
    title_size_pt: float = 9.0
    label_size_pt: float = 5.6
    line_width_mm: float = 0.65
    safe_margin_mm: float = 3.0

    def validated(self) -> "ChartSpec":
        if self.chart_type not in CHART_TYPES:
            raise ValueError(f"Unsupported chart type: {self.chart_type}")
        if self.aggregation not in AGGREGATIONS:
            raise ValueError(f"Unsupported aggregation: {self.aggregation}")
        if self.width < 35 or self.height < 30:
            raise ValueError("Chart frame must be at least 35 x 30 mm.")
        if self.top_n < 1 or self.top_n > 50:
            raise ValueError("Top N must be between 1 and 50.")
        if self.bins < 3 or self.bins > 40:
            raise ValueError("Histogram bins must be between 3 and 40.")
        if self.safe_margin_mm < 0 or self.safe_margin_mm > 25:
            raise ValueError("Safe margin must be between 0 and 25 mm.")
        if not 6.0 <= self.title_size_pt <= 24.0:
            raise ValueError("Chart title size must be between 6 and 24 pt.")
        if not 4.0 <= self.label_size_pt <= 16.0:
            raise ValueError("Chart label size must be between 4 and 16 pt.")
        if not 0.1 <= self.line_width_mm <= 3.0:
            raise ValueError("Chart line width must be between 0.1 and 3 mm.")
        if not self.palette:
            raise ValueError("Chart palette cannot be empty.")
        from ..pixel_qa import contrast_ratio
        if contrast_ratio(self.text_color, self.background_color) < 4.5:
            raise ValueError("Chart text/background contrast must be at least WCAG AA (4.5:1).")
        if min(contrast_ratio(color, self.background_color) for color in self.palette) < 1.4:
            raise ValueError("Every chart palette colour must remain distinguishable from its background.")
        if self.chart_type == "histogram" and not self.value_field:
            raise ValueError("Histogram requires a numeric value field.")
        if self.chart_type != "histogram" and not self.category_field:
            raise ValueError("This chart requires a category field.")
        if self.chart_type in ("grouped_bar", "stacked_bar", "multi_line") and not self.series_field:
            raise ValueError("This chart type requires a series field.")
        if self.aggregation != "count" and not self.value_field:
            raise ValueError(f"{self.aggregation.title()} requires a numeric value field.")
        return self
