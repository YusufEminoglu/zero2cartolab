"""Pixel-level QA for exported Print Layout rasters."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import median

try:
    from qgis.PyQt.QtGui import QColor, QImage
except ImportError:
    QColor = QImage = None


@dataclass(frozen=True)
class PixelMetrics:
    width: int
    height: int
    dpi: float
    sampled_pixels: int
    ink_ratio: float
    edge_ink_ratio: float
    unique_color_buckets: int
    content_bbox: tuple[int, int, int, int] | None
    minimum_content_margin_px: int

    def as_dict(self):
        return asdict(self)


def _rgb(value):
    if isinstance(value, str):
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    if hasattr(value, "red"):
        return value.red(), value.green(), value.blue()
    return tuple(value[:3])


def contrast_ratio(first, second):
    """WCAG contrast ratio for two RGB tuples, QColor objects or hex strings."""
    def luminance(color):
        channels = []
        for channel in _rgb(color):
            value = channel / 255.0
            channels.append(value / 12.92 if value <= 0.04045
                            else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    one, two = luminance(first), luminance(second)
    return (max(one, two) + 0.05) / (min(one, two) + 0.05)


def analyze_export(image_or_path, dpi: float = 150.0, safe_margin_mm: float = 3.0,
                   sample_step: int = 3) -> PixelMetrics:
    """Measure real rendered content, edge safety and colour diversity."""
    if QImage is None:
        raise RuntimeError("Pixel QA requires a QGIS/PyQt runtime.")
    image = QImage(image_or_path) if isinstance(image_or_path, str) else image_or_path
    if image is None or image.isNull():
        raise ValueError("Exported image could not be loaded.")
    width, height = image.width(), image.height()
    corners = [
        _rgb(image.pixelColor(0, 0)), _rgb(image.pixelColor(width - 1, 0)),
        _rgb(image.pixelColor(0, height - 1)),
        _rgb(image.pixelColor(width - 1, height - 1)),
    ]
    background = tuple(int(median(channel)) for channel in zip(*corners))
    border = max(1, int(round(float(dpi) * safe_margin_mm / 25.4)))
    step = max(1, int(sample_step))
    sampled = ink = edge_sampled = edge_ink = 0
    colors = set()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(0, height, step):
        for x in range(0, width, step):
            color = _rgb(image.pixelColor(x, y))
            sampled += 1
            colors.add(tuple(channel // 16 for channel in color))
            distance = math.sqrt(sum((color[i] - background[i]) ** 2 for i in range(3)))
            is_ink = distance > 28.0
            is_edge = x < border or y < border or x >= width - border or y >= height - border
            if is_edge:
                edge_sampled += 1
            if is_ink:
                ink += 1
                min_x, min_y = min(min_x, x), min(min_y, y)
                max_x, max_y = max(max_x, x), max(max_y, y)
                if is_edge:
                    edge_ink += 1
    bbox = None if max_x < 0 else (min_x, min_y, max_x, max_y)
    minimum_margin = min(min_x, min_y, width - 1 - max_x, height - 1 - max_y) if bbox else 0
    return PixelMetrics(
        width=width, height=height, dpi=float(dpi), sampled_pixels=sampled,
        ink_ratio=ink / max(1, sampled),
        edge_ink_ratio=edge_ink / max(1, edge_sampled),
        unique_color_buckets=len(colors), content_bbox=bbox,
        minimum_content_margin_px=int(minimum_margin),
    )


def validate_pixels(metrics: PixelMetrics, safe_margin_mm: float = 3.0):
    """Return actionable pixel QA findings."""
    issues = []
    expected_margin = int(round(metrics.dpi * safe_margin_mm / 25.4))
    if metrics.ink_ratio < 0.002:
        issues.append({"severity": "error", "code": "pixel_blank", "message": "Export is blank or nearly blank."})
    if metrics.unique_color_buckets < 4:
        issues.append({"severity": "warning", "code": "pixel_low_diversity", "message": "Export has unusually low colour diversity."})
    if metrics.edge_ink_ratio > 0.002 or (metrics.content_bbox and metrics.minimum_content_margin_px < expected_margin):
        issues.append({
            "severity": "warning", "code": "pixel_safe_margin",
            "message": f"Rendered content enters the {safe_margin_mm:g} mm print-safe edge band.",
        })
    return issues


def format_pixel_report(metrics: PixelMetrics, issues) -> str:
    status = "READY" if not issues else "CHECK"
    lines = [
        f"Pixel QA · {status}",
        f"{metrics.width} × {metrics.height}px at {metrics.dpi:g} DPI",
        f"Ink {metrics.ink_ratio * 100:.1f}% · edge ink {metrics.edge_ink_ratio * 100:.2f}%",
        f"Colour buckets {metrics.unique_color_buckets} · minimum content margin {metrics.minimum_content_margin_px}px",
    ]
    lines.extend(f"{issue['severity'].upper()}: {issue['message']}" for issue in issues)
    return "\n".join(lines)
