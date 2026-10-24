# -*- coding: utf-8 -*-
"""
02CartoLab Practical Guide — headless screenshot generator.

Runs the *real* CartoLab code (Processing algorithms, layout builders, the
actual dashboard widgets) inside a genuine QGIS Python runtime, on real
urban data, and captures publication-grade panel composites that the
Practical Guide embeds.

Nothing in this file is mocked: every map panel is a QGIS render of a layer
that the plugin itself produced, every parameter panel is the literal
parameter dictionary handed to the algorithm, and every GUI panel is a
screenshot of the real dashboard widget tree.

Run (Windows / OSGeo4W):
    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat docs\\PRACTICAL_GUIDE\\practical_guide_runner.py
    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat docs\\PRACTICAL_GUIDE\\practical_guide_runner.py --module bivariate

Run (anywhere QGIS Python is importable):
    python practical_guide_runner.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from contextlib import suppress
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent          # .../zero2cartolab
REPO_ROOT = PLUGIN_ROOT.parent             # .../qgis_plugins
SHOTS = HERE / "screenshots"
MANIFEST = HERE / "manifest"

# ── QGIS bootstrap ──────────────────────────────────────────────────────────
from qgis.core import QgsApplication  # noqa: E402

qgs = QgsApplication([], True)
qgs.initQgis()

import qgis  # noqa: E402

for _plugins_dir in (
    os.path.abspath(os.path.join(os.path.dirname(qgis.__file__), "..", "plugins")),
    "/usr/share/qgis/python/plugins",
):
    if os.path.isdir(os.path.join(_plugins_dir, "processing")):
        if _plugins_dir in sys.path:
            sys.path.remove(_plugins_dir)
        sys.path.insert(0, _plugins_dir)
        break

if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

# Headless OSGeo4W does not always discover system fonts — register a small
# fallback set so captured text is readable instead of tofu boxes.
from qgis.PyQt.QtGui import QFontDatabase  # noqa: E402

for _font_root in (Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts",
                   Path("/usr/share/fonts/truetype/dejavu")):
    for _font_name in ("segoeui.ttf", "arial.ttf", "consola.ttf", "DejaVuSans.ttf"):
        _fp = _font_root / _font_name
        if _fp.exists():
            QFontDatabase.addApplicationFont(str(_fp))

import processing  # noqa: E402
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

from qgis.PyQt.QtCore import QRectF, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import (  # noqa: E402
    QColor, QFont, QImage, QPainter, QPen,
)
from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsField, QgsFields, QgsGeometry, QgsMapRendererParallelJob,
    QgsMapSettings, QgsPointXY, QgsProcessingContext, QgsProcessingFeedback,
    QgsProcessingUtils, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant  # noqa: E402

from zero2cartolab.processing.cartolab_provider import CartoLabProvider  # noqa: E402

_PROVIDER = CartoLabProvider()
QgsApplication.processingRegistry().addProvider(_PROVIDER)

print(f"QGIS {qgis.core.Qgis.QGIS_VERSION} — 02CartoLab provider registered "
      f"({len(list(_PROVIDER.algorithms()))} algorithms)", flush=True)

# ── Brand palette (matches the plugin's own accent colours) ────────────────
INK = "#0f172a"
INK_SOFT = "#334155"
PAPER = "#ffffff"
CANVAS = "#f1f5f9"
ACCENT = "#7c3aed"
ACCENT_DARK = "#5b21b6"
ACCENT_LIGHT = "#c4b5fd"
GOLD = "#f59e0b"
HEADER_BG = "#111827"

PANEL_W, PANEL_H, HEADER_H = 900, 620, 58


# ══════════════════════════════════════════════════════════════════════════
#  DATA RESOLUTION — real urban datasets, never synthetic stand-ins
# ══════════════════════════════════════════════════════════════════════════
DATA_ROOTS = [
    Path(os.environ.get("CARTOLAB_DATA", "")) if os.environ.get("CARTOLAB_DATA") else None,
    Path.home() / "Downloads" / "geo3d_test_data",
    Path.home() / "Downloads",
    Path("C:/Users/YE/Downloads/geo3d_test_data"),
    Path("C:/Users/YE/Downloads"),
]

IZMIR_CANDIDATES = ["mahalle_population_2024.geojson", "mahalle_population_2024.GeoJSON"]
KADIFEKALE_BUILDINGS = "kadifekale/kadifekale_osm_binalar.gpkg"
KADIFEKALE_DEM = "kadifekale/kadifekale_dem_copernicus30m.tif"
TIRE_SOCIO = "tire_mahalle_upi_sosyoekonomik.gpkg"


def _find(rel_names):
    """Return the first existing file for any of the given relative names."""
    if isinstance(rel_names, str):
        rel_names = [rel_names]
    for root in DATA_ROOTS:
        if root is None:
            continue
        for rel in rel_names:
            candidate = root / rel
            if candidate.exists():
                return candidate
    return None


class DataBundle:
    """Resolved real inputs plus derived analysis layers."""

    def __init__(self):
        self.notes = []
        self.izmir_path = _find(IZMIR_CANDIDATES)
        self.buildings_path = _find(KADIFEKALE_BUILDINGS)
        self.dem_path = _find(KADIFEKALE_DEM)
        self.tire_path = _find(TIRE_SOCIO)

        self.mahalle = None          # polygons, EPSG:32635, with derived fields
        self.mahalle_points = None   # population-weighted interior points
        self.districts = None        # İzmir ilçe (district) polygons, aggregated
        self.buildings = None        # OSM buildings, EPSG:32635
        self.dem = None              # Copernicus DEM
        self.flow_zones = None       # points: assembly areas + critical assets
        self.flows = None            # OD table (in-memory layer)
        self.flows_path = None       # OD table (CSV on disk, for the reader)

    # ------------------------------------------------------------------
    def resolve(self) -> bool:
        if not self.izmir_path:
            self.notes.append("İzmir mahalle layer NOT FOUND — thematic panels fall back to a "
                              "deterministic demo grid.")
            return False
        self.notes.append(f"Thematic source: {self.izmir_path.name} (İzmir mahalle polygons, "
                          f"population 2024)")
        if self.buildings_path:
            self.notes.append(f"2.5D source: {self.buildings_path.name} (OSM buildings)")
        if self.dem_path:
            self.notes.append(f"Raster source: {self.dem_path.name} (Copernicus DEM 30 m)")
        if self.tire_path:
            self.notes.append(f"Flow source: {self.tire_path.name} (assembly areas + critical assets)")
        return True

    # ------------------------------------------------------------------
    def build(self) -> None:
        self.mahalle = self._build_mahalle()
        if self.mahalle is not None:
            self.mahalle_points = self._build_points(self.mahalle)
            self.districts = self._build_districts(self.mahalle)
        if self.buildings_path:
            lyr = QgsVectorLayer(str(self.buildings_path), "osm_buildings", "ogr")
            if lyr.isValid():
                self.buildings = lyr
        if self.dem_path:
            from qgis.core import QgsRasterLayer
            r = QgsRasterLayer(str(self.dem_path), "dem", "gdal")
            if r.isValid():
                self.dem = self._project_raster(r)
        if self.tire_path:
            self._build_flow_inputs()

    # ------------------------------------------------------------------
    def _build_mahalle(self):
        """İzmir neighbourhood polygons → EPSG:32635 with derived indicators."""
        src = QgsVectorLayer(str(self.izmir_path), "mahalle", "ogr")
        if not src.isValid():
            return None
        target = QgsCoordinateReferenceSystem("EPSG:32635")
        tr = QgsCoordinateTransform(src.crs(), target, QgsProject.instance())

        mem = QgsVectorLayer("MultiPolygon?crs=EPSG:32635", "İzmir mahalle (2024)", "memory")
        dp = mem.dataProvider()
        dp.addAttributes([
            QgsField("mahalle", QVariant.String),
            QgsField("district", QVariant.String),
            QgsField("pop_total", QVariant.Double),
            QgsField("pop_0_14", QVariant.Double),
            QgsField("pop_15_64", QVariant.Double),
            QgsField("pop_65_plus", QVariant.Double),
            QgsField("area_km2", QVariant.Double),
            QgsField("pop_density", QVariant.Double),
            QgsField("child_share", QVariant.Double),
            QgsField("working_share", QVariant.Double),
            QgsField("elderly_share", QVariant.Double),
            QgsField("female_share", QVariant.Double),
            QgsField("dependency", QVariant.Double),
        ])
        mem.updateFields()

        feats = []
        for f in src.getFeatures():
            g = QgsGeometry(f.geometry())
            if g.isEmpty():
                continue
            with suppress(Exception):
                g.transform(tr)
            area_km2 = g.area() / 1_000_000.0
            pop = float(f["pop_total"] or 0)
            p014 = float(f["pop_0_14"] or 0)
            p1564 = float(f["pop_15_64"] or 0)
            p65 = float(f["pop_65_plus"] or 0)
            base = max(pop, 1.0)
            nf = QgsFeature(mem.fields())
            nf.setGeometry(g)
            nf.setAttributes([
                str(f["mahalle_name"] or ""),
                str(f["district_name"] or ""),
                pop, p014, p1564, p65,
                round(area_km2, 4),
                round(pop / area_km2, 3) if area_km2 > 0 else 0.0,
                round(p014 / base, 5),
                round(p1564 / base, 5),
                round(p65 / base, 5),
                round(float(f["female_share"] or 0), 5),
                round((p014 + p65) / base, 5),
            ])
            feats.append(nf)
        dp.addFeatures(feats)
        mem.updateExtents()
        return mem

    # ------------------------------------------------------------------
    def _build_districts(self, polygon_layer):
        """Dissolve the 1 317 neighbourhoods into İzmir's districts.

        Cartograms read best with a few dozen units: the province-level
        aggregation is also the honest analytical scale for "where does
        İzmir's population actually live".
        """
        ctx = QgsProcessingContext()
        ctx.setProject(QgsProject.instance())
        dissolved = processing.run(
            "native:dissolve",
            {"INPUT": polygon_layer, "FIELD": ["district"], "OUTPUT": "memory:"},
            context=ctx, feedback=QgsProcessingFeedback(),
        )
        dissolved_layer = dissolved["OUTPUT"]
        if isinstance(dissolved_layer, str):
            dissolved_layer = QgsProcessingUtils.mapLayerFromString(dissolved_layer, ctx)
        if dissolved_layer is None or not dissolved_layer.isValid():
            return None

        agg = {}
        for f in polygon_layer.getFeatures():
            key = str(f["district"])
            rec = agg.setdefault(key, {"pop": 0.0, "p014": 0.0, "p1564": 0.0, "p65": 0.0})
            rec["pop"] += float(f["pop_total"] or 0)
            rec["p014"] += float(f["pop_0_14"] or 0)
            rec["p1564"] += float(f["pop_15_64"] or 0)
            rec["p65"] += float(f["pop_65_plus"] or 0)

        mem = QgsVectorLayer("MultiPolygon?crs=EPSG:32635", "İzmir ilçeleri", "memory")
        dp = mem.dataProvider()
        dp.addAttributes([
            QgsField("district", QVariant.String),
            QgsField("pop_total", QVariant.Double),
            QgsField("pop_0_14", QVariant.Double),
            QgsField("pop_15_64", QVariant.Double),
            QgsField("pop_65_plus", QVariant.Double),
            QgsField("area_km2", QVariant.Double),
            QgsField("pop_density", QVariant.Double),
            QgsField("elderly_share", QVariant.Double),
            QgsField("child_share", QVariant.Double),
            QgsField("dependency", QVariant.Double),
        ])
        mem.updateFields()
        feats = []
        for f in dissolved_layer.getFeatures():
            name = str(f["district"])
            rec = agg.get(name)
            if rec is None:
                continue
            g = QgsGeometry(f.geometry())
            area_km2 = g.area() / 1_000_000.0
            base = max(rec["pop"], 1.0)
            nf = QgsFeature(mem.fields())
            nf.setGeometry(g)
            nf.setAttributes([
                name, rec["pop"], rec["p014"], rec["p1564"], rec["p65"],
                round(area_km2, 3),
                round(rec["pop"] / area_km2, 2) if area_km2 > 0 else 0.0,
                round(rec["p65"] / base, 5),
                round(rec["p014"] / base, 5),
                round((rec["p014"] + rec["p65"]) / base, 5),
            ])
            feats.append(nf)
        dp.addFeatures(feats)
        mem.updateExtents()
        return mem

    # ------------------------------------------------------------------
    def _build_points(self, polygon_layer):
        """Interior points carrying the same indicators — for point cartography."""
        mem = QgsVectorLayer("Point?crs=EPSG:32635", "İzmir mahalle noktaları", "memory")
        dp = mem.dataProvider()
        dp.addAttributes([
            QgsField("mahalle", QVariant.String),
            QgsField("district", QVariant.String),
            QgsField("pop_total", QVariant.Double),
            QgsField("pop_density", QVariant.Double),
            QgsField("elderly_share", QVariant.Double),
            QgsField("child_share", QVariant.Double),
            QgsField("dependency", QVariant.Double),
        ])
        mem.updateFields()
        feats = []
        for f in polygon_layer.getFeatures():
            g = f.geometry()
            if g.isEmpty():
                continue
            p = g.pointOnSurface().asPoint()
            nf = QgsFeature(mem.fields())
            nf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p.x(), p.y())))
            nf.setAttributes([
                f["mahalle"], f["district"], f["pop_total"],
                f["pop_density"], f["elderly_share"], f["child_share"], f["dependency"],
            ])
            feats.append(nf)
        dp.addFeatures(feats)
        mem.updateExtents()
        return mem

    # ------------------------------------------------------------------
    def _project_raster(self, raster):
        """Reproject a raster to EPSG:32635.

        The ridge engine displaces scanlines by the raw raster value, which is
        only meaningful in map units — a Copernicus DEM in EPSG:4326 would
        fling the ridges thousands of degrees away. Reprojecting here is the
        workflow the guide teaches.
        """
        if not raster.crs().isGeographic():
            return raster
        import tempfile
        ctx = QgsProcessingContext()
        ctx.setProject(QgsProject.instance())
        target_tif = Path(tempfile.mkdtemp(prefix="cartolab_dem_")) / "dem_utm35n.tif"
        try:
            res = processing.run(
                "gdal:warpreproject",
                {
                    "INPUT": raster,
                    "SOURCE_CRS": raster.crs(),
                    "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:32635"),
                    "RESAMPLING": 1,          # bilinear
                    "TARGET_RESOLUTION": 30,  # keep the Copernicus 30 m grid
                    "OUTPUT": str(target_tif),
                },
                context=ctx, feedback=QgsProcessingFeedback(),
            )
            out = res.get("OUTPUT")
            if isinstance(out, str):
                from qgis.core import QgsRasterLayer as _RL
                out = _RL(out, "dem_utm35n", "gdal")
            if out is not None and hasattr(out, "isValid") and out.isValid():
                self.notes.append("DEM reprojected from "
                                   f"{raster.crs().authid()} to EPSG:32635 "
                                   "(the ridge engine needs map units)")
                return out
        except Exception as exc:  # noqa: BLE001
            print(f"  ! DEM reprojection failed: {exc}", flush=True)
        return raster

    # ------------------------------------------------------------------
    def _build_flow_inputs(self):
        """Real emergency-mobility OD table: assembly areas → critical assets.

        Origins: AYDES toplanma alanları (real capacity_persons).
        Destinations: kritik altyapı (real hospitals / emergency services).
        Volumes are a documented distance-decay gravity product of the two
        real attribute sets — never invented coordinates.
        """
        gpkg = QgsVectorLayer(f"{self.tire_path}|layername=tire_toplanma_alanlari_epsg5253",
                              "assembly", "ogr")
        crit = QgsVectorLayer(f"{self.tire_path}|layername=tire_kritik_altyapi_epsg5253",
                              "critical", "ogr")
        if not gpkg.isValid() or not crit.isValid():
            return

        zones = QgsVectorLayer("Point?crs=EPSG:5253", "OD zones", "memory")
        dp = zones.dataProvider()
        dp.addAttributes([
            QgsField("zone_id", QVariant.String),
            QgsField("kind", QVariant.String),
            QgsField("name", QVariant.String),
            QgsField("capacity", QVariant.Double),
        ])
        zones.updateFields()

        origins, destinations = [], []
        feats = []
        for f in gpkg.getFeatures():
            zid = f["id"]
            feats.append((f"AA_{zid}", "assembly", str(f["name_tr"] or ""),
                          float(f["capacity_persons"] or 0), f.geometry()))
            origins.append((f"AA_{zid}", float(f["capacity_persons"] or 0), f.geometry()))
        for f in crit.getFeatures():
            zid = f["id"]
            feats.append((f"CR_{zid}", "critical", str(f["name"] or ""), 0.0, f.geometry()))
            destinations.append((f"CR_{zid}", f.geometry()))

        out_feats = []
        for zid, kind, name, cap, geom in feats:
            nf = QgsFeature(zones.fields())
            nf.setGeometry(QgsGeometry(geom))
            nf.setAttributes([zid, kind, name, cap])
            out_feats.append(nf)
        dp.addFeatures(out_feats)
        zones.updateExtents()
        self.flow_zones = zones

        rows = []
        for oid, cap, og in origins:
            for did, dg in destinations:
                dist = og.distance(dg)
                if dist <= 0 or dist > 25000:
                    continue
                decay = 1.0 / (1.0 + (dist / 4000.0) ** 2)
                volume = cap * decay
                if volume < 1.0:
                    continue
                rows.append((oid, did, round(volume, 3)))
        rows.sort(key=lambda r: -r[2])
        rows = rows[:900]

        csv_path = HERE / "data" / "od_table.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8") as fh:
            fh.write("origin_id,dest_id,flow_vol\n")
            for r in rows:
                fh.write(f"{r[0]},{r[1]},{r[2]}\n")
        self.flows_path = csv_path
        # The portal only publishes web suffixes; keep a .txt twin of the
        # table so readers can download the exact example used in the guide.
        (HERE / "data" / "od_table.txt").write_text(
            csv_path.read_text(encoding="utf-8"), encoding="utf-8")

        # Load the OD table as a memory layer: deterministic and independent of
        # the delimitedtext provider's CSV dialect handling.
        flows = QgsVectorLayer("None?crs=EPSG:5253", "OD table", "memory")
        fdp = flows.dataProvider()
        fdp.addAttributes([
            QgsField("origin_id", QVariant.String),
            QgsField("dest_id", QVariant.String),
            QgsField("flow_vol", QVariant.Double),
        ])
        flows.updateFields()
        ffeats = []
        for oid, did, vol in rows:
            nf = QgsFeature(flows.fields())
            nf.setAttributes([oid, did, vol])
            ffeats.append(nf)
        fdp.addFeatures(ffeats)
        flows.updateExtents()
        self.flows = flows
        self.notes.append(f"OD table: {len(rows)} real origin→critical-asset pairs "
                          f"(distance-decay gravity on real capacities)")


# ══════════════════════════════════════════════════════════════════════════
#  RENDER + COMPOSITE HELPERS
# ══════════════════════════════════════════════════════════════════════════
def _render(layers, extent, size, background="#ffffff"):
    """Render layers bottom-first (the caller lists the base layer first).

    QGIS draws the *first* entry of QgsMapSettings.setLayers() on top, so the
    list is reversed here to keep every call site in natural map order.
    """
    valid = [l for l in layers if l is not None and l.isValid()]
    if not valid or extent is None or extent.isEmpty():
        return QImage()
    settings = QgsMapSettings()
    settings.setLayers(list(reversed(valid)))
    settings.setExtent(extent)
    settings.setOutputSize(size)
    settings.setBackgroundColor(QColor(background))
    settings.setDestinationCrs(valid[0].crs())
    settings.setOutputDpi(96)
    job = QgsMapRendererParallelJob(settings)
    job.start()
    job.waitForFinished()
    return job.renderedImage()


def _extent_of(layers, pad=1.10):
    extent = None
    for lyr in layers:
        if lyr is None or not lyr.isValid():
            continue
        e = lyr.extent()
        if e.isEmpty():
            continue
        extent = QgsRectangle(e) if extent is None else extent
        extent.combineExtentWith(e)
    if extent is None or extent.isEmpty():
        return None
    extent.scale(pad)
    return extent


def _neutral(layer, color="#d7dde5"):
    """Render a copy of a layer in flat neutral grey (for the INPUT panel)."""
    clone = layer.clone()
    from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer
    sym = QgsFillSymbol.createSimple({
        "color": color, "outline_color": "#94a3b8", "outline_width": "0.25",
        "outline_style": "solid"})
    clone.setRenderer(QgsSingleSymbolRenderer(sym))
    clone.setOpacity(1.0)
    return clone


def _band_label(painter, x, y, w, text, sub=""):
    painter.fillRect(QRectF(x, y, w, 36), QColor(ACCENT))
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    painter.drawText(QRectF(x + 12, y + 3, w - 24, 30),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
    if sub:
        painter.fillRect(QRectF(x, y + 36, w, 20), QColor(255, 255, 255, 235))
        painter.setPen(QColor(INK_SOFT))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(x + 12, y + 37, w - 24, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)


def _draw_map_panel(painter, x, y, w, h, layers, extent, label, sub):
    if not layers:
        painter.fillRect(QRectF(x, y, w, h), QColor(CANVAS))
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "no layer")
    else:
        img = _render(layers, extent, QSize(int(w), int(h)))
        if not img.isNull():
            painter.drawImage(int(x), int(y), img)
        else:
            painter.fillRect(QRectF(x, y, w, h), QColor(CANVAS))
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, "render unavailable")
    _band_label(painter, x, y, w, label, sub)


def _draw_params_panel(painter, x, y, w, h, title, sub, param_text, notes=""):
    painter.fillRect(QRectF(x, y, w, h), QColor("#fbfbfd"))
    margin = 18
    body_top = y + 72
    notes_h = 0
    if notes:
        notes_h = min(190.0, h * 0.34)
    params_h = (h - (body_top - y) - 18) - (notes_h + 14 if notes else 0)

    painter.setPen(QPen(QColor(ACCENT_LIGHT), 1.4))
    painter.drawRect(QRectF(x + margin, body_top, w - 2 * margin, params_h))
    painter.setPen(QColor(INK))
    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    painter.drawText(int(x + margin + 10), int(body_top + 18), title)
    painter.setFont(QFont("Consolas", 8))
    painter.setPen(QColor(INK_SOFT))
    yy = body_top + 36
    for line in param_text.splitlines()[:30]:
        painter.drawText(int(x + margin + 10), int(yy), line)
        yy += 12.0

    if notes:
        ny = body_top + params_h + 14
        painter.setPen(QPen(QColor("#f59e0b"), 1.4))
        painter.drawRect(QRectF(x + margin, ny, w - 2 * margin, notes_h))
        painter.setPen(QColor("#92400e"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(int(x + margin + 10), int(ny + 18), "READ THE OUTPUT")
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        ny2 = ny + 36
        for line in notes.splitlines()[:12]:
            painter.drawText(int(x + margin + 10), int(ny2), line)
            ny2 += 12.0

    _band_label(painter, x, y, w, "2 · PARAMETERS USED", sub)


def compose_4panel(module_id, display, panel_inputs, panel_params, panel_result,
                   panel_context, param_text, out_path, subtitle="", notes="",
                   extent=None):
    """Compose the standard 4-panel practical-guide composite."""
    img = QImage(QSize(PANEL_W * 2, PANEL_H * 2 + HEADER_H), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(PAPER))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    if extent is None:
        extent = _extent_of(panel_inputs + panel_result + panel_context, 1.08)

    _draw_map_panel(p, 0, HEADER_H, PANEL_W, PANEL_H, panel_inputs, extent,
                    "1 · INPUT DATA", "source layer(s) used by this run")
    _draw_params_panel(p, PANEL_W, HEADER_H, PANEL_W, PANEL_H, display, subtitle,
                       param_text, notes)
    _draw_map_panel(p, 0, HEADER_H + PANEL_H, PANEL_W, PANEL_H, panel_result, extent,
                    "3 · RESULT", "output produced by 02CartoLab")
    _draw_map_panel(p, PANEL_W, HEADER_H + PANEL_H, PANEL_W, PANEL_H, panel_context, extent,
                    "4 · IN CONTEXT", "result over the base geography")

    p.fillRect(QRectF(0, 0, PANEL_W * 2, HEADER_H), QColor(HEADER_BG))
    p.setPen(QColor(ACCENT_LIGHT))
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    p.drawText(18, 30, f"02CartoLab — {display}")
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(18, 47, f"{module_id}  ·  real QGIS {qgis.core.Qgis.QGIS_VERSION} run  ·  "
                       f"real urban data, no mock-ups")
    p.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), "PNG")
    return out_path


def compose_single(module_id, display, layers, extent, out_path, caption="", footer=""):
    """Compose a single wide render panel (used for print-layout modules)."""
    W, H = 1800, 1150
    img = QImage(QSize(W, H + 78), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(PAPER))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    rendered = _render(layers, extent, QSize(W, H))
    if not rendered.isNull():
        p.drawImage(0, 0, rendered)
    else:
        p.fillRect(QRectF(0, 0, W, H), QColor(CANVAS))
    p.fillRect(QRectF(0, H, W, 78), QColor(HEADER_BG))
    p.setPen(QColor(ACCENT_LIGHT))
    p.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    p.drawText(18, 30, f"02CartoLab — {display}")
    p.setPen(QColor("#cbd5e1"))
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(18, 49, caption)
    if footer:
        p.setPen(QColor(GOLD))
        p.drawText(18, 67, footer)
    p.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), "PNG")
    return out_path


# ══════════════════════════════════════════════════════════════════════════
#  PROCESSING RUN HELPER
# ══════════════════════════════════════════════════════════════════════════
def run_algo(algo_id, params):
    ctx = QgsProcessingContext()
    ctx.setProject(QgsProject.instance())
    algo = QgsApplication.processingRegistry().algorithmById(algo_id)
    feedback = QgsProcessingFeedback()
    res = processing.run(algo_id, params, context=ctx, feedback=feedback)
    outputs = {}
    for key, value in res.items():
        layer = None
        if isinstance(value, str):
            layer = QgsProcessingUtils.mapLayerFromString(value, ctx)
            if layer is None:
                matches = QgsProject.instance().mapLayersByName(value.replace("memory:", ""))
                if matches:
                    layer = matches[0]
        if layer is None and hasattr(value, "isValid"):
            layer = value
        outputs[key] = layer if layer is not None else value
    return outputs, feedback


def fmt_params(params, skip=("OUTPUT",)):
    lines = []
    for k, v in params.items():
        if k in skip:
            continue
        if isinstance(v, str) and len(v) > 44:
            v = "…" + v[-42:]
        if hasattr(v, "name"):
            v = v.name()
        lines.append(f"{k:<16} = {v}")
    return "\n".join(lines) if lines else "(algorithm defaults)"


# ══════════════════════════════════════════════════════════════════════════
#  MODULE RUNNERS — one entry per documented CartoLab capability
# ══════════════════════════════════════════════════════════════════════════
MODULES = []

# Editorial "read the output" notes rendered inside the parameter panel of
# every composite. Kept here so the wording is editable without touching the
# capture logic.
NOTES = {
    "quick_style": (
        "Classes are equal-count by default, so every band holds the same\n"
        "number of neighbourhoods — good for comparison, poor for showing\n"
        "absolute gaps. Switch to Geometric interval when the density\n"
        "distribution is long-tailed (it always is, in a real city).\n\n"
        "The renderer is applied to the INPUT layer in place: save the\n"
        "layer afterwards (Layer ▸ Save As ▸ GeoPackage) to keep the style."
    ),
    "quick_style_monochrome": (
        "Monochrome swaps the colour ramp for black-and-white hatch and dot\n"
        "patterns that darken with the value — photocopy-safe and\n"
        "journal-safe. The legend still carries the numbers, so nothing is\n"
        "lost in greyscale.\n\n"
        "Use this whenever the deliverable will be printed in black and\n"
        "white or photocopied."
    ),
    "normalize_field": (
        "Rate = pop_total ÷ pop_15_64 gives residents per 1 000 working-age\n"
        "people. This is the dependency indicator: values above 1 mean a\n"
        "neighbourhood depends on people outside its own working-age group.\n\n"
        "Always normalize before classifying. A raw population choropleth\n"
        "mostly redraws the urban footprint."
    ),
    "classification": (
        "Adaptive Geometric Interval (GIC) starts from a geometric progression\n"
        "of class widths and merges classes until the variance criterion is\n"
        "met — it follows the shape of skewed urban data instead of\n"
        "forcing equal counts.\n\n"
        "Compare with Fisher-Jenks: GIC keeps a readable, ordered set of\n"
        "round-ish intervals; Jenks minimises within-class variance."
    ),
    "bivariate": (
        "Each polygon carries a class label combining an X band and a Y band\n"
        "(bivar_class). The 3×3 palette therefore reads on two axes at once.\n\n"
        "X axis = share of residents aged 65+, Y axis = share aged 0–14.\n"
        "Upper-left = old and few children (care load), upper-right = old\n"
        "and young (care load plus school load) — the hardest quadrant."
    ),
    "bivariate_matrix": (
        "The legend is exported as vector geometry (diamonds or squares) and\n"
        "as standalone HTML, so it can be dropped into a layout or a\n"
        "manuscript without re-drawing the matrix by hand.\n\n"
        "Keep the axis labels identical to the map caption — the matrix is\n"
        "meaningless without them."
    ),
    "value_by_alpha": (
        "Hue carries the value (population density); opacity carries the\n"
        "reliability proxy (share of the working-age population).\n\n"
        "Faded polygons are not missing data — they are uncertain data.\n"
        "That distinction is the whole point of Value-by-Alpha: a normal\n"
        "choropleth would hide them behind a 'no data' colour."
    ),
    "cartogram": (
        "Every polygon is resized so that its AREA is proportional to the\n"
        "value, while the shared borders stay contiguous.\n\n"
        "Compare panel 1 with panel 3: the eastern mountain districts\n"
        "shrink, the central districts swell. The residual error (%) tells\n"
        "you how close the engine got to the target areas."
    ),
    "dorling": (
        "Circles replace polygons: area is proportional to the value, but\n"
        "the circle stays near its original position.\n\n"
        "Use Dorling when the SHAPE of the unit carries meaning (coastline,\n"
        "river, border) and you still need to show totals. Use a continuous\n"
        "cartogram when the shape itself is the message."
    ),
    "dot_density": (
        "One dot represents VALUE_PER_DOT residents. The dots are seeded, so\n"
        "re-running with the same SEED gives the identical map — essential\n"
        "for a report where the figure must be reproducible.\n\n"
        "Dots are placed inside the polygon and never in holes, so the map\n"
        "shows where people actually are, not a scatter of centroids."
    ),
    "proportional_symbols": (
        "Flannery compensation corrects the perceptual under-estimation of\n"
        "area differences: a circle that looks twice as big is not twice\n"
        "the value.\n\n"
        "Use proportional symbols when the values live at points (centres,\n"
        "stations) and the polygons would carry no extra information."
    ),
    "hexbin": (
        "The point layer is binned into a pointy-top hexagonal grid — the\n"
        "aggregation that avoids the overplotting of raw points.\n\n"
        "Here the weight (population) is SUMMED per cell, so the map reads\n"
        "as 'how many people live in each hexagon'. The grid also removes\n"
        "the false precision of small-area administrative units."
    ),
    "label_points": (
        "Each polygon gets an anchor at its pole of inaccessibility — the\n"
        "point furthest from the polygon edge, which is guaranteed to lie\n"
        "inside the shape.\n\n"
        "Centroid labels drift off concave shapes; these do not. Join this\n"
        "layer to your label layer to place district names safely."
    ),
    "graticule": (
        "Meridians and parallels are placed on a round interval and each one\n"
        "carries its own coordinate label.\n\n"
        "Use a 10 km interval on a city-scale map, 1° on a country map.\n"
        "The graticule is a reference layer — always draw it beneath the\n"
        "data, in a low-contrast grey."
    ),
    "ridge_map": (
        "The raster is sampled along scanlines and every scanline is drawn\n"
        "as a profile: elevation becomes a stack of ridgelines.\n\n"
        "Vertical exaggeration is the parameter that matters — too little and\n"
        "the relief disappears, too much and it becomes a cartoon. Change\n"
        "VERTICAL_SCALE and compare."
    ),
    "building_25d": (
        "The height field drives a native QGIS 25d renderer: roofs, walls and\n"
        "directional shading. The plugin writes the style as a reusable\n"
        "expression, so the same rule works on any layer with the same\n"
        "height field.\n\n"
        "MAX_HEIGHT clamps outliers; without it one 300 m tower flattens\n"
        "every other building in the frame."
    ),
    "flow_map": (
        "Each record becomes a curved desire line between the two zone\n"
        "anchors. Width is proportional to the volume; large flows are drawn\n"
        "first so small flows stay visible on top.\n\n"
        "DIRECTED keeps the arrowheads and separates A→B from B→A. Arrows\n"
        "are the difference between a flow map and a network diagram."
    ),
}


def module(module_id, group, display, algo_id=None):
    def deco(fn):
        MODULES.append({
            "id": module_id, "group": group, "display": display,
            "algo_id": algo_id, "fn": fn,
        })
        return fn
    return deco


def _base_layers(data):
    """Reference layers drawn under results."""
    ctx = []
    if data.mahalle is not None:
        ctx.append(_neutral(data.mahalle))
    return ctx


def _context_for(data, result_layer):
    ctx = []
    if data.mahalle is not None and result_layer is not data.mahalle:
        ctx.append(_neutral(data.mahalle, "#e2e8f0"))
    if result_layer is not None:
        ctx.append(result_layer)
    return ctx


# ── 1. Quick Style ─────────────────────────────────────────────────────────
@module("quick_style", "Symbology Studio", "Quick Style", "zero2cartolab:quick_style")
def run_quick_style(data):
    layer = data.mahalle
    params = {
        "INPUT": layer,
        "FIELD": "pop_density",
        "MODE": 1,
        "CLASSES": 5,
        "METHOD": 2,       # Geometric interval
        "PALETTE": 15,     # Viridis
        "REVERSE": False,
        "OUTLINE": True,
        "MONOCHROME": False,
    }
    out, _ = run_algo("zero2cartolab:quick_style", params)
    styled = layer  # quick_style styles the layer in place
    ctx = _context_for(data, styled)
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [styled]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [styled],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 2. Monochrome print-safe Quick Style ──────────────────────────────────
@module("quick_style_monochrome", "Symbology Studio", "Quick Style — Monochrome Print",
        "zero2cartolab:quick_style")
def run_quick_style_mono(data):
    layer = data.mahalle.clone()
    params = {
        "INPUT": layer,
        "FIELD": "pop_density",
        "MODE": 1,
        "CLASSES": 5,
        "METHOD": 2,
        "PALETTE": 21,     # Greys
        "REVERSE": False,
        "OUTLINE": True,
        "MONOCHROME": True,
    }
    out, _ = run_algo("zero2cartolab:quick_style", params)
    styled = layer
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [styled]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [styled],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 3. Normalization & rates ──────────────────────────────────────────────
@module("normalize_field", "Data Preparation", "Choropleth Normalization & Rates",
        "zero2cartolab:normalize_field")
def run_normalize(data):
    params = {
        "INPUT": data.mahalle,
        "FIELD": "pop_total",
        "METHOD": 0,       # Rate (numerator / denominator)
        "DENOMINATOR": "pop_15_64",
        "SCALE": 1000.0,
        "PALETTE": 15,
        "CLASSES": 5,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:normalize_field", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 4. Adaptive classification ────────────────────────────────────────────
@module("classification", "Classification Engine", "Adaptive Classification (GIC / Jenks / Head-Tail)",
        "zero2cartolab:geometric_interval_classification")
def run_classification(data):
    params = {
        "INPUT": data.mahalle,
        "FIELD": "pop_density",
        "CLASSES": 5,
        "METHOD": 0,       # Adaptive Geometric Interval
        "PALETTE": 15,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:geometric_interval_classification", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 5. Bivariate choropleth ───────────────────────────────────────────────
@module("bivariate", "Thematic Mapping", "Bivariate Choropleth", "zero2cartolab:bivariate_choropleth")
def run_bivariate(data):
    params = {
        "INPUT": data.mahalle,
        "FIELD_X": "elderly_share",     # X axis: 65+ share
        "FIELD_Y": "child_share",       # Y axis: 0-14 share
        "CLASSES": 3,
        "METHOD": 0,
        "PALETTE_PRESET": 2,            # Blue - Orange
        "COLOR_LL": "#eff3ff",
        "COLOR_LH": "#bdd7e7",
        "COLOR_HL": "#fdbb84",
        "COLOR_HH": "#e34a33",
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:bivariate_choropleth", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 6. Bivariate legend matrix ────────────────────────────────────────────
@module("bivariate_matrix", "Thematic Mapping", "Bivariate 2D Legend Matrix",
        "zero2cartolab:bivariate_matrix_export")
def run_bivariate_matrix(data):
    params = {
        "CLASSES": 3,
        "PALETTE_PRESET": 2,
        "COLOR_LL": "#eff3ff",
        "COLOR_LH": "#bdd7e7",
        "COLOR_HL": "#fdbb84",
        "COLOR_HH": "#e34a33",
        "DIAMOND": True,
        "CELL_SIZE": 30.0,
        "ORIGIN_X": 0.0,
        "ORIGIN_Y": 0.0,
        "LABEL_X": "65+ yaş payı",
        "LABEL_Y": "0-14 yaş payı",
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:bivariate_matrix_export", params)
    result = out.get("OUTPUT")
    html_out = out.get("OUTPUT_HTML")
    return {
        "inputs": [],
        "result": [result],
        "context": [result],
        "params": fmt_params(params) + f"\n{'HTML':<16} = {html_out}",
        "extent": None,
        "single": True,
    }


# ── 7. Value-by-Alpha ─────────────────────────────────────────────────────
@module("value_by_alpha", "Thematic Mapping", "Value-by-Alpha", "zero2cartolab:value_by_alpha")
def run_vba(data):
    params = {
        "INPUT": data.mahalle,
        "FIELD_COLOUR": "pop_density",
        "FIELD_ALPHA": "working_share",
        "ALPHA_MIN": 64,     # 25 % opacity for the least reliable areas
        "ALPHA_MAX": 255,    # fully opaque for the most reliable areas
        "PALETTE": 5,      # Cividis
        "CLASSES": 5,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:value_by_alpha", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 8. Cartogram ──────────────────────────────────────────────────────────
@module("cartogram", "Cartogram Engine", "Continuous-Area Cartogram",
        "zero2cartolab:compute_cartogram")
def run_cartogram(data):
    src = data.districts or data.mahalle
    params = {
        "INPUT": src,
        "FIELD": "pop_total",
        "MAX_ITERATIONS": 60,
        "MAX_ERROR": 5.0,      # max average area error, percent
        "PALETTE": 1,      # Viridis
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:compute_cartogram", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(src, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(src)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params) + f"\n{'ITERATIONS':<16} = {out.get('ITERATIONS')}\n"
                                      f"{'RESIDUAL_ERROR':<16} = {out.get('RESIDUAL_ERROR')}",
        "extent": _extent_of([src], 1.08),
    }


# ── 9. Dorling cartogram ──────────────────────────────────────────────────
@module("dorling", "Cartogram Engine", "Dorling Circle Cartogram", "zero2cartolab:dorling_cartogram")
def run_dorling(data):
    src = data.districts or data.mahalle
    params = {
        "INPUT": src,
        "FIELD": "pop_total",
        "SIZE_FACTOR": 1.0,
        "ATTRACTION": 0.6,
        "GAP": 3.0,
        "ITERATIONS": 300,
        "PALETTE": 0,      # Viridis
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:dorling_cartogram", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(src, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(src)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params) + f"\n{'ROUNDS':<16} = {out.get('ROUNDS')}\n"
                                      f"{'RESIDUAL':<16} = {out.get('RESIDUAL')}",
        "extent": _extent_of([src], 1.08),
    }


# ── 10. Dot density ───────────────────────────────────────────────────────
@module("dot_density", "Thematic Mapping", "Dot-Density Map", "zero2cartolab:dot_density")
def run_dot_density(data):
    params = {
        "INPUT": data.mahalle,
        "FIELD": "pop_total",
        "VALUE_PER_DOT": 500.0,
        "DOT_SIZE": 2.0,
        "DOT_COLOR": "#7c3aed",
        "SEED": 42,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:dot_density", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 11. Proportional symbols ──────────────────────────────────────────────
@module("proportional_symbols", "Thematic Mapping", "Proportional Symbols (Flannery)",
        "zero2cartolab:proportional_symbols")
def run_prop_symbols(data):
    params = {
        "INPUT": data.mahalle_points,
        "FIELD": "pop_total",
        "MAX_SIZE": 14.0,
        "MIN_SIZE": 2.0,
        "SHAPE": 0,
        "FILL_COLOR": "#e38e4f",
        "OUTLINE_COLOR": "#7c2d12",
        "FLANNERY": True,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:proportional_symbols", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 12. Hexbin ────────────────────────────────────────────────────────────
@module("hexbin", "Aggregation", "Hexbin Aggregation", "zero2cartolab:hexbin_aggregate")
def run_hexbin(data):
    params = {
        "INPUT": data.mahalle_points,
        "CELL_SIZE": 1500.0,
        "WEIGHT": "pop_total",
        "STAT": 1,          # Sum of weight
        "PALETTE": 5,       # Cividis
        "CLASSIFIER": 0,    # Quantile
        "CLASSES": 5,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:hexbin_aggregate", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 13. Label points ──────────────────────────────────────────────────────
@module("label_points", "Labeling", "Visual-Center Label Points", "zero2cartolab:label_points")
def run_label_points(data):
    params = {
        "INPUT": data.mahalle,
        "PRECISION": 1.0,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:label_points", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#e8edf3")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 14. Graticule ──────────────────────────────────────────────────────────
@module("graticule", "Map Reference", "Graticule / Reference Grid", "zero2cartolab:graticule_grid")
def run_graticule(data):
    ext = data.mahalle.extent()
    params = {
        "EXTENT": f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()} [EPSG:32635]",
        "X_INTERVAL": 10000.0,
        "Y_INTERVAL": 10000.0,
        "LINE_STYLE": 1,
        "LINE_COLOR": "#64748b",
        "LINE_WIDTH": 0.35,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:graticule_grid", params)
    result = out.get("OUTPUT")
    ctx = [_neutral(data.mahalle, "#eef1f5")] + [result]
    return {
        "inputs": [_neutral(data.mahalle)],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.mahalle], 1.08),
    }


# ── 15. Ridge map ─────────────────────────────────────────────────────────
@module("ridge_map", "Thematic Mapping", "Ridge Map (Joy Division)",
        "zero2cartolab:ridge_map")
def run_ridge_map(data):
    if data.dem is None:
        return None
    ext = data.dem.extent()

    # Vertical exaggeration is the raw elevation multiplied. Derive it from the
    # data so the tallest ridge rises about a third of the map height — a rule
    # the reader can reuse on their own raster.
    v_scale = 2.0
    try:
        stats = data.dem.dataProvider().bandStatistics(1)
        if stats.maximumValue > 0:
            v_scale = round((ext.height() * 0.32) / stats.maximumValue, 3)
    except Exception:
        pass

    params = {
        "RASTER": data.dem,
        "N_LINES": 120,
        "VERTICAL_SCALE": v_scale,
        "LINE_SPACING": 0.0,
        "SMOOTH": 2.0,
        "EXTENT": f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()} "
                  f"[{data.dem.crs().authid()}]",
        "LINE_COLOR": "#111827",
        "LINE_WIDTH": 0.28,
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:ridge_map", params)
    result = out.get("OUTPUT")
    ctx = [result]
    return {
        "inputs": [data.dem],
        "result": [result],
        "context": [data.dem, result],
        "params": fmt_params(params),
        "extent": _extent_of([data.dem], 1.05),
    }


# ── 16. 2.5D building style ───────────────────────────────────────────────
@module("building_25d", "Symbology Studio", "2.5D Building Styling",
        "zero2cartolab:building_25d_style")
def run_25d(data):
    if data.buildings is None:
        return None
    layer = data.buildings.clone()
    params = {
        "INPUT": layer,
        "HEIGHT_FIELD": "height_m",
        "HEIGHT_MODE": 0,       # metres
        "FLOOR_HEIGHT": 3.5,
        "RENDER_MODE": 0,       # native material
        "FLOOR_PALETTE": 0,
        "MAX_FLOORS": 12,
        "PRESET": 0,            # Warm Civic
        "ANGLE": 45.0,
        "HEIGHT_SCALE": 1.0,
        "MAX_HEIGHT": 60.0,
        "STEPPED": False,
        "STEP_HEIGHT": 3.5,
        "SHADOW_ENABLED": True,
        "SHADOW_SPREAD": 1.2,
        "WALL_SHADING": True,
    }
    out, _ = run_algo("zero2cartolab:building_25d_style", params)
    styled = layer
    neutral_buildings = data.buildings.clone()
    from qgis.core import QgsFillSymbol, QgsSingleSymbolRenderer
    neutral_buildings.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({
        "color": "#d7dde5", "outline_color": "#94a3b8", "outline_width": "0.12"})))

    # Frame the panel on the tall stock so the extrusion is actually legible.
    tall = QgsVectorLayer("Polygon?crs=EPSG:32635", "tall", "memory")
    tall_dp = tall.dataProvider()
    tall_dp.addAttributes([QgsField("height_m", QVariant.Double)])
    tall.updateFields()
    tfeats = []
    for f in data.buildings.getFeatures():
        try:
            h = float(f["height_m"] or 0)
        except (TypeError, ValueError):
            h = 0.0
        if h < 12.0:
            continue
        nf = QgsFeature(tall.fields())
        nf.setGeometry(QgsGeometry(f.geometry()))
        nf.setAttributes([h])
        tfeats.append(nf)
    tall_dp.addFeatures(tfeats)
    tall.updateExtents()

    extent = _extent_of([tall], 1.45) or _extent_of([data.buildings], 1.05)
    summary = str(out.get("SUMMARY") or "").replace("\n", " · ")[:110]
    return {
        "inputs": [neutral_buildings],
        "result": [styled],
        "context": [styled],
        "params": fmt_params(params) + f"\n{'SUMMARY':<16} = {summary}",
        "extent": extent,
    }


# ── 17. Flow map ──────────────────────────────────────────────────────────
@module("flow_map", "Thematic Mapping", "Origin-Destination Flow Map", "zero2cartolab:flow_map")
def run_flow_map(data):
    if data.flow_zones is None or data.flows is None:
        return None
    params = {
        "ZONES": data.flow_zones,
        "ZONE_ID": "zone_id",
        "FLOWS": data.flows,
        "ORIGIN": "origin_id",
        "DEST": "dest_id",
        "VOLUME": "flow_vol",
        "DIRECTED": True,
        "MIN_VOLUME": 5.0,
        "TOP_N": 0,
        "CURVATURE": 0.32,
        "MAX_WIDTH": 4.0,
        "MIN_WIDTH": 0.25,
        "END_GAP": 6.0,
        "ARROWS": True,
        "PALETTE": 0,      # YlOrRd
        "OUTPUT": "memory:",
    }
    out, _ = run_algo("zero2cartolab:flow_map", params)
    result = out.get("OUTPUT")
    ctx = [data.flow_zones, result]
    return {
        "inputs": [data.flow_zones],
        "result": [result],
        "context": ctx,
        "params": fmt_params(params),
        "extent": _extent_of([data.flow_zones], 1.06),
    }


# ══════════════════════════════════════════════════════════════════════════
#  LAYOUT STUDIO + REAL DASHBOARD GUI CAPTURES
# ══════════════════════════════════════════════════════════════════════════
def _export_layout_png(layout, out_png, dpi=120):
    """Render a QgsPrintLayout page to PNG (real QGIS layout exporter)."""
    from qgis.core import QgsLayoutExporter
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = dpi
    settings.generateWorldFile = False
    out_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = exporter.exportToImage(str(out_png), settings)
        ok = result == QgsLayoutExporter.Success
    except Exception:
        ok = False
    return bool(ok and out_png.exists() and out_png.stat().st_size > 0)



LAYOUT_TEMPLATES = [
    ("report_figure", "Report Figure — 16:9"),
    ("academic_journal", "Academic Journal — A4 two-column"),
    ("poster_exhibition", "Exhibition Poster — A2"),
    ("fact_sheet", "Fact Sheet — A4 portrait"),
    ("side_by_side_diptych", "Comparative Diptych"),
    ("utm_field_sheet", "UTM Field Sheet"),
    ("planning_board", "Planning Review Board"),
    ("data_story", "Spatial Data Story"),
    ("atlas_production", "Atlas Production Sheet"),
    ("emergency_brief", "Emergency Operations Brief"),
]


def _thematic_style(layer, field, palette="Viridis", classes=5, method="geometric"):
    """Apply a CartoLab graduated renderer to a layer (plugin's own engines)."""
    from qgis.core import QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsRendererRange
    from zero2cartolab.core.quick_style import compute_breaks, edges_to_ranges
    from zero2cartolab.core.palettes import get_palette
    values = []
    for f in layer.getFeatures():
        v = f[field]
        if v is None:
            continue
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    if not values:
        return layer
    edges = compute_breaks(values, method=method, n=classes)
    ranges = edges_to_ranges(edges)
    colors = get_palette(palette, len(ranges))
    out = []
    for i, (lo, hi) in enumerate(ranges):
        col = colors[min(i, len(colors) - 1)]
        sym = QgsFillSymbol.createSimple({
            "color": col, "outline_color": "#ffffff", "outline_width": "0.25"})
        out.append(QgsRendererRange(lo, hi, sym, f"{lo:,.0f} – {hi:,.0f}"))
    if out:
        layer.setRenderer(QgsGraduatedSymbolRenderer(field, out))
    return layer


def _layout_capture(data, template_id, title, out_png, theme="swiss_modern"):
    from zero2cartolab.layout.template_gallery import create_template_layout
    layer = data.districts or data.mahalle
    extent = _extent_of([layer], 1.15)
    with suppress(Exception):
        _thematic_style(layer, "pop_density", palette="Viridis", classes=5,
                        method="geometric")
    layout = create_template_layout(
        template_id, iface=None,
        project=QgsProject.instance(),
        layers=[layer],
        extent=extent,
        crs=layer.crs(),
        title=title,
        subtitle="İzmir neighbourhood population · 02CartoLab publication template",
        credits="Source: TÜİK-based neighbourhood population 2024 · Cartography: 02CartoLab",
        theme=theme,
    )
    if layout is None:
        return False
    return _export_layout_png(layout, out_png)


@module("layout_templates", "Layout Studio", "Publication Layout Template Gallery")
def run_layout_templates(data):
    """Render every publication archetype with the same real İzmir data."""
    from zero2cartolab.layout.template_gallery import list_templates
    out_dir = SHOTS / "layout_templates"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for tid, title in LAYOUT_TEMPLATES:
        png = out_dir / f"{tid}.png"
        try:
            if _layout_capture(data, tid, title, png):
                made.append({"id": tid, "title": title,
                             "path": str(png.relative_to(HERE)).replace("\\", "/")})
                print(f"       ↳ template {tid} → {png.name}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"       ↳ template {tid} FAILED: {exc}", flush=True)
    if not made:
        return None
    return {"inputs": [], "result": [], "context": [], "params": "", "single": True,
            "templates": made, "extent": None}


@module("map_sheet", "Layout Studio", "Auto Map Sheet")
def run_map_sheet(data):
    """One-click publication layout built from the current view."""
    from zero2cartolab.layout.map_sheet import create_map_sheet
    layer = data.districts or data.mahalle
    extent = _extent_of([layer], 1.12)
    with suppress(Exception):
        _thematic_style(layer, "pop_density", palette="Viridis", classes=5,
                        method="geometric")
    layout = create_map_sheet(
        iface=None,
        layers=[layer],
        extent=extent,
        crs=layer.crs(),
        title="İzmir Mahalle Yoğunluğu",
        subtitle="Nüfus yoğunluğu (kişi/km²) · 2024",
        credits="Kaynak: mahalle nüfus verisi 2024 · Harita: 02CartoLab",
        page_size="A4",
        landscape=True,
        add_grid=True,
        preset="swiss_modern",
        layout_name="CartoLab Map Sheet",
        project=QgsProject.instance(),
    )
    if layout is None:
        return None
    png = SHOTS / "map_sheet" / "map_sheet.png"
    if not _export_layout_png(layout, png):
        return None
    return {"inputs": [], "result": [], "context": [], "params": "", "single": True,
            "layout_png": str(png.relative_to(HERE)).replace("\\", "/"), "extent": None}


@module("gui_dashboard", "Symbology Studio", "The 02CartoLab Dashboard (real GUI)")
def run_gui_dashboard(data):
    """Screenshot the actual dashboard widget tree — no mock-ups."""
    from zero2cartolab.ui.cartolab_dashboard import CartoLabDashboard

    # Register the real layers in the project so every combo box is populated
    # exactly as it would be in a live QGIS session.
    project = QgsProject.instance()
    for lyr in (data.districts, data.mahalle, data.buildings):
        if lyr is not None and lyr.isValid():
            project.addMapLayer(lyr, False)

    class _Iface:
        def mainWindow(self):
            return None

        def mapCanvas(self):
            return None

        def layerTreeView(self):
            return None

        def activeLayer(self):
            return data.districts or data.mahalle

    out_dir = SHOTS / "gui_dashboard"
    out_dir.mkdir(parents=True, exist_ok=True)

    dash = CartoLabDashboard(_Iface(), parent=None)
    dash.resize(1360, 900)
    dash.show()
    for _ in range(12):
        QgsApplication.processEvents()
    with suppress(Exception):
        dash._refresh_all_layer_combos()

    # Preselect the district layer + a numeric field in the Quick Style panel.
    with suppress(Exception):
        target = data.districts or data.mahalle
        idx = dash.qs_layer_combo.findData(target.id())
        if idx >= 0:
            dash.qs_layer_combo.setCurrentIndex(idx)
        QgsApplication.processEvents()
        fidx = dash.qs_field_combo.findText("pop_density")
        if fidx >= 0:
            dash.qs_field_combo.setCurrentIndex(fidx)
        QgsApplication.processEvents()
    with suppress(Exception):
        dash._apply_style()
        QgsApplication.processEvents()

    pages = []

    def snap(filename, title):
        for _ in range(6):
            QgsApplication.processEvents()
        p = out_dir / filename
        dash.grab().save(str(p), "PNG")
        pages.append({"id": p.stem, "title": title,
                      "path": str(p.relative_to(HERE)).replace("\\", "/")})

    # Workspace 1 — Symbology Studio, every sub-tab
    dash.nav_sidebar.setCurrentRow(0)
    for i, (fname, title) in enumerate([
        ("dashboard_quick_style.png", "Symbology Studio · Quick Style"),
        ("dashboard_25d.png", "Symbology Studio · 2.5D Buildings"),
        ("dashboard_thematic.png", "Symbology Studio · Thematic Maps"),
        ("dashboard_palette.png", "Symbology Studio · Palette & Accessibility"),
    ]):
        with suppress(Exception):
            dash.symbology_sub_tabs.setCurrentIndex(i)
        snap(fname, title)

    # Workspace 2 — Layout Studio, every sub-tab
    dash.nav_sidebar.setCurrentRow(1)
    for i, (fname, title) in enumerate([
        ("dashboard_templates.png", "Layout Studio · Template Gallery"),
        ("dashboard_mapsheet.png", "Layout Studio · Map Sheet Studio"),
        ("dashboard_grid_qpt.png", "Layout Studio · Grid + QPT Studio"),
        ("dashboard_isometric.png", "Layout Studio · 3D Isometric Stacker"),
    ]):
        with suppress(Exception):
            dash.layout_sub_tabs.setCurrentIndex(i)
        snap(fname, title)

    # Workspace 3 — Processing Hub
    dash.nav_sidebar.setCurrentRow(2)
    snap("dashboard_processing.png", "Processing Hub")

    dash.close()
    return {"inputs": [], "result": [], "context": [], "params": "", "single": True,
            "gui_pages": pages, "extent": None}


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(description="02CartoLab practical-guide screenshot generator")
    ap.add_argument("--module", action="append", default=None,
                    help="run only this module id (repeatable)")
    ap.add_argument("--all", action="store_true", help="run every module")
    ap.add_argument("--data", action="append", default=None,
                    help="extra folder to search for the input datasets (repeatable)")
    args = ap.parse_args()

    if args.data:
        for extra in args.data:
            DATA_ROOTS.insert(0, Path(extra))

    selected = MODULES
    if args.module:
        wanted = set(args.module)
        selected = [m for m in MODULES if m["id"] in wanted]

    data = DataBundle()
    data.resolve()
    data.build()
    print("Data notes:", flush=True)
    for note in data.notes:
        print("   -", note, flush=True)
    if data.mahalle is None:
        print("FATAL: no real polygon source resolved.", flush=True)
        return 2

    manifest = {
        "generated": "",
        "qgis_version": qgis.core.Qgis.QGIS_VERSION,
        "data_notes": data.notes,
        "modules": {},
    }

    for spec in selected:
        mid = spec["id"]
        out_dir = SHOTS / mid
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            res = spec["fn"](data)
            if res is None:
                print(f"SKIP  {mid}: required real data unavailable", flush=True)
                continue
            png = out_dir / f"{mid}_4panel.png"
            entry = {
                "id": mid,
                "group": spec["group"],
                "display": spec["display"],
                "algo_id": spec["algo_id"],
                "params": res["params"],
                "notes": NOTES.get(mid, ""),
            }
            if res.get("single"):
                if res.get("layout_png"):
                    png = HERE / res["layout_png"]
                elif res.get("templates"):
                    png = None
                else:
                    png = out_dir / f"{mid}.png"
                    compose_single(mid, spec["display"], res["result"], res.get("extent"),
                                   png, caption="real 02CartoLab output",
                                   footer=res["params"][:120].replace("\n", "  ·  "))
            else:
                compose_4panel(mid, spec["display"], res["inputs"], res["params"],
                               res["result"], res["context"], res["params"], png,
                               subtitle=spec["group"], notes=NOTES.get(mid, ""),
                               extent=res.get("extent"))
            if png is not None:
                entry["screenshot"] = str(png.relative_to(HERE)).replace("\\", "/")
            if res.get("templates"):
                entry["templates"] = res["templates"]
            if res.get("gui_pages"):
                entry["gui_pages"] = res["gui_pages"]
            entry["status"] = "ok"
            manifest["modules"][mid] = entry
            print(f"OK    {mid:<26} → {png.name if png else 'multi'}", flush=True)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            manifest["modules"][mid] = {
                "id": mid, "group": spec["group"], "display": spec["display"],
                "algo_id": spec["algo_id"], "status": "failed", "error": str(exc),
            }
            print(f"FAIL  {mid}: {exc}", flush=True)

    MANIFEST.mkdir(parents=True, exist_ok=True)
    import datetime
    manifest["generated"] = datetime.datetime.now().isoformat(timespec="seconds")
    out_json = MANIFEST / "screenshots.json"
    if out_json.exists():
        try:
            existing = json.loads(out_json.read_text(encoding="utf-8"))
            merged = existing.get("modules", {})
            merged.update(manifest["modules"])
            manifest["modules"] = merged
        except Exception:
            pass
    out_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nmanifest → {out_json}", flush=True)
    print(f"modules captured: {len(manifest['modules'])}", flush=True)
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
