# -*- coding: utf-8 -*-
"""
Floating Annotation Tool — Click-to-inspect feature with HTML charts.

Implements a QgsMapTool that intercepts canvas clicks, extracts
indicator values from the clicked feature, builds an HTML radar-chart
card via html_graph_factory, and shows it in a bordered popup dialog.
"""
from __future__ import annotations

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.core import (
        QgsPointXY, QgsGeometry, QgsMapLayer, QgsProject, QgsRectangle, QgsFeatureRequest,
    )
    from qgis.gui import QgsMapTool
except ImportError:
    QDialog = QVBoxLayout = QHBoxLayout = QPushButton = QLabel = None
    Qt = QgsPointXY = QgsGeometry = QgsMapLayer = QgsProject = QgsRectangle = QgsFeatureRequest = None
    QgsMapTool = object


class AnnotationDialog(QDialog if QDialog else object):
    """Frameless floating dialog showing an HTML annotation card."""

    def __init__(self, iface, html: str, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("CartoLab — Feature Inspector")
        self.setMinimumSize(340, 280)
        self.resize(380, 340)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
        )
        self._build(html)

    def _build(self, html: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # render HTML — try QWebEngineView first (QGIS 4), fall back
        web_view = None
        try:
            from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
            web_view = QWebEngineView()
            web_view.setHtml(html)
            web_view.setMinimumHeight(260)
        except ImportError:
            pass

        if web_view is None:
            try:
                from qgis.PyQt.QtWebKitWidgets import QWebView
                web_view = QWebView()
                web_view.setHtml(html)
                web_view.setMinimumHeight(260)
            except ImportError:
                pass

        if web_view is None:
            # pure text fallback
            lbl = QLabel("HTML rendering not available.\n\nInstall PyQtWebEngine for rich charts.")
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
        else:
            layout.addWidget(web_view, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        btn_row.setContentsMargins(8, 4, 8, 8)
        layout.addLayout(btn_row)


class FloatingAnnotationTool(QgsMapTool):
    """
    Map tool: click a feature to see its indicator profile as a radar chart.

    Usage from main_plugin::

        self.annotation_tool = FloatingAnnotationTool(iface, canvas)
        canvas.setMapTool(self.annotation_tool)
    """

    def __init__(self, iface, canvas):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.cursor = Qt.CursorShape.CrossCursor

    def activate(self):
        # super() keeps the associated QAction (setAction) checked state in sync
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self):
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        super().deactivate()

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self._inspect_at(point)

    def _visible_vector_layers(self):
        """Spatial vector layers the canvas renders, topmost first, hidden ones skipped."""
        root = QgsProject.instance().layerTreeRoot()
        scale = self.canvas.scale()
        out = []
        for lyr in self.canvas.layers():  # render order: first = topmost
            if lyr is None or lyr.type() != QgsMapLayer.LayerType.VectorLayer or not lyr.isSpatial():
                continue
            node = root.findLayer(lyr.id()) if root is not None else None
            if node is not None and not node.isVisible():
                continue
            if lyr.hasScaleBasedVisibility() and not lyr.isInScaleRange(scale):
                continue
            out.append(lyr)
        return out

    def _to_layer_crs(self, layer, rect, point):
        """Canvas-CRS rect/point in *layer* CRS; (None, None) if not transformable."""
        try:
            return self.toLayerCoordinates(layer, rect), self.toLayerCoordinates(layer, point)
        except Exception:  # QgsCsException: click outside the layer CRS bounds
            return None, None

    def _inspect_at(self, point: QgsPointXY) -> None:
        layers = self._visible_vector_layers()
        if not layers:
            self.iface.messageBar().pushWarning(
                "CartoLab", "No visible vector layers on the map."
            )
            return

        # small search radius in canvas (map) units, transformed per layer CRS
        radius = self.canvas.mapUnitsPerPixel() * 8
        search_rect = QgsRectangle(
            point.x() - radius, point.y() - radius,
            point.x() + radius, point.y() + radius
        )
        for layer in layers:
            layer_rect, layer_pt = self._to_layer_crs(layer, search_rect, point)
            if layer_rect is None or layer_rect.isEmpty():
                continue
            rect_geom = QgsGeometry.fromRect(layer_rect)
            pt_geom = QgsGeometry.fromPointXY(layer_pt)
            best = None
            req = QgsFeatureRequest().setFilterRect(layer_rect)
            for feat in layer.getFeatures(req):
                geom = feat.geometry()
                if geom.isNull() or geom.isEmpty() or not geom.intersects(rect_geom):
                    continue
                dist = geom.distance(pt_geom)
                if best is None or dist < best[0]:
                    best = (dist, feat)
            if best is not None:
                self._show_feature_card(layer, best[1])
                return

        self.iface.messageBar().pushInfo(
            "CartoLab", "No feature found at click location."
        )

    def _show_feature_card(self, layer, feat) -> None:
        """Build an HTML card and show it in a dialog."""
        fields = layer.fields()

        # extract numeric fields as metrics
        metrics = {}
        labels = []
        values = []
        for field in fields:
            name = field.name()
            val = feat[name]
            if val is None:
                continue
            try:
                fval = float(val)
                metrics[name] = fval
                labels.append(name)
                values.append(fval)
            except (ValueError, TypeError):
                # non-numeric — show as string in metrics
                metrics[name] = str(val)

        # normalize values 0..1 for radar
        if values:
            vmax = max(values) or 1
            vmin = min(values)
            vrange = vmax - vmin if vmax != vmin else 1
            normed = [(v - vmin) / vrange for v in values]
        else:
            normed = []

        # get feature display name
        feat_name = f"{layer.name()} — FID {feat.id()}"

        from ..core.html_graph_factory import build_floating_card
        html = build_floating_card(
            title=feat_name,
            metrics={k: v for k, v in list(metrics.items())[:8]},
            indicator_labels=labels[:8] if labels else None,
            indicator_values=normed[:8] if normed else None,
        )

        dlg = AnnotationDialog(self.iface, html, self.iface.mainWindow())
        dlg.exec()
