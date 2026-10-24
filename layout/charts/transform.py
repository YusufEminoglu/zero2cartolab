"""Pure data shaping adapted from zero2viz's grouped-chart architecture."""
from __future__ import annotations

import math
from statistics import median

from .spec import ChartSpec


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _aggregate(values, count, method):
    if method == "count":
        return float(count)
    numeric = [number for number in (_number(value) for value in values) if number is not None]
    if not numeric:
        return 0.0
    if method == "sum":
        return sum(numeric)
    if method == "mean":
        return sum(numeric) / len(numeric)
    if method == "median":
        return median(numeric)
    if method == "min":
        return min(numeric)
    if method == "max":
        return max(numeric)
    raise ValueError(f"Unsupported aggregation: {method}")


def _histogram(values, bins):
    numeric = [number for number in (_number(value) for value in values) if number is not None]
    if not numeric:
        return [], []
    low, high = min(numeric), max(numeric)
    if low == high:
        return [f"{low:g}"], [float(len(numeric))]
    width = (high - low) / bins
    counts = [0] * bins
    for value in numeric:
        index = min(bins - 1, int((value - low) / width))
        counts[index] += 1
    labels = [f"{low + i * width:g}–{low + (i + 1) * width:g}" for i in range(bins)]
    return labels, [float(count) for count in counts]


def build_chart_data(spec: ChartSpec, columns):
    """Create deterministic categories and values ready for native rendering."""
    spec.validated()
    x_values = None
    if spec.chart_type == "histogram":
        categories, values = _histogram(columns.get(spec.value_field, []), spec.bins)
    elif spec.chart_type == "scatter":
        pairs = []
        for raw_x, raw_y in zip(
                columns.get(spec.category_field, []), columns.get(spec.value_field, [])):
            x_value, y_value = _number(raw_x), _number(raw_y)
            if x_value is not None and y_value is not None:
                pairs.append((x_value, y_value))
        if not pairs:
            raise ValueError("Scatter chart requires numeric X and Y fields.")
        pairs = pairs[: spec.top_n]
        x_values = [pair[0] for pair in pairs]
        categories = [f"{pair[0]:g}" for pair in pairs]
        values = [pair[1] for pair in pairs]
    elif spec.chart_type in ("grouped_bar", "stacked_bar", "multi_line"):
        category_raw = columns.get(spec.category_field, [])
        series_raw = columns.get(spec.series_field, [])
        value_raw = columns.get(spec.value_field, [])
        category_order, series_order, buckets, counts = [], [], {}, {}
        for index, raw_category in enumerate(category_raw):
            category = "(null)" if raw_category is None else str(raw_category)
            raw_series = series_raw[index] if index < len(series_raw) else None
            series = "(null)" if raw_series is None else str(raw_series)
            if category not in category_order:
                category_order.append(category)
            if series not in series_order:
                series_order.append(series)
            key = (series, category)
            buckets.setdefault(key, [])
            counts[key] = counts.get(key, 0) + 1
            if index < len(value_raw):
                buckets[key].append(value_raw[index])
        totals = []
        for category in category_order:
            totals.append(sum(_aggregate(buckets.get((series, category), []),
                                         counts.get((series, category), 0), spec.aggregation)
                              for series in series_order))
        ranked = sorted(range(len(category_order)), key=lambda i: totals[i], reverse=True)[:spec.top_n]
        categories = [category_order[i] for i in ranked]
        series_data = []
        for series in series_order:
            series_data.append({
                "name": series,
                "values": [
                    _aggregate(buckets.get((series, category), []),
                               counts.get((series, category), 0), spec.aggregation)
                    for category in categories
                ],
            })
        values = totals
    else:
        categories_raw = columns.get(spec.category_field, [])
        values_raw = columns.get(spec.value_field, []) if spec.value_field else []
        order, buckets, counts = [], {}, {}
        for index, category in enumerate(categories_raw):
            key = "(null)" if category is None else str(category)
            if key not in counts:
                order.append(key)
                buckets[key] = []
                counts[key] = 0
            counts[key] += 1
            if index < len(values_raw):
                buckets[key].append(values_raw[index])
        values = [_aggregate(buckets[key], counts[key], spec.aggregation) for key in order]
        ranked = sorted(range(len(order)), key=lambda i: values[i], reverse=True)[:spec.top_n]
        categories = [order[i] for i in ranked]
        values = [values[i] for i in ranked]
    if not categories:
        raise ValueError("The selected fields contain no chartable data.")
    if spec.chart_type in ("pie", "donut") and any(v < 0 for v in values):
        raise ValueError(
            "Pie and donut charts require non-negative values; "
            "a negative wedge cannot be drawn truthfully."
        )
    result = {"categories": categories, "values": values}
    if x_values is not None:
        result["x_values"] = x_values
    if spec.chart_type in ("grouped_bar", "stacked_bar", "multi_line"):
        result["series"] = series_data
    return result
