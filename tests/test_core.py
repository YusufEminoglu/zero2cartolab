# -*- coding: utf-8 -*-
"""Comprehensive unit tests for zero2cartolab core modules.

Tests every algorithm with normal, edge-case, and adversarial data.
Runs without QGIS — mocks qgis.* imports for pure-logic verification.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import types

# ---------------------------------------------------------------------------
# Mock qgis.* so we can import core modules outside QGIS
# ---------------------------------------------------------------------------

class FakeQColor:
    def __init__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], str):
            h = args[0].lstrip("#")
            self._r = int(h[0:2], 16) if len(h) >= 2 else 0
            self._g = int(h[2:4], 16) if len(h) >= 4 else 0
            self._b = int(h[4:6], 16) if len(h) >= 6 else 0
        elif len(args) == 3:
            self._r, self._g, self._b = args
        else:
            self._r = self._g = self._b = 0
    def red(self):   return self._r
    def green(self): return self._g
    def blue(self):  return self._b
    def name(self):  return f"#{self._r:02x}{self._g:02x}{self._b:02x}"
    def __repr__(self): return f"QColor({self._r},{self._g},{self._b})"

def _make_mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m

qgis_core = _make_mod("qgis.core",
    QgsCoordinateReferenceSystem=_make_mod("CRS", fromProj=classmethod(lambda c, p: _make_mod("X", isGeographic=lambda s: False))),
    QgsCoordinateTransformContext=_make_mod("CTC"),
    QgsDistanceArea=_make_mod("DA",
        setSourceCrs=lambda s, *a: None,
        setEllipsoid=lambda s, *a: None,
        measureArea=lambda s, g: getattr(g, 'area', lambda: 100.0)() if callable(getattr(g, 'area', None)) else 100.0,
    ),
    QgsGeometry=_make_mod("Geom"),
    QgsVertexId=_make_mod("VID", IsValid=lambda s: True, VertexType=_make_mod("VT", SegmentVertex=0, CurveVertex=1)),
    QgsPoint=_make_mod("P"),
    QgsPointXY=_make_mod("PXY"),
    QgsFeature=_make_mod("F"),
    QgsField=_make_mod("Field"),
    QgsFields=_make_mod("Fields"),
    QgsVectorLayer=_make_mod("VL"),
    QgsWkbTypes=_make_mod("Wkb"),
    QgsFeatureSink=_make_mod("FS", Flag=_make_mod("Flag", FastInsert=1)),
    QgsProcessingFeedback=_make_mod("PF"),
    QgsProcessingException=Exception,
    QgsRasterLayer=_make_mod("RL"),
    QgsRectangle=_make_mod("Rect"),
    QgsProcessing=_make_mod("Proc", SourceType=_make_mod("ST", TypeVectorPolygon=0, TypeVectorAnyGeometry=1)),
)
qgis_qtgui = _make_mod("qgis.PyQt.QtGui", QColor=FakeQColor)
qgis_qtcore = _make_mod("qgis.PyQt.QtCore", QVariant=lambda v=None: v)

# Wire package hierarchy
qgis_mod = _make_mod("qgis", core=qgis_core)
qgis_pyqt = _make_mod("qgis.PyQt", QtGui=qgis_qtgui, QtCore=qgis_qtcore)

sys.modules["qgis"] = qgis_mod
sys.modules["qgis.core"] = qgis_core
sys.modules["qgis.PyQt"] = qgis_pyqt
sys.modules["qgis.PyQt.QtGui"] = qgis_qtgui
sys.modules["qgis.PyQt.QtCore"] = qgis_qtcore

# Patch qgis.core.QgsGeometry inline for cartogram_engine
class FakeCentroid:
    def asPoint(self):
        class P: x = lambda s: 0.0; y = lambda s: 0.0
        return P()

class FakeGeometry:
    def __init__(self, wkt_or_obj=None):
        self._wkt = wkt_or_obj if isinstance(wkt_or_obj, str) else "POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))"
    def asWkt(self): return self._wkt
    def fromWkt(self, wkt):
        self._wkt = wkt
        return self
    def area(self): return 100.0
    def centroid(self): return FakeCentroid()
    def isEmpty(self): return False
    def isNull(self): return False
    def constParts(self): return []
    def buffer(self, dist, segs): return FakeGeometry()

qgis_core.QgsGeometry = FakeGeometry

# ---------------------------------------------------------------------------
# Add project root to path
# ---------------------------------------------------------------------------
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(PROJ))

from zero2cartolab.core import bivariate_engine as be
from zero2cartolab.core import dependency_manager as dm
from zero2cartolab.core import affine_matrix as am
from zero2cartolab.core import cartogram_engine as ce
from zero2cartolab.core import qgis_25d_style as s25d
from zero2cartolab.core import dot_density as dd
from zero2cartolab.core import proportional_symbols as psym
from zero2cartolab.core import hexgrid as hxg
from zero2cartolab.core import label_points as lblp
from zero2cartolab.core import graticule as grat
from zero2cartolab.core import normalize as norm
from zero2cartolab.core import layout_math as lm
from zero2cartolab.core import palettes as pal
from zero2cartolab.core import quick_style as qs
from zero2cartolab.core import color_accessibility as ca
from zero2cartolab.core import sun_lighting as sl
from zero2cartolab.core import publication_styler as ps

# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------
passed = 0
failed = 0
errors = []

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        msg = f"FAIL [{name}]: {detail}"
        errors.append(msg)
        print(f"  {msg}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ===================================================================
# 1. BIVARIATE ENGINE — Classification
# ===================================================================
section("Bivariate Engine — Classification")

# Test data
NORMAL   = [10, 15, 22, 25, 30, 35, 40, 55, 60, 70, 85, 100, 120, 150, 200]
SKEWED   = [1]*30 + [2]*15 + [5]*8 + [10]*4 + [50]*2 + [100, 200, 500]
NEGATIVE = [-50, -30, -10, 0, 10, 20, 30, 50, 80, 120]
UNIFORM  = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

# -- Geometric Interval --
breaks = be.geometric_interval_breaks(NORMAL, 5)
check("GIC returns n_classes+1 breaks", len(breaks) == 6, str(breaks))
check("GIC first break is min", abs(breaks[0] - min(NORMAL)) < 1, f"{breaks[0]} vs {min(NORMAL)}")
check("GIC last break >= max", breaks[-1] >= max(NORMAL), f"{breaks[-1]} vs {max(NORMAL)}")
check("GIC monotonic increasing", all(breaks[i] < breaks[i+1] for i in range(len(breaks)-1)))

breaks_neg = be.geometric_interval_breaks(NEGATIVE, 4)
check("GIC handles negative values", len(breaks_neg) == 5 and abs(breaks_neg[0] - min(NEGATIVE)) < 1)

breaks_skew = be.geometric_interval_breaks(SKEWED, 5)
check("GIC handles skewed data", len(breaks_skew) == 6)

breaks_two = be.geometric_interval_breaks([1, 100], 3)
check("GIC handles 2 values", len(breaks_two) == 4 and breaks_two[0] <= 1 and breaks_two[-1] >= 100)

breaks_same = be.geometric_interval_breaks([5, 5, 5, 5, 5], 3)
check("GIC handles identical values", len(breaks_same) == 4)

breaks_many = be.geometric_interval_breaks([1, 2, 3], 10)
check("GIC more classes than values", len(breaks_many) == 11)

# -- Head/Tail Breaks --
ht = be.head_tail_breaks(NORMAL)
check("Head/Tail returns >= 2 breaks", len(ht) >= 2, str(ht))
check("Head/Tail monotonic", all(ht[i] < ht[i+1] for i in range(len(ht)-1)))

ht_power = be.head_tail_breaks(SKEWED)
check("Head/Tail skewed data", len(ht_power) >= 2)

ht_small = be.head_tail_breaks([1, 2, 3])
check("Head/Tail handles tiny data", len(ht_small) >= 2)

# -- Fisher-Jenks --
fj = be.fisher_jenks_breaks(NORMAL, 5)
check("Fisher-Jenks returns n+1 breaks", len(fj) == 6)
check("Fisher-Jenks monotonic", all(fj[i] < fj[i+1] for i in range(len(fj)-1)))
check("Fisher-Jenks covers data", fj[0] <= min(NORMAL) and fj[-1] >= max(NORMAL))

fj_skew = be.fisher_jenks_breaks(SKEWED, 4)
check("Fisher-Jenks skewed ok", len(fj_skew) == 5)

fj_many_classes = be.fisher_jenks_breaks(NORMAL, len(NORMAL) - 1)
check("Fisher-Jenks many classes ok", len(fj_many_classes) == len(NORMAL))

# -- Standard Deviation Breaks --
sdb = be.standard_deviation_breaks(NORMAL, 5)
check("Standard Deviation returns >= 2 breaks", len(sdb) >= 2, str(sdb))
check("Standard Deviation monotonic", all(sdb[i] < sdb[i+1] for i in range(len(sdb)-1)))
check("Standard Deviation spans bounds", sdb[0] == min(NORMAL) and sdb[-1] >= max(NORMAL))

sdb_neg = be.standard_deviation_breaks(NEGATIVE, 4)
check("Standard Deviation handles negative", len(sdb_neg) >= 2 and sdb_neg[0] == min(NEGATIVE))

sdb_same = be.standard_deviation_breaks([10, 10, 10, 10], 5)
check("Standard Deviation handles constant", len(sdb_same) == 2)

sdb_custom_std = be.standard_deviation_breaks(NORMAL, 5, interval_std=1.0)
check("Standard Deviation custom interval", len(sdb_custom_std) >= 2)

# -- Box Plot / Tukey Breaks --
bpb = be.box_plot_breaks(NORMAL)
check("Box Plot returns >= 3 breaks", len(bpb) >= 3, str(bpb))
check("Box Plot monotonic", all(bpb[i] < bpb[i+1] for i in range(len(bpb)-1)))
check("Box Plot spans bounds", bpb[0] == min(NORMAL) and bpb[-1] >= max(NORMAL))

bpb_outliers = be.box_plot_breaks([-100, 10, 12, 14, 15, 16, 18, 20, 500], iqr_multiplier=1.5)
check("Box Plot isolates extreme outliers", bpb_outliers[0] == -100 and bpb_outliers[-1] >= 500)

tukey_b = be.tukey_breaks(NORMAL)
check("Tukey alias matches box plot", tukey_b == bpb)

bpb_small = be.box_plot_breaks([1, 2, 3])
check("Box Plot handles small dataset", len(bpb_small) == 2)

# -- Equal Area / Quantile Refinement --
eab = be.equal_area_breaks(NORMAL, n_classes=5)
check("Equal area unweighted returns n+1 breaks", len(eab) == 6, str(eab))
check("Equal area unweighted monotonic", all(eab[i] < eab[i+1] for i in range(len(eab)-1)))

weights = [100, 100, 100, 100]
eab_w = be.equal_area_breaks([10, 20, 30, 40], weights=weights, n_classes=4)
check("Equal area weighted returns breaks", len(eab_w) == 5, str(eab_w))
check("Equal area weighted monotonic", all(eab_w[i] < eab_w[i+1] for i in range(len(eab_w)-1)))

# -- _validate_values --
try:
    be._validate_values([])
    check("_validate_values raises ValueError on empty", False)
except ValueError:
    check("_validate_values raises ValueError on empty", True)

vals = be._validate_values([None, math.nan, 5, float('inf'), 10, -float('inf'), 15])
check("_validate_values filters garbage", vals == [5, 10, 15], str(vals))

# ===================================================================
# 2. BIVARIATE ENGINE — Colours & VbA
# ===================================================================
section("Bivariate Engine — Colours & VbA")

matrix = be.bivariate_colour_matrix(4)
check("Colour matrix 4 rows", len(matrix) == 4)
check("Colour matrix each 4 cols", all(len(r) == 4 for r in matrix))
for row in matrix:
    for c in row:
        check("Colour matrix valid RGB", 0 <= c.red() <= 255 and 0 <= c.green() <= 255 and 0 <= c.blue() <= 255)

m2 = be.bivariate_colour_matrix(7)
check("Colour matrix 7x7", len(m2) == 7 and len(m2[0]) == 7)

m1 = be.bivariate_colour_matrix(2)
check("Colour matrix 2x2", len(m1) == 2 and len(m1[0]) == 2)

check("BIVARIATE_PALETTE_PRESETS has teal_brown", "teal_brown" in be.BIVARIATE_PALETTE_PRESETS)
check("BIVARIATE_PALETTE_PRESETS has stevens_pink_cyan", "stevens_pink_cyan" in be.BIVARIATE_PALETTE_PRESETS)
check("BIVARIATE_PALETTE_PRESETS has pink_green", "pink_green" in be.BIVARIATE_PALETTE_PRESETS)
m_hex = be.bivariate_colour_matrix_hex(3, "#e8e8e8", "#5ab4ac", "#d8b365", "#8c510a")
check("bivariate_colour_matrix_hex returns 3x3 hex strings", len(m_hex) == 3 and len(m_hex[0]) == 3 and m_hex[0][0].startswith("#"))
m_hex_preset = be.bivariate_colour_matrix_hex(size=4, preset="teal_brown")
check("bivariate_colour_matrix_hex with preset returns 4x4", len(m_hex_preset) == 4 and len(m_hex_preset[0]) == 4)
m_hex_alias = be.bivariate_colour_matrix_hex("stevens_pink_cyan", n_classes=3)
check("bivariate_colour_matrix_hex with positional preset and n_classes returns 3x3", len(m_hex_alias) == 3 and len(m_hex_alias[0]) == 3)

# -- Value-by-Alpha --
p_vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
r_vals = [90, 80, 70, 60, 50, 40, 30, 20, 10, 5]
alphas = be.compute_alpha_values(p_vals, r_vals, 30, 255)
check("VbA len matches input", len(alphas) == 10)
check("VbA values in alpha range", all(30 <= a <= 255 for a in alphas))

alphas2 = be.compute_alpha_values(p_vals[:5], p_vals[:5], 10, 200)
check("VbA small set ok", len(alphas2) == 5)
check("VbA small set range ok", all(10 <= a <= 200 for a in alphas2))

# Identical reliability — all max alpha
alphas3 = be.compute_alpha_values([10, 20, 30], [50, 50, 50], 0, 255)
check("VbA identical reliability", len(set(alphas3)) == 1, str(alphas3))

# Sparse valid values must follow the same null policy as the Jenks path.
alphas4 = be.compute_alpha_values([10, 20, 30], [1, None, 3], 30, 255)
check("VbA sparse null keeps output aligned", len(alphas4) == 3, str(alphas4))
check("VbA sparse null uses minimum opacity", alphas4[1] == 30, str(alphas4))
check("VbA sparse values stay bounded", all(30 <= a <= 255 for a in alphas4))

# ===================================================================
# 3. AFFINE MATRIX
# ===================================================================
section("Affine Matrix")

ident = am.AffineMatrix.identity()
check("identity a,b,c,d,tx,ty", (ident.a, ident.b, ident.c, ident.d, ident.tx, ident.ty) == (1, 0, 0, 1, 0, 0))
check("identity transform preserves x", ident.transform_point(5, 10)[0] == 5)
check("identity transform preserves y", ident.transform_point(5, 10)[1] == 10)

iso = am.AffineMatrix.from_isometric_angles(30, 100, math.degrees(math.atan(1 / math.sqrt(2))))
check("isometric a nonzero", iso.a != 0 or iso.b != 0)

tx, ty = iso.transform_point(100, 200)
check("isometric transform returns 2-tuple", isinstance(tx, float) and isinstance(ty, float))

comp = ident.compose(iso)
check("compose with identity a", abs(comp.a - iso.a) < 1e-9)
check("compose with identity d", abs(comp.d - iso.d) < 1e-9)

tr = ident.translate(15, 25)
check("translate origin", tr.transform_point(0, 0) == (15, 25))

sc = ident.scale(2, 3)
check("scale apply", sc.transform_point(10, 10) == (20, 30))

offsets = am.compute_isometric_layer_offsets(5, 50, 30, 35.264)
check("iso offsets len", len(offsets) == 5)
check("iso offsets dy ascending", all(offsets[i][1] < offsets[i+1][1] for i in range(4)))
check("iso offsets dx follow the tilt angle",
      all(abs(dx - i * 50 * math.sin(math.radians(30))) < 1e-9 for i, (dx, _) in enumerate(offsets)))
check("iso offsets dx zero at 0 deg tilt",
      all(dx == 0.0 for dx, _ in am.compute_isometric_layer_offsets(4, 50, 0, 35.264)))
check("iso offsets steeper tilt shifts further",
      am.compute_isometric_layer_offsets(2, 50, 60, 35.264)[1][0] > offsets[1][0])

# ===================================================================
# 4. CARTOGRAM ENGINE
# ===================================================================
section("Cartogram Engine")

mock_geom = FakeGeometry("POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))")
cf = ce.CartogramFeature(1, mock_geom, 25.0)
check("CartogramFeature created", cf.id == 1)
check("CartogramFeature value", cf.value == 25.0)
check("CartogramFeature has WKT", cf.wkt_str is not None and "POLYGON" in cf.wkt_str)

# Edge: zero value
cf_zero = ce.CartogramFeature(2, mock_geom, 0.0)
check("CartogramFeature zero value clamped", cf_zero.value == 1e-12)

# Edge: None value
cf_none = ce.CartogramFeature(3, mock_geom, None)
check("CartogramFeature None value clamped", cf_none.value == 1e-12)

# Edge: null geometry raises
try:
    ce.CartogramFeature(4, None, 10.0)
    check("CartogramFeature rejects null geometry", False)
except ValueError:
    check("CartogramFeature rejects null geometry", True)

# ===================================================================
# 5. DEPENDENCY MANAGER
# ===================================================================
section("Dependency Manager")

avail, miss_req, miss_opt = dm.check_packages(dm.CARTO_LAB_DEPS)
check("check_packages returns 3 lists", all(isinstance(x, list) for x in [avail, miss_req, miss_opt]))
check("numpy tracked", "numpy" in avail or "numpy" in miss_req)
check("matplotlib tracked", "matplotlib" in avail or "matplotlib" in miss_opt)

report = dm.get_status_report(dm.CARTO_LAB_DEPS, "TEST")
check("status report non-empty string", isinstance(report, str) and len(report) > 50)
check("status report title present", "TEST" in report)
check("status report has OK marker", "[OK]" in report or "[!!]" in report)

# dependency_manager must NOT be able to install anything (no subprocess/pip):
check("no install_packages (Hub security)", not hasattr(dm, "install_packages"))
check("no ensure_required (Hub security)", not hasattr(dm, "ensure_required"))
check("dependency_manager does not import subprocess",
      "subprocess" not in dir(dm))

# ===================================================================
# 6. QGIS 2.5D STYLE
# ===================================================================
section("QGIS 2.5D Style")

cfg = s25d.Style25DConfig(
    height_field="Hmax",
    height_scale=1.5,
    max_height=60,
    stepped=True,
    step_height=3.5,
)
expr = s25d.build_height_expression(cfg)
check("25D expression quotes field", '"Hmax"' in expr, expr)
check("25D expression scales height", "* 1.5" in expr, expr)
check("25D expression steps height", "round(" in expr and "/ 3.5" in expr, expr)
check("25D expression avoids unsupported clamp functions", "greatest(" not in expr and "least(" not in expr, expr)
check("25D expression clamps height with CASE", "CASE WHEN" in expr and "THEN 60" in expr, expr)

summary = s25d.build_style_summary("Buildings", cfg)
check("25D summary names layer", "Buildings" in summary)
check("25D summary names field", "Hmax" in summary)
floor_cfg = s25d.Style25DConfig(
    height_field="Kat_Sayisi",
    height_mode=s25d.HEIGHT_MODE_FLOOR_COUNT,
    floor_height=3.5,
)
floor_expr = s25d.build_height_expression(floor_cfg)
check("25D floor count expression uses floor height", '"Kat_Sayisi"' in floor_expr and "* 3.5" in floor_expr, floor_expr)
check("25D has urban_gold preset", "urban_gold" in s25d.STYLE_25D_PRESETS)
check("25D has cyberpunk_night preset", "cyberpunk_night" in s25d.STYLE_25D_PRESETS)
check("25D has nordic_minimalist preset", "nordic_minimalist" in s25d.STYLE_25D_PRESETS)
check("estimate_building_height 5 floors", abs(s25d.estimate_building_height(5, 3.2) - 16.0) < 1e-6)

check("25D floor field detected", s25d.looks_like_floor_count_field("Kat_Sayisi"))
check("25D floor field detected with spaces", s25d.looks_like_floor_count_field("Kat Sayisi"))
floor_summary = s25d.build_style_summary("Buildings", floor_cfg)
check("25D floor summary explains source", "Height source: floor count" in floor_summary and "Floor height: 3.5" in floor_summary, floor_summary)

band_cfg = s25d.Style25DConfig(
    height_field="Kat_Sayisi",
    height_mode=s25d.HEIGHT_MODE_FLOOR_COUNT,
    render_mode=s25d.RENDER_MODE_FLOOR_BANDS,
    floor_palette="planning_bands",
    floor_height=3.5,
    max_floors=8,
)
floor_count_expr = s25d.build_floor_count_expression(band_cfg)
check("25D floor count expression rounds safely", "to_int(round(to_real(\"Kat_Sayisi\")))" in floor_count_expr, floor_count_expr)
check("25D floor count expression clamps negative", "CASE WHEN" in floor_count_expr and "THEN 0" in floor_count_expr, floor_count_expr)
wall_expr = s25d.build_floor_band_wall_expression(band_cfg, 3)
roof_expr = s25d.build_floor_band_roof_expression(band_cfg, 3, 8)
top_roof_expr = s25d.build_floor_band_roof_expression(band_cfg, 8, 8)
check("25D floor band wall uses extrusion", "segments_to_lines" in wall_expr and "extrude" in wall_expr and "order_parts" in wall_expr, wall_expr)
check("25D floor band wall gates by floor", ">= 3" in wall_expr, wall_expr)
check("25D floor band roof gates exact floor", "= 3" in roof_expr and "translate($geometry" in roof_expr, roof_expr)
check("25D top floor cap catches taller buildings", ">= 8" in top_roof_expr, top_roof_expr)
check("25D floor legend labels regular floors", s25d.build_floor_band_legend_label(band_cfg, 3, 8) == "Floor 3 (10.5 units)")
check("25D floor legend labels top catch-all", s25d.build_floor_band_legend_label(band_cfg, 8, 8) == "Floor 8+ (28 units)")
check("25D floor band height scales", s25d.floor_band_height(s25d.Style25DConfig(
    height_field="Kat_Sayisi",
    height_mode=s25d.HEIGHT_MODE_FLOOR_COUNT,
    floor_height=3.5,
    height_scale=2,
)) == 7.0)
auto_band_cfg = s25d.Style25DConfig(
    height_field="Kat_Sayisi",
    height_mode=s25d.HEIGHT_MODE_FLOOR_COUNT,
    render_mode=s25d.RENDER_MODE_FLOOR_BANDS,
    max_floors=0,
)
check("25D auto max floors detected", s25d.is_auto_max_floors(auto_band_cfg))
check("25D auto max floors fallback safe", s25d.sanitised_max_floors(auto_band_cfg) == s25d.DEFAULT_MAX_FLOORS)
check("25D floor count value normalises", s25d.normalise_floor_count_value("5.4") == 5 and s25d.normalise_floor_count_value("-2") == 0)
auto_summary = s25d.build_style_summary("Buildings", auto_band_cfg)
check("25D auto max floor summary", "Maximum floor bands: auto from layer" in auto_summary, auto_summary)
check("25D floor palette colour valid", s25d.HEX_COLOR_RE.match(s25d.floor_band_color(2, "planning_bands")))
check("25D floor wall colour differs", s25d.floor_band_color(2, "planning_bands", wall=True) != s25d.floor_band_color(2, "planning_bands"))
band_summary = s25d.build_style_summary("Buildings", band_cfg)
check("25D floor band summary names renderer", "Renderer: per-floor colour bands" in band_summary and "Maximum floor bands: 8" in band_summary, band_summary)
check("25D floor band summary explains legend", "Legend: one rule per floor band" in band_summary, band_summary)

order_expr = s25d.build_order_by_expression()
check("25D order expression uses map extent", "@map_extent_center" in order_expr)
check("25D presets exist", len(s25d.STYLE_25D_PRESETS) >= 4)
check("25D preset colours are valid", all(
    s25d.HEX_COLOR_RE.match(p["roof"]) and s25d.HEX_COLOR_RE.match(p["wall"]) and s25d.HEX_COLOR_RE.match(p["shadow"])
    for p in s25d.STYLE_25D_PRESETS.values()
))
check("25D floor palettes exist", len(s25d.FLOOR_BAND_PALETTES) >= 3)
check("25D floor palette colours are valid", all(
    s25d.HEX_COLOR_RE.match(color)
    for p in s25d.FLOOR_BAND_PALETTES.values()
    for color in p["colors"]
))
check("25D colour fallback", s25d.normalise_hex_color("bad", "#123456") == "#123456")

# ===================================================================
# 7. DOT DENSITY
# ===================================================================
section("Dot Density")

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]
HOLE = [(4, 4), (6, 4), (6, 6), (4, 6)]

check("dots_for_value rounds", dd.dots_for_value(250, 50) == 5, str(dd.dots_for_value(250, 50)))
check("dots_for_value floor", dd.dots_for_value(249, 50, "floor") == 4)
check("dots_for_value ceil", dd.dots_for_value(201, 50, "ceil") == 5)
check("dots_for_value zero value", dd.dots_for_value(0, 50) == 0)
check("dots_for_value negative value", dd.dots_for_value(-100, 50) == 0)
check("dots_for_value bad per_dot", dd.dots_for_value(100, 0) == 0)
check("dots_for_value None", dd.dots_for_value(None, 50) == 0)

check("point_in_polygon inside", dd.point_in_polygon([SQUARE], 5, 5) is True)
check("point_in_polygon outside", dd.point_in_polygon([SQUARE], 15, 5) is False)
check("point_in_polygon in hole = outside", dd.point_in_polygon([SQUARE, HOLE], 5, 5) is False)
check("point_in_polygon between hole and edge", dd.point_in_polygon([SQUARE, HOLE], 1, 1) is True)

ddots = dd.generate_dots([SQUARE], (0, 0, 10, 10), 50, seed=7)
check("generate_dots count", len(ddots) == 50, str(len(ddots)))
check("generate_dots all inside", all(dd.point_in_polygon([SQUARE], x, y) for x, y in ddots))
check("generate_dots deterministic", ddots == dd.generate_dots([SQUARE], (0, 0, 10, 10), 50, seed=7))
check("generate_dots seed varies", ddots != dd.generate_dots([SQUARE], (0, 0, 10, 10), 50, seed=8))
check("generate_dots hole excluded", all(not dd.point_in_polygon([HOLE], x, y)
                                          for x, y in dd.generate_dots([SQUARE, HOLE], (0, 0, 10, 10), 30, seed=3)))
check("generate_dots zero count", dd.generate_dots([SQUARE], (0, 0, 10, 10), 0, seed=1) == [])
check("generate_dots degenerate bbox", dd.generate_dots([SQUARE], (0, 0, 0, 0), 5, seed=1) == [])

# ===================================================================
# 8. PROPORTIONAL SYMBOLS
# ===================================================================
section("Proportional Symbols")

check("symbol_size at max == max", abs(psym.symbol_size(100, 100, 8.0) - 8.0) < 1e-9)
check("symbol_size min for zero", psym.symbol_size(0, 100, 8.0, 1.0) == 1.0)
check("symbol_size min for negative", psym.symbol_size(-5, 100, 8.0, 1.0) == 1.0)
check("symbol_size monotonic", psym.symbol_size(25, 100, 8.0) < psym.symbol_size(75, 100, 8.0))
check("symbol_size within bounds", 1.0 <= psym.symbol_size(40, 100, 8.0, 1.0) <= 8.0)
check("symbol_size flannery differs from linear",
      abs(psym.symbol_size(25, 100, 8.0, 0.0, True) - psym.symbol_size(25, 100, 8.0, 0.0, False)) > 1e-6)
check("symbol_size flannery more spread at mid", psym.symbol_size(25, 100, 8.0, 0.0, True) < psym.symbol_size(25, 100, 8.0, 0.0, False))
check("symbol_size bad vmax", psym.symbol_size(5, 0, 8.0, 1.0) == 1.0)
check("symbol_size clamps over-max", abs(psym.symbol_size(200, 100, 8.0) - 8.0) < 1e-9)
check("symbol_size None value", psym.symbol_size(None, 100, 8.0, 1.0) == 1.0)

leg = psym.nice_legend_values(0, 4200, 3)
check("legend descending", leg == sorted(leg, reverse=True) and len(leg) >= 1, str(leg))
check("legend distinct", len(leg) == len(set(leg)))
check("legend top not above max", leg[0] <= 4200, str(leg))
check("legend all positive", all(v > 0 for v in leg))
check("legend empty for nonpositive max", psym.nice_legend_values(0, 0, 3) == [])

# ===================================================================
# 9. HEXGRID
# ===================================================================
section("Hexgrid")

check("hex_vertices count", len(hxg.hex_vertices(0, 0, 3.0)) == 6)
for q, r in [(0, 0), (2, 1), (-3, 4), (5, -2), (10, -7)]:
    cx, cy = hxg.cell_center(q, r, 3.0)
    check(f"hex round-trip ({q},{r})", hxg.point_to_cell(cx, cy, 3.0) == (q, r),
          f"{hxg.point_to_cell(cx, cy, 3.0)}")
cx0, cy0 = hxg.cell_center(4, 4, 5.0)
check("hex point near centre maps to cell", hxg.point_to_cell(cx0 + 0.4, cy0 - 0.4, 5.0) == (4, 4))
cells = {hxg.point_to_cell(x * 0.5, y * 0.5, 2.0) for x in range(20) for y in range(20)}
check("hex binning many points", len(cells) >= 4)
verts = hxg.hex_vertices(10, 10, 4.0)
check("hex_vertices around centre", all(abs(((vx - 10) ** 2 + (vy - 10) ** 2) ** 0.5 - 4.0) < 1e-6 for vx, vy in verts))

# ===================================================================
# 10. LABEL POINTS (polylabel)
# ===================================================================
section("Label Points")

lx, ly, ld = lblp.polylabel([SQUARE])
check("polylabel square centre x", abs(lx - 5.0) < 0.2, str(lx))
check("polylabel square centre y", abs(ly - 5.0) < 0.2, str(ly))
check("polylabel square distance", abs(ld - 5.0) < 0.2, str(ld))
check("polylabel inside square", lblp.point_to_polygon_dist(lx, ly, [SQUARE]) > 0)

LSHAPE = [(0, 0), (10, 0), (10, 3), (3, 3), (3, 10), (0, 10)]
ax, ay, ad = lblp.polylabel([LSHAPE], 0.1)
check("polylabel L-shape inside", lblp.point_to_polygon_dist(ax, ay, [LSHAPE]) > 0)
check("polylabel L-shape positive dist", ad > 0)

hx2, hy2, hd2 = lblp.polylabel([SQUARE, HOLE], 0.1)
check("polylabel avoids hole", not dd.point_in_polygon([HOLE], hx2, hy2), f"({hx2:.2f},{hy2:.2f})")
check("polylabel degenerate ring", lblp.polylabel([[(0, 0), (1, 1)]])[2] == 0.0)

check("point_to_polygon_dist outside negative", lblp.point_to_polygon_dist(20, 20, [SQUARE]) < 0)
check("seg dist sq basic", abs(lblp._seg_dist_sq(0, 0, 3, 0, 3, 4) - 9.0) < 1e-9)

RECT_H = [(0, 0), (100, 0), (100, 10), (0, 10)]
deg_h = lblp.polygon_orientation_angle(RECT_H)
check("orientation angle horizontal rectangle is near 0", abs(deg_h) < 5.0, str(deg_h))

RECT_V = [(0, 0), (10, 0), (10, 100), (0, 100)]
deg_v = lblp.polygon_orientation_angle(RECT_V)
check("orientation angle vertical rectangle is near 90 or -90", abs(abs(deg_v) - 90.0) < 5.0, str(deg_v))

# ===================================================================
# 11. GRATICULE
# ===================================================================
section("Graticule")

check("nice_interval 100", grat.nice_interval(100) in (10.0, 20.0), str(grat.nice_interval(100)))
check("nice_interval monotone scale", grat.nice_interval(1000) > grat.nice_interval(100))
check("nice_interval tiny", grat.nice_interval(0.37) > 0)
check("nice_interval zero span", grat.nice_interval(0) == 1.0)

av = grat.aligned_values(3, 47, 10)
check("aligned_values multiples", av == [10, 20, 30, 40], str(av))
check("aligned_values within range", all(3 <= v <= 47 for v in av))
check("aligned_values bad step", grat.aligned_values(0, 10, 0) == [])

check("format_coord integer", grat.format_coord(20.0) == "20")
check("format_coord decimal", grat.format_coord(20.5) == "20.5")

glines = grat.graticule_lines(0, 0, 100, 80, 20, 20)
mer = [g for g in glines if g["orientation"] == "meridian"]
par = [g for g in glines if g["orientation"] == "parallel"]
check("graticule meridian count", len(mer) == 6, str(len(mer)))
check("graticule parallel count", len(par) == 5, str(len(par)))
check("graticule each line 2 points", all(len(g["points"]) == 2 for g in glines))
check("graticule meridian spans y", mer[0]["points"][0][1] == 0 and mer[0]["points"][1][1] == 80)
check("graticule points within extent",
      all(0 <= p[0] <= 100 and 0 <= p[1] <= 80 for g in glines for p in g["points"]))
check("graticule labels present", all(g["label"] for g in glines))

# ===================================================================
# 12. NORMALIZE
# ===================================================================
section("Normalize")

NV = [10, 20, 30, 40, 50]
zz = norm.z_scores(NV)
check("z_scores mean ~ 0", abs(sum(zz) / len(zz)) < 1e-9, str(zz))
check("z_scores std ~ 1", abs(norm.pstdev(zz) - 1.0) < 1e-9)
check("z_scores constant -> 0", norm.z_scores([5, 5, 5]) == [0.0, 0.0, 0.0])
check("z_scores keeps None", norm.z_scores([10, None, 30])[1] is None)

mm = norm.min_max(NV)
check("min_max range", mm == [0.0, 0.25, 0.5, 0.75, 1.0], str(mm))
check("min_max in 0-1", all(0.0 <= v <= 1.0 for v in mm))
check("min_max constant -> lo", norm.min_max([7, 7, 7]) == [0.0, 0.0, 0.0])
check("min_max custom range", norm.min_max([0, 10], 0, 100) == [0.0, 100.0])

rr = norm.rate([10, 20, 5], [100, 0, 50], 1000)
check("rate computes", abs(rr[0] - 100.0) < 1e-9, str(rr))
check("rate zero denom -> None", rr[1] is None)
check("rate scaled", abs(rr[2] - 100.0) < 1e-9)

pr = norm.percentile_rank([10, 20, 30, 40])
check("percentile ascending", pr == sorted(pr))
check("percentile bounds", all(0 <= v <= 100 for v in pr))

rz = norm.robust_z([1, 2, 3, 4, 5, 6, 7, 100])
check("robust_z flags outlier", rz[-1] > 5, str(rz[-1]))
check("robust_z median centred", abs(norm.median([1, 2, 3, 4, 5, 6, 7, 100]) - 4.5) < 1e-9)
check("robust_z degenerate MAD -> 0", norm.robust_z([5, 5, 5, 5, 100])[0] == 0.0)

lg = norm.log_scale([1, 10, 100, 1000])
check("log_scale base10", all(abs(a - b) < 1e-9 for a, b in zip(lg, [0.0, 1.0, 2.0, 3.0])), str(lg))
check("log_scale shifts nonpositive", all(v is not None for v in norm.log_scale([-5, 0, 5])))
lq = norm.location_quotient([10, 20], [100, 100])
check("location_quotient computes relative specialisation", lq[0] < 1.0 < lq[1], str(lq))

wmm = norm.winsorized_min_max([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000], 10.0, 90.0)
check("winsorized_min_max caps extreme outlier", wmm[-1] == 1.0 and wmm[0] == 0.0, str(wmm))

dr = norm.decile_rank([10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
check("decile_rank assigns deciles 1 to 10", dr[0] == 1 and dr[-1] == 10, str(dr))

# -- New transforms: sigmoid, power_transform, quantile_normalize --
sig = norm.sigmoid_scale([10, 20, 30, 40, 50])
check("sigmoid_scale bounds in 0-1", all(0.0 <= s <= 1.0 for s in sig if s is not None))
check("sigmoid_scale preserves None", norm.sigmoid_scale([10, None, 30])[1] is None)

pw = norm.power_transform([1, 4, 9, 16, 25], lmbda=0.5)
check("power_transform computes square root transform", len(pw) == 5 and all(p is not None for p in pw))

pw_log = norm.power_transform([1, 10, 100], lmbda=0.0)
check("power_transform lmbda=0 falls back to log", abs(pw_log[0] - 0.0) < 0.01)

qn = norm.quantile_normalize([10, 20, 30, 40, 50])
check("quantile_normalize produces uniform [0, 1]", qn[0] == 0.1 and qn[-1] == 0.9, str(qn))

riqr = norm.robust_iqr([10, 20, 30, 40, 50])
check("robust_iqr median centred", abs(riqr[2]) < 1e-6, str(riqr))
check("robust_iqr monotonic", riqr[0] < riqr[1] < riqr[2] < riqr[3] < riqr[4])

thr = norm.tukey_hinge_rank([-100, 10, 20, 30, 40, 500])
check("tukey_hinge_rank assigns classes 1 to 6", thr[0] == 1 and thr[-1] == 6, str(thr))

check("normalize methods catalogue >= 14", len(norm.METHODS) >= 14)

# ===================================================================
# 13. LAYOUT MATH — nice intervals, unique names, page geometry
# ===================================================================
section("Layout Math")

check("nice_number 625 -> 500", lm.nice_number(625) == 500.0, str(lm.nice_number(625)))
check("nice_number 8 -> 10", lm.nice_number(8) == 10.0, str(lm.nice_number(8)))
check("nice_number 0.0043 -> 0.005",
      abs(lm.nice_number(0.0043) - 0.005) < 1e-9, str(lm.nice_number(0.0043)))
check("nice_number ceil 2.1 -> 5", lm.nice_number(2.1, round_down=False) == 5.0,
      str(lm.nice_number(2.1, round_down=False)))
check("nice_number nonpositive -> 0", lm.nice_number(0) == 0.0 and lm.nice_number(-5) == 0.0)

iv = lm.nice_interval(5000.0, 8)
check("nice_interval 5000/8 rounded", iv == 500.0, str(iv))
check("nice_interval splits span into >=5 parts", 5000.0 / iv >= 5, str(5000.0 / iv))
check("nice_interval degrees span", lm.nice_interval(0.05, 8) > 0, str(lm.nice_interval(0.05, 8)))
check("nice_interval zero span -> 0", lm.nice_interval(0, 8) == 0.0)
check("nice_interval negative span -> 0", lm.nice_interval(-100, 8) == 0.0)

check("unique_name free base", lm.unique_name(["a", "b"], "Map") == "Map")
check("unique_name first collision -> 2", lm.unique_name(["Map"], "Map") == "Map 2")
check("unique_name chained collisions",
      lm.unique_name(["Map", "Map 2", "Map 3"], "Map") == "Map 4",
      lm.unique_name(["Map", "Map 2", "Map 3"], "Map"))

check("page A4 portrait", lm.page_size_mm("A4", landscape=False) == (210.0, 297.0))
check("page A4 landscape swaps axes", lm.page_size_mm("A4", landscape=True) == (297.0, 210.0))
check("page unknown falls back to A4",
      lm.page_size_mm("ZZ", landscape=False) == (210.0, 297.0))
check("page A3 landscape", lm.page_size_mm("A3", landscape=True) == (420.0, 297.0))
check("page square is genuinely square", lm.page_size_mm("SQUARE") == (250.0, 250.0))
check("map_width_to_km metres", lm.map_width_to_km(12500.0, 0.001) == 12.5)
check("map_width_to_km kilometres factor", lm.map_width_to_km(12.5, 1.0) == 12.5)
check("map_width_to_km rejects invalid",
      lm.map_width_to_km(-1.0, 0.001) == 0.0 and lm.map_width_to_km(10.0, 0.0) == 0.0)
fit_seg, fit_right, fit_left = lm.fitted_scalebar_segments(450.0, 220.0, 55.0, 3)
fit_physical_mm = (fit_seg * fit_right / 450.0) * 220.0
check("fitted scalebar respects narrow sidebar", fit_physical_mm <= 55.0,
      (fit_seg, fit_right, fit_physical_mm))
check("fitted scalebar uses clean segment", fit_seg in (1, 2, 5, 10, 20, 50, 100))

# ===================================================================
# 14. PALETTES — ColorBrewer + scientific colour ramps
# ===================================================================
section("Palettes")

def _is_hex(c):
    return isinstance(c, str) and len(c) == 7 and c[0] == "#" and \
        all(ch in "0123456789abcdefABCDEF" for ch in c[1:])

# every palette yields valid hex at several class counts
_bad = []
for _name in pal.PALETTES:
    for _n in (1, 3, 5, 7):
        cols = pal.get_palette(_name, _n)
        if len(cols) != _n or not all(_is_hex(c) for c in cols):
            _bad.append(f"{_name}@{_n}")
check("all palettes produce n valid hex colours", not _bad, str(_bad[:5]))

# sequential endpoints match the gradient ends
blues = pal.get_palette("Blues", 9)
check("sequential get_palette length", len(blues) == 9)
check("sequential first == first stop", blues[0].lower() == "#f7fbff")
check("sequential last == last stop", blues[-1].lower() == "#08306b")

# single class returns one colour
check("get_palette n=1 -> one colour", len(pal.get_palette("Viridis", 1)) == 1)
check("get_palette n=0 -> empty", pal.get_palette("Viridis", 0) == [])

# qualitative takes swatches in order and cycles when short
set2 = pal.get_palette("Set2", 3)
check("qualitative first three exact",
      set2 == ["#66c2a5", "#fc8d62", "#8da0cb"], str(set2))
check("qualitative cycles when n>len",
      len(pal.get_palette("Set2", 20)) == 20)

# colour-blind safety flags for new & classic ramps
check("batlow is cb-safe", pal.is_colorblind_safe("Batlow"))
check("twilight is cb-safe", pal.is_colorblind_safe("Twilight"))
check("sunset is cb-safe", pal.is_colorblind_safe("Sunset"))
check("roma is cb-safe", pal.is_colorblind_safe("Roma"))
check("tealrose is cb-safe", pal.is_colorblind_safe("TealRose"))
check("bamako is cb-safe", pal.is_colorblind_safe("Bamako"))
check("nuuk is cb-safe", pal.is_colorblind_safe("Nuuk"))
check("viridis is cb-safe", pal.is_colorblind_safe("Viridis"))
check("mako is cb-safe", pal.is_colorblind_safe("Mako"))
check("rocket is cb-safe", pal.is_colorblind_safe("Rocket"))
check("bathymetry is cb-safe", pal.is_colorblind_safe("Bathymetry"))
check("icefire is cb-safe", pal.is_colorblind_safe("IceFire"))
check("turbo is not cb-safe", not pal.is_colorblind_safe("Turbo"))
check("spectral is not cb-safe", not pal.is_colorblind_safe("Spectral"))
check("RdYlGn not cb-safe (red-green)", not pal.is_colorblind_safe("RdYlGn"))

# Batlow, Twilight, Sunset specific tests
batlow_5 = pal.get_palette("Batlow", 5)
check("Batlow samples 5 colors", len(batlow_5) == 5 and all(_is_hex(c) for c in batlow_5))

twilight_7 = pal.get_palette("Twilight", 7)
check("Twilight samples 7 colors", len(twilight_7) == 7 and all(_is_hex(c) for c in twilight_7))

sunset_6 = pal.get_palette("Sunset", 6)
check("Sunset samples 6 colors", len(sunset_6) == 6 and all(_is_hex(c) for c in sunset_6))

# Helper functions in palettes
check("reverse_palette reverses list", pal.reverse_palette(["#111111", "#222222"]) == ["#222222", "#111111"])
check("interpolate_palette interpolates", len(pal.interpolate_palette(["#000000", "#ffffff"], 5)) == 5)
check("blend_colors 50% blend", pal.blend_colors("#000000", "#ffffff", 0.5) == "#808080")
check("hex_to_rgb conversion", pal.hex_to_rgb("#ff8000") == (255, 128, 0))
check("rgb_to_hex conversion", pal.rgb_to_hex((255, 128, 0)) == "#ff8000")

# listing + filters
check("list all non-empty", len(pal.list_palettes()) == len(pal.PALETTES))
check("list sequential only", all(pal.palette_kind(n) == pal.SEQUENTIAL
                                  for n in pal.list_palettes(kind=pal.SEQUENTIAL)))
check("list cb-safe excludes Spectral", "Spectral" not in pal.list_palettes(cb_safe_only=True))
check("list cb-safe includes Batlow", "Batlow" in pal.list_palettes(cb_safe_only=True))

# defaults + unknown handling
check("default sequential is Viridis", pal.default_palette(pal.SEQUENTIAL) == "Viridis")
check("default diverging is RdBu", pal.default_palette(pal.DIVERGING) == "RdBu")
try:
    pal.get_palette("NoSuchPalette", 5)
    check("unknown palette raises", False)
except ValueError:
    check("unknown palette raises", True)

# ===================================================================
# 15. QUICK STYLE — class breaks
# ===================================================================
section("Quick Style")

vals = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
qb = qs.quantile_breaks(vals, 5)
check("quantile returns n+1 edges", len(qb) == 6, str(qb))
check("quantile edges monotonic", all(qb[i] <= qb[i + 1] for i in range(len(qb) - 1)))
check("quantile spans data", qb[0] == 1 and qb[-1] == 10)

ei = qs.equal_interval_breaks(vals, 5)
check("equal interval n+1 edges", len(ei) == 6)
check("equal interval evenly spaced",
      all(abs((ei[i + 1] - ei[i]) - 1.8) < 1e-9 for i in range(5)), str(ei))

check("quantile degenerate (all equal)", qs.quantile_breaks([5, 5, 5], 4) == [5, 5])
check("equal degenerate (all equal)", qs.equal_interval_breaks([5, 5, 5], 4) == [5, 5])
check("breaks ignore None", len(qs.quantile_breaks([1, None, 2, None, 3], 2)) == 3)
check("empty values -> empty", qs.quantile_breaks([], 5) == [])

jb = qs.jenks_breaks(vals, 3)
check("jenks breaks returns edges", len(jb) >= 3 and jb[0] == 1 and jb[-1] >= 10)

htb = qs.head_tail_breaks_method([1, 2, 3, 5, 8, 20, 50, 100, 500])
check("head_tail breaks returns edges", len(htb) >= 2)

sdb = qs.std_dev_breaks(vals, 5)
check("std_dev breaks returns edges", len(sdb) >= 2)

bpb_qs = qs.box_plot_breaks(vals, 5)
check("box_plot_breaks returns edges", len(bpb_qs) >= 3 and bpb_qs[0] == 1 and bpb_qs[-1] >= 10)

tukey_qs = qs.tukey_breaks(vals)
check("tukey_breaks returns edges", len(tukey_qs) >= 3)

eab_qs = qs.equal_area_breaks(vals, n=4)
check("equal_area_breaks returns edges", len(eab_qs) == 5)

mb = qs.maximum_breaks([1, 2, 3, 10, 11, 12, 100, 101, 102], 3)
check("maximum_breaks splits at largest gaps", len(mb) >= 3 and mb[0] == 1 and mb[-1] == 102)

pb = qs.pretty_breaks([12, 45, 78, 120, 340, 500], 5)
check("pretty_breaks produces monotonic breaks", len(pb) >= 3 and pb[0] <= 12 and pb[-1] >= 500)

cb_j = qs.compute_breaks(vals, qs.JENKS, 4)
check("compute_breaks with jenks works", len(cb_j) >= 4)
cb_max = qs.compute_breaks(vals, qs.MAXIMUM, 3)
check("compute_breaks with maximum breaks works", len(cb_max) >= 3)
cb_pretty = qs.compute_breaks(vals, qs.PRETTY, 4)
check("compute_breaks with pretty breaks works", len(cb_pretty) >= 3)
cb_bp = qs.compute_breaks(vals, qs.BOX_PLOT, 5)
check("compute_breaks with box plot works", len(cb_bp) >= 3)
cb_ea = qs.compute_breaks(vals, qs.EQUAL_AREA, 4)
check("compute_breaks with equal area works", len(cb_ea) == 5)
cb_sd = qs.compute_breaks(vals, qs.STD_DEV, 5)
check("compute_breaks with std dev works", len(cb_sd) >= 2)

check("dedupe drops zero-width", qs.dedupe_edges([1, 1, 2, 3, 3]) == [1, 2, 3])
check("edges_to_ranges pairs", qs.edges_to_ranges([0, 1, 2, 3]) ==
      [(0, 1), (1, 2), (2, 3)])
check("edges_to_ranges skips dup class",
      qs.edges_to_ranges([0, 0, 1, 2]) == [(0, 1), (1, 2)])

# ===================================================================
# 16. PRINT LAYOUT DESIGNER INTEGRATION
# ===================================================================
section("Print Layout Designer Integration")
from zero2cartolab.layout import designer_integration as di
check("designer_integration setup function exists", callable(di.setup_designer_integration))
check("designer_integration attach function exists", callable(di.attach_cartolab_to_designer))
check("designer_integration dock creator exists", callable(di.create_cartolab_layout_dock))
check("designer_integration teardown function exists", callable(di.teardown_designer_integration))
check("designer integration tracks docks by designer", isinstance(di._INTEGRATED_DESIGNERS, dict))

# ===================================================================
# 17. PAPER CANVAS THEMES
# ===================================================================
section("Paper Canvas Themes")
from zero2cartolab.layout import paper_themes as pt
check("paper themes dict exists", len(pt.PAPER_THEMES) >= 6)
check("blueprint theme exists", "blueprint" in pt.PAPER_THEMES)
check("sepia_atlas theme exists", "sepia_atlas" in pt.PAPER_THEMES)
check("swiss_modern theme exists", "swiss_modern" in pt.PAPER_THEMES)
check("dark_matter theme exists", "dark_matter" in pt.PAPER_THEMES)
check("warm_editorial theme exists", "warm_editorial" in pt.PAPER_THEMES)
check("japanese_washi theme exists", "japanese_washi" in pt.PAPER_THEMES)
check("apply_paper_theme function exists", callable(pt.apply_paper_theme))

# ===================================================================
# 18. PUBLICATION AUTO-STYLER ENGINE
# ===================================================================
section("Publication Auto-Styler Engine")
check("auto_style_layer function exists", callable(ps.auto_style_layer))
check("style_choropleth_layer function exists", callable(ps.style_choropleth_layer))
check("style_cartogram_layer function exists", callable(ps.style_cartogram_layer))
check("style_dot_density_layer function exists", callable(ps.style_dot_density_layer))
check("style_25d_layer function exists", callable(ps.style_25d_layer))
check("auto_style_layer handles None safely", ps.auto_style_layer(None) is False)
check("auto_style_layer 25d handles None safely", ps.auto_style_layer(None, "25d") is False)

# ===================================================================
# 19. VERTICAL SIDEBAR NAVIGATION WORKSPACE
# ===================================================================
section("Vertical Sidebar Navigation Workspace")
from zero2cartolab.ui import cartolab_dashboard as cd
check("CartoLabDashboard class exists", hasattr(cd, "CartoLabDashboard"))

from zero2cartolab.layout import legend_decorator as ld
check("add_scalebar_to_layout function exists", callable(ld.add_scalebar_to_layout))
check("add_scale_combo_to_layout function exists", callable(ld.add_scale_combo_to_layout))
check("add_north_arrow_to_layout function exists", callable(ld.add_north_arrow_to_layout))

from zero2cartolab.layout import legend_styler as ls
check("style_layout_legend function exists", callable(ls.style_layout_legend))

from zero2cartolab.layout import title_block as tb
check("add_publication_title_block function exists", callable(tb.add_publication_title_block))

from zero2cartolab.layout import locator_map as lm
check("add_locator_inset_map function exists", callable(lm.add_locator_inset_map))

from zero2cartolab.layout import coordinate_grid as cg
check("apply_coordinate_grid_decorator function exists", callable(cg.apply_coordinate_grid_decorator))

from zero2cartolab.layout import layout_optimizer as lo
check("optimize_layout_visual_balance function exists", callable(lo.optimize_layout_visual_balance))

# ===================================================================
# 20. COLOR ACCESSIBILITY & CONTRAST ENGINE
# ===================================================================
section("Color Accessibility & Contrast Engine")
check("relative_luminance black is 0.0", abs(ca.relative_luminance("#000000") - 0.0) < 0.001)
check("relative_luminance white is 1.0", abs(ca.relative_luminance("#ffffff") - 1.0) < 0.001)
cr = ca.contrast_ratio("#ffffff", "#000000")
check("contrast_ratio B/W is 21.0", abs(cr - 21.0) < 0.01)
sim_d = ca.simulate_cvd_hex("#ff0000", "deuteranopia")
check("CVD simulation returns valid hex", sim_d.startswith("#") and len(sim_d) == 7)

# CVD severity simulations
sim_p_half = ca.simulate_cvd_hex("#ff0000", "protanopia", severity=0.5)
check("CVD severity 0.5 returns valid hex", sim_p_half.startswith("#") and len(sim_p_half) == 7)
sim_anom = ca.simulate_cvd_hex("#00ff00", "deuteranomaly")
check("CVD anomaly returns valid hex", sim_anom.startswith("#") and len(sim_anom) == 7)

# WCAG 2.1 detailed evaluation
wcag_eval = ca.evaluate_wcag_contrast("#000000", "#ffffff", font_size_pt=10, is_bold=False)
check("evaluate_wcag_contrast B/W passes AA", wcag_eval["passes_aa"] is True)
check("evaluate_wcag_contrast B/W passes AAA", wcag_eval["passes_aaa"] is True)
check("evaluate_wcag_contrast normal text flag", wcag_eval["aa_normal_text"] is True)

wcag_large = ca.evaluate_wcag_contrast("#777777", "#ffffff", font_size_pt=18, is_bold=False)
check("evaluate_wcag_contrast large text detected", wcag_large["is_large_text"] is True)

# Suggest accessible color
sug_dark = ca.suggest_accessible_color("#888888", "#ffffff", target_ratio=4.5)
check("suggest_accessible_color meets target ratio on light bg", ca.contrast_ratio(sug_dark, "#ffffff") >= 4.5)

sug_light = ca.suggest_accessible_color("#888888", "#000000", target_ratio=4.5)
check("suggest_accessible_color meets target ratio on dark bg", ca.contrast_ratio(sug_light, "#000000") >= 4.5)

eval_res = ca.evaluate_palette_accessibility(["#ffffff", "#3b82f6", "#0f172a"])
check("evaluate_palette_accessibility has rating", "rating" in eval_res and "min_step_contrast" in eval_res)
check("evaluate_palette_accessibility has CVD distinctness", "deuteranopia" in eval_res["cvd_distinct"])

# CIE L*a*b* & Delta E
delta_e_same = ca.delta_e_cie76("#123456", "#123456")
check("Delta E same color is 0", abs(delta_e_same) < 0.001)

delta_e_diff = ca.delta_e_cie76("#000000", "#ffffff")
check("Delta E black vs white is ~100", delta_e_diff > 80.0)

# ===================================================================
# 21. SOLAR POSITION & 2.5D ARCHITECTURAL LIGHTING
# ===================================================================
section("Solar Position & 2.5D Architectural Lighting")
alt, az = sl.calculate_solar_position(latitude_deg=38.4, day_of_year=172, solar_hour=12.5)
check("solar altitude at noon is positive", alt > 60.0)
check("solar azimuth is valid degree", 0.0 <= az <= 360.0)
sun_res = sl.solar_to_25d_lighting(latitude_deg=38.4, season="summer_solstice", time_preset="afternoon_studio")
check("solar_to_25d_lighting returns shadow multiplier", "shadow_length_mult" in sun_res and sun_res["shadow_length_mult"] > 0)

# Lambertian shading contrast & shadow vectors
contrast = sl.calculate_solar_shading_contrast(45.0, 180.0, aspect_deg=180.0, slope_deg=30.0)
check("solar shading contrast in [0, 1]", 0.0 <= contrast <= 1.0)

dx, dy, length = sl.calculate_shadow_vector(45.0, 180.0, height=20.0)
check("shadow vector length positive", length > 0.0)

check("SOLAR_TIMES has dawn_crisp", "dawn_crisp" in sl.SOLAR_TIMES)
check("SOLAR_SEASONS has autumn_equinox", "autumn_equinox" in sl.SOLAR_SEASONS)

# ===================================================================
# 22. LAYOUT & EXTENSION TOOLS
# ===================================================================
section("Layout & Extension Tools")
from zero2cartolab.layout import atlas_builder as ab
check("setup_layout_atlas function exists", callable(ab.setup_layout_atlas))

from zero2cartolab.layout import typography_engine as te
check("apply_typography_hierarchy function exists", callable(te.apply_typography_hierarchy))
check("TYPOGRAPHY_PRESETS has swiss_modern", "swiss_modern" in te.TYPOGRAPHY_PRESETS)
check("TYPOGRAPHY_PRESETS has academic_serif", "academic_serif" in te.TYPOGRAPHY_PRESETS)

from zero2cartolab.core import qgis_25d_style as q25
check("25D preset emerald_metropolis exists", "emerald_metropolis" in q25.STYLE_25D_PRESETS)
check("25D preset terracotta_mediterranean exists", "terracotta_mediterranean" in q25.STYLE_25D_PRESETS)
check("25D floor palette turbo_height exists", "turbo_height" in q25.FLOOR_BAND_PALETTES)
check("25D floor palette viridis_height exists", "viridis_height" in q25.FLOOR_BAND_PALETTES)

from zero2cartolab.core.utils import (
    resolve_layers_by_id,
    safe_float,
    safe_int,
)
check("safe_float cleans meter suffix '8 m'", safe_float("8 m") == 8.0)
check("safe_float cleans area suffix '15.5 sqm'", safe_float("15.5 sqm") == 15.5)
check("safe_int cleans floor suffix '4 floors'", safe_int("4 floors") == 4)

_same_name_a = object()
_same_name_b = object()
_resolved = resolve_layers_by_id(
    ["layer-b", "stale", "layer-a", "layer-b"],
    {"layer-a": _same_name_a, "layer-b": _same_name_b},
)
check(
    "isometric selection resolves IDs, ignores stale/duplicate IDs and keeps order",
    _resolved == [_same_name_b, _same_name_a],
)
check(
    "isometric selection respects a zero layer limit",
    resolve_layers_by_id(["layer-a"], {"layer-a": _same_name_a}, limit=0) == [],
)

from zero2cartolab.layout import map_sheet as ms
check("create_map_sheet is callable", callable(ms.create_map_sheet))

from zero2cartolab.layout import locator_map as lm
check("add_locator_inset_map is callable", callable(lm.add_locator_inset_map))

from zero2cartolab.layout import isometric_stacker as iso
check("create_isometric_stack_layout is callable", callable(iso.create_isometric_stack_layout))

from zero2cartolab.ui import floating_annotation as fa
check("FloatingAnnotationTool class exists", hasattr(fa, "FloatingAnnotationTool"))

# ===================================================================
# 23. TEMPLATE GALLERY & PUBLICATION ARCHETYPES
# ===================================================================
section("Template Gallery & Publication Archetypes")
from zero2cartolab.layout import template_gallery as tg
check("TEMPLATE_GALLERY exists and has 10 archetypes", len(tg.TEMPLATE_GALLERY) == 10)
check("report_figure template registered", "report_figure" in tg.TEMPLATE_GALLERY)
check("academic_journal template registered", "academic_journal" in tg.TEMPLATE_GALLERY)
check("exhibition_poster template registered", "exhibition_poster" in tg.TEMPLATE_GALLERY and tg.get_template_info("poster_exhibition") is not None)
check("fact_sheet template registered", "fact_sheet" in tg.TEMPLATE_GALLERY)
check("diptych template registered", "diptych" in tg.TEMPLATE_GALLERY and tg.get_template_info("side_by_side_diptych") is not None)
for _advanced_template in ("utm_field_sheet", "planning_board", "data_story",
                           "atlas_production", "emergency_brief"):
    check(f"advanced template {_advanced_template} registered", _advanced_template in tg.TEMPLATE_GALLERY)

check("create_report_figure is callable", callable(tg.create_report_figure))
check("create_academic_journal is callable", callable(tg.create_academic_journal))
check("create_exhibition_poster is callable", callable(tg.create_exhibition_poster))
check("create_fact_sheet is callable", callable(tg.create_fact_sheet))
check("create_diptych is callable", callable(tg.create_diptych))
check("create_template_layout is callable", callable(tg.create_template_layout))

# Verify schema of each template in gallery
for tkey, tinfo in tg.TEMPLATE_GALLERY.items():
    check(f"template {tkey} has valid name", isinstance(tinfo.get("name"), str) and len(tinfo["name"]) > 0)
    check(f"template {tkey} has category", isinstance(tinfo.get("category"), str))
    check(f"template {tkey} has tagline", isinstance(tinfo.get("tagline"), str))
    check(f"template {tkey} has description", isinstance(tinfo.get("description"), str))
    check(f"template {tkey} has features list", isinstance(tinfo.get("features"), list) and len(tinfo["features"]) >= 3)
    check(f"template {tkey} has callable builder", callable(tinfo.get("builder")))
    check(f"template {tkey} has default_page", tinfo.get("default_page") in ("A4", "A3", "A2", "A1", "A0", "16:9"))

try:
    tg.create_template_layout("invalid_template_id")
    check("create_template_layout raises on invalid id", False)
except ValueError:
    check("create_template_layout raises on invalid id", True)

from zero2cartolab.layout.grid_presets import GRID_PRESETS, list_grid_presets
check("grid gallery has 7 compositions", len(GRID_PRESETS) == 7)
check("grid gallery includes layered UTM field preset",
      len(GRID_PRESETS["utm_field"]["components"]) == 2)
check("grid gallery includes dual CRS reference preset",
      len(GRID_PRESETS["dual_reference"]["components"]) == 2)
check("grid preset metadata is serializable", all(meta.get("id") for meta in list_grid_presets()))

from zero2cartolab.layout.qpt_inspector import format_qpt_report, inspect_qpt
_qpt_xml = """<Layout units="mm" printResolution="300" name="UTM Test">
<PageCollection><LayoutItem type="65638" id="" size="297,210,mm" position="0,0,mm"/></PageCollection>
<LayoutItem type="65639" id="Map 1" size="250,170,mm" position="20,20,mm">
<ComposerMapGrid name="UTM" show="1" annotationExpression="mgrs_gzd(0,0,'EPSG:32635')"/>
</LayoutItem><LayoutItem type="65641" id="Info" size="80,20,mm" position="-90,10,mm"/>
</Layout>"""
_qpt_fd, _qpt_path = tempfile.mkstemp(suffix=".qpt")
os.close(_qpt_fd)
with open(_qpt_path, "w", encoding="utf-8") as _qpt_handle:
    _qpt_handle.write(_qpt_xml)
_qpt_report = inspect_qpt(_qpt_path)
os.remove(_qpt_path)
check("QPT inspector identifies grid stack", _qpt_report["grid_count"] == 1)
check("QPT inspector detects external MGRS dependency",
      _qpt_report["external_functions"] == ["mgrs_gzd"])
check("QPT inspector blocks unsafe external-function import", not _qpt_report["safe_to_import"])
check("QPT inspector detects off-page item", any("outside" in w for w in _qpt_report["warnings"]))
check("QPT report formatter includes compatibility notes",
      "Compatibility notes" in format_qpt_report(_qpt_report))

# ===================================================================
# 26. NATIVE PRINT LAYOUT CHARTS
# ===================================================================
section("Native Print Layout Charts")
from zero2cartolab.layout.charts.spec import ChartSpec, CHART_TYPES
from zero2cartolab.layout.charts.transform import build_chart_data
from zero2cartolab.layout.charts.placement import best_position, intersection_area
from zero2cartolab.layout.charts.theme_adapter import discover_zero2viz_themes

_chart_cols = {"district": ["A", "B", "A", "C"], "value": [4, 7, 6, 3]}
_bar_data = build_chart_data(
    ChartSpec(category_field="district", value_field="value", aggregation="sum"),
    _chart_cols,
)
check("chart engine exposes ten publication chart types", len(CHART_TYPES) == 10)
check("chart aggregation groups categories", _bar_data == {
    "categories": ["A", "B", "C"], "values": [10.0, 7.0, 3.0]
})
_hist_data = build_chart_data(
    ChartSpec(chart_type="histogram", value_field="value", bins=3), _chart_cols
)
check("histogram conserves observations", sum(_hist_data["values"]) == 4)
_scatter_data = build_chart_data(
    ChartSpec(chart_type="scatter", category_field="value", value_field="value"),
    _chart_cols,
)
check("scatter preserves numeric X/Y pairs", _scatter_data["x_values"] == [4.0, 7.0, 6.0, 3.0])
_multi_data = build_chart_data(
    ChartSpec(chart_type="grouped_bar", category_field="district", value_field="value",
              series_field="series", aggregation="sum"),
    {**_chart_cols, "series": ["X", "X", "Y", "Y"]},
)
check("multi-series transform builds pivoted series", len(_multi_data["series"]) == 2)
check("chart overlap area is exact", intersection_area((0, 0, 10, 10), (5, 5, 10, 10)) == 25)
check(
    "best chart position avoids occupied lower-right",
    best_position(297, 210, 90, 60, [((197, 140, 90, 60), 5)]) != (197, 140),
)
try:
    ChartSpec(chart_type="bar", aggregation="sum", category_field="district").validated()
    _invalid_chart_rejected = False
except ValueError:
    _invalid_chart_rejected = True
check("chart spec rejects missing numeric value", _invalid_chart_rejected)
from zero2cartolab.layout.pixel_qa import contrast_ratio
check("dark ink on white exceeds WCAG AAA", contrast_ratio("#0f172a", "#ffffff") >= 7.0)
check("identical colours have unit contrast", abs(contrast_ratio("#ffffff", "#ffffff") - 1.0) < 1e-9)
try:
    ChartSpec(category_field="district", background_color="#ffffff", text_color="#dddddd").validated()
    _low_contrast_rejected = False
except ValueError:
    _low_contrast_rejected = True
check("chart spec rejects low-contrast typography", _low_contrast_rejected)

class _FakeVizPlugin:
    def print_layout_theme_catalog(self):
        return {
            "api": "zero2viz.print_layout_themes", "api_version": 1,
            "themes": [{
                "id": "studio_light", "label": "Studio Light",
                "palette": ["#2a8f85", "#fa8e7a"],
                "background": "#fbfbfd", "text": "#16323f", "grid": "#e3e7ec",
                "font_family": "Segoe UI", "title_size_pt": 9,
                "label_size_pt": 5.6, "line_width_mm": 0.65,
            }],
        }

_viz_themes, _viz_status = discover_zero2viz_themes({"zero2viz": _FakeVizPlugin()})
check("02viz adapter accepts versioned theme catalog", len(_viz_themes) == 1)
check("02viz adapter transfers palette and typography",
      _viz_themes[0]["palette"][0] == "#2a8f85"
      and _viz_themes[0]["font_family"] == "Segoe UI")
check("02viz adapter reports connected status", _viz_status.startswith("02viz connected"))
_fallback_themes, _fallback_status = discover_zero2viz_themes({})
check("02viz adapter remains optional", not _fallback_themes and "built-in" in _fallback_status)

# ===================================================================
# FLOW MAP — aggregation, arcs, widths, id matching
# ===================================================================
section("Flow Map")
import math as _m
from zero2cartolab.core import flow_map as fm

_agg = fm.aggregate_flows([("a", "b", 5), ("a", "b", "7"), ("b", "a", 2), ("a", "a", 9),
                           ("a", "c", -1), ("a", "c", "x"), (None, "c", 3),
                           ("c", "a", float("nan"))])
check("flows: duplicates summed, self/negative/text/null/NaN dropped",
      _agg == {("a", "b"): 12.0, ("b", "a"): 2.0}, str(_agg))
_two = fm.aggregate_flows([("a", "b", 5), ("b", "a", 2)], directed=False)
check("flows: undirected merges both directions", _two == {("a", "b"): 7.0}, str(_two))
_sel = fm.select_flows({("a", "b"): 1.0, ("c", "d"): 9.0, ("e", "f"): 5.0}, min_volume=2.0, top_n=1)
check("flows: threshold then top-N keeps the largest", _sel == [(("c", "d"), 9.0)], str(_sel))
check("flows: width linear in volume", abs(fm.flow_width(50, 100, 4.0, 0.0) - 2.0) < 1e-12)
check("flows: width clamps at max and handles junk",
      fm.flow_width(500, 100, 4.0, 1.0) == 4.0 and fm.flow_width(None, 100, 4.0, 1.0) == 1.0)
_arc = fm.flow_arc((0.0, 0.0), (100.0, 0.0), curvature=0.2, segments=20)
check("flows: arc starts and ends on the zone points",
      _m.dist(_arc[0], (0, 0)) < 1e-9 and _m.dist(_arc[-1], (100, 0)) < 1e-9)
check("flows: travelling east, the arc bends right (south)",
      min(y for _, y in _arc) < -5 and max(y for _, y in _arc) <= 1e-9)
_back = fm.flow_arc((100.0, 0.0), (0.0, 0.0), curvature=0.2, segments=20)
check("flows: the reverse direction bends to the other side", min(y for _, y in _back) >= -1e-9)
_trim = fm.flow_arc((0.0, 0.0), (100.0, 0.0), curvature=0.3, segments=40, trim_start=0.1, trim_end=0.1)
_full = fm.flow_arc((0.0, 0.0), (100.0, 0.0), curvature=0.3, segments=400)
check("flows: trims remove 10% of the chord from each end, along the curve",
      abs((fm.polyline_length(_full) - fm.polyline_length(_trim)) - 20.0) < 0.5,
      f"{fm.polyline_length(_full) - fm.polyline_length(_trim):.3f}")
check("flows: straight lines when curvature is 0",
      fm.flow_arc((0, 0), (10, 0), curvature=0.0) == [(0.0, 0.0), (10.0, 0.0)])
check("flows: coincident points and over-trimmed lines give nothing",
      fm.flow_arc((1, 1), (1, 1)) == [] and fm.flow_arc((0, 0), (10, 0), 0.0, trim_start=0.6, trim_end=0.6) == [])
check("flows: 7, 7.0 and '7' are one zone id",
      fm.normalise_zone_id(7) == fm.normalise_zone_id(7.0) == fm.normalise_zone_id(" 7 ") == "7")
check("flows: NULL-like ids are rejected",
      fm.normalise_zone_id(None) is None and fm.normalise_zone_id("NULL") is None
      and fm.normalise_zone_id(float("nan")) is None)
_lk, _dup = fm.zone_lookup([(1, (0, 0)), (1.0, (5, 5)), ("2", (1, 1))])
check("flows: duplicate zone ids reported, first wins", _lk == {"1": (0, 0), "2": (1, 1)} and _dup == ["1"])

# ===================================================================
# DORLING — radii, separation, stability
# ===================================================================
section("Dorling Cartogram")
import random as _rnd
from zero2cartolab.core import dorling as dor

_r = dor.dorling_radii([4.0, 1.0, 0.0, None, -3.0], target_area=_m.pi * 5.0)
check("dorling: area proportional to value, total = target",
      abs(_r[0] - 2.0) < 1e-12 and abs(_r[1] - 1.0) < 1e-12 and _r[2:] == [0.0, 0.0, 0.0], str(_r))
_g = _rnd.Random(5)
_centers = [(_g.uniform(0, 1000), _g.uniform(0, 1000)) for _ in range(300)]
_radii = dor.dorling_radii([_g.lognormvariate(2, 1) for _ in range(300)], 0.5 * 1000 * 1000)
check("dorling: random input starts with heavy overlap",
      dor.max_overlap(_centers, _radii) > 10.0)
_pos, _used, _res = dor.dorling_layout(_centers, _radii)
check("dorling: layout removes overlap (residual < 0.5% of mean radius)",
      _res < 0.005, f"residual {_res:.5f} after {_used} rounds")
_brute = max(_radii[i] + _radii[j] - _m.dist(_pos[i], _pos[j])
             for i in range(300) for j in range(i + 1, 300))
check("dorling: brute-force pair check agrees with the grid search",
      abs(_brute - _res * (sum(_radii) / 300)) < 1e-6, f"{_brute} vs grid")
_mean_r = sum(_radii) / 300
_shift = sorted(dor.displacement(a, b) for a, b in zip(_centers, _pos))
check("dorling: circles stay near home (median shift < 2 mean radii)",
      _shift[150] < 2.0 * _mean_r, f"{_shift[150] / _mean_r:.2f}")
_same, _, _ = dor.dorling_layout([(0.0, 0.0)] * 3, [1.0, 1.0, 1.0])
check("dorling: coincident centres are split deterministically",
      len({(round(x, 6), round(y, 6)) for x, y in _same}) == 3
      and _same == dor.dorling_layout([(0.0, 0.0)] * 3, [1.0, 1.0, 1.0])[0])
_calls = []
dor.dorling_layout(_centers, _radii, callback=lambda n, ph: _calls.append(n) or n >= 3)
check("dorling: callback can cancel the run", max(_calls) <= 4, str(max(_calls)))

# ===================================================================
# MONOCHROME HATCH PATTERNS
# ===================================================================
section("Monochrome Patterns")
from zero2cartolab.core import hatch_patterns as hp

for _n in range(2, hp.MAX_GRADUATED + 1):
    _cov = [hp.ink_coverage(p) for p in hp.graduated_patterns(_n)]
    check(f"hatch: {_n}-class ramp darkens strictly",
          len(_cov) == _n and all(a < b for a, b in zip(_cov, _cov[1:])), str(_cov))
_g5 = hp.graduated_patterns(5)
check("hatch: ramp runs from blank to solid",
      _g5[0]["kind"] == "none" and _g5[-1]["kind"] == "solid")
check("hatch: ramp is clamped to the readable maximum",
      len(hp.graduated_patterns(40)) == hp.MAX_GRADUATED)
_cats = hp.categorical_patterns(hp.MAX_CATEGORICAL)
check("hatch: categorical patterns are all distinct up to the maximum",
      len({hp.pattern_key(p) for p in _cats}) == hp.MAX_CATEGORICAL)
check("hatch: categorical patterns repeat only beyond the maximum",
      hp.pattern_key(hp.categorical_patterns(hp.MAX_CATEGORICAL + 1)[-1]) == hp.pattern_key(_cats[0]))
check("hatch: coverage formulas",
      abs(hp.ink_coverage({"kind": "lines", "spacing": 2.0, "width": 0.5}) - 0.25) < 1e-12
      and abs(hp.ink_coverage({"kind": "cross", "spacing": 2.0, "width": 0.5}) - 0.4375) < 1e-12)

# ===================================================================
# REGRESSIONS — classification, colour, CVD, dots, cartogram, ranks
# ===================================================================
section("Regressions — audit fixes")

# Fisher-Jenks sampling keeps the maximum, and n in 5001..9999 is sampled
_big = [float(i) for i in range(10001)]  # step 3 would skip the last value
_fj_big = be.fisher_jenks_breaks(_big, 2)
check("Fisher-Jenks sample keeps the maximum", _fj_big[-1] >= 10000.0, str(_fj_big[-1]))
check("Fisher-Jenks large n returns n+1 breaks", len(_fj_big) == 3, str(_fj_big))

# Jenks interior breaks are class upper bounds (lo < v <= hi like QGIS ranges)
_fj_up = be.fisher_jenks_breaks([1, 2, 3, 10, 11, 12], 2)
check("Fisher-Jenks break is upper bound of lower class", _fj_up[1] == 3.0, str(_fj_up))
check("class_index: break value belongs to the class it closes",
      be.class_index(3.0, _fj_up) == 0 and be.class_index(10.0, _fj_up) == 1)
check("class_index: below first break -> first class", be.class_index(-5, [0, 1, 2]) == 0)
check("class_index: above last break -> last class (not class 0)", be.class_index(99, [0, 1, 2]) == 1)
check("class_index: first class includes its lower bound", be.class_index(0, [0, 1, 2]) == 0)

# compute_alpha_values: every member of a natural cluster gets the same alpha
_rel = [1, 1, 1, 10, 10, 10, 20, 20, 20, 30, 30, 30, 40, 40, 40]
_al = be.compute_alpha_values(_rel, _rel, 30, 255)
_groups = [_al[i:i + 3] for i in range(0, 15, 3)]
check("VbA alpha uniform within each Jenks class", all(len(set(g)) == 1 for g in _groups), str(_al))
check("VbA alpha increases with reliability",
      all(_groups[i][0] < _groups[i + 1][0] for i in range(4)), str(_al))

# Bivariate corners: "lh" = LOW X / HIGH Y, "hl" = HIGH X / LOW Y; matrix[row=Y][col=X]
_bm = be.bivariate_colour_matrix(2, "#ffffff", "#ff0000", "#0000ff", "#000000")
check("Bivariate lh colours low-X/high-Y cell", _bm[1][0].name() == "#ff0000", _bm[1][0].name())
check("Bivariate hl colours high-X/low-Y cell", _bm[0][1].name() == "#0000ff", _bm[0][1].name())
check("Bivariate presets keep their on-map appearance",
      be.bivariate_colour_matrix_hex(2, preset="teal_brown") == [["#e8e8e8", "#5ab4ac"], ["#d8b365", "#8c510a"]])

# Class labels follow the class count
for _n in range(1, 21):
    _lb = be.class_labels(_n)
    check(f"class_labels({_n}) has {_n} distinct labels", len(_lb) == _n and len(set(_lb)) == _n, str(_lb))
check("class_labels(5) keeps the classic names",
      be.class_labels(5) == ["Very Low", "Low", "Medium", "High", "Very High"])
check("class_labels(7) ends High-most", be.class_labels(7)[-1] == "Very High" and be.class_labels(7)[0] == "Very Low")

# Std-dev breaks symmetric for >= 7 classes
_sd7 = be.standard_deviation_breaks(list(range(-50, 51)), 7, interval_std=0.25)
check("Std-dev 7 classes gives 8 breaks", len(_sd7) == 8, str(_sd7))
check("Std-dev 7 classes symmetric about the mean",
      all(abs(_sd7[i] + _sd7[-1 - i]) < 1e-6 for i in range(1, 4)), str(_sd7))
_sd8 = be.standard_deviation_breaks(list(range(-500, 501)), 8, interval_std=0.25)
_mid8 = _sd8[1:-1]
check("Std-dev 8 classes has a break at the mean", any(abs(b) < 1e-6 for b in _mid8), str(_sd8))

# CVD: Machado 2009 in linear RGB
check("CVD Machado deuteranopia of red", ca.simulate_cvd_hex("#ff0000", "deuteranopia") == "#a39000",
      ca.simulate_cvd_hex("#ff0000", "deuteranopia"))
check("CVD Machado protanopia of red", ca.simulate_cvd_hex("#ff0000", "protanopia") == "#6d5f00",
      ca.simulate_cvd_hex("#ff0000", "protanopia"))
check("CVD Machado tritanopia of blue", ca.simulate_cvd_hex("#0000ff", "tritanopia") == "#006b96",
      ca.simulate_cvd_hex("#0000ff", "tritanopia"))
for _t in ("deuteranopia", "protanopia", "tritanopia", "achromatopsia"):
    check(f"CVD {_t} keeps neutral greys",
          [ca.simulate_cvd_hex(h, _t) for h in ("#000000", "#808080", "#ffffff")] == ["#000000", "#808080", "#ffffff"])
_ach = ca.simulate_cvd_hex("#3b82f6", "achromatopsia")
check("CVD achromatopsia preserves relative luminance",
      abs(ca.relative_luminance(_ach) - ca.relative_luminance("#3b82f6")) < 0.01, _ach)
check("CVD severity 0 is identity", ca.simulate_cvd_hex("#3b82f6", "protanopia", severity=0.0) == "#3b82f6")
check("CVD protanomaly uses the protan matrix",
      ca.simulate_cvd_hex("#ff0000", "protanomaly", severity=0.5)
      == ca.simulate_cvd_hex("#ff0000", "protanopia", severity=0.5))
check("CVD red/green confusable for deuteranopes",
      ca.delta_e_cie76(ca.simulate_cvd_hex("#d62728", "deuteranopia"), ca.simulate_cvd_hex("#2ca02c", "deuteranopia"))
      < ca.delta_e_cie76("#d62728", "#2ca02c") / 2)

# Dot density: far-apart islands and sparse shapes still get every dot
_isl_a = [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]]
_isl_b = [[(1000, 1000), (1003, 1000), (1003, 1001), (1000, 1001), (1000, 1000)]]
_mp = dd.generate_dots_in_parts([_isl_a, _isl_b], 200, seed=5)
check("dots multipart: all requested dots placed", len(_mp) == 200, str(len(_mp)))
_in_a = sum(1 for x, y in _mp if dd.point_in_polygon(_isl_a, x, y))
_in_b = sum(1 for x, y in _mp if dd.point_in_polygon(_isl_b, x, y))
check("dots multipart: shared by area (1:3)", _in_a == 50 and _in_b == 150, f"{_in_a}/{_in_b}")
check("dots multipart deterministic", _mp == dd.generate_dots_in_parts([_isl_a, _isl_b], 200, seed=5))
_sq = [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]]
check("dots single part matches generate_dots",
      dd.generate_dots_in_parts([_sq], 40, seed=9) == dd.generate_dots(_sq[0:1], (0, 0, 10, 10), 40, seed=9))
_thin_l = [[(0, 0), (100, 0), (100, 0.5), (0.5, 0.5), (0.5, 100), (0, 100), (0, 0)]]  # ~1% of its bbox
check("dots sparse L-shape gets all dots", len(dd.generate_dots(_thin_l, (0, 0, 100, 100), 300, seed=2)) == 300)
check("allocate_by_area sums to count", sum(dd.allocate_by_area([1.0, 2.0, 0.0, 3.3], 17)) == 17)
check("polygon_area subtracts holes", abs(dd.polygon_area([_sq[0], [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]]) - 96.0) < 1e-9)

# Cartogram: cancel before the first iteration must not raise UnboundLocalError
class _CancelFB:
    def isCanceled(self): return True
    def setProgress(self, p): pass
    def pushInfo(self, m): pass

class _PreloadedCartogram(ce.CartogramEngine):
    def _load_features(self):
        for i, (area, val) in enumerate(((100.0, 1.0), (100.0, 3.0))):
            f = ce.CartogramFeature(i, FakeGeometry(), val)
            f.area, f.radius, f.cx, f.cy = area, math.sqrt(area / math.pi), i * 10.0, 0.0
            self.features.append(f)
        self._area_value_ratio = 200.0 / 4.0

try:
    _it, _err = _PreloadedCartogram(None, "v", 10, 5.0).run(_CancelFB())
    check("Cartogram cancel before first iteration returns cleanly", _it == 0 and _err > 1.0, f"{_it}, {_err}")
except Exception as _e:
    check("Cartogram cancel before first iteration returns cleanly", False, repr(_e))
try:
    _it0, _ = _PreloadedCartogram(None, "v", 0, 5.0).run(None)
    check("Cartogram max_iterations=0 returns cleanly", _it0 == 0)
except Exception as _e:
    check("Cartogram max_iterations=0 returns cleanly", False, repr(_e))

class _OneFeatureLayer:
    def getFeatures(self):
        class _F:
            def geometry(self): return FakeGeometry()
            def id(self): return 1
            def __getitem__(self, k): return 5.0
        return [_F()]

_orig_geom = ce.QgsGeometry
class _StaticGeom(FakeGeometry):
    @staticmethod
    def fromWkt(wkt): return FakeGeometry(wkt)
ce.QgsGeometry = _StaticGeom
try:
    ce.CartogramEngine(_OneFeatureLayer(), "v").run(None)
    check("Cartogram single feature raises a clear ValueError", False)
except ValueError as _e:
    check("Cartogram single feature raises a clear ValueError", "at least 2" in str(_e), str(_e))
finally:
    ce.QgsGeometry = _orig_geom

# Percentile rank: O(n log n) and still mid-rank for ties
import time as _time
check("percentile_rank ties use mid-rank", norm.percentile_rank([1, 2, 2, 3]) == [12.5, 50.0, 50.0, 87.5],
      str(norm.percentile_rank([1, 2, 2, 3])))
_t0 = _time.perf_counter()
_pr = norm.percentile_rank([float((i * 7919) % 30011) for i in range(30000)] + [None])
check("percentile_rank 30k values runs fast (sort + bisect)", _time.perf_counter() - _t0 < 2.0)
check("percentile_rank keeps None aligned", _pr[-1] is None and len(_pr) == 30001)
check("decile_rank built on fast ranks", norm.decile_rank([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == list(range(1, 11)),
      str(norm.decile_rank(list(range(1, 11)))))

# ===================================================================
# Regression tests — 2026-10-20 audit
# ===================================================================
section("2026-10-20 audit regressions")

for _bad_base, _label in ((1.0, "1"), (0.0, "0"), (-2.0, "negative"), (float("nan"), "NaN")):
    try:
        norm.log_scale([1.0, 10.0], base=_bad_base)
        check(f"log_scale rejects base {_label}", False)
    except ValueError:
        check(f"log_scale rejects base {_label}", True)
check("log_scale base 2 exact", norm.log_scale([1.0, 2.0, 4.0], base=2.0) == [0.0, 1.0, 2.0],
      str(norm.log_scale([1.0, 2.0, 4.0], base=2.0)))

for _bad_size in (0.0, -1.0, float("nan")):
    try:
        hxg.axial_from_point(1.0, 1.0, _bad_size)
        check(f"axial_from_point rejects size {_bad_size}", False)
    except ValueError:
        check(f"axial_from_point rejects size {_bad_size}", True)

_sq = [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]]
_d = lblp.polylabel(_sq, precision=float("nan"))[2]
check("polylabel NaN precision converges", _d > 0 and math.isfinite(_d), f"d={_d}")
_d2 = lblp.polylabel(_sq, precision=-5.0)[2]
check("polylabel negative precision converges", _d2 > 0 and math.isfinite(_d2), f"d={_d2}")

for _args, _label in (((91.0,), "latitude 91"), ((38.4, 0), "day 0"), ((38.4, 172, 24.0), "hour 24")):
    try:
        sl.calculate_solar_position(*_args)
        check(f"solar position rejects {_label}", False)
    except ValueError:
        check(f"solar position rejects {_label}", True)

class _TwoFeatureLayer:
    def getFeatures(self):
        class _F:
            def __init__(self, i): self._i = i
            def geometry(self): return FakeGeometry()
            def id(self): return self._i
            def __getitem__(self, k): return 5.0
        return [_F(1), _F(2)]

_orig_geom2 = ce.QgsGeometry
ce.QgsGeometry = _StaticGeom
try:
    _eng = ce.CartogramEngine(_TwoFeatureLayer(), "v", max_iterations=1)
    _eng._load_features()
    _n_first = len(_eng.features)
    _eng._load_features()
    check("cartogram engine reload does not duplicate features",
          _n_first == 2 and len(_eng.features) == 2, f"{_n_first} -> {len(_eng.features)}")
finally:
    ce.QgsGeometry = _orig_geom2

# ===================================================================
# SUMMARY
# ===================================================================
section("RESULTS")
total = passed + failed
print(f"Total tests: {total}, Passed: {passed}, Failed: {failed}")

def test_all_cartolab_core_modules():
    assert failed == 0, f"{failed} core tests failed"

if __name__ == "__main__":
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)
