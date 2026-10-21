# -*- coding: utf-8 -*-
"""Real-QGIS smoke test for the plugin UI (dashboard, inspector tool, unload).

Run headless, with the directory that contains the ``zero2cartolab`` package on
PYTHONPATH::

    QT_QPA_PLATFORM=offscreen PYTHONPATH=<parent-of-zero2cartolab> python3 tests/qgis_ui_smoke.py

Exits non-zero when any check fails.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

for _p in ("/usr/share/qgis/python/plugins", "/usr/lib/qgis/python/plugins"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
try:
    from processing.core.Processing import Processing
    Processing.initialize()
except Exception as _exc:  # pragma: no cover - environment dependent
    print("WARN: Processing init failed:", _exc)

_repo = Path(__file__).resolve().parents[1]
if _repo.name == "zero2cartolab" and str(_repo.parent) not in sys.path:
    sys.path.insert(0, str(_repo.parent))

from qgis.gui import QgsMapCanvas, QgsMapToolPan  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication, QEvent, QObject, Qt, pyqtSignal  # noqa: E402
from qgis.PyQt.QtGui import QKeyEvent  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow, QMessageBox, QToolBar  # noqa: E402

try:
    from qgis.PyQt import sip
except ImportError:  # pragma: no cover
    import sip  # type: ignore

# ── Non-blocking message boxes ─────────────────────────────────────────
MSGBOXES = []


def _fake_box(kind):
    def _f(parent, title, text, *a, **k):
        MSGBOXES.append((kind, title, text))
        return QMessageBox.StandardButton.Yes
    return _f


for _k in ("information", "warning", "critical", "question"):
    setattr(QMessageBox, _k, staticmethod(_fake_box(_k)))


# ── Minimal fake iface ────────────────────────────────────────────────
class _Sig(QObject):
    opened = pyqtSignal(object)


class _MsgBar:
    def __init__(self):
        self.log = []

    def _push(kind):  # noqa: N805
        def f(self, title, text, *a, **k):
            self.log.append((kind, text))
        return f

    pushSuccess = _push("ok")
    pushInfo = _push("info")
    pushWarning = _push("warn")
    pushCritical = _push("crit")

    def pushMessage(self, *a, **k):
        self.log.append(("msg", a))


class _Designer:
    def __init__(self, window):
        self._w = window

    def window(self):
        return self._w

    def layout(self):
        return None


class FakeIface:
    def __init__(self):
        self.mw = QMainWindow()
        self.tb = QToolBar("Plugins")
        self.mw.addToolBar(self.tb)
        self.menus = {}
        self.canvas = QgsMapCanvas(self.mw)
        self.mb = _MsgBar()
        self._sig = _Sig()
        self.layoutDesignerOpened = self._sig.opened
        self.designers = []
        self.active = None

    def mainWindow(self):
        return self.mw

    def addToolBarIcon(self, a):
        self.tb.addAction(a)

    def removeToolBarIcon(self, a):
        self.tb.removeAction(a)

    def addPluginToMenu(self, name, a):
        self.menus.setdefault(name, []).append(a)

    def removePluginMenu(self, name, a):
        self.menus.get(name, []).remove(a)

    def messageBar(self):
        return self.mb

    def mapCanvas(self):
        return self.canvas

    def layoutDesigners(self):
        return list(self.designers)

    def activeLayer(self):
        return self.active


# ── Check bookkeeping ─────────────────────────────────────────────────
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"ok   {name}")
    else:
        print(f"FAIL {name} {detail}")
        FAILURES.append(name)


def flush_deletes():
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _deleted(obj):
    try:
        return sip.isdeleted(obj)
    except Exception:
        return False


def _receivers(obj, signal_name):
    with_sig = getattr(obj, signal_name)
    try:
        return obj.receivers(with_sig)
    except Exception:
        return -1


def mem_layer(uri, name, feats):
    lyr = QgsVectorLayer(uri, name, "memory")
    out = []
    for geom, attrs in feats:
        f = QgsFeature(lyr.fields())
        if geom is not None:
            f.setGeometry(geom)
        f.setAttributes(attrs)
        out.append(f)
    lyr.dataProvider().addFeatures(out)
    lyr.updateExtents()
    return lyr


def main() -> int:
    import zero2cartolab
    from zero2cartolab.ui import cartolab_dashboard as dash_mod
    from zero2cartolab.processing.alg_quick_style import QuickStyleAlgorithm
    from zero2cartolab.core.sun_lighting import solar_to_25d_lighting
    from zero2cartolab.core.qgis_25d_style import HEIGHT_MODE_FLOOR_COUNT, HEIGHT_MODE_HEIGHT
    from zero2cartolab.ui import floating_annotation as fa

    print("QGIS", Qgis.QGIS_VERSION)
    proj = QgsProject.instance()
    base_added = _receivers(proj, "layersAdded")
    base_removed = _receivers(proj, "layersRemoved")

    iface = FakeIface()
    plg = zero2cartolab.classFactory(iface)
    plg.initGui()

    # Layers: polygons near Sydney (southern hemisphere), a floors layer, a table.
    def sq(x, y, d=0.001):
        return QgsGeometry.fromRect(QgsRectangle(x, y, x + d, y + d))
    poly = mem_layer("Polygon?crs=EPSG:4326&field=pop:double&field=name:string&field=h:double",
                     "polys", [(sq(151.20 + i * 0.002, -33.87), [float(i * i), f"n{i % 3}", h])
                               for i, h in enumerate((10.0, 20.0, 30.0, 20.0, 40.0))])
    floors = mem_layer("Polygon?crs=EPSG:4326&field=id:integer&field=Levels:integer",
                       "floors", [(sq(10.0, 50.0), [1, 4])])
    table = mem_layer("None?field=v:double", "table", [(None, [1.0])])
    proj.addMapLayers([poly, floors, table])

    # A9: count on a never-shown dashboard (isVisible() would be False for all cards).
    hidden_dash = dash_mod.CartoLabDashboard(iface, iface.mw)
    n_cards = len(hidden_dash.card_widgets)
    check("A9 hub count correct before any filter edit",
          n_cards > 0 and hidden_dash.card_count.text() == f"Visible: {n_cards}/{n_cards}",
          hidden_dash.card_count.text())
    hidden_dash.search.setText("zzzz-no-such-algorithm")
    check("A9 hub count follows filter", hidden_dash.card_count.text() == f"Visible: 0/{n_cards}",
          hidden_dash.card_count.text())
    hidden_dash.search.setText("")

    plg.open_dashboard()
    d = plg.dialog

    # A6: no geometry-less tables in vector layer pickers.
    qs_names = [d.qs_layer_combo.itemText(i) for i in range(d.qs_layer_combo.count())]
    check("A6 non-spatial table excluded", "table" not in qs_names and "polys" in qs_names, qs_names)

    # A2: method combo mirrors the algorithm and the selected method is the one run.
    labels = [d.qs_method_combo.itemText(i) for i in range(d.qs_method_combo.count())]
    check("A2 method combo == algorithm METHODS",
          labels == [m[0] for m in QuickStyleAlgorithm.METHODS], labels)
    captured = []

    class _ProcStub:
        @staticmethod
        def run(alg_id, params, *a, **k):
            captured.append(params)
            return {"SUMMARY": "stub"}
    real_processing = dash_mod.processing
    dash_mod.processing = _ProcStub()
    try:
        d.qs_layer_combo.setCurrentIndex(d.qs_layer_combo.findData(poly.id()))
        d.qs_field_combo.setCurrentText("pop")
        mismatches = []
        for i, (label, _key) in enumerate(QuickStyleAlgorithm.METHODS):
            d.qs_method_combo.setCurrentIndex(d.qs_method_combo.findText(label))
            d._on_apply_quick_style()
            sent = captured[-1]["METHOD"] if captured else None
            if sent is None or QuickStyleAlgorithm.METHODS[sent][0] != label:
                mismatches.append((label, sent))
        check("A2 every choice runs the named method", not mismatches, mismatches)
    finally:
        dash_mod.processing = real_processing

    # A8: palette selection survives a filter-driven rebuild.
    d.qs_kind_combo.setCurrentIndex(0)
    d.qs_cbsafe_check.setChecked(False)
    d.qs_palette_combo.setCurrentIndex(min(5, d.qs_palette_combo.count() - 1))
    before = d.qs_palette_combo.currentData()
    d._populate_qs_palettes()
    check("A8 palette kept after rebuild", d.qs_palette_combo.currentData() == before,
          (before, d.qs_palette_combo.currentData()))

    # A11: overview and readiness are separate and both populated.
    d._refresh()
    check("A11 readiness has its own widget", d.readiness is not d.overview)
    check("A11 overview content kept", "Loaded layers" in d.overview.toPlainText(),
          d.overview.toPlainText()[:80])
    check("A11 readiness content", "Tool coverage" in d.readiness.toPlainText())

    # A10: sun angles use the layer latitude and convert units correctly.
    d.show_panel("2.5d")
    idx = d.layer25d_combo.findData(poly.id())
    check("A10 polygon layer listed for 2.5D", idx >= 0,
          [d.layer25d_combo.itemText(i) for i in range(d.layer25d_combo.count())])
    if idx >= 0:
        d.layer25d_combo.setCurrentIndex(idx)
        d._refresh_25d_fields()
        d.height25d_combo.setCurrentIndex(d.height25d_combo.findData("h"))
        d.mode25d_combo.setCurrentIndex(d.mode25d_combo.findData(HEIGHT_MODE_HEIGHT))
        d.scale25d_spin.setValue(1.0)
        d.max25d_spin.setValue(0)
        d.solar_time_combo.setCurrentIndex(d.solar_time_combo.findData("afternoon_studio"))
        lat = poly.extent().center().y()  # layer is EPSG:4326, Sydney (~ -33.87)
        d._on_apply_sun_lighting()
        last = iface.mb.log[-1][1] if iface.mb.log else ""
        check("A10 latitude from layer extent", f"{lat:.2f}" in str(last), last)
        ref = solar_to_25d_lighting(latitude_deg=lat, season="equinox", time_preset="afternoon_studio")
        exp_angle = round((90.0 - ref["shadow_angle_deg"]) % 360.0, 1)
        exp_spread = round(ref["shadow_length_mult"] * 20.0, 2)  # median height 20
        check("A10 projection angle = shadow direction",
              abs(d.angle25d_spin.value() - exp_angle) < 0.11,
              (d.angle25d_spin.value(), exp_angle, ref["solar_altitude_deg"]))
        check("A10 spread scaled by building height",
              abs(d.shadow_spread25d_spin.value() - exp_spread) < 0.011,
              (d.shadow_spread25d_spin.value(), exp_spread))

        # Minor: floor auto-detect does nothing on a layer without a floor field ...
        d.mode25d_combo.setCurrentIndex(d.mode25d_combo.findData(HEIGHT_MODE_HEIGHT))
        d._on_25d_auto_estimate_height()
        check("auto-detect leaves mode when no floor field",
              d.mode25d_combo.currentData() == HEIGHT_MODE_HEIGHT
              and iface.mb.log and iface.mb.log[-1][0] == "warn")
    # ... and finds a (case-insensitive) 'Levels' field.
    fidx = d.layer25d_combo.findData(floors.id())
    if fidx >= 0:
        d.layer25d_combo.setCurrentIndex(fidx)
        d._refresh_25d_fields()
        d.mode25d_combo.setCurrentIndex(d.mode25d_combo.findData(HEIGHT_MODE_HEIGHT))
        d._on_25d_auto_estimate_height()
        check("auto-detect picks Levels + floor mode",
              d.height25d_combo.currentData() == "Levels"
              and d.mode25d_combo.currentData() == HEIGHT_MODE_FLOOR_COUNT,
              (d.height25d_combo.currentData(), d.mode25d_combo.currentData()))
    else:
        check("floors layer listed for 2.5D", False)

    # Minor: Ctrl+F switches to the Processing Hub page before focusing search.
    d.nav_sidebar.setCurrentRow(0)
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    d.keyPressEvent(ev)
    page = d.stack.currentWidget()
    check("Ctrl+F shows search page", page is not None and page.isAncestorOf(d.search)
          and d.nav_sidebar.currentRow() == d.stack.currentIndex())

    # A5: inspector honours layer CRS, render order and visibility.
    canvas = iface.canvas
    canvas.resize(800, 600)
    canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
    wgs = QgsCoordinateReferenceSystem("EPSG:4326")
    p4326 = QgsPointXY(27.14, 38.42)
    p3857 = QgsCoordinateTransform(wgs, canvas.mapSettings().destinationCrs(), proj).transform(p4326)
    bottom = mem_layer("Point?crs=EPSG:4326&field=v:double", "pts4326",
                       [(QgsGeometry.fromPointXY(p4326), [5.0])])
    top = mem_layer("Point?crs=EPSG:3857&field=v:double", "pts3857",
                    [(QgsGeometry.fromPointXY(p3857), [1.0])])
    proj.addMapLayers([bottom, top])
    canvas.setLayers([top, bottom])  # first = topmost
    canvas.setExtent(QgsRectangle(p3857.x() - 1000, p3857.y() - 1000, p3857.x() + 1000, p3857.y() + 1000))
    tool = fa.FloatingAnnotationTool(iface, canvas)
    shown = []
    tool._show_feature_card = lambda lyr, f: shown.append(lyr.name())
    tool._inspect_at(p3857)
    check("A5 topmost layer wins", shown == ["pts3857"], shown)
    proj.layerTreeRoot().findLayer(top.id()).setItemVisibilityChecked(False)
    shown.clear()
    tool._inspect_at(p3857)
    check("A5 hidden layer skipped, 4326 layer hit from 3857 canvas", shown == ["pts4326"], shown)
    proj.layerTreeRoot().findLayer(top.id()).setItemVisibilityChecked(True)

    # A7: menu action follows the active map tool.
    plg.action_annotate.trigger()
    check("A7 action on activates tool", plg.action_annotate.isChecked()
          and canvas.mapTool() is plg.annotation_tool)
    pan = QgsMapToolPan(canvas)
    canvas.setMapTool(pan)
    check("A7 action unchecked when another tool takes over", not plg.action_annotate.isChecked())
    plg.action_annotate.trigger()
    check("A7 single click re-activates", plg.action_annotate.isChecked()
          and canvas.mapTool() is plg.annotation_tool)
    plg.action_annotate.trigger()
    check("A7 click again deactivates", not plg.action_annotate.isChecked()
          and canvas.mapTool() is not plg.annotation_tool)

    # A3 + A4: unload cleans dialogs, project signals and designer menus; no growth on reload.
    if hasattr(hidden_dash, "disconnect_project_signals"):
        hidden_dash.disconnect_project_signals()
    hidden_dash.deleteLater()
    flush_deletes()
    dwin = QMainWindow()
    dtb = QToolBar("mLayoutToolbar")
    dtb.setObjectName("mLayoutToolbar")
    dwin.addToolBar(dtb)
    iface.designers = [_Designer(dwin)]
    plg.unload()
    flush_deletes()

    def cartolab_menus():
        return [a for a in dwin.menuBar().actions() if a.text() == "&02CartoLab"]

    for cycle in range(3):
        p = zero2cartolab.classFactory(iface)
        p.initGui()
        QCoreApplication.processEvents()
        p.open_dashboard()
        p.open_welcome()
        p.welcome._on_dashboard()  # routes to the plugin-owned dashboard
        check(f"A3 welcome reuses plugin dashboard (cycle {cycle + 1})",
              len([w for w in iface.mw.findChildren(dash_mod.CartoLabDashboard)
                   if not _deleted(w) and w.isVisible()]) == 1)
        check(f"A4 one designer menu while loaded (cycle {cycle + 1})", len(cartolab_menus()) == 1,
              len(cartolab_menus()))
        dlg, wel = p.dialog, p.welcome
        p.unload()
        flush_deletes()
        check(f"A3 dashboard deleted on unload (cycle {cycle + 1})", _deleted(dlg))
        check(f"A3 welcome deleted on unload (cycle {cycle + 1})", wel is None or _deleted(wel))
        check(f"A3 project signals detached (cycle {cycle + 1})",
              _receivers(proj, "layersAdded") == base_added
              and _receivers(proj, "layersRemoved") == base_removed,
              (_receivers(proj, "layersAdded"), base_added))
        check(f"A4 designer menu removed on unload (cycle {cycle + 1})", len(cartolab_menus()) == 0,
              len(cartolab_menus()))

    crit = [m for m in MSGBOXES if m[0] == "critical"]
    check("no critical message boxes", not crit, crit)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:
        traceback.print_exc()
        rc = 2
    print("RESULT:", "PASS" if rc == 0 else f"FAIL ({len(FAILURES)} checks)")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
