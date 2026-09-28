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
system_plugins_dir = os.path.abspath(os.path.join(os.path.dirname(qgis.__file__), "..", "plugins"))
if system_plugins_dir in sys.path:
    sys.path.remove(system_plugins_dir)
sys.path.insert(0, system_plugins_dir)
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
# later layout tests build legends from the project: leave it as we found it
QgsProject.instance().removeMapLayers(_style_loaded_ids)

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
