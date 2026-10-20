# 02CartoLab Practical Guide

**Companion to the [Academic Reference Manual](../CARTOLAB_REFERENCE_MANUAL.html).**

The Reference Manual explains *why* each cartographic method works — the maths,
the literature, the interpretation rules. This guide shows *how to actually do
it*, with every step executed against real urban data and every result
captured as a screenshot.

Nothing in this guide is a mock-up. Every map panel is a QGIS render of a
layer the plugin actually produced; every parameter panel is the literal
parameter dictionary handed to the algorithm; every interface panel is a
screenshot of the real dashboard widget tree; every layout is an exported print
layout.

---

## 📁 Structure

```text
zero2cartolab/docs/PRACTICAL_GUIDE/
├── practical_guide.html            # ← interactive guide (English, browser)
├── practical_guide_static.html     # ← print/PDF guide (Turkish)
├── practical_guide_static_en.html  # ← print/PDF guide (English)
├── practical_guide_runner.py       # headless capture harness (real QGIS)
├── extract_registry.py             # live Processing registry → JSON
├── build_guide.py                  # content + manifest → HTML
├── optimize_images.py              # web-sized JPEG copies
├── run_practical_guide.bat         # Windows launcher
├── manifest/
│   ├── guide_content.json          # authored copy, EN + TR, per module
│   ├── algorithms.json             # live registry metadata (auto-generated)
│   └── screenshots.json            # what was captured, and with which parameters
├── screenshots/
│   ├── <module>/<module>_4panel.png
│   ├── gui_dashboard/              # real dashboard screenshots
│   ├── layout_templates/           # the 10 publication archetypes, exported
│   └── web/                        # optimised JPEG copies used by the HTML
└── data/
    └── od_table.csv                # the OD example used by the flow map
```

---

## 🚀 Quick start

### Prerequisites

- QGIS 3.28+ (tested on 3.44 LTR and 4.2) via OSGeo4W
- Python with Pillow for the image optimisation step

### Real data the harness looks for

| Purpose | File | Searched under |
|---|---|---|
| Thematic choropleths, cartograms, density | `mahalle_population_2024.geojson` (İzmir neighbourhoods, population 2024) | `~/Downloads` |
| 2.5D building extrusion | `kadifekale_osm_binalar.gpkg` (OSM buildings with `height_m`, `levels`) | `~/Downloads/geo3d_test_data` |
| Ridge maps | `kadifekale_dem_copernicus30m.tif` (Copernicus DEM 30 m) | `~/Downloads/geo3d_test_data` |
| Origin–destination flow map | `tire_mahalle_upi_sosyoekonomik.gpkg` (assembly areas + critical assets) | `~/Downloads` |

Point the harness somewhere else with `--data`:

```cmd
run_practical_guide.bat --all --data D:\my_city_data
```

Any dataset works as long as it exposes a polygon layer with a numeric field,
a point layer, a DEM and (for the flow map) an OD table.

### Run

```cmd
run_practical_guide.bat                      REM every module
run_practical_guide.bat --module bivariate   REM one module
run_practical_guide.bat --module layout_templates --module gui_dashboard
```

Then rebuild the HTML:

```cmd
python build_guide.py
python optimize_images.py
```

---

## 📸 The 4-panel composite

Every algorithmic module produces the same four-panel image, so the guide
reads consistently:

```text
┌──────────────────────┬──────────────────────┐
│ 1 · INPUT DATA       │ 2 · PARAMETERS USED  │
│ source layer(s)      │ exact run + reading  │
│                      │ notes                │
├──────────────────────┼──────────────────────┤
│ 3 · RESULT           │ 4 · IN CONTEXT       │
│ output by 02CartoLab │ result over the base │
└──────────────────────┴──────────────────────┘
```

## 🗺 Covered modules

| Workspace | Modules |
|---|---|
| Getting started | Dashboard tour |
| Symbology Studio | Quick Style, Monochrome print, 2.5D Buildings, Palette & Accessibility |
| Data Preparation | Normalization & rates |
| Classification Engine | Adaptive classification (GIC / Jenks / Head-Tail) |
| Thematic Mapping | Bivariate choropleth, Bivariate legend matrix, Value-by-Alpha, Ridge map, Dot density, Proportional symbols, Origin–Destination flow map |
| Cartogram Engine | Continuous-area cartogram, Dorling cartogram |
| Aggregation | Hexbin aggregation |
| Labeling | Visual-centre label points |
| Map Reference | Graticule / reference grid |
| Layout Studio | Publication template gallery (10 archetypes), Auto Map Sheet |

---

## 🛠 Extending the guide

### Add a module

1. Write a capture function in `practical_guide_runner.py` decorated with
   `@module("<id>", "<group>", "<display>", "<algo id>")`.
2. Return a dict with `inputs`, `result`, `context`, `params` and `extent`.
3. Add the copy for the module in `manifest/guide_content.json` under both
   `en` and `tr`.
4. Re-run the runner and `build_guide.py`.

### Add text to an existing module

Everything the reader sees lives in `manifest/guide_content.json`:

```json
"bivariate": {
  "group": "Thematic Mapping",
  "algo": "zero2cartolab:bivariate_choropleth",
  "en": {
    "title": "Bivariate choropleth — two variables, one honest map",
    "question": "Which neighbourhoods are both old and full of children?",
    "what": "…",
    "steps": ["…", "…"],
    "interpret": "…",
    "trouble": ["…", "…"]
  },
  "tr": { "…": "…" }
}
```

Parameter tables are **not** authored — they are extracted from the live
Processing registry by `extract_registry.py`, so they cannot drift from the code.

---

## 📄 License

Same as 02CartoLab: **GPL-3.0** © Yusuf Eminoğlu
