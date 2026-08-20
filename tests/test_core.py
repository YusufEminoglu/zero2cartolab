# -*- coding: utf-8 -*-
"""Comprehensive unit tests for zero2cartolab core modules.

Tests every algorithm with normal, edge-case, and adversarial data.
Runs without QGIS — mocks qgis.* imports for pure-logic verification.
"""
from __future__ import annotations

import math
import os
import sys
import types
import traceback

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
    global passed, failed, errors
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
check("iso offsets dx zero", all(dx == 0.0 for dx, _ in offsets))

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
check("map_width_to_km metres", lm.map_width_to_km(12500.0, 0.001) == 12.5)
check("map_width_to_km kilometres factor", lm.map_width_to_km(12.5, 1.0) == 12.5)
check("map_width_to_km rejects invalid",
      lm.map_width_to_km(-1.0, 0.001) == 0.0 and lm.map_width_to_km(10.0, 0.0) == 0.0)

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

from zero2cartolab.core.utils import safe_float, safe_int
check("safe_float cleans meter suffix '8 m'", safe_float("8 m") == 8.0)
check("safe_float cleans area suffix '15.5 sqm'", safe_float("15.5 sqm") == 15.5)
check("safe_int cleans floor suffix '4 floors'", safe_int("4 floors") == 4)

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
check("TEMPLATE_GALLERY exists and has 5 archetypes", len(tg.TEMPLATE_GALLERY) == 5)
check("report_figure template registered", "report_figure" in tg.TEMPLATE_GALLERY)
check("academic_journal template registered", "academic_journal" in tg.TEMPLATE_GALLERY)
check("exhibition_poster template registered", "exhibition_poster" in tg.TEMPLATE_GALLERY and tg.get_template_info("poster_exhibition") is not None)
check("fact_sheet template registered", "fact_sheet" in tg.TEMPLATE_GALLERY)
check("diptych template registered", "diptych" in tg.TEMPLATE_GALLERY and tg.get_template_info("side_by_side_diptych") is not None)

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

