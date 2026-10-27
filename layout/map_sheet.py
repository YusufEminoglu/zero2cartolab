# -*- coding: utf-8 -*-
"""
Auto Map Sheet — one-click publication-ready print layout.

Assembles a complete :class:`QgsPrintLayout` from the current map view:
titled map frame at the current extent, filtered legend, scale bar,
north arrow, optional coordinate grid, neat-line and credits. The result
is added to the project's layout manager so it opens straight in the
Layout Designer.
"""
from __future__ import annotations

import math
from contextlib import suppress
from typing import List, Optional

try:
    from qgis.PyQt.QtGui import QColor, QFont, QFontMetricsF, QPolygonF
    from qgis.PyQt.QtCore import QModelIndex, QPointF, Qt
    from qgis.core import (
        QgsProject,
        QgsPrintLayout,
        QgsLayoutItemMap,
        QgsLayoutItemLabel,
        QgsLayoutItemLegend,
        QgsLayoutItemScaleBar,
        QgsLayoutItemPicture,
        QgsLayoutItemPolygon,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsLayoutMeasurement,
        QgsUnitTypes,
        QgsRectangle,
        QgsFillSymbol,
        QgsDistanceArea,
        QgsPointXY,
        QgsCoordinateTransform,
    )
    _MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters
except ImportError:
    QColor = QFont = QFontMetricsF = QPolygonF = QModelIndex = QPointF = Qt = None
    QgsProject = QgsPrintLayout = QgsLayoutItemMap = QgsLayoutItemLabel = QgsLayoutItemLegend = None
    QgsLayoutItemScaleBar = QgsLayoutItemPicture = QgsLayoutItemPolygon = QgsLayoutPoint = QgsLayoutSize = None
    QgsDistanceArea = QgsPointXY = QgsCoordinateTransform = None
    _MM = 0

from ..core.layout_math import fitted_scalebar_segments, map_width_to_km, page_size_mm
from .layout_utils import set_legend_style_text, unique_layout_name, zoom_map_to_extent

# A real font fallback chain with standard installed Windows/Unix fonts
_FONT_FAMILIES = ["Segoe UI", "Arial", "Helvetica", "sans-serif"]


def _font(size: float, bold: bool = False, family: str = "Segoe UI") -> QFont:
    f = QFont(family, int(round(size)))
    hint = getattr(getattr(QFont, "StyleHint", QFont), "SansSerif", getattr(QFont, "SansSerif", None))
    if hint is not None and hasattr(f, "setStyleHint"):
        with suppress(Exception):
            f.setStyleHint(hint)
    if hasattr(f, "setFamilies"):
        f.setFamilies([family] + _FONT_FAMILIES)
    if hasattr(f, "setPointSizeF"):
        f.setPointSizeF(float(size))
    f.setBold(bold)
    return f


def _legend_style(legend, name: str):
    from qgis.core import QgsLegendStyle
    scoped = getattr(QgsLegendStyle, "Style", QgsLegendStyle)
    return getattr(scoped, name, getattr(QgsLegendStyle, name, None))


def _set_legend_typography(legend, label_size: float) -> None:
    """Apply a compact hierarchy while retaining a readable lower bound."""
    sizes = {
        "Title": min(10.0, label_size + 1.2),
        "Group": min(9.5, label_size + 0.8),
        "Subgroup": min(9.0, label_size + 0.4),
        "SymbolLabel": label_size,
    }
    for style_name, size in sizes.items():
        style_enum = _legend_style(legend, style_name)
        if style_enum is None:
            continue
        set_legend_style_text(legend, style_enum, _font(size, bold=style_name in ("Title", "Group")),
                              QColor("#0f172a"))


def _legend_model_texts(legend) -> list[str]:
    """Collect every visible layer/group/symbol label from the legend model."""
    model = legend.model()
    texts = []
    display_role = Qt.ItemDataRole.DisplayRole
    display_role = int(getattr(display_role, "value", display_role))

    def visit(parent):
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            value = model.data(index, display_role)
            if value is not None and str(value).strip():
                texts.append(str(value).strip())
            visit(index)

    visit(QModelIndex())
    return texts


def _legend_text_budget(legend, label_size: float, symbol_width: float,
                        symbol_height: float, box_space: float) -> tuple[float, float]:
    """Estimate rendered content in mm using actual Qt glyph metrics."""
    texts = _legend_model_texts(legend)
    if not texts:
        return 0.0, 0.0
    metrics = QFontMetricsF(_font(label_size))
    advance = getattr(metrics, "horizontalAdvance", None)
    if advance is None:
        advance = getattr(metrics, "width")
    widest_px = max(float(advance(text)) for text in texts)
    # QFontMetricsF uses device pixels; QGIS layout's standard logical text DPI
    # is 96. Add symbol and both-side spacing to obtain the real row budget.
    width_mm = widest_px * 25.4 / 96.0 + symbol_width + box_space * 2.0 + 2.0
    line_height_mm = max(symbol_height, float(metrics.height()) * 25.4 / 96.0)
    height_mm = len(texts) * line_height_mm + box_space * 2.0
    return width_mm, height_mm


def _legend_natural_size(legend) -> Optional[tuple]:
    """Natural legend content size in mm, measured by QGIS's own legend renderer.

    This lays the legend out exactly as the item paints it, with the fonts Qt
    actually resolves on this machine (a requested "Segoe UI" may fall back to
    a much wider face such as DejaVu Sans), so no font family is assumed.
    Returns ``None`` when the renderer API is unavailable.
    """
    try:
        from qgis.core import QgsLayoutUtils, QgsLegendRenderer
        renderer = QgsLegendRenderer(legend.model(), legend.legendSettings())
        context = QgsLayoutUtils.createRenderContextForLayout(legend.layout(), None)
        size = renderer.minimumSize(context)
        return float(size.width()), float(size.height())
    except Exception:
        return None


def _split_long_token(word: str, max_chars: int) -> list:
    """Split an overlong token at snake/kebab/path delimiters or into fixed chunks."""
    if len(word) <= max_chars:
        return [word]
    parts: list = []
    buf = ""
    for ch in word:
        buf += ch
        if ch in ("_", "-", "/"):
            parts.append(buf)
            buf = ""
    if buf:
        parts.append(buf)
    chunks: list = []
    cur = ""
    for part in parts:
        while len(part) > max_chars:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(part[:max_chars])
            part = part[max_chars:]
        if cur and len(cur) + len(part) > max_chars:
            chunks.append(cur)
            cur = part
        else:
            cur += part
    if cur:
        chunks.append(cur)
    return chunks or [word]


def _wrap_text(text: str, max_chars: int) -> str:
    """Greedy word wrap with newlines (the legend renderer breaks lines on them)."""
    max_chars = max(4, int(max_chars))
    lines: list = []
    for paragraph in str(text).split("\n"):
        line = ""
        for raw_word in paragraph.split():
            for word in _split_long_token(raw_word, max_chars):
                if line and len(line) + 1 + len(word) > max_chars:
                    lines.append(line)
                    line = word
                else:
                    line = f"{line} {word}" if line else word
        lines.append(line)
    return "\n".join(lines)


_WRAPPED_PROPERTY = "cartolab/wrapped_legend_labels"
_TRIMMED_PROPERTY = "cartolab/trimmed_legend_count"
_ORIG_COUNT_PROPERTY = "cartolab/orig_legend_count"
_CLEANED_PROPERTY = "cartolab/cleaned_legend_symbols"


def _legend_layer_nodes(legend) -> list:
    model = legend.model()
    root = model.rootGroup() if model is not None else None
    return list(root.findLayers()) if root is not None else []


def _order_layers_rasters_bottom(layers: Optional[List]) -> List:
    """Place raster layers beneath vector layers so opaque DEMs never hide vectors."""
    if not layers:
        return []
    vectors: List = []
    rasters: List = []
    for lyr in layers:
        if lyr is None:
            continue
        is_raster = False
        with suppress(Exception):
            cls_name = type(lyr).__name__
            is_raster = "Raster" in cls_name or int(getattr(lyr.type(), "value", lyr.type())) == 1
        if is_raster:
            rasters.append(lyr)
        else:
            vectors.append(lyr)
    return vectors + rasters


def _clean_legend_patch_symbol(symbol):
    """Clone symbol without centroid/font text sub-layers that overflow tiny legend patches."""
    if symbol is None or not hasattr(symbol, "clone") or not hasattr(symbol, "symbolLayerCount"):
        return None
    count = symbol.symbolLayerCount()
    if count <= 1:
        return None
    remove_indices = [
        idx for idx in range(count)
        if type(symbol.symbolLayer(idx)).__name__ in ("QgsCentroidFillSymbolLayer", "QgsFontMarkerSymbolLayer")
    ]
    if not remove_indices or len(remove_indices) >= count:
        return None
    cloned = symbol.clone()
    for idx in reversed(remove_indices):
        with suppress(Exception):
            cloned.deleteSymbolLayer(idx)
    return cloned


def _sync_legend_layers(legend, layers: Optional[List] = None) -> None:
    """Populate legend's private layer tree from linked map layers and clean patch symbols."""
    if legend is None:
        return
    with suppress(Exception):
        from qgis.core import QgsMapLayerLegendUtils
        target_layers = list(layers) if layers else []
        if not target_layers and legend.linkedMap() is not None:
            target_layers = list(legend.linkedMap().layers())
        target_layers = [lyr for lyr in target_layers if lyr is not None]
        legend.setAutoUpdateModel(False)
        model = legend.model()
        root = model.rootGroup() if model is not None else None
        if root is None:
            return
        if target_layers:
            existing_layers = [n.layer() for n in root.findLayers() if n.layer() is not None]
            if existing_layers != target_layers:
                root.clear()
                for lyr in target_layers:
                    root.addLayer(lyr)
        for node in root.findLayers():
            orig_nodes = list(model.layerOriginalLegendNodes(node))
            if not node.customProperty(_ORIG_COUNT_PROPERTY) and not node.customProperty("legend/node-order"):
                node.setCustomProperty(_ORIG_COUNT_PROPERTY, str(len(orig_nodes)))
            if node.customProperty(_CLEANED_PROPERTY):
                continue
            cleaned_any = False
            for idx, ln in enumerate(orig_nodes):
                sym = ln.symbol() if hasattr(ln, "symbol") else None
                cleaned = _clean_legend_patch_symbol(sym)
                if cleaned is not None:
                    QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(node, idx, cleaned)
                    cleaned_any = True
            node.setCustomProperty(_CLEANED_PROPERTY, "1")
            if cleaned_any:
                model.refreshLayerLegend(node)


def _node_base_symbol_label(model, node, index: int) -> str:
    """Return the unwrapped label for ``index`` (including any (+N more) trim suffix)."""
    import re
    display_role = Qt.ItemDataRole.DisplayRole
    orig_nodes = list(model.layerOriginalLegendNodes(node))
    if index < 0 or index >= len(orig_nodes):
        return ""
    base = str(orig_nodes[index].data(display_role) or "").replace("\n", " ").strip()
    base = re.sub(r"\s*\(\+\d+\s+more\)$", "", base).strip()
    orig_total = int(node.customProperty(_ORIG_COUNT_PROPERTY) or len(orig_nodes))
    trimmed_raw = node.customProperty(_TRIMMED_PROPERTY)
    if trimmed_raw:
        with suppress(Exception):
            kept_count = int(trimmed_raw)
            if 0 < kept_count < orig_total and index == kept_count - 1:
                omitted = orig_total - kept_count
                return f"{base} (+{omitted} more)" if base else f"(+{omitted} more)"
    return base


def _apply_trim_to_node(model, node, kept_count: Optional[int]) -> None:
    """Restrict ``node`` to its first ``kept_count`` symbol items with a (+N more) suffix."""
    from qgis.core import QgsMapLayerLegendUtils
    orig_nodes = list(model.layerOriginalLegendNodes(node))
    if not node.customProperty(_ORIG_COUNT_PROPERTY) and not node.customProperty("legend/node-order"):
        node.setCustomProperty(_ORIG_COUNT_PROPERTY, str(len(orig_nodes)))
    total = int(node.customProperty(_ORIG_COUNT_PROPERTY) or len(orig_nodes))
    if kept_count is None or kept_count >= total or total <= 1:
        if node.customProperty(_TRIMMED_PROPERTY):
            prev_kept = int(node.customProperty(_TRIMMED_PROPERTY) or 0)
            if prev_kept > 0:
                node.removeCustomProperty(f"legend/label-{prev_kept - 1}")
            node.removeCustomProperty(_TRIMMED_PROPERTY)
        node.removeCustomProperty("legend/node-order")
        model.refreshLayerLegend(node)
        return
    kept_count = max(1, int(kept_count))
    prev_raw = node.customProperty(_TRIMMED_PROPERTY)
    if prev_raw:
        with suppress(Exception):
            prev_kept = int(prev_raw)
            if prev_kept > 0 and prev_kept != kept_count:
                node.removeCustomProperty(f"legend/label-{prev_kept - 1}")
    node.setCustomProperty(_TRIMMED_PROPERTY, str(kept_count))
    QgsMapLayerLegendUtils.setLegendNodeOrder(node, list(range(kept_count)))
    last_idx = kept_count - 1
    QgsMapLayerLegendUtils.setLegendNodeUserLabel(
        node, last_idx, _node_base_symbol_label(model, node, last_idx)
    )
    model.refreshLayerLegend(node)


def _unwrap_legend_labels(legend, reset_trim: bool = False) -> None:
    """Remove labels a previous fit wrapped, restoring the natural labels."""
    from qgis.core import QgsMapLayerLegendUtils
    model = legend.model()
    for node in _legend_layer_nodes(legend):
        if reset_trim and node.customProperty(_TRIMMED_PROPERTY):
            _apply_trim_to_node(model, node, None)
        wrapped = node.customProperty(_WRAPPED_PROPERTY)
        if not wrapped:
            continue
        for token in str(wrapped).split(","):
            index = int(token)
            if index < 0:
                node.removeCustomProperty("legend/title-label")
            else:
                trimmed_raw = node.customProperty(_TRIMMED_PROPERTY)
                is_trimmed_tail = False
                if trimmed_raw and not reset_trim:
                    with suppress(Exception):
                        is_trimmed_tail = (index == int(trimmed_raw) - 1)
                if is_trimmed_tail:
                    QgsMapLayerLegendUtils.setLegendNodeUserLabel(
                        node, index, _node_base_symbol_label(model, node, index)
                    )
                else:
                    node.removeCustomProperty(f"legend/label-{index}")
        node.removeCustomProperty(_WRAPPED_PROPERTY)
        model.refreshLayerLegend(node)


def _legend_label_texts(legend) -> list:
    """(node, index, text) for every layer title (index -1) and active symbol label."""
    model = legend.model()
    entries = []
    for node in _legend_layer_nodes(legend):
        title = node.customProperty("legend/title-label") or node.name()
        entries.append((node, -1, str(title)))
        orig_nodes = list(model.layerOriginalLegendNodes(node))
        total = len(orig_nodes)
        active_count = total
        trimmed_raw = node.customProperty(_TRIMMED_PROPERTY)
        if trimmed_raw:
            with suppress(Exception):
                tc = int(trimmed_raw)
                if 0 < tc < total:
                    active_count = tc
        for index in range(active_count):
            text = _node_base_symbol_label(model, node, index)
            if text:
                entries.append((node, index, str(text)))
    return entries


def _wrap_legend_labels(legend, max_chars: int) -> None:
    """Wrap long labels in the legend's own model (project layers untouched)."""
    from qgis.core import QgsMapLayerLegendUtils
    model = legend.model()
    wrapped_by_node: dict = {}
    for node, index, text in _legend_label_texts(legend):
        wrapped = _wrap_text(text, max_chars)
        if wrapped == text:
            continue
        if index < 0:
            node.setCustomProperty("legend/title-label", wrapped)
        else:
            QgsMapLayerLegendUtils.setLegendNodeUserLabel(node, index, wrapped)
        wrapped_by_node.setdefault(id(node), (node, []))[1].append(str(index))
    for node, indexes in wrapped_by_node.values():
        node.setCustomProperty(_WRAPPED_PROPERTY, ",".join(indexes))
        model.refreshLayerLegend(node)


def _apply_legend_size(legend, size: float) -> tuple:
    scale = size / 9.0
    symbol_width = max(3.2, 6.0 * scale)
    symbol_height = max(2.6, 4.0 * scale)
    box_space = max(1.0, 2.0 * scale)
    _set_legend_typography(legend, size)
    legend.setSymbolWidth(symbol_width)
    legend.setSymbolHeight(symbol_height)
    legend.setBoxSpace(box_space)
    with suppress(Exception):
        legend.setColumnSpace(max(1.0, 2.0 * scale))
    for style_name in ("Title", "Group", "Subgroup", "Symbol", "SymbolLabel"):
        style_enum = _legend_style(legend, style_name)
        if style_enum is None:
            continue
        with suppress(Exception):
            st = legend.rstyle(style_enum)
            Side = getattr(st, "Side", st)
            top_side = getattr(Side, "Top", 0)
            bottom_side = getattr(Side, "Bottom", 1)
            left_side = getattr(Side, "Left", 2)
            if style_name in ("Title", "Group", "Subgroup"):
                st.setMargin(top_side, max(0.8, 2.0 * scale))
                st.setMargin(bottom_side, max(0.4, 1.0 * scale))
            elif style_name == "Symbol":
                st.setMargin(top_side, max(0.4, 1.2 * scale))
                st.setMargin(left_side, max(0.8, 1.5 * scale))
            legend.setStyle(style_enum, st)
    return symbol_width, symbol_height, box_space


def _fit_legend_to_box(legend, width_mm: float, height_mm: float) -> dict:
    """Shrink typography/symbols, wrap labels, and cap excess categories to fit box.

    Sizes are measured with QGIS's legend renderer (the same layout code the
    item paints with), so the result holds whatever font Qt falls back to.
    Type is first reduced to a legible 7 pt; if long labels still overflow,
    they are word-wrapped (in the legend's own model) before shrinking further.
    When a dataset contains dozens of categories whose vertical stack exceeds
    ``height_mm`` even at compact font sizes, the longest layer's legend nodes
    are progressively capped with a ``(+N more)`` indicator so the legend never
    bleeds outside its container.
    """
    result = {"font_pt": 9.0, "natural_width_mm": 0.0,
              "natural_height_mm": 0.0, "fits": False}
    with suppress(Exception):
        _sync_legend_layers(legend)
    with suppress(Exception):
        legend.setColumnCount(1)
    with suppress(Exception):
        _unwrap_legend_labels(legend, reset_trim=True)

    def measure(size, symbol_width, symbol_height, box_space):
        natural = _legend_natural_size(legend)
        if natural is None:
            legend.setResizeToContents(True)
            legend.adjustBoxSize()
            metric_w, metric_h = _legend_text_budget(
                legend, size, symbol_width, symbol_height, box_space
            )
            natural = (max(float(legend.rect().width()), metric_w),
                       max(float(legend.rect().height()), metric_h))
        natural_w, natural_h = natural
        return {"font_pt": size, "natural_width_mm": natural_w,
                "natural_height_mm": natural_h,
                "fits": natural_w <= width_mm and natural_h <= height_mm}

    def wrap_for_size(size: float) -> dict:
        with suppress(Exception):
            _unwrap_legend_labels(legend, reset_trim=False)
        res = measure(size, *_apply_legend_size(legend, size))
        if res["fits"]:
            return res
        texts = []
        with suppress(Exception):
            texts = [text for _, _, text in _legend_label_texts(legend)]
        longest = max((len(text) for text in texts), default=0)
        if not longest or res["natural_width_mm"] <= width_mm:
            return res
        ratio = width_mm / max(1e-6, res["natural_width_mm"])
        max_chars = max(6, int(longest * ratio * 0.95))
        while True:
            with suppress(Exception):
                _unwrap_legend_labels(legend, reset_trim=False)
                _wrap_legend_labels(legend, max_chars)
            res = measure(size, *_apply_legend_size(legend, size))
            if res["fits"] or res["natural_width_mm"] <= width_mm or max_chars <= 6:
                break
            max_chars = max(6, max_chars - max(1, max_chars // 8))
        return res

    sizes = [9.0 - step * 0.5 for step in range(9)]  # 9.0 ... 5.0 pt
    for size in sizes:
        if size < 7.0:
            break
        result = measure(size, *_apply_legend_size(legend, size))
        if result["fits"]:
            break

    if not result["fits"]:
        for size in [s for s in sizes if s <= 7.0]:
            result = wrap_for_size(size)
            if result["fits"]:
                break

    if not result["fits"]:
        with suppress(Exception):
            _unwrap_legend_labels(legend, reset_trim=True)
            model = legend.model()
            nodes = _legend_layer_nodes(legend)
            counts = {
                id(n): (
                    n,
                    int(n.customProperty(_ORIG_COUNT_PROPERTY) or len(list(model.layerOriginalLegendNodes(n)))),
                )
                for n in nodes
            }
            for trim_size in (6.5, 6.0, 5.5, 5.0):
                for n, orig_c in counts.values():
                    _apply_trim_to_node(model, n, orig_c)
                current = {nid: orig_c for nid, (_, orig_c) in counts.items()}
                result = wrap_for_size(trim_size)
                if result["fits"]:
                    break
                guard = 0
                while not result["fits"] and guard < 40:
                    guard += 1
                    best_nid = max(
                        current, key=lambda nid: current[nid], default=None
                    )
                    if best_nid is None or current[best_nid] <= 1:
                        break
                    cur_c = current[best_nid]
                    if result["natural_height_mm"] > height_mm * 1.35 and cur_c > 4:
                        frac = max(0.15, (height_mm / max(1e-6, result["natural_height_mm"])) * 0.85)
                        new_c = max(1, min(cur_c - 1, int(cur_c * frac)))
                    else:
                        new_c = max(1, cur_c - 1)
                    current[best_nid] = new_c
                    _apply_trim_to_node(model, counts[best_nid][0], new_c)
                    result = wrap_for_size(trim_size)
                if result["fits"]:
                    break

    # Lock the final box: no later refresh may expand it into page margins.
    legend.setResizeToContents(False)
    legend.attemptResize(QgsLayoutSize(width_mm, height_mm, _MM))
    legend.setCustomProperty("cartolab/legend_fit_font_pt", result["font_pt"])
    legend.setCustomProperty("cartolab/legend_natural_width_mm", result["natural_width_mm"])
    legend.setCustomProperty("cartolab/legend_natural_height_mm", result["natural_height_mm"])
    legend.setCustomProperty("cartolab/legend_fits", result["fits"])
    return result


def _resolve_layers(iface, project: QgsProject) -> List:
    """Visible canvas layers if a canvas is available, else all project layers."""
    if iface is not None:
        with suppress(Exception):
            canvas_layers = iface.mapCanvas().layers()
            if canvas_layers:
                return list(canvas_layers)
    return [
        node.layer()
        for node in project.layerTreeRoot().findLayers()
        if node.isVisible() and node.layer() is not None
    ] or list(project.mapLayers().values())


def _resolve_crs(iface, project: QgsProject, layers):
    """Resolve canvas/project CRS, preferring a valid input-layer CRS headlessly."""
    if iface is not None:
        with suppress(Exception):
            crs = iface.mapCanvas().mapSettings().destinationCrs()
            if crs is not None and crs.isValid():
                return crs
    for layer in layers or []:
        with suppress(Exception):
            crs = layer.crs()
            if crs is not None and crs.isValid():
                return crs
    with suppress(Exception):
        crs = project.crs()
        if crs is not None and crs.isValid():
            return crs
    return None


def _resolve_extent(
    iface,
    layers,
    target_crs=None,
    project: Optional[QgsProject] = None,
) -> Optional[QgsRectangle]:
    """Current canvas extent, else layer extents transformed to one CRS."""
    if iface is not None:
        with suppress(Exception):
            ext = iface.mapCanvas().extent()
            if ext is not None and not ext.isEmpty():
                return QgsRectangle(ext)
    extent = None
    for layer in layers:
        with suppress(Exception):
            le = layer.extent()
            if le is None or le.isEmpty():
                continue
            layer_crs = layer.crs()
            if (
                target_crs is not None
                and target_crs.isValid()
                and layer_crs is not None
                and layer_crs.isValid()
                and layer_crs != target_crs
                and QgsCoordinateTransform is not None
            ):
                context = project.transformContext() if project is not None else QgsProject.instance().transformContext()
                le = QgsCoordinateTransform(layer_crs, target_crs, context).transformBoundingBox(le)
            if extent is None:
                extent = QgsRectangle(le)
            else:
                extent.combineExtentWith(le)
    return extent


def _distance_kilometres_unit():
    return getattr(
        QgsUnitTypes,
        "DistanceKilometers",
        getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceKilometers", 1),
    )


def _distance_metres_unit():
    return getattr(
        QgsUnitTypes,
        "DistanceMeters",
        getattr(getattr(QgsUnitTypes, "DistanceUnit", None), "DistanceMeters", 0),
    )


def _crs_is_geographic(crs) -> bool:
    is_geographic = False
    with suppress(Exception):
        is_geographic = bool(crs is not None and crs.isValid() and crs.isGeographic())
    return is_geographic


def _crs_unit_to_km(crs) -> float:
    factor = 0.001
    with suppress(Exception):
        factor = float(QgsUnitTypes.fromUnitToUnitFactor(crs.mapUnits(), _distance_kilometres_unit()))
    return factor if factor > 0 else 0.001


def _fallback_geographic_width_km(extent: QgsRectangle) -> float:
    """Approximate longitude span in kilometres when QgsDistanceArea is unavailable."""
    lat = (float(extent.yMinimum()) + float(extent.yMaximum())) * 0.5
    km_per_degree_lon = 111.320 * max(0.01, abs(math.cos(math.radians(lat))))
    return map_width_to_km(float(extent.width()), km_per_degree_lon)


def _geodesic_extent_width_km(extent: QgsRectangle, crs, project: QgsProject) -> float:
    if QgsDistanceArea is None or QgsPointXY is None:
        return 0.0

    width_km = 0.0
    with suppress(Exception):
        distance = QgsDistanceArea()
        if project is not None and hasattr(project, "transformContext"):
            distance.setSourceCrs(crs, project.transformContext())
        if project is not None and hasattr(project, "ellipsoid"):
            ellipsoid = project.ellipsoid()
        else:
            ellipsoid = ""
        if not ellipsoid or str(ellipsoid).upper() == "NONE":
            with suppress(Exception):
                ellipsoid = crs.ellipsoidAcronym()
        distance.setEllipsoid(ellipsoid or "WGS84")
        mid_y = (float(extent.yMinimum()) + float(extent.yMaximum())) * 0.5
        width = distance.measureLine(
            QgsPointXY(float(extent.xMinimum()), mid_y),
            QgsPointXY(float(extent.xMaximum()), mid_y),
        )
        unit_to_km = QgsUnitTypes.fromUnitToUnitFactor(
            distance.lengthUnits(), _distance_kilometres_unit()
        )
        width_km = map_width_to_km(float(width), float(unit_to_km))
    return width_km


def _map_extent_width_km(map_item: QgsLayoutItemMap, project: QgsProject) -> float:
    """Return the linked map frame's real-world width in kilometres."""
    extent = map_item.extent()
    if extent is None or extent.isEmpty():
        return 0.0

    crs = None
    with suppress(Exception):
        crs = map_item.crs()

    if _crs_is_geographic(crs):
        width_km = _geodesic_extent_width_km(extent, crs, project)
        if width_km > 0:
            return width_km
        return _fallback_geographic_width_km(extent)

    return map_width_to_km(float(extent.width()), _crs_unit_to_km(crs))


def _dataset_summary_metrics(layers, extent, crs, project: Optional[QgsProject] = None) -> dict:
    """Compute real-world area (km²/ha) and feature/layer totals for KPI cards."""
    area_km2 = 0.0
    with suppress(Exception):
        if extent is not None and not extent.isEmpty():
            if _crs_is_geographic(crs):
                w_km = _geodesic_extent_width_km(extent, crs, project) or _fallback_geographic_width_km(extent)
                h_km = float(extent.height()) * 110.574
            else:
                factor = _crs_unit_to_km(crs)
                w_km = map_width_to_km(float(extent.width()), factor)
                h_km = map_width_to_km(float(extent.height()), factor)
            area_km2 = max(0.0, w_km * h_km)
    total_features = 0
    layer_count = 0
    for lyr in layers or []:
        if lyr is None:
            continue
        layer_count += 1
        with suppress(Exception):
            if hasattr(lyr, "featureCount"):
                fc = int(lyr.featureCount())
                if fc > 0:
                    total_features += fc
    return {
        "area_km2": area_km2,
        "area_ha": area_km2 * 100.0,
        "total_features": total_features,
        "layer_count": layer_count,
    }


def _configure_scalebar(
    bar: QgsLayoutItemScaleBar,
    map_item: QgsLayoutItemMap,
    project: QgsProject,
    *,
    max_width_mm: float,
    target_segments: int = 3,
) -> bool:
    """Configure a metric scale bar that stays inside its layout budget."""
    if bar is None or map_item is None:
        return False
    map_w_km = _map_extent_width_km(map_item, project)
    if map_w_km <= 0:
        return False

    map_frame_w_mm = 0.0
    with suppress(Exception):
        map_frame_w_mm = float(map_item.rect().width())
    if map_frame_w_mm <= 0:
        map_frame_w_mm = max_width_mm * 3.0

    seg_km, n_right, n_left = fitted_scalebar_segments(
        map_w_km,
        map_frame_w_mm,
        max_width_mm,
        target_segments=target_segments,
    )
    use_metres = map_w_km < 5.0
    bar.setUnits(_distance_metres_unit() if use_metres else _distance_kilometres_unit())
    bar.setUnitLabel("m" if use_metres else "km")
    # QgsLayoutItemScaleBar converts its selected distance unit against the
    # linked map CRS. A non-1 manual factor is an additional divisor and would
    # corrupt labels (for example 0.5 km becoming 0.0005 km).
    bar.setMapUnitsPerScaleBarUnit(1.0)
    bar.setNumberOfSegments(n_right)
    bar.setNumberOfSegmentsLeft(n_left)
    segment_display_units = seg_km * 1000.0 if use_metres else seg_km
    bar.setUnitsPerSegment(segment_display_units)
    with suppress(Exception):
        bar.setMaximumBarWidth(float(max_width_mm))
    with suppress(Exception):
        bar.resizeToMinimumWidth()
    return True


def create_map_sheet(
    iface=None,
    *,
    layers: Optional[List] = None,
    extent: Optional[QgsRectangle] = None,
    crs=None,
    title: str = "",
    subtitle: str = "",
    credits: str = "",
    page_size: str = "A4",
    landscape: bool = True,
    add_title: bool = True,
    add_legend: bool = True,
    add_scalebar: bool = True,
    add_north_arrow: bool = True,
    add_grid: bool = False,
    add_frame: bool = True,
    preset: str = "swiss_modern",
    layout_name: str = "CartoLab Map Sheet",
    project: Optional[QgsProject] = None,
    template: Optional[str] = None,
) -> QgsPrintLayout:
    """
    Build and register a finished publication-ready map sheet or template archetype.

    Every element is optional via the ``add_*`` switches. Inputs left as
    ``None`` are resolved from ``iface`` (canvas layers / extent / CRS).
    Supports typography and styling presets ('swiss_modern', 'academic_serif', 'technical_blueprint', 'editorial_warm').
    If ``template`` is specified ('report_figure', 'academic_journal', 'poster_exhibition', 'fact_sheet', 'side_by_side_diptych'),
    delegates directly to the corresponding Template Gallery builder.

    Returns the :class:`QgsPrintLayout`, already added to the project's
    layout manager.
    """
    if template:
        from .template_gallery import create_template_layout
        return create_template_layout(
            template,
            iface=iface,
            layers=layers,
            extent=extent,
            crs=crs,
            title=title or "CartoLab Map Sheet",
            subtitle=subtitle,
            credits=credits or "Cartography: Geophilo · PlanX CartoLab",
            layout_name=layout_name,
            project=project,
        )

    project = project or QgsProject.instance()
    layers = layers if layers is not None else _resolve_layers(iface, project)
    if crs is None:
        crs = _resolve_crs(iface, project, layers)
    extent = extent if extent is not None else _resolve_extent(
        iface, layers, target_crs=crs, project=project
    )

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(unique_layout_name(project, layout_name))

    page_w, page_h = page_size_mm(page_size, landscape)
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(page_w, page_h, _MM))

    # --- geometry budget (millimetres) -----------------------------------
    margin = 12.0
    gap = 4.0
    title_h = 16.0 if add_title else 0.0
    legend_w = 58.0 if add_legend else 0.0
    bottom_h = 13.0 if (add_scalebar or credits) else 0.0

    map_x = margin
    map_y = margin + (title_h + gap if add_title else 0.0)
    right_reserve = (legend_w + gap) if add_legend else 0.0
    bottom_reserve = (bottom_h + gap) if bottom_h else 0.0
    map_w = page_w - 2 * margin - right_reserve
    map_h = page_h - map_y - margin - bottom_reserve

    # --- map frame -------------------------------------------------------
    map_item = QgsLayoutItemMap(layout)
    map_item.setId("cartolab_map")
    map_item.attemptResize(QgsLayoutSize(map_w, map_h, _MM))
    map_item.attemptMove(QgsLayoutPoint(map_x, map_y, _MM))
    if crs is not None and crs.isValid():
        map_item.setCrs(crs)
    if extent is not None and not extent.isEmpty():
        zoom_map_to_extent(map_item, extent)
    if layers:
        map_item.setLayers(_order_layers_rasters_bottom(layers))
        map_item.setKeepLayerSet(True)
    if add_frame:
        map_item.setFrameEnabled(True)
        map_item.setFrameStrokeColor(QColor("#333333"))
        map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, _MM))
    layout.addLayoutItem(map_item)

    if add_grid:
        from .coordinate_grid import apply_coordinate_grid_decorator
        # Annotations go inside the frame: the sheet leaves only a 4 mm gap
        # between the map and the legend / scale bar / credits.
        apply_coordinate_grid_decorator(
            layout,
            main_map=map_item,
            target_divisions_x=6,
            target_divisions_y=5,
            grid_style="Solid",
            frame_style="Zebra",
            show_annotations=True,
            annotations_inside=True,
        )

    # --- title / subtitle ------------------------------------------------
    if add_title:
        text = title or project.title() or "Map"
        label = QgsLayoutItemLabel(layout)
        label.setId("cartolab_title")
        label.setText(text)
        label.setBackgroundEnabled(False)
        label.setFrameEnabled(False)
        label.setFont(_font(18, bold=True))
        label.setFontColor(QColor("#0f172a"))
        label.attemptMove(QgsLayoutPoint(margin, margin, _MM))
        label.attemptResize(QgsLayoutSize(page_w - 2 * margin, 9.0, _MM))
        layout.addLayoutItem(label)

        if subtitle:
            sub = QgsLayoutItemLabel(layout)
            sub.setId("cartolab_subtitle")
            sub.setText(subtitle)
            sub.setBackgroundEnabled(False)
            sub.setFrameEnabled(False)
            sub.setFont(_font(9.5))
            sub.setFontColor(QColor("#475569"))
            sub.attemptMove(QgsLayoutPoint(margin, margin + 9.5, _MM))
            sub.attemptResize(QgsLayoutSize(page_w - 2 * margin, 5.5, _MM))
            layout.addLayoutItem(sub)

    # --- legend ----------------------------------------------------------
    legend = None
    if add_legend:
        legend = QgsLayoutItemLegend(layout)
        legend.setId("cartolab_legend")
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)
        legend.setResizeToContents(True)
        legend.setBackgroundEnabled(False)
        legend.setFrameEnabled(False)
        legend.setTitle("")
        if hasattr(legend, "rstyle"):
            with suppress(Exception):
                _set_legend_typography(legend, 9.0)
        _sync_legend_layers(legend, layers)
        legend.attemptMove(QgsLayoutPoint(map_x + map_w + gap, map_y, _MM))
        legend.attemptResize(QgsLayoutSize(legend_w, map_h, _MM))
        layout.addLayoutItem(legend)
        # Fit text and symbols to the actual sidebar instead of merely clipping
        # an oversized natural legend at its boundary.
        with suppress(Exception):
            _fit_legend_to_box(legend, legend_w, map_h)

    # --- scale bar -------------------------------------------------------
    if add_scalebar:
        bar = QgsLayoutItemScaleBar(layout)
        bar.setId("cartolab_scalebar")
        bar.setLinkedMap(map_item)
        bar.applyDefaultSettings()
        bar.setStyle("Line Ticks Up" if preset == "swiss_modern" else "Single Box")
        bar.applyDefaultSize()

        bar.setNumberOfSegments(3)
        bar.setNumberOfSegmentsLeft(0)
        bar.setBackgroundEnabled(False)
        bar.setFrameEnabled(False)
        _configure_scalebar(
            bar,
            map_item,
            project,
            max_width_mm=max(32.0, map_w * 0.32),
            target_segments=3,
        )
        with suppress(Exception):
            tf_sb = bar.textFormat()
            tf_sb.setFont(_font(8.0))
            tf_sb.setColor(QColor("#0f172a"))
            bar.setTextFormat(tf_sb)
        bar.attemptMove(
            QgsLayoutPoint(map_x, map_y + map_h + gap, _MM)
        )
        layout.addLayoutItem(bar)

    # --- north arrow -----------------------------------------------------
    if add_north_arrow:
        _add_north_arrow(layout, map_x + map_w - 16.0, map_y + 4.0)

    # --- credits ---------------------------------------------------------
    if credits:
        cred = QgsLayoutItemLabel(layout)
        cred.setId("cartolab_credits")
        cred.setText(credits)
        cred.setBackgroundEnabled(False)
        cred.setFrameEnabled(False)
        cred.setFont(_font(8))
        cred.setFontColor(QColor("#64748b"))
        cred.attemptResize(QgsLayoutSize(map_w * 0.6, bottom_h, _MM))
        cred.attemptMove(
            QgsLayoutPoint(map_x + map_w * 0.4, map_y + map_h + gap, _MM)
        )
        layout.addLayoutItem(cred)

    # Apply paper theme and typography hierarchy preset if specified
    if preset:
        with suppress(Exception):
            from .typography_engine import apply_typography_hierarchy
            apply_typography_hierarchy(layout, preset=preset)
        with suppress(Exception):
            from .paper_themes import apply_paper_theme
            apply_paper_theme(layout, theme_key=preset)

    # Typography themes may restyle legend text, so fit once more after every
    # theme has run. This is the final authority on the sidebar dimensions.
    if legend is not None:
        _fit_legend_to_box(legend, legend_w, map_h)

    project.layoutManager().addLayout(layout)
    layout.refresh()
    return layout


def _add_north_arrow(layout, x: float, y: float, size: float = 12.0) -> None:
    """Add a crisp vector north arrow with Segoe UI typography."""
    _add_drawn_north_arrow(layout, x, y, size)


def _add_drawn_north_arrow(layout, x: float, y: float, size: float = 12.0, color: str = "#0f172a") -> None:
    """Vector north arrow: a filled triangle plus an 'N' label."""
    half = size / 2.0
    poly = QPolygonF([
        QPointF(x + half, y),
        QPointF(x + size, y + size),
        QPointF(x + half, y + size * 0.72),
        QPointF(x, y + size),
    ])
    arrow = QgsLayoutItemPolygon(poly, layout)
    arrow.setId("cartolab_north_arrow")
    arrow.setBackgroundEnabled(False)
    arrow.setFrameEnabled(False)
    outline_col = "#0f172a" if str(color).lower() in ("#ffffff", "#f8fafc", "#e2e8f0", "white") else "#ffffff"
    if QgsFillSymbol:
        sym = QgsFillSymbol.createSimple({
            "color": color, "outline_color": outline_col, "outline_width": "0.35",
        })
        if sym:
            arrow.setSymbol(sym)
    layout.addLayoutItem(arrow)

    label = QgsLayoutItemLabel(layout)
    label.setId("cartolab_north_arrow_label")
    label.setText("N")
    label.setBackgroundEnabled(False)
    label.setFrameEnabled(False)
    label.setFont(_font(8.5, bold=True))
    label.setFontColor(QColor(color))
    with suppress(Exception):
        tf = label.textFormat()
        tf.setFont(_font(8.5, bold=True))
        tf.setColor(QColor(color))
        buf = tf.buffer()
        buf.setEnabled(True)
        buf.setSize(0.75)
        buf.setColor(QColor(outline_col))
        buf.setOpacity(0.9)
        tf.setBuffer(buf)
        label.setTextFormat(tf)
    label.setHAlign(Qt.AlignmentFlag.AlignHCenter)
    label.setVAlign(Qt.AlignmentFlag.AlignVCenter)
    label.attemptResize(QgsLayoutSize(size, 4.5, _MM))
    label.attemptMove(QgsLayoutPoint(x, y - 4.5, _MM))
    layout.addLayoutItem(label)
