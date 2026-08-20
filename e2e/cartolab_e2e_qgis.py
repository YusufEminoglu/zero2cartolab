# -*- coding: utf-8 -*-
"""
End-to-end real-QGIS test for zero2cartolab — runs ALL 12 Processing
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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# line-buffer stdout so PASS/FAIL lines survive the os._exit() hard exit
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

from qgis.core import QgsApplication

qgs = QgsApplication([], False)
qgs.initQgis()

import qgis
system_plugins_dir = os.path.abspath(os.path.join(os.path.dirname(qgis.__file__), "..", "plugins"))
if system_plugins_dir in sys.path:
    sys.path.remove(system_plugins_dir)
sys.path.insert(0, system_plugins_dir)
sys.path.append(r"C:\Users\YE\PyCharmMiscProject\qgis_plugins")

import processing
from processing.core.Processing import Processing
Processing.initialize()





from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsFeature, QgsFields, QgsField,
    QgsGeometry, QgsPointXY, QgsProcessingContext, QgsProcessingFeedback,
    QgsProcessingUtils, QgsProject, QgsVectorLayer, QgsRasterLayer,
)
from qgis.PyQt.QtCore import QVariant

print(f"QGIS version: {Qgis.QGIS_VERSION}")

from zero2cartolab.processing.cartolab_provider import CartoLabProvider
from zero2cartolab.core.dot_density import dots_for_value

_prov = CartoLabProvider()  # keep a reference so it is not GC'd
QgsApplication.processingRegistry().addProvider(_prov)

# Regression guard: prevent silent algorithm-count drift
_algo_count = len(list(_prov.algorithms()))
assert _algo_count == 14, f"expected 14 algorithms, got {_algo_count}"
print(f"Provider algorithm count: {_algo_count} (pinned at 14)\n")
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
    try:
        res = processing.run(algo_id, params, context=ctx, feedback=QgsProcessingFeedback())
    except Exception as exc:
        traceback.print_exc()
        fails.append(f"{label}: raised {exc}")
        return None, ctx
    out = {}
    for k, v in res.items():
        if isinstance(v, str) and "\n" not in v and not v.lower().endswith((".html", ".pdf", ".md", ".qml")):
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


def build_polygons():
    lyr = QgsVectorLayer(
        f"Polygon?crs={CRS}&field=uid:integer&field=count:double"
        "&field=pop:double&field=score:double&field=floors:integer",
        "units", "memory")
    dp = lyr.dataProvider()
    feats = []
    for j in range(N):
        for i in range(N):
            uid = j * N + i
            x0, y0 = i * CELL, j * CELL
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

# ===========================================================================
# LAYOUT SUBSYSTEM (real QgsPrintLayout assembly)
# ===========================================================================
print("\n--- Layout subsystem ---")
from qgis.core import (
    QgsLayoutItemMap, QgsLayoutItemLegend, QgsLayoutItemScaleBar,
    QgsLayoutItemLabel, QgsLayoutItemPicture, QgsLayoutItemPolygon,
    QgsPrintLayout,
)
from zero2cartolab.layout.map_sheet import create_map_sheet
from zero2cartolab.layout.grid_styler import apply_minimalist_grid, GRID_ID
from zero2cartolab.layout.legend_decorator import add_bivariate_legend_to_layout
from zero2cartolab.layout.typography_engine import apply_typography_hierarchy
from zero2cartolab.layout.isometric_stacker import create_isometric_stack_layout
from zero2cartolab.layout.layout_utils import export_layout


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

_sm = next(it for it in sheet.items() if isinstance(it, QgsLayoutItemMap))
apply_minimalist_grid(sheet)
apply_minimalist_grid(sheet)  # idempotent — must not stack duplicates
_named = [g for g in _sm.grids().asList() if g.name() == GRID_ID]
ok("grid idempotent (single 02CartoLab grid)", len(_named) == 1, str(len(_named)))
ok("grid interval auto-derived > 0", _named[0].intervalX() > 0, str(_named[0].intervalX()))

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

# ===========================================================================
# TEMPLATE GALLERY E2E (all 5 publication archetypes)
# ===========================================================================
print("\n--- Template Gallery Subsystem ---")
from zero2cartolab.layout.template_gallery import (
    TEMPLATE_GALLERY,
    create_template_layout,
    create_report_figure,
    create_academic_journal,
    create_exhibition_poster,
    create_fact_sheet,
    create_diptych,
)

ok("template gallery has 5 archetypes", len(TEMPLATE_GALLERY) == 5)

for tkey in ("report_figure", "academic_journal", "exhibition_poster", "fact_sheet", "diptych"):
    t_lay = create_template_layout(
        tkey, iface=None, layers=[polys, points],
        title=f"E2E {tkey}", subtitle="Automated Test Subtitle", credits="02CartoLab Suite",
    )
    ok(f"template {tkey} creates print layout", isinstance(t_lay, QgsPrintLayout))
    ok(f"template {tkey} has map frame(s)", _count(t_lay, QgsLayoutItemMap) >= 1)
    ok(f"template {tkey} has label(s)", _count(t_lay, QgsLayoutItemLabel) >= 1)
    _tpng = os.path.join(tempfile.gettempdir(), f"cartolab_e2e_template_{tkey}.png")
    ok(f"template {tkey} exports to PNG", export_layout(t_lay, _tpng, dpi=72) and os.path.exists(_tpng))

# ===========================================================================
# REAL DATASET E2E (geostats_Sample_Dataset.gpkg)
# ===========================================================================
real_gpkg = r"C:\Users\YE\Downloads\geostats_Sample_Dataset.gpkg"
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
