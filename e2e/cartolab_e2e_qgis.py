# -*- coding: utf-8 -*-
"""
End-to-end real-QGIS test for zero2cartolab — runs all Processing
algorithms in a genuine QGIS Python environment (not stubs) and asserts
numeric correctness on the six new cartography algorithms.

Run:
    C:/OSGeo4W/bin/python-qgis-ltr.bat scratch/cartolab_e2e_qgis.py
    C:/OSGeo4W/bin/python-qgis.bat      scratch/cartolab_e2e_qgis.py
"""
import os
import sys
import tempfile
import traceback
from contextlib import suppress
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# line-buffer stdout so PASS/FAIL lines survive the os._exit() hard exit
with suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)

from qgis.core import QgsApplication

qgs = QgsApplication([], False)
qgs.initQgis()

# Headless OSGeo4W does not always discover system fonts. Register a small
# fallback set so visual-regression PNGs contain readable text, not tofu boxes.
from qgis.PyQt.QtGui import QFontDatabase
font_roots = [
    Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts",
    Path("/usr/share/fonts/truetype/dejavu"),
]
for font_root in font_roots:
    for font_name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        font_path = font_root / font_name
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))

import qgis
# The Processing plugin ships next to the qgis package on Windows (OSGeo4W)
# and in /usr/share/qgis/python/plugins on Linux packages and Docker images.
for system_plugins_dir in (
    os.path.abspath(os.path.join(os.path.dirname(qgis.__file__), "..", "plugins")),
    "/usr/share/qgis/python/plugins",
):
    if os.path.isdir(os.path.join(system_plugins_dir, "processing")):
        if system_plugins_dir in sys.path:
            sys.path.remove(system_plugins_dir)
        sys.path.insert(0, system_plugins_dir)
        break
source_parent = str(Path(__file__).resolve().parents[2])
if source_parent not in sys.path:
    sys.path.append(source_parent)

import processing
from processing.core.Processing import Processing
Processing.initialize()





from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsFeature,
    QgsGeometry, QgsPointXY, QgsProcessingContext, QgsProcessingFeedback,
    QgsProcessingUtils, QgsProject, QgsRectangle, QgsVectorLayer, QgsRasterLayer,
)

print(f"QGIS version: {Qgis.QGIS_VERSION}")

try:
    from qgis.core import NULL as NULL_VALUE
except ImportError:  # QGIS builds without the NULL alias
    NULL_VALUE = None

from zero2cartolab.processing.cartolab_provider import CartoLabProvider
from zero2cartolab.core.dot_density import dots_for_value

_prov = CartoLabProvider()  # keep a reference so it is not GC'd
QgsApplication.processingRegistry().addProvider(_prov)

# Regression guard: prevent silent algorithm-count drift
_algo_count = len(list(_prov.algorithms()))
assert _algo_count == 16, f"expected 16 algorithms, got {_algo_count}"
print(f"Provider algorithm count: {_algo_count} (pinned at 16)\n")
assert all(alg.helpUrl() == 'https://github.com/YusufEminoglu/zero2cartolab#module-catalog' for alg in _prov.algorithms()), 'helpUrl regression detected'

CRS = "EPSG:3857"
fails = []
passed = 0


def ok(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        fails.append(f"{name}: {detail}")
        print(f"  FAIL  {name}: {detail}")


def run(algo_id, params, label):
    ctx = QgsProcessingContext()
    ctx.setProject(QgsProject.instance())
    algorithm = QgsApplication.processingRegistry().algorithmById(algo_id)
    try:
        res = processing.run(algo_id, params, context=ctx, feedback=QgsProcessingFeedback())
    except Exception as exc:
        traceback.print_exc()
        fails.append(f"{label}: raised {exc}")
        return None, ctx
    out = {}
    for k, v in res.items():
        output_def = algorithm.outputDefinition(k) if algorithm is not None else None
        layer_output = (
            output_def is not None
            and output_def.__class__.__name__ in {
                "QgsProcessingOutputMapLayer",
                "QgsProcessingOutputRasterLayer",
                "QgsProcessingOutputVectorLayer",
            }
        )
        if layer_output and isinstance(v, str):
            lyr = QgsProcessingUtils.mapLayerFromString(v, ctx)
            if not lyr:
                matches = QgsProject.instance().mapLayersByName(v.replace("memory:", ""))
                if matches:
                    lyr = matches[0]
            if not lyr:
                lyr = QgsProject.instance().mapLayer(v)
            if lyr is not None:
                out[k] = lyr
                continue
        out[k] = v
    return out, ctx


# ---------------------------------------------------------------------------
# Synthetic inputs
# ---------------------------------------------------------------------------
CELL = 1000.0
N = 5  # 5x5 grid -> extent 0..5000


def build_polygons(crs=CRS, origin_x=0.0, origin_y=0.0, name="units"):
    lyr = QgsVectorLayer(
        f"Polygon?crs={crs}&field=uid:integer&field=count:double"
        "&field=pop:double&field=score:double&field=floors:integer",
        name, "memory")
    dp = lyr.dataProvider()
    feats = []
    for j in range(N):
        for i in range(N):
            uid = j * N + i
            x0, y0 = origin_x + i * CELL, origin_y + j * CELL
            ring = [QgsPointXY(x0, y0), QgsPointXY(x0 + CELL, y0),
                    QgsPointXY(x0 + CELL, y0 + CELL), QgsPointXY(x0, y0 + CELL),
                    QgsPointXY(x0, y0)]
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPolygonXY([ring]))
            pop = 0.0 if uid == 12 else 1000.0 + uid * 100.0
            f.setAttributes([uid, (uid + 1) * 50.0, pop, uid * 3.0 + 1.0, (uid % 6) + 1])
            feats.append(f)
    dp.addFeatures(feats)
    lyr.updateExtents()
    return lyr


def build_points():
    lyr = QgsVectorLayer(f"Point?crs={CRS}&field=weight:double", "pts", "memory")
    dp = lyr.dataProvider()
    feats = []
    import random
    rng = random.Random(123)
    for _ in range(200):
        # two clusters so several hex cells are occupied
        cx, cy = (1200, 1200) if rng.random() < 0.5 else (3600, 3200)
        x = cx + rng.uniform(-800, 800)
        y = cy + rng.uniform(-800, 800)
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        f.setAttributes([rng.uniform(1, 10)])
        feats.append(f)
    dp.addFeatures(feats)
    lyr.updateExtents()
    return lyr


def build_raster():
    from osgeo import gdal, osr
    path = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_dem_{os.getpid()}.tif")
    if os.path.exists(path):
        with suppress(Exception):
            os.remove(path)
    w = h = 60
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(path, w, h, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([0.0, 5000.0 / w, 0.0, 5000.0, 0.0, -5000.0 / h])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    rows = []
    for r in range(h):
        row = []
        for c in range(w):
            dx, dy = c - w / 2.0, r - h / 2.0
            row.append(100.0 * (2.718 ** (-(dx * dx + dy * dy) / 400.0)))
        rows.append(row)
    import struct
    for r in range(h):
        band.WriteRaster(0, r, w, 1, struct.pack(f"<{w}f", *rows[r]))
    band.FlushCache()
    ds = None
    return path


polys = build_polygons()
points = build_points()
QgsProject.instance().addMapLayer(polys)
QgsProject.instance().addMapLayer(points)
raster_path = build_raster()
rlayer = QgsRasterLayer(raster_path, "dem")
QgsProject.instance().addMapLayer(rlayer)
ok("raster valid", rlayer.isValid(), raster_path)

# expected dot total from the same pure-python function
counts = [(uid + 1) * 50.0 for uid in range(N * N)]
expected_dots = sum(dots_for_value(c, 100.0) for c in counts)

# ===========================================================================
# NEW ALGORITHMS (numeric asserts)
# ===========================================================================
print("\n--- New algorithms ---")

# 1) Dot density
out, _ = run("zero2cartolab:dot_density",
             {"INPUT": polys, "FIELD": "count", "VALUE_PER_DOT": 100.0,
              "SEED": 42, "OUTPUT": "memory:"}, "dot_density")
if out:
    lyr = out["OUTPUT"]
    ok("dot_density total == expected", lyr.featureCount() == expected_dots,
       f"{lyr.featureCount()} vs {expected_dots}")
    # every dot must fall inside the polygon union
    union = QgsGeometry.unaryUnion([f.geometry() for f in polys.getFeatures()])
    inside = all(union.contains(f.geometry()) for f in lyr.getFeatures())
    ok("dot_density all dots inside polygons", inside)

# 2) Proportional symbols (on polygons -> centroids)
out, _ = run("zero2cartolab:proportional_symbols",
             {"INPUT": polys, "FIELD": "score", "MAX_SIZE": 12.0, "MIN_SIZE": 1.0,
              "FLANNERY": True, "OUTPUT": "memory:"}, "proportional_symbols")
if out:
    lyr = out["OUTPUT"]
    ok("proportional count == input", lyr.featureCount() == 25, str(lyr.featureCount()))
    sizes = [f["psym_size"] for f in lyr.getFeatures()]
    ok("proportional max size == MAX_SIZE", abs(max(sizes) - 12.0) < 1e-6, str(max(sizes)))
    ok("proportional sizes within bounds", all(1.0 - 1e-9 <= s <= 12.0 + 1e-9 for s in sizes))

# 3) Hexbin
out, _ = run("zero2cartolab:hexbin_aggregate",
             {"INPUT": points, "CELL_SIZE": 600.0, "WEIGHT": "weight", "STAT": 1,
              "OUTPUT": "memory:"}, "hexbin_aggregate")
if out:
    lyr = out["OUTPUT"]
    total_count = sum(f["hex_count"] for f in lyr.getFeatures())
    ok("hexbin conserves points", total_count == 200, f"{total_count} vs 200")
    ok("hexbin produced multiple cells", lyr.featureCount() >= 2, str(lyr.featureCount()))
    ok("hexbin mean == sum/count",
       all(abs(f["hex_mean"] - f["hex_sum"] / f["hex_count"]) < 1e-6 for f in lyr.getFeatures()))

# 4) Label points
out, _ = run("zero2cartolab:label_points",
             {"INPUT": polys, "PRECISION": 0.0, "OUTPUT": "memory:"}, "label_points")
if out:
    lyr = out["OUTPUT"]
    ok("label_points count == input", lyr.featureCount() == 25, str(lyr.featureCount()))
    geom_by_uid = {f["uid"]: f.geometry() for f in polys.getFeatures()}
    all_in = all(geom_by_uid[f["uid"]].contains(f.geometry()) for f in lyr.getFeatures())
    ok("label_points inside own polygon", all_in)
    ok("label_points dist ~ 500 for square cells",
       all(abs(f["lbl_dist"] - 500.0) < 25.0 for f in lyr.getFeatures()))

# 5) Graticule
out, _ = run("zero2cartolab:graticule_grid",
             {"EXTENT": f"0,5000,0,5000 [{CRS}]", "X_INTERVAL": 1000.0,
              "Y_INTERVAL": 1000.0, "OUTPUT": "memory:"}, "graticule_grid")
if out:
    lyr = out["OUTPUT"]
    ok("graticule line count == 12", lyr.featureCount() == 12, str(lyr.featureCount()))
    orients = sorted(f["orientation"] for f in lyr.getFeatures())
    ok("graticule 6 meridians + 6 parallels",
       orients.count("meridian") == 6 and orients.count("parallel") == 6, str(orients))

# 6) Normalize (rate)
out, _ = run("zero2cartolab:normalize_field",
             {"INPUT": polys, "FIELD": "score", "METHOD": 0, "DENOMINATOR": "pop",
              "SCALE": 1000.0, "OUTPUT": "memory:"}, "normalize_field")
if out:
    lyr = out["OUTPUT"]
    by_uid = {f["uid"]: f for f in lyr.getFeatures()}
    f0 = by_uid[0]
    ok("normalize rate uid0 == score/pop*1000", abs(f0["norm_value"] - 1.0) < 1e-9,
       str(f0["norm_value"]))
    ok("normalize zero-denominator -> NULL", by_uid[12]["norm_value"] in (None,) or
       str(by_uid[12]["norm_value"]) == "NULL", str(by_uid[12]["norm_value"]))

# Normalize (z-score) mean ~ 0
out, _ = run("zero2cartolab:normalize_field",
             {"INPUT": polys, "FIELD": "score", "METHOD": 1, "SCALE": 1.0,
              "OUTPUT": "memory:"}, "normalize_field_z")
if out:
    lyr = out["OUTPUT"]
    zs = [f["norm_value"] for f in lyr.getFeatures() if f["norm_value"] is not None]
    ok("normalize z-score mean ~ 0", abs(sum(zs) / len(zs)) < 1e-6, str(sum(zs) / len(zs)))

# Normalize (robust IQR)
out, _ = run("zero2cartolab:normalize_field",
             {"INPUT": polys, "FIELD": "score", "METHOD": 3, "PALETTE": 0, "CLASSES": 5,
              "OUTPUT": "memory:"}, "normalize_field_robust_iqr")
if out:
    lyr = out["OUTPUT"]
    ok("normalize robust IQR output valid", lyr is not None and lyr.featureCount() == 25)

# 7) Bivariate Matrix Export
out_bme, _ = run("zero2cartolab:bivariate_matrix_export",
                 {"CLASSES": 3, "PALETTE_PRESET": 0, "DIAMOND": False, "CELL_SIZE": 50.0,
                  "OUTPUT": "memory:"}, "bivariate_matrix_export_square")
if out_bme:
    lyr = out_bme["OUTPUT"]
    ok("bivariate matrix square count == 9", lyr.featureCount() == 9, str(lyr.featureCount()))
    ok("bivariate matrix has bivar_class and hex_color",
       lyr.fields().indexFromName("bivar_class") >= 0 and lyr.fields().indexFromName("hex_color") >= 0)
    ok("bivariate matrix HTML table generated",
       isinstance(out_bme.get("OUTPUT_HTML"), str) and "<table" in out_bme.get("OUTPUT_HTML", ""))

out_bme_d, _ = run("zero2cartolab:bivariate_matrix_export",
                   {"CLASSES": 4, "PALETTE_PRESET": 1, "DIAMOND": True, "CELL_SIZE": 40.0,
                    "OUTPUT": "memory:"}, "bivariate_matrix_export_diamond")
if out_bme_d:
    lyr = out_bme_d["OUTPUT"]
    ok("bivariate matrix diamond count == 16", lyr.featureCount() == 16, str(lyr.featureCount()))

# ===========================================================================
# EXISTING ALGORITHMS (smoke)
# ===========================================================================
print("\n--- Existing algorithms ---")

out, _ = run("zero2cartolab:geometric_interval_classification",
             {"INPUT": polys, "FIELD": "score", "CLASSES": 5, "METHOD": 0,
              "OUTPUT": "memory:"}, "classification")
ok("classification output", out is not None and out["OUTPUT"].featureCount() == 25)

out_sd, _ = run("zero2cartolab:geometric_interval_classification",
                {"INPUT": polys, "FIELD": "score", "CLASSES": 5, "METHOD": 3,
                 "OUTPUT": "memory:"}, "classification_std_dev")
ok("classification std dev output", out_sd is not None and out_sd["OUTPUT"].featureCount() == 25)

out_bp, _ = run("zero2cartolab:geometric_interval_classification",
                {"INPUT": polys, "FIELD": "score", "CLASSES": 5, "METHOD": 4,
                 "OUTPUT": "memory:"}, "classification_box_plot")
ok("classification box plot output", out_bp is not None and out_bp["OUTPUT"].featureCount() == 25)

out, _ = run("zero2cartolab:bivariate_choropleth",
             {"INPUT": polys, "FIELD_X": "score", "FIELD_Y": "count", "CLASSES": 4,
              "METHOD": 0, "OUTPUT": "memory:"}, "bivariate")
ok("bivariate output", out is not None and out["OUTPUT"].featureCount() == 25
   and out["OUTPUT"].fields().indexFromName("bivar_class") >= 0)

out, _ = run("zero2cartolab:value_by_alpha",
             {"INPUT": polys, "FIELD_COLOUR": "score", "FIELD_ALPHA": "pop",
              "ALPHA_MIN": 25, "ALPHA_MAX": 255, "OUTPUT": "memory:"}, "value_by_alpha")
ok("value_by_alpha output", out is not None and out["OUTPUT"].featureCount() == 25
   and out["OUTPUT"].fields().indexFromName("vba_alpha") >= 0)

out, _ = run("zero2cartolab:compute_cartogram",
             {"INPUT": polys, "FIELD": "count", "MAX_ITERATIONS": 8, "MAX_ERROR": 10.0,
              "OUTPUT": "memory:"}, "cartogram")
ok("cartogram output", out is not None and out["OUTPUT"].featureCount() > 0)

out, _ = run("zero2cartolab:ridge_map",
             {"RASTER": rlayer, "N_LINES": 20, "VERTICAL_SCALE": 1.0,
              "LINE_SPACING": 1.0, "SMOOTH": 2, "OUTPUT": "memory:"}, "ridge_map")
ok("ridge_map output", out is not None and out["OUTPUT"].featureCount() > 0)

out, _ = run("zero2cartolab:building_25d_style",
             {"INPUT": polys, "HEIGHT_FIELD": "floors", "HEIGHT_MODE": 1,
              "FLOOR_HEIGHT": 3.5, "RENDER_MODE": 0, "PRESET": 0}, "building_25d_style")
ok("building_25d_style summary", out is not None and isinstance(out.get("SUMMARY"), str)
   and len(out.get("SUMMARY", "")) > 10)

# ---------------------------------------------------------------------------
# Quick Style — one-click graduated / categorized renderer
# ---------------------------------------------------------------------------
print("\n--- Quick Style ---")
from qgis.core import QgsGraduatedSymbolRenderer, QgsCategorizedSymbolRenderer

run("zero2cartolab:quick_style",
    {"INPUT": polys, "FIELD": "score", "MODE": 1, "CLASSES": 5, "METHOD": 0,
     "PALETTE": 0, "REVERSE": False, "OUTLINE": True}, "quick_style_graduated")
ok("quick_style applies graduated renderer with 5 classes",
   isinstance(polys.renderer(), QgsGraduatedSymbolRenderer)
   and len(polys.renderer().ranges()) == 5, str(type(polys.renderer()).__name__))

run("zero2cartolab:quick_style",
    {"INPUT": polys, "FIELD": "floors", "MODE": 2, "CLASSES": 5, "METHOD": 0,
     "PALETTE": 0, "REVERSE": False, "OUTLINE": True}, "quick_style_categorized")
ok("quick_style applies categorized renderer",
   isinstance(polys.renderer(), QgsCategorizedSymbolRenderer)
   and len(polys.renderer().categories()) >= 2, str(type(polys.renderer()).__name__))

# Monochrome print-safe patterns
_qs = processing.run("zero2cartolab:quick_style",
    {"INPUT": polys, "FIELD": "score", "MODE": 1, "CLASSES": 5, "METHOD": 0,
     "PALETTE": 0, "REVERSE": False, "OUTLINE": True, "MONOCHROME": True})
_mono = polys.renderer()
_mono_ranges = _mono.ranges() if isinstance(_mono, QgsGraduatedSymbolRenderer) else []
_kinds = [[type(_mono_ranges[i].symbol().symbolLayer(k)).__name__
           for k in range(_mono_ranges[i].symbol().symbolLayerCount())]
          for i in range(len(_mono_ranges))]
ok("monochrome graduated: 5 classes from blank to solid",
   len(_kinds) == 5 and _kinds[0] == ["QgsSimpleFillSymbolLayer", "QgsSimpleFillSymbolLayer"]
   and _mono_ranges[-1].symbol().color().name() == "#000000", str(_kinds))
ok("monochrome graduated: pattern layers sit between ground and outline",
   all(k[0] == "QgsSimpleFillSymbolLayer" and k[-1] == "QgsSimpleFillSymbolLayer" for k in _kinds)
   and any("LinePatternFill" in n for k in _kinds for n in k)
   and any("PointPatternFill" in n for k in _kinds for n in k), str(_kinds))
ok("monochrome graduated: summary says patterns", "monochrome" in _qs["SUMMARY"], _qs["SUMMARY"])
_qs = processing.run("zero2cartolab:quick_style",
    {"INPUT": polys, "FIELD": "floors", "MODE": 2, "PALETTE": 0, "REVERSE": False,
     "OUTLINE": True, "MONOCHROME": True})
_mono_cats = polys.renderer().categories()  # keep the copies alive: they own the symbols
_cat_syms = [c.symbol() for c in _mono_cats]
_sigs = {tuple((type(s.symbolLayer(k)).__name__,
                round(getattr(s.symbolLayer(k), "lineAngle", lambda: -1)(), 1))
               for k in range(s.symbolLayerCount())) for s in _cat_syms}
ok("monochrome categories: every category gets a distinct texture",
   len(_cat_syms) == 6 and len(_sigs) == 6, f"{len(_cat_syms)} cats, {len(_sigs)} textures")
_qs = processing.run("zero2cartolab:quick_style",
    {"INPUT": points, "FIELD": "weight", "MODE": 1, "CLASSES": 5, "METHOD": 0,
     "PALETTE": 0, "REVERSE": False, "OUTLINE": True, "MONOCHROME": True})
ok("monochrome on points falls back to a grey ramp", "Greys" in _qs["SUMMARY"], _qs["SUMMARY"])

# ---------------------------------------------------------------------------
# Output symbology reaches the loaded layer for temporary AND file outputs.
# Styling inside processAlgorithm only ever reached memory layers; a GeoPackage
# result is re-read from disk on load and arrived as a plain single symbol.
# ---------------------------------------------------------------------------
print("\n--- Output symbology survives file outputs ---")
from qgis.core import QgsSingleSymbolRenderer, QgsWkbTypes
from qgis.PyQt.QtCore import Qt

_style_dir = tempfile.mkdtemp(prefix="cartolab_style_")


_style_loaded_ids = []


def _loaded(algo, params, kind, stem=None):
    p = dict(params)
    p["OUTPUT"] = ("TEMPORARY_OUTPUT" if kind == "memory"
                   else os.path.join(_style_dir, f"{stem or algo}.gpkg"))
    before = set(QgsProject.instance().mapLayers())
    try:
        processing.runAndLoadResults(f"zero2cartolab:{algo}", p)
    except Exception as exc:
        traceback.print_exc()
        return None, str(exc)
    new_ids = set(QgsProject.instance().mapLayers()) - before
    _style_loaded_ids.extend(new_ids)
    new = [QgsProject.instance().mapLayer(i) for i in new_ids]
    return (new[0] if new else None), f"{len(new)} layers loaded"


def _vba_opacity_is_data_defined(layer):
    if not isinstance(layer.renderer(), QgsGraduatedSymbolRenderer):
        return False
    # ranges() returns copies that own their symbols: keep the list alive, or
    # symbol() is a dangling pointer (segfaults QGIS 4).
    ranges = layer.renderer().ranges()
    return bool(ranges) and ranges[0].symbol().dataDefinedProperties().hasActiveProperties()


def _dd_size(layer):
    sym = layer.renderer().symbol() if isinstance(layer.renderer(), QgsSingleSymbolRenderer) else None
    return sym is not None and sym.dataDefinedSize().isActive()


_style_cases = [
    ("hexbin_aggregate",
     {"INPUT": points, "CELL_SIZE": 600.0, "WEIGHT": "weight", "STAT": 1},
     lambda l: isinstance(l.renderer(), QgsGraduatedSymbolRenderer)
     and l.renderer().classAttribute() == "hex_sum" and len(l.renderer().ranges()) >= 2),
    ("normalize_field",
     {"INPUT": polys, "FIELD": "score", "METHOD": 1, "SCALE": 1.0},
     lambda l: isinstance(l.renderer(), QgsGraduatedSymbolRenderer)
     and l.renderer().classAttribute() == "norm_value"),
    ("geometric_interval_classification",
     {"INPUT": polys, "FIELD": "score", "CLASSES": 5, "METHOD": 0},
     lambda l: isinstance(l.renderer(), QgsGraduatedSymbolRenderer)
     and len(l.renderer().ranges()) == 5),
    ("bivariate_choropleth",
     {"INPUT": polys, "FIELD_X": "score", "FIELD_Y": "count", "CLASSES": 3, "METHOD": 0},
     lambda l: isinstance(l.renderer(), QgsCategorizedSymbolRenderer)
     and l.renderer().classAttribute() == "bivar_class"
     and len(l.renderer().categories()) == 9),
    ("value_by_alpha",
     {"INPUT": polys, "FIELD_COLOUR": "score", "FIELD_ALPHA": "pop",
      "ALPHA_MIN": 25, "ALPHA_MAX": 255},
     _vba_opacity_is_data_defined),
    ("compute_cartogram",
     {"INPUT": polys, "FIELD": "count", "MAX_ITERATIONS": 4, "MAX_ERROR": 10.0},
     lambda l: isinstance(l.renderer(), QgsGraduatedSymbolRenderer)),
    ("bivariate_matrix_export",
     {"CLASSES": 3, "PALETTE_PRESET": 0, "DIAMOND": False, "CELL_SIZE": 50.0},
     lambda l: isinstance(l.renderer(), QgsCategorizedSymbolRenderer)
     and len(l.renderer().categories()) == 9),
    ("proportional_symbols",
     {"INPUT": polys, "FIELD": "score", "MAX_SIZE": 12.0, "MIN_SIZE": 1.0, "FLANNERY": True},
     _dd_size),
    ("dot_density",
     {"INPUT": polys, "FIELD": "count", "VALUE_PER_DOT": 100.0, "SEED": 42},
     lambda l: isinstance(l.renderer(), QgsSingleSymbolRenderer)
     and l.renderer().symbol().symbolLayer(0).strokeStyle() == Qt.PenStyle.NoPen),
]
for _algo, _params, _check in _style_cases:
    for _kind in ("memory", "gpkg"):
        _lyr, _info = _loaded(_algo, _params, _kind)
        _desc = type(_lyr.renderer()).__name__ if _lyr is not None else _info
        ok(f"{_algo} styled on load ({_kind})",
           _lyr is not None and bool(_check(_lyr)), _desc)

_carto_lyr, _ = _loaded("compute_cartogram",
                        {"INPUT": polys, "FIELD": "count", "MAX_ITERATIONS": 4,
                         "MAX_ERROR": 10.0}, "gpkg", stem="cartogram_multitype")
ok("cartogram GeoPackage declares a multi-polygon layer",
   _carto_lyr is not None and QgsWkbTypes.isMultiType(_carto_lyr.wkbType()),
   QgsWkbTypes.displayString(_carto_lyr.wkbType()) if _carto_lyr else "no layer")
# ---------------------------------------------------------------------------
# Origin-destination flow map
# ---------------------------------------------------------------------------
print("\n--- Flow map ---")
import math as _math

od = QgsVectorLayer("None?field=o:string&field=d:integer&field=v:double", "od", "memory")
_od_rows = [("0", 24, 100.0), ("0", 24, 50.0), ("24", 0, 30.0), ("3", 3, 99.0),
            ("5", 999, 40.0), ("1", 2, 10.0), ("7.0", 8, 0.0)]
_od_feats = []
for _o, _d, _v in _od_rows:
    _f = QgsFeature(od.fields())
    _f.setAttributes([_o, _d, _v])
    _od_feats.append(_f)
od.dataProvider().addFeatures(_od_feats)
_zone_pt = {f["uid"]: f.geometry().pointOnSurface().asPoint() for f in polys.getFeatures()}

_flow_params = {"ZONES": polys, "ZONE_ID": "uid", "FLOWS": od, "ORIGIN": "o",
                "DEST": "d", "VOLUME": "v", "CURVATURE": 0.25, "MAX_WIDTH": 5.0,
                "MIN_WIDTH": 0.5, "END_GAP": 5.0, "OUTPUT": "memory:"}
out, _ = run("zero2cartolab:flow_map", dict(_flow_params), "flow_map_directed")
if out:
    lyr = out["OUTPUT"]
    by_pair = {(f["flow_o"], f["flow_d"]): f for f in lyr.getFeatures()}
    ok("flow map: duplicates summed, self-flow / zero / unknown zone dropped",
       sorted(by_pair) == [("0", "24"), ("1", "2"), ("24", "0")], str(sorted(by_pair)))
    if ("0", "24") in by_pair and ("24", "0") in by_pair:
        fwd, back = by_pair[("0", "24")], by_pair[("24", "0")]
        ok("flow map: largest pair has rank 1 and full width",
           fwd["flow_vol"] == 150.0 and fwd["flow_rank"] == 1
           and abs(fwd["flow_width"] - 5.0) < 1e-9, f"{fwd['flow_vol']} {fwd['flow_rank']} {fwd['flow_width']}")
        ok("flow map: width is linear in volume",
           abs(back["flow_width"] - (0.5 + 4.5 * 30.0 / 150.0)) < 1e-6, str(back["flow_width"]))
        ok("flow map: shares sum to 100%",
           abs(sum(f["flow_share"] for f in lyr.getFeatures()) - 100.0) < 1e-2)
        # opposite directions bend to opposite sides of the chord
        a, b = _zone_pt[0], _zone_pt[24]
        def _side(feat):
            g = feat.geometry()
            line = g.asMultiPolyline()[0] if g.isMultipart() else g.asPolyline()
            m = line[len(line) // 2]
            return (b.x() - a.x()) * (m.y() - a.y()) - (b.y() - a.y()) * (m.x() - a.x())
        ok("flow map: A->B and B->A are separate arcs on opposite sides",
           _side(fwd) * _side(back) < 0, f"{_side(fwd)} {_side(back)}")
        chord = _math.hypot(b.x() - a.x(), b.y() - a.y())
        _fg = fwd.geometry()
        start = (_fg.asMultiPolyline()[0] if _fg.isMultipart() else _fg.asPolyline())[0]
        ok("flow map: end gap trims 5% of the chord along the curve",
           abs(_math.hypot(start.x() - a.x(), start.y() - a.y()) - 0.05 * chord) < 0.01 * chord,
           f"{_math.hypot(start.x() - a.x(), start.y() - a.y()):.1f} vs {0.05 * chord:.1f}")
    r = lyr.renderer()
    # Keep the list alive: a symbol read from a temporary ranges() copy is
    # freed with it, and symbolLayerCount() then reads freed memory.
    _ranges = r.ranges() if isinstance(r, QgsGraduatedSymbolRenderer) else []
    ok("flow map: graduated renderer draws large flows first with arrowheads",
       isinstance(r, QgsGraduatedSymbolRenderer) and r.orderByEnabled()
       and _ranges and _ranges[0].symbol().symbolLayerCount() == 2,
       type(r).__name__)

_undirected = dict(_flow_params, DIRECTED=False)
out, _ = run("zero2cartolab:flow_map", _undirected, "flow_map_two_way")
if out:
    vols = sorted(f["flow_vol"] for f in out["OUTPUT"].getFeatures())
    ok("flow map: two-way mode merges directions", vols == [10.0, 180.0], str(vols))

out, _ = run("zero2cartolab:flow_map", dict(_flow_params, TOP_N=1), "flow_map_top1")
if out:
    ok("flow map: top-N keeps the largest", out["OUTPUT"].featureCount() == 1
       and next(out["OUTPUT"].getFeatures())["flow_vol"] == 150.0)

# ---------------------------------------------------------------------------
# Dorling circle cartogram
# ---------------------------------------------------------------------------
print("\n--- Dorling cartogram ---")
out, _ = run("zero2cartolab:dorling_cartogram",
             {"INPUT": polys, "FIELD": "count", "SIZE_FACTOR": 0.6, "OUTPUT": "memory:"},
             "dorling_cartogram")
if out:
    lyr = out["OUTPUT"]
    circles = list(lyr.getFeatures())
    ok("dorling: one circle per positive value", len(circles) == 25, str(len(circles)))
    ratios = [c.geometry().area() / c["dor_value"] for c in circles]
    ok("dorling: circle area proportional to value",
       max(ratios) / min(ratios) < 1.001, f"{min(ratios):.2f}..{max(ratios):.2f}")
    poly_area = sum(f.geometry().area() for f in polys.getFeatures())
    ok("dorling: total circle area = size factor x layer area (within 1%)",
       abs(sum(c.geometry().area() for c in circles) / (0.6 * poly_area) - 1.0) < 0.01)
    worst = 0.0
    for i, ci in enumerate(circles):
        for cj in circles[i + 1:]:
            if ci.geometry().intersects(cj.geometry()):
                worst = max(worst, ci.geometry().intersection(cj.geometry()).area())
    ok("dorling: circles do not overlap (<0.5% of the smallest circle)",
       worst < 0.005 * min(c.geometry().area() for c in circles), f"worst overlap {worst:.1f}")
    ok("dorling: residual output reported", out.get("RESIDUAL", 1.0) <= 0.01, str(out.get("RESIDUAL")))

# later layout tests build legends from the project: leave it as we found it
QgsProject.instance().removeMapLayers(_style_loaded_ids)

# ===========================================================================
# AUDIT REGRESSIONS (core + processing fixes)
# ===========================================================================
print("\n--- Audit regressions ---")


def _is_null(v):
    return v is None or v == NULL_VALUE or (hasattr(v, "isNull") and v.isNull())


def _mem(geom_type, fields, rows, name="reg"):
    lyr = QgsVectorLayer(f"{geom_type}?crs={CRS}&" + "&".join(f"field={n}:{t}" for n, t in fields),
                         name, "memory")
    feats = []
    for wkt, attrs in rows:
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromWkt(wkt))
        f.setAttributes(attrs)
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    return lyr


def _sq(x, y, s=10):
    return f"POLYGON(({x} {y},{x + s} {y},{x + s} {y + s},{x} {y + s},{x} {y}))"


# 1) Ridge map reads block.value(row, col) and zeroes NoData
def _ridge_raster():
    from osgeo import gdal, osr
    import struct
    path = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_ridge_{os.getpid()}.tif")
    ds = gdal.GetDriverByName("GTiff").Create(path, 4, 3, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([0.0, 100.0, 0.0, 300.0, 0.0, -100.0])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(3857)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    for r in range(3):
        vals = [r * 10.0 + c for c in range(4)]
        if r == 1:
            vals[2] = -9999.0
        band.WriteRaster(0, r, 4, 1, struct.pack("<4f", *vals))
    band.FlushCache()
    ds = None
    return path


try:
    from zero2cartolab.core.style_transformer import generate_ridge_lines
    _rr = QgsRasterLayer(_ridge_raster(), "ridge_reg")
    _rl = generate_ridge_lines(_rr, n_lines=3, vertical_scale=1.0, smooth_iterations=0)
    _offs = {}
    for _f in _rl.getFeatures():
        _base = [0.0, 150.0, 300.0][_f["line_id"]]
        _offs[_f["line_id"]] = [round(v.y() - _base, 6) for v in _f.geometry().vertices()]
    ok("ridge: top scanline follows raster row 0 (row, col order)",
       _offs.get(2) == [0.0, 1.0, 2.0, 3.0], str(_offs.get(2)))
    ok("ridge: bottom scanline follows the last raster row",
       _offs.get(0) == [20.0, 21.0, 22.0, 23.0], str(_offs.get(0)))
    ok("ridge: NoData cell gives no deformation",
       _offs.get(1) == [10.0, 11.0, 0.0, 13.0], str(_offs.get(1)))
except Exception as _exc:
    traceback.print_exc()
    ok("ridge: row/col + NoData regression", False, repr(_exc))

_reg_polys = _mem("Polygon", [("v", "double")],
                  [(_sq(i * 10, 0), [float(v) if v is not None else None])
                   for i, v in enumerate([1, 2, 3, 10, 11, 12, None])])

# 2/3/6) Advanced Classification keeps NULL features; Jenks upper bounds
out, _ = run("zero2cartolab:geometric_interval_classification",
             {"INPUT": _reg_polys, "FIELD": "v", "CLASSES": 2, "METHOD": 2, "OUTPUT": "memory:"},
             "gic_null")
if out:
    _feats = list(out["OUTPUT"].getFeatures())
    _rows = {f["v"]: f["gic_class"] for f in _feats if not _is_null(f["v"])}
    _null_rows = [f for f in _feats if _is_null(f["v"])]
    ok("classification keeps NULL features", len(_feats) == 7, str(len(_feats)))
    ok("classification NULL feature has NULL class and label",
       len(_null_rows) == 1 and _is_null(_null_rows[0]["gic_class"]) and _is_null(_null_rows[0]["gic_label"]))
    ok("classification Jenks classes use upper bounds (3 low, 10 high)",
       _rows.get(3.0) == 0 and _rows.get(10.0) == 1, str(_rows))

_seq = _mem("Polygon", [("v", "double")], [(_sq(i * 10, 0), [float(i)]) for i in range(70)])
for _mi in range(7):
    out, _ = run("zero2cartolab:geometric_interval_classification",
                 {"INPUT": _seq, "FIELD": "v", "CLASSES": 4, "METHOD": _mi, "OUTPUT": "memory:"},
                 f"gic_method_{_mi}")
    if out:
        _cls = {f["v"]: f["gic_class"] for f in out["OUTPUT"].getFeatures()}
        ok(f"classification method {_mi}: maximum value is in the top class",
           _cls[69.0] == max(_cls.values()) and _cls[69.0] > 0, str(_cls[69.0]))

# 9) labels follow the class count
out, _ = run("zero2cartolab:geometric_interval_classification",
             {"INPUT": _seq, "FIELD": "v", "CLASSES": 7, "METHOD": 2, "OUTPUT": "memory:"}, "gic_7")
if out:
    _pairs = {(f["gic_class"], f["gic_label"]) for f in out["OUTPUT"].getFeatures()}
    ok("classification 7 classes -> 7 distinct labels",
       len(_pairs) == 7 and len({lab for _, lab in _pairs}) == 7, str(sorted(_pairs)))
    ok("classification top class labelled highest", (6, "Very High") in _pairs, str(sorted(_pairs)))

# 5) Re-running on own output overwrites the computed fields
out1, _ = run("zero2cartolab:normalize_field",
              {"INPUT": _seq, "FIELD": "v", "METHOD": 1, "OUTPUT": "memory:"}, "norm_first")
if out1:
    out2, _ = run("zero2cartolab:normalize_field",
                  {"INPUT": out1["OUTPUT"], "FIELD": "v", "METHOD": 4, "OUTPUT": "memory:"}, "norm_rerun")
    if out2:
        _l2 = out2["OUTPUT"]
        _vals = {f["v"]: (f["norm_value"], f["norm_method"]) for f in _l2.getFeatures()}
        ok("normalize rerun overwrites norm_value / norm_method",
           abs(_vals[69.0][0] - 1.0) < 1e-9 and _vals[0.0][0] == 0.0 and _vals[0.0][1] == "minmax",
           str(_vals[0.0]))
        ok("normalize rerun does not duplicate fields",
           _l2.fields().count() == out1["OUTPUT"].fields().count(), str(_l2.fields().names()))

_rerun_cases = [
    ("geometric_interval_classification", {"FIELD": "v", "CLASSES": 2, "METHOD": 6},
     {"FIELD": "v", "CLASSES": 5, "METHOD": 6}, "gic_class"),
    ("bivariate_choropleth", {"FIELD_X": "v", "FIELD_Y": "v", "CLASSES": 2, "METHOD": 3},
     {"FIELD_X": "v", "FIELD_Y": "v", "CLASSES": 4, "METHOD": 3}, "bivar_class"),
    ("value_by_alpha", {"FIELD_COLOUR": "v", "FIELD_ALPHA": "v", "ALPHA_MIN": 10, "ALPHA_MAX": 100},
     {"FIELD_COLOUR": "v", "FIELD_ALPHA": "v", "ALPHA_MIN": 120, "ALPHA_MAX": 255}, "vba_alpha"),
    ("proportional_symbols", {"FIELD": "v", "MAX_SIZE": 5.0, "MIN_SIZE": 1.0},
     {"FIELD": "v", "MAX_SIZE": 20.0, "MIN_SIZE": 2.0}, "psym_size"),
]
for _alg, _p1, _p2, _fld in _rerun_cases:
    _o1, _ = run(f"zero2cartolab:{_alg}", dict(_p1, INPUT=_seq, OUTPUT="memory:"), f"{_alg}_first")
    _fresh, _ = run(f"zero2cartolab:{_alg}", dict(_p2, INPUT=_seq, OUTPUT="memory:"), f"{_alg}_fresh")
    if _o1 and _fresh:
        _o2, _ = run(f"zero2cartolab:{_alg}", dict(_p2, INPUT=_o1["OUTPUT"], OUTPUT="memory:"),
                     f"{_alg}_rerun")
        if _o2:
            _a = sorted((f["v"], f[_fld]) for f in _o2["OUTPUT"].getFeatures())
            _b = sorted((f["v"], f[_fld]) for f in _fresh["OUTPUT"].getFeatures())
            ok(f"{_alg} rerun on own output matches a fresh run", _a == _b, f"{_a[-3:]} vs {_b[-3:]}")
            ok(f"{_alg} rerun keeps one '{_fld}' column",
               _o2["OUTPUT"].fields().names().count(_fld) == 1, str(_o2["OUTPUT"].fields().names()))

_lp1, _ = run("zero2cartolab:label_points", {"INPUT": _seq, "PRECISION": 0.0, "OUTPUT": "memory:"},
              "lbl_first")
if _lp1:
    _lp_poly = processing.run("native:buffer",
                              {"INPUT": _lp1["OUTPUT"], "DISTANCE": 2.0, "SEGMENTS": 32,
                               "OUTPUT": "memory:"})["OUTPUT"]
    _lp2, _ = run("zero2cartolab:label_points", {"INPUT": _lp_poly, "PRECISION": 0.0, "OUTPUT": "memory:"},
                  "lbl_rerun")
    if _lp2:
        _dists = [f["lbl_dist"] for f in _lp2["OUTPUT"].getFeatures()]
        ok("label_points rerun writes new lbl_dist (circle radius ~2, not stale ~5)",
           all(abs(d - 2.0) < 0.2 for d in _dists), str(_dists[:3]))
        ok("label_points rerun keeps one lbl_dist column",
           _lp2["OUTPUT"].fields().names().count("lbl_dist") == 1)

# 4/6) Bivariate custom corners and NULL features
from qgis.PyQt.QtGui import QColor as _QColor
_bv = _mem("Polygon", [("x", "double"), ("y", "double")],
           [(_sq(0, 0), [1.0, 1.0]), (_sq(20, 0), [9.0, 1.0]), (_sq(40, 0), [1.0, 9.0]),
            (_sq(60, 0), [9.0, 9.0]), (_sq(80, 0), [None, 5.0])])
_custom = {"PALETTE_PRESET": 5, "COLOR_LL": _QColor("#ffffff"), "COLOR_LH": _QColor("#ff0000"),
           "COLOR_HL": _QColor("#0000ff"), "COLOR_HH": _QColor("#000000")}
out, _ = run("zero2cartolab:bivariate_choropleth",
             dict(_custom, INPUT=_bv, FIELD_X="x", FIELD_Y="y", CLASSES=2, METHOD=3, OUTPUT="memory:"),
             "bivariate_custom")
if out:
    _bl = out["OUTPUT"]
    _cats = {c.value(): c.symbol().color().name() for c in _bl.renderer().categories()}
    _col = {(f["x"], f["y"]): _cats[f["bivar_class"]]
            for f in _bl.getFeatures() if not _is_null(f["bivar_class"])}
    ok("bivariate Top-Left colour (Low X, High Y) on low-X/high-Y feature",
       _col.get((1.0, 9.0)) == "#ff0000", str(_col))
    ok("bivariate Bottom-Right colour (High X, Low Y) on high-X/low-Y feature",
       _col.get((9.0, 1.0)) == "#0000ff", str(_col))
    _nulls = [f for f in _bl.getFeatures() if _is_null(f["x"])]
    ok("bivariate keeps the NULL feature with NULL class",
       _bl.featureCount() == 5 and len(_nulls) == 1 and _is_null(_nulls[0]["bivar_class"]))

out, _ = run("zero2cartolab:bivariate_matrix_export",
             dict(_custom, CLASSES=2, OUTPUT="memory:"), "bivariate_matrix_custom")
if out:
    _cells = {(f["col"], f["row"]): f["hex_color"] for f in out["OUTPUT"].getFeatures()}
    ok("bivariate legend export: corners match the map (Top-Left = Low X / High Y)",
       _cells.get((0, 1)) == "#ff0000" and _cells.get((1, 0)) == "#0000ff", str(_cells))

# 7) Value-by-Alpha excludes NULLs from breaks and gives NULL reliability alpha_min
_pv = _mem("Polygon", [("c", "double"), ("a", "double")],
           [(_sq(i * 10, 0), [100.0 + i, 50.0 + i]) for i in range(8)] + [(_sq(200, 0), [None, None])])
out, _ = run("zero2cartolab:value_by_alpha",
             {"INPUT": _pv, "FIELD_COLOUR": "c", "FIELD_ALPHA": "a", "ALPHA_MIN": 25,
              "ALPHA_MAX": 255, "OUTPUT": "memory:"}, "vba_null")
if out:
    _vl = out["OUTPUT"]
    _lows = [r.lowerValue() for r in _vl.renderer().ranges()]
    ok("value_by_alpha colour breaks ignore NULL (no 0.0 class)", min(_lows) >= 100.0, str(_lows))
    _al = {f["a"]: f["vba_alpha"] for f in _vl.getFeatures() if not _is_null(f["a"])}
    _null_alpha = [f["vba_alpha"] for f in _vl.getFeatures() if _is_null(f["a"])]
    ok("value_by_alpha NULL reliability -> alpha_min", _null_alpha == [25], str(_null_alpha))
    ok("value_by_alpha lowest real reliability in the first alpha class", _al[50.0] == 25, str(_al))
    ok("value_by_alpha highest reliability opaque", _al[57.0] == 255, str(_al))

# 8) Hexbin mean ignores NULL weights
_hp = _mem("Point", [("w", "double")],
           [("POINT(0 0)", [10.0]), ("POINT(0.1 0)", [None]), ("POINT(100 100)", [1.0])])
out, _ = run("zero2cartolab:hexbin_aggregate",
             {"INPUT": _hp, "CELL_SIZE": 5.0, "WEIGHT": "w", "STAT": 2, "OUTPUT": "memory:"}, "hexbin_null")
if out:
    _hx = sorted((f["hex_count"], f["hex_sum"], f["hex_mean"]) for f in out["OUTPUT"].getFeatures())
    ok("hexbin mean divides by non-NULL weights only", (2, 10.0, 10.0) in _hx, str(_hx))

# 12) Dot density on far-apart multipart islands places every dot
_mp_wkt = ("MULTIPOLYGON(((0 0,10 0,10 10,0 10,0 0)),"
           "((5000 5000,5010 5000,5010 5010,5000 5010,5000 5000)))")
_dmp = _mem("MultiPolygon", [("n", "double")], [(_mp_wkt, [400.0])])
out, _ = run("zero2cartolab:dot_density",
             {"INPUT": _dmp, "FIELD": "n", "VALUE_PER_DOT": 1.0, "SEED": 3, "OUTPUT": "memory:"},
             "dots_multipart")
if out:
    ok("dot density multipart islands get all 400 dots", out["OUTPUT"].featureCount() == 400,
       str(out["OUTPUT"].featureCount()))


class _WarnFeedback(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        self.warnings = []

    def pushWarning(self, msg):
        self.warnings.append(msg)
        super().pushWarning(msg)


_sliver = _mem("Polygon", [("n", "double")],
               [("POLYGON((0 0,1000 1000,1000 1000.001,0 0))", [20.0])])
_wfb = _WarnFeedback()
try:
    _sctx = QgsProcessingContext()
    _sres = processing.run("zero2cartolab:dot_density",
                           {"INPUT": _sliver, "FIELD": "n", "VALUE_PER_DOT": 1.0, "SEED": 1,
                            "OUTPUT": "memory:"}, context=_sctx, feedback=_wfb)
    _sl = _sres["OUTPUT"]
    if isinstance(_sl, str):
        _sl = _sctx.getMapLayer(_sl)
    _placed = _sl.featureCount() if _sl is not None else -1
    ok("dot density shortfall is reported as a warning",
       0 <= _placed < 20 and any("could be placed" in w for w in _wfb.warnings), f"{_placed} {_wfb.warnings}")
except Exception as _exc:
    traceback.print_exc()
    ok("dot density shortfall is reported as a warning", False, repr(_exc))

# 13) Cartogram on a single feature: clear QgsProcessingException
from qgis.core import QgsProcessingException as _QPE
_one = _mem("Polygon", [("v", "double")], [(_sq(0, 0), [5.0])])
try:
    processing.run("zero2cartolab:compute_cartogram", {"INPUT": _one, "FIELD": "v", "OUTPUT": "memory:"},
                   feedback=QgsProcessingFeedback())
    ok("cartogram single feature raises a clear error", False, "no exception")
except Exception as _exc:
    ok("cartogram single feature raises a clear error",
       isinstance(_exc, _QPE) and "at least 2" in str(_exc), f"{type(_exc).__name__}: {_exc}")

# ===========================================================================
# LAYOUT SUBSYSTEM (real QgsPrintLayout assembly)
# ===========================================================================
print("\n--- Layout subsystem ---")
from qgis.core import (
    QgsLayoutItemMap, QgsLayoutItemLegend, QgsLayoutItemScaleBar,
    QgsLayoutItemLabel, QgsLayoutItemPicture, QgsLayoutItemPolygon,
    QgsPrintLayout, QgsLayoutSize,
)
from zero2cartolab.layout.map_sheet import create_map_sheet, _map_extent_width_km
from zero2cartolab.layout.grid_styler import apply_minimalist_grid, GRID_ID
from zero2cartolab.layout.legend_decorator import (
    add_bivariate_legend_to_layout,
    add_scalebar_to_layout,
)
from zero2cartolab.layout.typography_engine import apply_typography_hierarchy
from zero2cartolab.layout.isometric_stacker import create_isometric_stack_layout
from zero2cartolab.layout.layout_utils import export_layout
from zero2cartolab.layout.preflight import preflight_layout, summarize_preflight
from zero2cartolab.layout.locator_map import add_locator_inset_map
from zero2cartolab.layout.atlas_builder import setup_layout_atlas
from zero2cartolab.layout.coordinate_grid import apply_coordinate_grid_decorator


def _count(lay, cls):
    return sum(1 for it in lay.items() if isinstance(it, cls))


sheet = create_map_sheet(iface=None, layers=[polys, points], title="E2E Sheet",
                         credits="synthetic", add_grid=True)
ok("map sheet is print layout", isinstance(sheet, QgsPrintLayout))
ok("map sheet has 1 map", _count(sheet, QgsLayoutItemMap) == 1)
ok("map sheet has legend + scalebar",
   _count(sheet, QgsLayoutItemLegend) == 1 and _count(sheet, QgsLayoutItemScaleBar) == 1)
ok("map sheet has north arrow",
   _count(sheet, QgsLayoutItemPicture) >= 1
   or any(hasattr(it, "id") and it.id() == "cartolab_north_arrow" for it in sheet.items())
   or _count(sheet, QgsLayoutItemPolygon) >= 1)
_north_arrow = next(it for it in sheet.items() if hasattr(it, "id") and it.id() == "cartolab_north_arrow")
_north_label = next(it for it in sheet.items() if hasattr(it, "id") and it.id() == "cartolab_north_arrow_label")
ok(
    "north notation N shares the arrow centre axis",
    abs(_north_arrow.sceneBoundingRect().center().x()
        - _north_label.sceneBoundingRect().center().x()) < 0.05,
    f"arrow={_north_arrow.sceneBoundingRect().center().x():.3f} "
    f"label={_north_label.sceneBoundingRect().center().x():.3f}",
)

_sm = next(it for it in sheet.items() if isinstance(it, QgsLayoutItemMap))
apply_minimalist_grid(sheet)
apply_minimalist_grid(sheet)  # idempotent — must not stack duplicates
_named = [g for g in _sm.grids().asList() if g.name() == GRID_ID]
ok("grid idempotent (single 02CartoLab grid)", len(_named) == 1, str(len(_named)))
ok("grid interval auto-derived > 0", _named[0].intervalX() > 0, str(_named[0].intervalX()))

small_projected_layout = QgsPrintLayout(QgsProject.instance())
small_projected_layout.initializeDefaults()
small_projected_map = QgsLayoutItemMap(small_projected_layout)
small_projected_map.attemptResize(QgsLayoutSize(100.0, 80.0))
small_projected_map.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
small_projected_map.setExtent(QgsRectangle(0.0, 0.0, 5.0, 5.0))
small_projected_layout.addLayoutItem(small_projected_map)
apply_coordinate_grid_decorator(small_projected_layout, small_projected_map)
small_grid = small_projected_map.grids().asList()[0]
ok("small projected grid is not treated as degrees", small_grid.annotationPrecision() == 0)

add_bivariate_legend_to_layout(sheet, legend_type="diamond", grid_size=4)
ok("bivariate diamond legend native polygons", _count(sheet, QgsLayoutItemPolygon) >= 16,
   str(_count(sheet, QgsLayoutItemPolygon)))
apply_typography_hierarchy(sheet)
ok("typography ran (labels present)", _count(sheet, QgsLayoutItemLabel) >= 2)

iso = create_isometric_stack_layout([polys, points])
ok("isometric stack is print layout with 2 maps",
   isinstance(iso, QgsPrintLayout) and _count(iso, QgsLayoutItemMap) == 2)

_png = os.path.join(tempfile.gettempdir(), "cartolab_e2e_sheet.png")
ok("layout exports to PNG", export_layout(sheet, _png, dpi=72) and os.path.exists(_png))
_pdf = os.path.join(tempfile.gettempdir(), "cartolab_e2e_sheet.pdf")
ok("layout exports to PDF", export_layout(sheet, _pdf, dpi=72) and os.path.exists(_pdf))
_svg = os.path.join(tempfile.gettempdir(), "cartolab_e2e_sheet.svg")
ok("layout exports to SVG", export_layout(sheet, _svg, dpi=72) and os.path.exists(_svg))

# A live legend stress layout: long layer/category labels must trigger actual
# type reduction and remain inside the fixed 58 mm publication sidebar.
legend_stress_layer = polys.clone()
legend_stress_layer.setName("Neighbourhood Development Performance Assessment")
legend_stress_renderer = legend_stress_layer.renderer()
with suppress(Exception):
    for category_index, _category in enumerate(legend_stress_renderer.categories()):
        legend_stress_renderer.updateCategoryLabel(
            category_index,
            f"Scenario {category_index + 1} · Long planning classification label",
        )
QgsProject.instance().addMapLayer(legend_stress_layer)
legend_stress = create_map_sheet(
    iface=None, layers=[legend_stress_layer], title="Legend Auto-fit Live QA",
    credits="long-label stress fixture", add_grid=True,
)
legend_stress_item = next(
    item for item in legend_stress.items() if isinstance(item, QgsLayoutItemLegend)
)
legend_fit_font = float(legend_stress_item.customProperty("cartolab/legend_fit_font_pt", 99.0))
legend_fit_width = float(legend_stress_item.customProperty("cartolab/legend_natural_width_mm", 999.0))
legend_fit_height = float(legend_stress_item.customProperty("cartolab/legend_natural_height_mm", 999.0))
legend_fit_ok = bool(legend_stress_item.customProperty("cartolab/legend_fits", False))
legend_model_rows = legend_stress_item.model().rowCount()
ok("legend stress fixture is visible in the real legend model", legend_model_rows > 0,
   str(legend_model_rows))
ok("long legend labels trigger automatic font reduction", legend_fit_font < 9.0, str(legend_fit_font))
ok(
    "long legend natural content fits its allocated sidebar",
    legend_fit_ok and legend_fit_width <= 58.0 and legend_fit_height <= 149.0,
    f"{legend_fit_width:.2f} x {legend_fit_height:.2f} mm @ {legend_fit_font:.1f} pt",
)
_legend_stress_png = os.path.join(tempfile.gettempdir(), "cartolab_e2e_legend_stress.png")
ok(
    "legend stress layout exports visible QA PNG",
    export_layout(legend_stress, _legend_stress_png, dpi=150)
    and os.path.exists(_legend_stress_png)
    and os.path.getsize(_legend_stress_png) > 10_000,
)
QgsProject.instance().removeMapLayer(legend_stress_layer.id())

# ===========================================================================
# TEMPLATE GALLERY E2E (all 5 publication archetypes)
# ===========================================================================
print("\n--- Template Gallery Subsystem ---")
from zero2cartolab.layout.template_gallery import (
    TEMPLATE_GALLERY,
    _create_scalebar,
    create_template_layout,
)

ok("template gallery has 10 archetypes", len(TEMPLATE_GALLERY) == 10)

for tkey in TEMPLATE_GALLERY:
    t_lay = create_template_layout(
        tkey, iface=None, layers=[polys, points],
        title=f"E2E {tkey}", subtitle="Automated Test Subtitle", credits="02CartoLab Suite",
    )
    ok(f"template {tkey} creates print layout", isinstance(t_lay, QgsPrintLayout))
    ok(f"template {tkey} has map frame(s)", _count(t_lay, QgsLayoutItemMap) >= 1)
    ok(f"template {tkey} has label(s)", _count(t_lay, QgsLayoutItemLabel) >= 1)
    main_maps = [
        item for item in t_lay.items()
        if isinstance(item, QgsLayoutItemMap) and item.id() != "cartolab_locator_map"
    ]
    ok(
        f"template {tkey} resolves layer CRS",
        bool(main_maps) and all(item.crs().authid() == "EPSG:3857" for item in main_maps),
        str([item.crs().authid() for item in main_maps]),
    )
    scale_bars = [item for item in t_lay.items() if isinstance(item, QgsLayoutItemScaleBar)]
    ok(
        f"template {tkey} uses readable scale units",
        all(
            0.0 < item.unitsPerSegment() < 100.0
            and abs(item.mapUnitsPerScaleBarUnit() - 1.0) < 1e-9
            for item in scale_bars
        ),
        str([
            (item.unitsPerSegment(), item.mapUnitsPerScaleBarUnit())
            for item in scale_bars
        ]),
    )
    template_issues = preflight_layout(t_lay)
    template_summary = summarize_preflight(template_issues)
    ok(
        f"template {tkey} passes print preflight",
        template_summary["errors"] == 0,
        str(template_issues),
    )
    _tpng = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_template_{tkey}.png")
    ok(f"template {tkey} exports to PNG", export_layout(t_lay, _tpng, dpi=72) and os.path.exists(_tpng))

from zero2cartolab.layout.grid_presets import (
    GRID_PRESETS,
    apply_grid_preset,
    remove_cartolab_grids,
)

utm_polys = build_polygons("EPSG:32635", 500000.0, 4200000.0, "UTM 35N units")
utm_polys.setRenderer(polys.renderer().clone())
QgsProject.instance().addMapLayer(utm_polys)
for preset_id, preset_meta in GRID_PRESETS.items():
    grid_sheet = create_map_sheet(
        iface=None, layers=[utm_polys], title=f"Grid Preset · {preset_meta['name']}"
    )
    # Keep visual-regression plates focused on marginalia.  The generic map
    # sheet legend sits beside the map and can crowd right-side annotations;
    # complete gallery templates test their own deliberately placed legends.
    for grid_legend in [
        item for item in grid_sheet.items() if isinstance(item, QgsLayoutItemLegend)
    ]:
        grid_sheet.removeLayoutItem(grid_legend)
    grid_map = next(item for item in grid_sheet.items() if isinstance(item, QgsLayoutItemMap))
    created = apply_grid_preset(grid_sheet, preset_id, grid_map)
    ok(
        f"grid preset {preset_id} creates expected stack",
        len(created) == len(preset_meta["components"]),
        str(len(created)),
    )
    apply_grid_preset(grid_sheet, preset_id, grid_map)
    generated = [
        grid for grid in grid_map.grids().asList()
        if grid.name().startswith("CartoLabPreset/")
    ]
    ok(
        f"grid preset {preset_id} is idempotent",
        len(generated) == len(preset_meta["components"]),
        str([grid.name() for grid in generated]),
    )
    _grid_png = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_grid_{preset_id}.png")
    ok(
        f"grid preset {preset_id} exports visual QA image",
        export_layout(grid_sheet, _grid_png, dpi=72) and os.path.exists(_grid_png),
    )
    ok(
        f"grid preset {preset_id} removal is scoped and complete",
        remove_cartolab_grids(grid_sheet, grid_map) == len(preset_meta["components"]),
    )

# Real Qt construction and screenshot for the full Print Layout Studio GUI.
from zero2cartolab.ui.cartolab_dashboard import CartoLabDashboard
dashboard = CartoLabDashboard(iface=object())
dashboard.nav_sidebar.setCurrentRow(1)
dashboard.layout_sub_tabs.setCurrentIndex(2)
dashboard.show()
QgsApplication.processEvents()
ok("print studio GUI has four workspaces", dashboard.layout_sub_tabs.count() == 4)
ok("print studio GUI exposes all grid presets",
   dashboard.layout_grid_preset_combo.count() == len(GRID_PRESETS))
ok("print studio GUI exposes QPT compatibility report", dashboard.qpt_report is not None)
_gui_png = os.path.join(tempfile.gettempdir(), "cartolab_e2e_print_studio_gui.png")
ok("print studio GUI screenshot saved", dashboard.grab().save(_gui_png) and os.path.exists(_gui_png))
dashboard.close()

square_sheet = create_map_sheet(
    iface=None, layers=[polys], title="Square E2E", page_size="SQUARE"
)
square_page = square_sheet.pageCollection().page(0).pageSize()
ok(
    "square map sheet has equal page dimensions",
    abs(square_page.width() - square_page.height()) < 0.01,
    f"{square_page.width()} x {square_page.height()}",
)
add_locator_inset_map(square_sheet)
add_locator_inset_map(square_sheet)
ok(
    "locator decorator is idempotent",
    sum(
        1 for item in square_sheet.items()
        if hasattr(item, "id") and item.id() == "cartolab_locator_inset"
    ) == 1,
)

atlas_sheet = create_map_sheet(iface=None, layers=[polys], title="Atlas E2E")
ok(
    "atlas setup accepts valid filter and sort",
    setup_layout_atlas(
        atlas_sheet, polys, name_field="uid", filter_expression='"uid" >= 0', sort_field="uid"
    ),
)
atlas = atlas_sheet.atlas()
ok(
    "atlas sorting is actually enabled",
    atlas.sortFeatures() and atlas.sortExpression() == '"uid"',
    atlas.sortExpression(),
)
ok(
    "atlas rejects invalid filter before configuration",
    not setup_layout_atlas(atlas_sheet, polys, filter_expression='"uid" >'),
)

geo_layout = QgsPrintLayout(QgsProject.instance())
geo_layout.initializeDefaults()
geo_map = QgsLayoutItemMap(geo_layout)
geo_map.attemptResize(QgsLayoutSize(100.0, 80.0))
geo_map.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
geo_map.setExtent(QgsRectangle(27.0, 38.0, 28.0, 39.0))
geo_layout.addLayoutItem(geo_map)
geo_width_km = _map_extent_width_km(geo_map, QgsProject.instance())
ok(
    "geographic map width is measured geodesically",
    80.0 < geo_width_km < 100.0,
    f"got {geo_width_km}",
)
gallery_bar = _create_scalebar(geo_layout, geo_map, 10.0, 10.0)
ok(
    "template scalebar uses geographic width",
    gallery_bar is not None
    and gallery_bar.unitsPerSegment() >= 5.0,
)
decorator_bar = add_scalebar_to_layout(geo_layout, map_item=geo_map)
ok(
    "designer scalebar uses geographic width",
    decorator_bar is not None
    and decorator_bar.unitsPerSegment() >= 5.0,
)

# ===========================================================================
# NATIVE PRINT-LAYOUT CHARTS + PHYSICAL OUTPUT QA
# ===========================================================================
print("\n--- Native Print Layout Charts ---")
from qgis.PyQt.QtGui import QColor, QImage, QPainter
from zero2cartolab.layout.charts import PALETTES, ChartSpec, add_chart_to_layout, list_charts, remove_chart
from zero2cartolab.layout.pixel_qa import analyze_export, validate_pixels

for chart_type in (
    "bar", "grouped_bar", "stacked_bar", "line", "multi_line", "area",
    "scatter", "pie", "donut", "histogram",
):
    chart_layout = create_map_sheet(
        iface=None, layers=[polys], title=f"{chart_type.title()} chart QA",
        add_legend=False, add_north_arrow=True,
    )
    chart_spec = ChartSpec(
        chart_type=chart_type,
        category_field="uid" if chart_type != "histogram" else "",
        value_field="score",
        series_field="floors" if chart_type in ("grouped_bar", "stacked_bar", "multi_line") else "",
        aggregation="sum",
        title=f"Score by unit · {chart_type.title()}",
        x=115.0, y=118.0, width=160.0, height=70.0,
        top_n=5, bins=5,
        palette=PALETTES["Colorblind Safe"] if chart_type == "donut" else PALETTES["Editorial"],
        background_color="#0f172a" if chart_type == "donut" else "#ffffff",
        text_color="#f8fafc" if chart_type == "donut" else "#0f172a",
        grid_color="#334155" if chart_type == "donut" else "#e2e8f0",
    )
    chart_root = add_chart_to_layout(chart_layout, polys, chart_spec)
    persisted = list_charts(chart_layout)
    ok(
        f"{chart_type} chart persists editable spec metadata",
        len(persisted) == 1 and persisted[0]["spec"]["chart_type"] == chart_type,
    )
    chart_items = [
        item for item in chart_layout.items()
        if hasattr(item, "id") and item.id().startswith(chart_root)
    ]
    ok(f"{chart_type} chart creates native layout items", len(chart_items) >= 4, str(len(chart_items)))
    frame = next(item for item in chart_items if item.id() == f"{chart_root}_frame")
    page_rect = chart_layout.pageCollection().page(0).sceneBoundingRect()
    ok(f"{chart_type} chart respects page boundary", page_rect.contains(frame.sceneBoundingRect()))
    chart_issues = preflight_layout(chart_layout)
    ok(
        f"{chart_type} chart passes frame/grid/scale preflight",
        not any(issue["severity"] == "error" for issue in chart_issues),
        str(chart_issues),
    )
    chart_png = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_chart_{chart_type}.png")
    exported = export_layout(chart_layout, chart_png, dpi=150)
    image = QImage(chart_png) if exported else QImage()
    ok(
        f"{chart_type} chart exports non-empty 150 DPI raster",
        exported and not image.isNull() and image.width() > 1000 and image.height() > 700
        and os.path.getsize(chart_png) > 10_000,
        f"{image.width()}x{image.height()} · {os.path.getsize(chart_png) if os.path.exists(chart_png) else 0} bytes",
    )
    pixel_metrics = analyze_export(chart_png, dpi=150, safe_margin_mm=3.0, sample_step=5)
    pixel_issues = validate_pixels(pixel_metrics, safe_margin_mm=3.0)
    ok(
        f"{chart_type} pixel QA finds ink, colour and safe edges",
        pixel_metrics.ink_ratio > 0.02
        and pixel_metrics.unique_color_buckets >= 8
        and not any(issue["severity"] == "error" for issue in pixel_issues)
        and pixel_metrics.edge_ink_ratio < 0.002,
        str(pixel_metrics.as_dict()) + " " + str(pixel_issues),
    )
    removed = remove_chart(chart_layout, chart_root)
    ok(f"{chart_type} chart removal is complete", removed == len(chart_items))

blank_image = QImage(400, 300, QImage.Format.Format_RGB32 if hasattr(QImage.Format, "Format_RGB32") else QImage.Format_RGB32)
blank_image.fill(QColor("#ffffff"))
blank_metrics = analyze_export(blank_image, dpi=150, sample_step=2)
ok(
    "pixel QA rejects blank exports",
    any(issue["code"] == "pixel_blank" and issue["severity"] == "error"
        for issue in validate_pixels(blank_metrics)),
)
edge_image = QImage(blank_image)
painter = QPainter(edge_image)
painter.fillRect(0, 0, 35, edge_image.height(), QColor("#0f172a"))
painter.end()
edge_metrics = analyze_export(edge_image, dpi=150, safe_margin_mm=3.0, sample_step=2)
ok(
    "pixel QA detects ink entering print-safe edge",
    any(issue["code"] == "pixel_safe_margin" for issue in validate_pixels(edge_metrics)),
)

# ===========================================================================
# LAYOUT REGRESSIONS (audit fixes)
# ===========================================================================
print("\n--- Layout regressions ---")
from qgis.core import (
    QgsLayerTree, QgsLayoutItemGroup, QgsLayoutItemMapGrid, QgsLayoutItemPage,
    QgsLayoutItemRegistry, QgsLayoutPoint, QgsUnitTypes as _QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt as _Qt
from qgis.PyQt.QtWidgets import QApplication as _QApplication
from zero2cartolab.layout.layout_utils import (
    copy_layout_to_clipboard, find_map_item, last_export_error, main_map_item,
)
_RMM = _QgsUnitTypes.LayoutUnit.LayoutMillimeters


def _furniture_overlaps(layout, ids):
    """Pairs of the given item ids whose scene rects overlap by > 0.5 mm²."""
    rects = {}
    for item_id in ids:
        item = layout.itemById(item_id)
        if item is not None:
            rects[item_id] = item.sceneBoundingRect()
    bad = []
    keys = sorted(rects)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a.startswith("cartolab_north_arrow") and b.startswith("cartolab_north_arrow"):
                continue  # the arrow and its "N" are one motif
            inter = rects[a].intersected(rects[b])
            if inter.width() * inter.height() > 0.5:
                bad.append((a, b))
    return bad


# 1. legend styler only relabels the legend, never the project layers
from zero2cartolab.layout.legend_styler import style_layout_legend
styler_layer = polys.clone()
styler_layer.setName("ss_choice_median")
QgsProject.instance().addMapLayer(styler_layer)
styler_layout = QgsPrintLayout(QgsProject.instance())
styler_layout.initializeDefaults()
styler_legend = style_layout_legend(styler_layout)
_styler_nodes = [n for n in styler_legend.model().rootGroup().findLayers() if n.layer() is styler_layer]
ok("legend styler keeps the project layer name", styler_layer.name() == "ss_choice_median", styler_layer.name())
ok("legend styler leaves project tree labels alone",
   QgsProject.instance().layerTreeRoot().findLayer(styler_layer.id()).customProperty("legend/title-label") in (None, ""))
ok("legend styler shows the cleaned label in the legend",
   bool(_styler_nodes) and styler_legend.model().data(
       styler_legend.model().node2index(_styler_nodes[0]), _Qt.ItemDataRole.DisplayRole) == "Choice Median",
   str([styler_legend.model().data(styler_legend.model().node2index(n), _Qt.ItemDataRole.DisplayRole)
        for n in _styler_nodes]))
QgsProject.instance().removeMapLayer(styler_layer.id())

# 2. main-map lookup never picks the locator inset
inset_sheet = create_map_sheet(iface=None, layers=[polys], title="Main map lookup")
add_locator_inset_map(inset_sheet)
_main = inset_sheet.itemById("cartolab_map")
_inset = inset_sheet.itemById("cartolab_locator_inset")
ok("main_map_item prefers cartolab_map over the locator inset",
   _inset is not None and main_map_item(inset_sheet) is _main and find_map_item(inset_sheet) is _main)
ok("scale bar links to the main map", add_scalebar_to_layout(inset_sheet).linkedMap() is _main)
apply_coordinate_grid_decorator(inset_sheet)
ok("coordinate grid goes on the main map",
   any(g.name() == "PlanXCoordGrid" for g in _main.grids().asList())
   and not any(g.name() == "PlanXCoordGrid" for g in _inset.grids().asList()))
plain_layout = QgsPrintLayout(QgsProject.instance())
plain_layout.initializeDefaults()
_small = QgsLayoutItemMap(plain_layout)
_small.attemptResize(QgsLayoutSize(30, 20, _RMM))
plain_layout.addLayoutItem(_small)
_big = QgsLayoutItemMap(plain_layout)
_big.attemptResize(QgsLayoutSize(200, 150, _RMM))
plain_layout.addLayoutItem(_big)
ok("main_map_item falls back to the largest map", main_map_item(plain_layout) is _big)
from zero2cartolab.layout.designer_integration import export_layout_and_report, snap_to_standard_scale
ok("snap scale picks the nearest standard scale", snap_to_standard_scale(23000) == 25000)

# 14. scale combo text follows the map scale
from zero2cartolab.layout.legend_decorator import add_scale_combo_to_layout
from qgis.core import QgsLayoutItemLabel as _Lbl
add_scale_combo_to_layout(inset_sheet)
_scale_labels = [it for it in inset_sheet.items() if isinstance(it, _Lbl) and "map_scale" in it.text()]
_main.setScale(12345)
ok("scale combo label is bound to the main map scale",
   len(_scale_labels) == 1 and "item_variables('cartolab_map')" in _scale_labels[0].text()
   and _scale_labels[0].currentText().replace(",", "").replace(" ", "").replace(" ", "").endswith("12345"),
   _scale_labels[0].currentText() if _scale_labels else "no label")

# 3 + 4. advanced templates: no-layer projects and on-page grid annotations
from zero2cartolab.layout.advanced_templates import (
    create_emergency_brief_layout, create_utm_field_sheet_layout,
)
_empty_project = QgsProject()
for _builder in (create_utm_field_sheet_layout, create_emergency_brief_layout):
    try:
        _built = _builder(layers=[], project=_empty_project)
        ok(f"{_builder.__name__} works without layers / CRS", isinstance(_built, QgsPrintLayout))
    except Exception as exc:
        ok(f"{_builder.__name__} works without layers / CRS", False, repr(exc))
    _utm_layout = _builder(layers=[utm_polys], title="UTM annotations")
    _utm_issues = [i for i in preflight_layout(_utm_layout) if i["severity"] == "error"]
    ok(f"{_builder.__name__} grid annotations stay on the page", not _utm_issues, str(_utm_issues))
    _utm_map = main_map_item(_utm_layout)
    _inside = getattr(getattr(QgsLayoutItemMapGrid, "AnnotationPosition", QgsLayoutItemMapGrid),
                      "InsideMapFrame", 0)
    _left = getattr(getattr(QgsLayoutItemMapGrid, "BorderSide", QgsLayoutItemMapGrid), "Left", 0)
    ok(f"{_builder.__name__} annotates inside the map frame",
       all(g.annotationPosition(_left) == _inside for g in _utm_map.grids().asList()
           if g.annotationEnabled()))

# 5. clipboard copy
ok("copy_layout_to_clipboard renders the page", copy_layout_to_clipboard(inset_sheet, dpi=40))
_cb = _QApplication.clipboard()
ok("clipboard holds the rendered page", _cb is not None and not _cb.image().isNull())

# 6. multi-page export leaves no temp files; failures are reported
_export_dir = tempfile.mkdtemp(prefix="cartolab_e2e_export_")
two_pages = QgsPrintLayout(QgsProject.instance())
two_pages.initializeDefaults()
_extra_page = QgsLayoutItemPage(two_pages)
_extra_page.setPageSize("A4")
two_pages.pageCollection().addPage(_extra_page)
for _ext in (".png", ".svg"):
    ok(f"multi-page {_ext} export succeeds", export_layout(two_pages, os.path.join(_export_dir, f"map{_ext}"), dpi=30))
ok("multi-page export writes final page names only",
   sorted(os.listdir(_export_dir)) == ["map.png", "map.svg", "map_2.png", "map_2.svg"],
   str(sorted(os.listdir(_export_dir))))
_blocker = os.path.join(_export_dir, "blocker")
with open(_blocker, "w") as _fh:
    _fh.write("x")
_bad_path = os.path.join(_blocker, "out.png")
ok("failed export returns False with a reason",
   export_layout(two_pages, _bad_path, dpi=30) is False and bool(last_export_error()))
_ok, _msg = export_layout_and_report(two_pages, _bad_path, 30)
ok("designer Export & Open gets an error message", _ok is False and bool(_msg), _msg)

# 7. create_map_sheet(add_grid=True) really adds a grid, inside the frame
grid_on_sheet = create_map_sheet(iface=None, layers=[polys], title="Grid on", credits="c", add_grid=True)
_grids = grid_on_sheet.itemById("cartolab_map").grids().asList()
ok("map sheet add_grid adds an enabled grid", any(g.enabled() for g in _grids), str(len(_grids)))
_grid_errors = [i for i in preflight_layout(grid_on_sheet) if i["severity"] == "error"]
ok("map sheet grid passes preflight", not _grid_errors, str(_grid_errors))

# 8. bivariate legend lands at the requested position and stays put
from zero2cartolab.layout.legend_decorator import add_bivariate_legend, replace_bivariate_legend


def _legend_bounds(group):
    # Union of the members' frames: QGIS 3.28 misreports a group's own rect
    # when it holds rotated labels, so measure what is drawn.
    bounds = None
    for member in group.items():
        rect = member.mapRectToScene(member.rect())
        bounds = rect if bounds is None else bounds.united(rect)
    return bounds


for _shape in ("diamond", "square"):
    bivar_layout = QgsPrintLayout(QgsProject.instance())
    bivar_layout.initializeDefaults()
    _grp = add_bivariate_legend(bivar_layout, legend_type=_shape, position=(20.0, 30.0))
    _r = _legend_bounds(_grp)
    ok(f"bivariate {_shape} legend top-left = requested position",
       abs(_r.left() - 20.0) < 0.05 and abs(_r.top() - 30.0) < 0.05, f"{_r.left():.2f},{_r.top():.2f}")
    _n_items = len(bivar_layout.items())
    for _ in range(3):
        _grp = replace_bivariate_legend(bivar_layout, [_grp], legend_type=_shape)
    _r = _legend_bounds(_grp)
    ok(f"bivariate {_shape} legend does not drift on update",
       abs(_r.left() - 20.0) < 0.05 and abs(_r.top() - 30.0) < 0.05
       and len(bivar_layout.items()) == _n_items, f"{_r.left():.2f},{_r.top():.2f} items {len(bivar_layout.items())}/{_n_items}")

# 9. isometric stack: tilt angle, transparent planes, data fits
iso_tilt = create_isometric_stack_layout([polys, points], angle_deg=30.0)
iso_flat = create_isometric_stack_layout([polys, points], angle_deg=0.0)


def _iso_maps(layout):
    return sorted((it for it in layout.items() if isinstance(it, QgsLayoutItemMap)), key=lambda m: m.id())


_tm, _fm = _iso_maps(iso_tilt), _iso_maps(iso_flat)
ok("isometric tilt angle shifts planes sideways",
   _tm[1].pos().x() - _tm[0].pos().x() > 1.0 and abs(_fm[1].pos().x() - _fm[0].pos().x()) < 1e-6,
   f"{_tm[1].pos().x() - _tm[0].pos().x():.2f} / {_fm[1].pos().x() - _fm[0].pos().x():.2f}")
ok("isometric planes are transparent", not any(m.hasBackground() for m in _tm))
_iso_labels = [it for it in iso_tilt.items() if isinstance(it, QgsLayoutItemLabel)]
ok("isometric captions draw above every plane",
   bool(_iso_labels) and min(lbl.zValue() for lbl in _iso_labels) > max(m.zValue() for m in _tm))
_data_extent = QgsRectangle(polys.extent())
_data_extent.combineExtentWith(points.extent())
ok("isometric planes show all the data (no fixed-scale clipping)",
   all(m.extent().contains(_data_extent) for m in _tm), str([m.scale() for m in _tm]))
_iso_errors = [i for i in preflight_layout(iso_tilt) if i["code"] == "outside_page"]
ok("isometric stack fits the page", not _iso_errors, str(_iso_errors))

# 10. atlas on a map sheet: no stacked title/counter; empty coverage fails
atlas_map_sheet = create_map_sheet(iface=None, layers=[polys], title="Atlas overlap", subtitle="sub")
ok("atlas setup on map sheet succeeds", setup_layout_atlas(atlas_map_sheet, polys, name_field="uid"))
_title_w = atlas_map_sheet.itemById("cartolab_title").rect().width()
ok("atlas setup re-run keeps the title row stable",
   setup_layout_atlas(atlas_map_sheet, polys, name_field="uid")
   and abs(atlas_map_sheet.itemById("cartolab_title").rect().width() - _title_w) < 1e-6)
ok("atlas furniture does not overlap the sheet title",
   atlas_map_sheet.itemById("cartolab_atlas_title") is None
   and not _furniture_overlaps(atlas_map_sheet, ["cartolab_title", "cartolab_subtitle", "cartolab_atlas_counter"]),
   str(_furniture_overlaps(atlas_map_sheet, ["cartolab_title", "cartolab_subtitle", "cartolab_atlas_counter"])))
_empty_cov = QgsVectorLayer(f"Polygon?crs={CRS}", "empty_cov", "memory")
ok("atlas with no coverage features reports failure",
   not setup_layout_atlas(create_map_sheet(iface=None, layers=[polys], title="Empty atlas"), _empty_cov))
ok("atlas whose filter matches nothing reports failure",
   not setup_layout_atlas(create_map_sheet(iface=None, layers=[polys], title="Filtered atlas"),
                          polys, filter_expression='"uid" < 0'))

# 11. QPT inspector item type ids match the registry
from zero2cartolab.layout.qpt_inspector import _TYPE_NAMES
_registry_ids = {
    "map": QgsLayoutItemRegistry.LayoutMap, "label": QgsLayoutItemRegistry.LayoutLabel,
    "legend": QgsLayoutItemRegistry.LayoutLegend, "shape": QgsLayoutItemRegistry.LayoutShape,
    "polygon": QgsLayoutItemRegistry.LayoutPolygon, "polyline": QgsLayoutItemRegistry.LayoutPolyline,
    "scale_bar": QgsLayoutItemRegistry.LayoutScaleBar, "picture": QgsLayoutItemRegistry.LayoutPicture,
    "page": QgsLayoutItemRegistry.LayoutPage,
}
ok("qpt inspector type ids match QgsLayoutItemRegistry",
   all(_TYPE_NAMES.get(int(getattr(v, "value", v))) == k for k, v in _registry_ids.items()),
   str({k: int(getattr(v, "value", v)) for k, v in _registry_ids.items()}))

# 12. typography: subtitle is styled as a subtitle, not a title
typo_sheet = create_map_sheet(iface=None, layers=[polys], title="Typography", subtitle="Sub line", preset="")
apply_typography_hierarchy(typo_sheet, preset="swiss_modern")
_sub = typo_sheet.itemById("cartolab_subtitle")
ok("typography styles cartolab_subtitle as subtitle",
   _sub.fontColor().name().lower() == "#64748b" and not _sub.font().bold(),
   f"{_sub.fontColor().name()} bold={_sub.font().bold()}")

# 13. auto-balance leaves no furniture overlaps
from zero2cartolab.layout.layout_optimizer import optimize_layout_visual_balance
_furniture_ids = ["cartolab_title", "cartolab_subtitle", "cartolab_credits", "cartolab_legend",
                  "cartolab_scalebar", "cartolab_map", "cartolab_north_arrow", "cartolab_north_arrow_label"]
for _arch in ("editorial_bottom", "sidebar_right", "sidebar_left"):
    _bal = create_map_sheet(iface=None, layers=[polys], title="Balance", subtitle="Subtitle line",
                            credits="Source: CartoLab e2e")
    ok(f"auto-balance {_arch} runs", optimize_layout_visual_balance(_bal, archetype=_arch))
    _overlaps = _furniture_overlaps(_bal, _furniture_ids)
    _bal_errors = [i for i in preflight_layout(_bal) if i["severity"] == "error"]
    ok(f"auto-balance {_arch} leaves no overlaps", not _overlaps and not _bal_errors,
       str(_overlaps) + str(_bal_errors))

# ===========================================================================
# REAL DATASET E2E (geostats_Sample_Dataset.gpkg)
# ===========================================================================
real_gpkg = os.environ.get("ZERO2CARTOLAB_REAL_GPKG", "")
if os.path.exists(real_gpkg):
    print("\n--- Real Dataset Testing (geostats_Sample_Dataset.gpkg) ---")
    real_layer = QgsVectorLayer(real_gpkg, "real_geostats", "ogr")
    ok("real gpkg valid", real_layer.isValid())
    if real_layer.isValid():
        QgsProject.instance().addMapLayer(real_layer)
        out_real_bivar, _ = run("zero2cartolab:bivariate_choropleth", {
            "INPUT": real_layer, "FIELD_X": "ss_choice_median", "FIELD_Y": "ss_integration_median",
            "CLASSES": 3, "OUTPUT": "memory:real_bivar_res"
        }, "real_bivariate")
        lyr = out_real_bivar["OUTPUT"] if out_real_bivar else None
        if hasattr(lyr, "featureCount"):
            ok("real dataset bivariate_choropleth", lyr.featureCount() == 387, f"got {lyr.featureCount()}")

        out_real_qs, _ = run("zero2cartolab:quick_style", {
            "INPUT": real_layer, "FIELD": "transit_accessibility", "MODE": 1, "CLASSES": 5, "METHOD": 0,
            "PALETTE": 0, "REVERSE": False, "OUTLINE": True
        }, "real_quick_style")
        ok("real dataset quick_style", out_real_qs is not None and isinstance(out_real_qs.get("SUMMARY"), str))

# ===========================================================================
print("\n" + "=" * 60)
print(f"PASSED: {passed}")
if fails:
    print(f"FAILED: {len(fails)}")
    for f in fails:
        print(f"   - {f}")
print("=" * 60)

# offscreen renders can segfault on exitQgis(); hard-exit instead
os._exit(1 if fails else 0)
