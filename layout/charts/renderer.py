"""Render charts as native QGIS layout vector items.

The output contains no web view, external image, temporary file, or optional
Python package, so it remains editable and exports consistently to PDF/SVG/PNG.
"""
from __future__ import annotations

import math
import json
from contextlib import suppress
from dataclasses import asdict
from uuid import uuid4

try:
    from qgis.PyQt.QtCore import QPointF
    from qgis.PyQt.QtGui import QColor, QFont, QPolygonF
    from qgis.core import (
        QgsFillSymbol,
        QgsLayoutItemLabel,
        QgsLayoutItemGroup,
        QgsLayoutItemPolygon,
        QgsLayoutItemPolyline,
        QgsLayoutItemShape,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLineSymbol,
        QgsUnitTypes,
    )
    _MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except ImportError:
    QPointF = QColor = QFont = QPolygonF = None
    QgsFillSymbol = QgsLayoutItemLabel = QgsLayoutItemGroup = QgsLayoutItemPolygon = None
    QgsLayoutItemPolyline = QgsLayoutItemShape = None
    QgsLayoutPoint = QgsLayoutSize = QgsLineSymbol = None
    _MM = 0

from .datasource import extract_columns
from .spec import ChartSpec
from .transform import build_chart_data


CHART_PREFIX = "cartolab_chart_"


def _fill(color, outline="transparent", width="0"):
    return QgsFillSymbol.createSimple({
        "color": color,
        "outline_color": outline,
        "outline_width": str(width),
    })


def _line(color="#64748b", width="0.25"):
    return QgsLineSymbol.createSimple({"color": color, "width": str(width)})


def _add_label(layout, item_id, text, x, y, w, h, size=7.0, bold=False,
               color="#334155", align=None):
    label = QgsLayoutItemLabel(layout)
    label.setId(item_id)
    label.setText(str(text))
    label.setBackgroundEnabled(False)
    label.setFrameEnabled(False)
    font = QFont("Segoe UI")
    font.setPointSizeF(float(size))
    font.setBold(bool(bold))
    label.setFont(font)
    label.setFontColor(QColor(color))
    if align is not None:
        with suppress(Exception):
            label.setHAlign(align)
    label.attemptMove(QgsLayoutPoint(x, y, _MM))
    label.attemptResize(QgsLayoutSize(max(0.5, w), max(0.5, h), _MM))
    layout.addLayoutItem(label)
    return label


def _add_rect(layout, item_id, x, y, w, h, color, outline="transparent", width=0):
    item = QgsLayoutItemShape(layout)
    item.setId(item_id)
    shape_enum = getattr(
        getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape),
        "Rectangle",
        getattr(QgsLayoutItemShape, "Rectangle", 0),
    )
    item.setShapeType(shape_enum)
    item.setSymbol(_fill(color, outline, width))
    item.attemptMove(QgsLayoutPoint(x, y, _MM))
    item.attemptResize(QgsLayoutSize(max(0.25, w), max(0.25, h), _MM))
    layout.addLayoutItem(item)
    return item


def _add_polyline(layout, item_id, points, color="#64748b", width=0.25):
    item = QgsLayoutItemPolyline(QPolygonF([QPointF(x, y) for x, y in points]), layout)
    item.setId(item_id)
    item.setSymbol(_line(color, width))
    layout.addLayoutItem(item)
    return item


def _fmt(value):
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}k"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.2g}"


def _cartesian(layout, root, spec, categories, values, x, y, w, h, x_values=None):
    left, right, top, bottom = 12.0, 3.0, 9.0, 11.0
    px, py = x + left, y + top
    pw, ph = max(10.0, w - left - right), max(10.0, h - top - bottom)
    minimum = min(0.0, min(values))
    maximum = max(0.0, max(values))
    span = maximum - minimum or 1.0
    value_y = lambda value: py + ph - ((float(value) - minimum) / span) * ph
    zero_y = value_y(0.0)

    _add_polyline(layout, f"{root}_axis_y", [(px, py), (px, py + ph)], spec.text_color, 0.22)
    _add_polyline(layout, f"{root}_axis_x", [(px, zero_y), (px + pw, zero_y)], spec.text_color, 0.22)
    for index in range(5):
        value = minimum + span * index / 4.0
        gy = value_y(value)
        _add_polyline(layout, f"{root}_grid_{index}", [(px, gy), (px + pw, gy)], spec.grid_color, 0.12)
        _add_label(layout, f"{root}_tick_{index}", _fmt(value), x + 0.5, gy - 2.0, left - 1.5, 4.0, 5.6, color=spec.text_color)

    count = len(categories)
    slot = pw / max(1, count)
    palette = spec.palette
    if spec.chart_type in ("bar", "histogram"):
        bar_w = max(0.5, slot * 0.68)
        for index, (category, value) in enumerate(zip(categories, values)):
            cx = px + slot * (index + 0.5)
            vy = value_y(value)
            top_y, bar_h = min(zero_y, vy), max(0.25, abs(zero_y - vy))
            _add_rect(layout, f"{root}_mark_{index}", cx - bar_w / 2, top_y,
                      bar_w, bar_h, palette[index % len(palette)])
            if spec.show_values and slot >= 8:
                _add_label(layout, f"{root}_value_{index}", _fmt(value),
                           cx - slot / 2, top_y - 4.0, slot, 3.5, 5.6, bold=True)
    else:
        if spec.chart_type == "scatter" and x_values:
            x_min, x_max = min(x_values), max(x_values)
            x_span = x_max - x_min or 1.0
            points = [(px + ((value - x_min) / x_span) * pw, value_y(y_value))
                      for value, y_value in zip(x_values, values)]
        else:
            points = [(px + slot * (index + 0.5), value_y(value))
                      for index, value in enumerate(values)]
        if spec.chart_type == "area" and points:
            polygon = QPolygonF([QPointF(points[0][0], zero_y)] +
                                [QPointF(a, b) for a, b in points] +
                                [QPointF(points[-1][0], zero_y)])
            area = QgsLayoutItemPolygon(polygon, layout)
            area.setId(f"{root}_area")
            area.setSymbol(_fill("#bfdbfe", "transparent"))
            layout.addLayoutItem(area)
        if spec.chart_type in ("line", "area") and len(points) > 1:
            _add_polyline(layout, f"{root}_line", points, palette[0], 0.7)
        for index, (cx, cy) in enumerate(points):
            marker = QgsLayoutItemShape(layout)
            marker.setId(f"{root}_mark_{index}")
            ellipse = getattr(
                getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape),
                "Ellipse", getattr(QgsLayoutItemShape, "Ellipse", 1),
            )
            marker.setShapeType(ellipse)
            marker.setSymbol(_fill(palette[index % len(palette)], "#ffffff", 0.2))
            marker.attemptMove(QgsLayoutPoint(cx - 1.2, cy - 1.2, _MM))
            marker.attemptResize(QgsLayoutSize(2.4, 2.4, _MM))
            layout.addLayoutItem(marker)

    max_labels = min(count, max(2, int(pw // 14)))
    stride = max(1, math.ceil(count / max_labels))
    for index, category in enumerate(categories):
        if index % stride:
            continue
        if spec.chart_type == "scatter" and x_values:
            x_min, x_max = min(x_values), max(x_values)
            cx = px + ((x_values[index] - x_min) / (x_max - x_min or 1.0)) * pw
        else:
            cx = px + slot * (index + 0.5)
        label = str(category)
        if len(label) > 14:
            label = label[:12] + "…"
        _add_label(layout, f"{root}_cat_{index}", label,
                   cx - slot * stride / 2, py + ph + 1.2,
                   slot * stride, bottom - 1.5, 5.5, color=spec.text_color)


def _pie(layout, root, spec, categories, values, x, y, w, h):
    total = sum(max(0.0, float(value)) for value in values)
    if total <= 0:
        raise ValueError("Pie and donut charts require at least one positive value.")
    legend_w = min(38.0, w * 0.38) if spec.show_legend else 0.0
    diameter = max(12.0, min(h - 14.0, w - legend_w - 8.0))
    cx, cy, radius = x + 4.0 + diameter / 2, y + 9.0 + diameter / 2, diameter / 2
    angle = -math.pi / 2
    palette = spec.palette
    for index, value in enumerate(values):
        fraction = max(0.0, float(value)) / total
        end = angle + fraction * math.tau
        steps = max(3, int(math.ceil(fraction * 48)))
        outer = [QPointF(cx + radius * math.cos(angle + (end - angle) * step / steps),
                         cy + radius * math.sin(angle + (end - angle) * step / steps))
                 for step in range(steps + 1)]
        if spec.chart_type == "donut":
            inner_radius = radius * 0.52
            inner = [QPointF(cx + inner_radius * math.cos(end - (end - angle) * step / steps),
                             cy + inner_radius * math.sin(end - (end - angle) * step / steps))
                     for step in range(steps + 1)]
            points = outer + inner
        else:
            points = [QPointF(cx, cy)] + outer
        wedge = QgsLayoutItemPolygon(QPolygonF(points), layout)
        wedge.setId(f"{root}_mark_{index}")
        wedge.setSymbol(_fill(palette[index % len(palette)], "#ffffff", 0.18))
        layout.addLayoutItem(wedge)
        angle = end

    if spec.show_legend:
        lx, ly = x + w - legend_w, y + 10.0
        row_h = min(7.0, max(4.2, (h - 13.0) / max(1, len(categories))))
        for index, (category, value) in enumerate(zip(categories, values)):
            yy = ly + index * row_h
            if yy + row_h > y + h - 2:
                break
            _add_rect(layout, f"{root}_key_{index}", lx, yy + 0.8, 3.2, 3.2,
                      palette[index % len(palette)])
            text = f"{str(category)[:15]}  {_fmt(value)}"
            _add_label(layout, f"{root}_legend_{index}", text, lx + 4.3, yy,
                       legend_w - 4.3, row_h, 5.6, color=spec.text_color)


def _multi_cartesian(layout, root, spec, categories, series, x, y, w, h):
    left, right, top, bottom = 12.0, 3.0, 14.0, 11.0
    px, py = x + left, y + top
    pw, ph = max(10.0, w - left - right), max(10.0, h - top - bottom)
    all_values = [float(value) for row in series for value in row["values"]]
    if spec.chart_type == "stacked_bar":
        maxima = [sum(max(0.0, float(row["values"][i])) for row in series)
                  for i in range(len(categories))]
        minima = [sum(min(0.0, float(row["values"][i])) for row in series)
                  for i in range(len(categories))]
        minimum, maximum = min([0.0] + minima), max([0.0] + maxima)
    else:
        minimum, maximum = min([0.0] + all_values), max([0.0] + all_values)
    span = maximum - minimum or 1.0
    value_y = lambda value: py + ph - ((float(value) - minimum) / span) * ph
    zero_y = value_y(0.0)
    _add_polyline(layout, f"{root}_axis_y", [(px, py), (px, py + ph)], spec.text_color, 0.22)
    _add_polyline(layout, f"{root}_axis_x", [(px, zero_y), (px + pw, zero_y)], spec.text_color, 0.22)
    for index in range(5):
        value = minimum + span * index / 4.0
        gy = value_y(value)
        _add_polyline(layout, f"{root}_grid_{index}", [(px, gy), (px + pw, gy)], spec.grid_color, 0.12)
        _add_label(layout, f"{root}_tick_{index}", _fmt(value), x + 0.5, gy - 2,
                   left - 1.5, 4, 5.6, color=spec.text_color)

    slot = pw / max(1, len(categories))
    if spec.chart_type == "grouped_bar":
        cluster_w = slot * 0.78
        bar_w = cluster_w / max(1, len(series))
        for s_index, row in enumerate(series):
            for c_index, value in enumerate(row["values"]):
                cx = px + slot * (c_index + 0.5) - cluster_w / 2 + bar_w * s_index
                vy = value_y(value)
                _add_rect(layout, f"{root}_mark_{s_index}_{c_index}", cx, min(vy, zero_y),
                          max(0.35, bar_w - 0.3), max(0.25, abs(zero_y - vy)),
                          spec.palette[s_index % len(spec.palette)])
    elif spec.chart_type == "stacked_bar":
        bar_w = slot * 0.68
        positive = [0.0] * len(categories)
        negative = [0.0] * len(categories)
        for s_index, row in enumerate(series):
            for c_index, value in enumerate(row["values"]):
                value = float(value)
                start = positive[c_index] if value >= 0 else negative[c_index]
                end = start + value
                if value >= 0:
                    positive[c_index] = end
                else:
                    negative[c_index] = end
                cx = px + slot * (c_index + 0.5) - bar_w / 2
                y1, y2 = value_y(start), value_y(end)
                _add_rect(layout, f"{root}_mark_{s_index}_{c_index}", cx, min(y1, y2),
                          bar_w, max(0.25, abs(y1 - y2)), spec.palette[s_index % len(spec.palette)])
    else:
        for s_index, row in enumerate(series):
            points = [(px + slot * (index + 0.5), value_y(value))
                      for index, value in enumerate(row["values"])]
            if len(points) > 1:
                _add_polyline(layout, f"{root}_line_{s_index}", points,
                              spec.palette[s_index % len(spec.palette)], 0.65)

    for index, category in enumerate(categories):
        label = str(category)[:12] + ("…" if len(str(category)) > 12 else "")
        _add_label(layout, f"{root}_cat_{index}", label,
                   px + slot * index, py + ph + 1.2, slot, bottom - 1.5,
                   5.5, color=spec.text_color)
    if spec.show_legend:
        legend_x = x + 4.0
        for index, row in enumerate(series[:6]):
            lx = legend_x + index * min(26.0, (w - 8) / max(1, min(6, len(series))))
            _add_rect(layout, f"{root}_key_{index}", lx, y + 8.2, 3.0, 2.5,
                      spec.palette[index % len(spec.palette)])
            _add_label(layout, f"{root}_legend_{index}", str(row["name"])[:12],
                       lx + 3.8, y + 7.5, 21.0, 4.0, 5.4, color=spec.text_color)


def add_chart_to_layout(layout, layer, spec: ChartSpec):
    """Extract, transform and add one editable native chart to a layout."""
    if layout is None:
        raise ValueError("No Print Layout is active.")
    spec.validated()
    pages = list(layout.pageCollection().pages()) if layout.pageCollection() else []
    if not pages:
        raise ValueError("The Print Layout has no page.")
    safe_margin = float(spec.safe_margin_mm)
    fits_page = False
    for page in pages:
        rect = page.sceneBoundingRect()
        if (spec.x >= rect.left() + safe_margin and spec.y >= rect.top() + safe_margin
                and spec.x + spec.width <= rect.right() - safe_margin
                and spec.y + spec.height <= rect.bottom() - safe_margin):
            fits_page = True
            break
    if not fits_page:
        raise ValueError("Chart frame does not fit inside the page's 3 mm print-safe margin.")
    fields = [spec.category_field, spec.series_field, spec.value_field]
    data = build_chart_data(spec, extract_columns(layer, fields))
    categories, values = data["categories"], data["values"]
    root = f"{CHART_PREFIX}{uuid4().hex[:10]}"

    _add_rect(layout, f"{root}_frame", spec.x, spec.y, spec.width, spec.height,
              spec.background_color, spec.grid_color, 0.25)
    _add_label(layout, f"{root}_title", spec.title or "Chart",
               spec.x + 4, spec.y + 2, spec.width - 8, 6, 9.0, True, spec.text_color)
    if spec.chart_type in ("pie", "donut"):
        _pie(layout, root, spec, categories, values,
             spec.x, spec.y, spec.width, spec.height)
    elif data.get("series"):
        _multi_cartesian(layout, root, spec, categories, data["series"],
                         spec.x, spec.y, spec.width, spec.height)
    else:
        _cartesian(layout, root, spec, categories, values,
                   spec.x, spec.y, spec.width, spec.height, data.get("x_values"))
    group = QgsLayoutItemGroup(layout)
    group.setId(root)
    group.setCustomProperty("cartolab/chart_spec", json.dumps(asdict(spec)))
    group.setCustomProperty("cartolab/chart_layer_id", layer.id() if hasattr(layer, "id") else "")
    layout.addLayoutItem(group)
    for item in list(layout.items()):
        if item is group:
            continue
        item_id = item.id() if hasattr(item, "id") else ""
        if item_id.startswith(root + "_"):
            group.addItem(item)
    with suppress(Exception):
        layout.refresh()
    return root


def list_charts(layout):
    """Return persisted chart metadata from an existing layout."""
    charts = []
    if layout is None:
        return charts
    for item in layout.items():
        item_id = item.id() if hasattr(item, "id") else ""
        if not item_id.startswith(CHART_PREFIX) or item_id.count("_") != 2:
            continue
        raw = item.customProperty("cartolab/chart_spec", "")
        if not raw:
            continue
        with suppress(ValueError, TypeError):
            charts.append({
                "id": item_id,
                "layer_id": item.customProperty("cartolab/chart_layer_id", ""),
                "spec": json.loads(raw),
            })
    return charts


def remove_chart(layout, chart_id: str) -> int:
    """Remove every native item belonging to one chart root ID."""
    if not chart_id:
        return 0
    removed = 0
    items = list(layout.items())
    groups = [
        item for item in items
        if hasattr(item, "id") and item.id() == chart_id
    ]
    for group in groups:
        with suppress(Exception):
            group.removeItems()
    for item in items:
        item_id = item.id() if hasattr(item, "id") else ""
        if item_id == chart_id or item_id.startswith(chart_id + "_"):
            layout.removeLayoutItem(item)
            removed += 1
    return removed
