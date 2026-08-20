# -*- coding: utf-8 -*-
"""
First-run welcome for PlanX CartoLab.

Delivers value in the first few seconds after install: one button builds a
fully-styled sample map sheet from an in-memory demo layer (no bundled data),
so a new user sees what CartoLab does before reading anything.
"""
from __future__ import annotations

import math
from contextlib import suppress

from qgis.PyQt.QtCore import QUrl, QSettings, QVariant
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsFields,
    QgsGraduatedSymbolRenderer,
    QgsRendererRange,
    QgsFillSymbol,
)

HUB_URL = "https://plugins.qgis.org/plugins/zero2cartolab/"
_SEEN_KEY = "zero2cartolab/seen_welcome"

# ColorBrewer "Blues" (5-class) — previews the Sprint 1 palette library.
_DEMO_RAMP = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]


def should_show(settings: QSettings = None) -> bool:
    """True the first time only."""
    settings = settings or QSettings()
    return not settings.value(_SEEN_KEY, False, type=bool)


def mark_seen(settings: QSettings = None) -> None:
    settings = settings or QSettings()
    settings.setValue(_SEEN_KEY, True)


def build_demo_layer(name: str = "CartoLab Sample") -> QgsVectorLayer:
    """
    Build an in-memory polygon grid whose values form a smooth radial pattern,
    so the sample choropleth looks like real data rather than noise. No files
    are written and nothing is bundled in the plugin.
    """
    layer = QgsVectorLayer("Polygon?crs=EPSG:3857", name, "memory")
    dp = layer.dataProvider()
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))
    fields.append(QgsField("value", QVariant.Double))
    dp.addAttributes(fields)
    layer.updateFields()

    cell, cols, rows = 1000.0, 9, 6
    cx, cy = cols * cell / 2.0, rows * cell / 2.0
    feats = []
    for j in range(rows):
        for i in range(cols):
            x0, y0 = i * cell, j * cell
            ring = [
                QgsPointXY(x0, y0), QgsPointXY(x0 + cell, y0),
                QgsPointXY(x0 + cell, y0 + cell), QgsPointXY(x0, y0 + cell),
                QgsPointXY(x0, y0),
            ]
            mx, my = x0 + cell / 2.0, y0 + cell / 2.0
            dist = math.hypot(mx - cx, my - cy)
            value = round(100.0 * math.exp(-(dist ** 2) / (2 * (2200.0 ** 2))), 1)
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPolygonXY([ring]))
            f.setAttributes([j * cols + i, value])
            feats.append(f)
    dp.addFeatures(feats)
    layer.updateExtents()
    return layer


def apply_demo_style(layer: QgsVectorLayer, field: str = "value") -> None:
    """Apply a 5-class graduated Blues renderer to the demo layer."""
    values = sorted(f[field] for f in layer.getFeatures())
    if not values:
        return
    lo, hi = values[0], values[-1]
    span = (hi - lo) or 1.0
    n = len(_DEMO_RAMP)
    ranges = []
    for k, colour in enumerate(_DEMO_RAMP):
        a = lo + span * k / n
        b = lo + span * (k + 1) / n
        sym = QgsFillSymbol.createSimple({
            "color": colour, "outline_color": "#ffffff", "outline_width": "0.2",
        })
        ranges.append(QgsRendererRange(a, b, sym, f"{a:.0f} – {b:.0f}"))
    layer.setRenderer(QgsGraduatedSymbolRenderer(field, ranges))


def create_sample_map(iface, project: QgsProject = None):
    """Build + style the demo layer and assemble a finished map sheet."""
    project = project or QgsProject.instance()
    layer = build_demo_layer()
    apply_demo_style(layer)
    project.addMapLayer(layer)
    from ..layout.map_sheet import create_map_sheet
    return create_map_sheet(
        iface=iface,
        layers=[layer],
        title="02CartoLab Sample Map",
        subtitle="A styled choropleth with legend, scale bar and north arrow",
        credits="Demo data · 02CartoLab",
        add_grid=True,
    )


class WelcomeDialog(QDialog):
    """Shown once on first run; also reachable from the dashboard."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("Welcome to 02CartoLab")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self) -> None:
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(20, 18, 20, 16)
        lyt.setSpacing(10)

        title = QLabel("Publication-quality maps, fast.")
        title.setStyleSheet("font-size:17px;font-weight:700;color:#1b2733;")
        lyt.addWidget(title)

        body = QLabel(
            "CartoLab turns ordinary layers into thematic maps and finished "
            "print layouts — choropleths, bivariate maps, cartograms, hexbins "
            "and one-click map sheets with a legend, scale bar and north arrow.\n\n"
            "See it in five seconds:"
        )
        body.setWordWrap(True)
        body.setStyleSheet("color:#40515e;")
        lyt.addWidget(body)

        btn_sample = QPushButton("★  Create a sample map")
        btn_sample.setStyleSheet(
            "QPushButton{background:#3182bd;color:#fff;font-weight:700;"
            "padding:9px 14px;border-radius:6px;}"
            "QPushButton:hover{background:#2b6ca3;}"
        )
        btn_sample.clicked.connect(self._on_sample)
        lyt.addWidget(btn_sample)

        row = QHBoxLayout()
        btn_dash = QPushButton("Open the Dashboard")
        btn_dash.clicked.connect(self._on_dashboard)
        btn_rate = QPushButton("Rate CartoLab ⭐")
        btn_rate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(HUB_URL)))
        row.addWidget(btn_dash)
        row.addWidget(btn_rate)
        lyt.addLayout(row)

        foot = QHBoxLayout()
        foot.addStretch()
        btn_close = QPushButton("Maybe later")
        btn_close.setFlat(True)
        btn_close.clicked.connect(self.close)
        foot.addWidget(btn_close)
        lyt.addLayout(foot)

    def _on_sample(self) -> None:
        try:
            layout = create_sample_map(self.iface)
            if hasattr(self.iface, "openLayoutDesigner"):
                self.iface.openLayoutDesigner(layout)
            if hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushSuccess(
                    "CartoLab", "Sample map created — this is what CartoLab does.")
        except Exception as exc:  # pragma: no cover - defensive
            if hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushWarning("CartoLab", str(exc))
        self.close()

    def _on_dashboard(self) -> None:
        self.close()
        with suppress(Exception):  # pragma: no cover - defensive
            from .cartolab_dashboard import CartoLabDashboard
            dlg = CartoLabDashboard(self.iface, self.iface.mainWindow())
            dlg.show()

    def closeEvent(self, event) -> None:
        mark_seen()
        super().closeEvent(event)
