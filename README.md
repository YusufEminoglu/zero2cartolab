<div align="center">

![0202CartoLab](media/banner.png)

# 0202CartoLab

**Publication-grade cartography — without leaving QGIS.**

[![Release](https://img.shields.io/github/v/release/YusufEminoglu/zero2cartolab?color=3b4994&label=release)](https://github.com/YusufEminoglu/zero2cartolab/releases)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/📖_Reference_Manual-13a0a0)](https://yusufeminoglu.github.io/YusufEminoglu/zero2cartolab/)
[![QGIS](https://img.shields.io/badge/QGIS-3.28%20LTR%20%E2%86%92%204.x-589632?logo=qgis&logoColor=white)](https://qgis.org)
[![Showcase](https://img.shields.io/badge/showcase-GitHub%20Pages-be64ac)](docs/index.html)
[![Part of PlanX](https://img.shields.io/badge/suite-PlanX-ff8a3d)](https://github.com/YusufEminoglu/PlanX)

The map types journals and design studios actually ask for —
**2.5D buildings, bivariate choropleths, Value-by-Alpha, cartograms, ridge maps, dot-density & proportional symbols, hexbins, visual-center labels and automated layouts** — as native QGIS styling, not fragile pasted QML.

[Install](#-installation) · [Modules](#-module-catalog) · [2.5D styling](#-25d-building-styling) · [Showcase](#-showcase) · [Türkçe](#-türkçe-özet)

</div>

---

## 📖 Documentation

**[Comprehensive Academic Reference Manual](https://yusufeminoglu.github.io/zero2cartolab/)** — complete documentation of every feature, parameter, and workflow. Hosted on GitHub Pages.


## ✨ Why 02CartoLab?

| | |
|---|---|
| ⚡ **One-click Quick Style** | Style any layer in a click — graduated for numbers, categories for text — with a **colour palette library** (ColorBrewer + the colour-blind-safe **viridis** family) and a live preview. Sensible defaults mean the first click already looks good. |
| 🏢 **2.5D that survives** | A native QGIS `25dRenderer` engine with presets, per-floor colour bands and one legend rule per floor — a reusable, legend-friendly replacement for ad-hoc QML extrusion hacks. One click exports the style back to QML. |
| 🎨 **Dual-variable honesty** | Bivariate choropleths (3×3 palettes, custom corner colours) and **Value-by-Alpha** maps that fade unreliable values instead of hiding them — reliability-aware visualisation built in. |
| 📐 **Classification for skewed cities** | Adaptive Geometric Interval, Fisher-Jenks and Head/Tail Breaks — made for the long-tailed indicators urban data actually has. |
| 🗺 **Shape as data** | Continuous-area **cartograms** distort polygons by value; **ridge-line maps** turn any raster (DEM, heat, density, accessibility) into joy-division-style relief. |
| 📊 **Point & density cartography** | **Dot-density**, Flannery **proportional symbols** and **hexbin** aggregation turn raw points and counts into honest density maps — plus visual-center **label anchors** (polylabel) and coordinate **graticules**. |
| 🧮 **Choropleth done right** | One-step **normalization** — rates per capita, z-score, robust MAD-z, percentile rank and log — so you map *rates*, not population. |
| 🖨 **Auto layouts** | One-click **Auto Map Sheet** builds a finished print layout from the current view — titled map frame, filtered legend, scale bar, north arrow, coordinate grid and credits — then opens it in the Designer. Plus a **Layout Manager** (open, duplicate, delete, export PNG/PDF) and decorators: native bivariate legends, isometric layer stacks, minimalist grids and typography hierarchy. |

Built for planners, urban researchers, studios and academic cartography workflows.

---

## 🛠 Module Catalog

Everything is reachable from the **02CartoLab Dashboard** (`Plugins → 0202CartoLab`) and the **Processing Toolbox → 0202CartoLab** provider:

| Module | What it does | Surface |
|---|---|---|
| **Quick Style** | One click: graduated (numeric) or categorized (text) renderer with quantile / equal-interval / geometric-interval breaks and a colour-palette picker | Dashboard panel + Processing |
| **Colour Palettes & Accessibility** | 24+ ramps (ColorBrewer + Scientific viridis/magma/cividis) with live 5-mode CVD simulation (Deuteranopia, Protanopia, Tritanopia, Achromatopsia) and WCAG 2.1 contrast scoring | Dashboard → Symbology Studio |
| **2.5D Building Styling** | Height/floor-field extrusion, material presets, shadows, wall shading, stepped floors, per-floor colour bands, QML export | Dashboard panel + Processing |
| **Bivariate Choropleth** | Two variables, one map; 3×3 palettes incl. custom corner colours; diamond/square legends | Processing + layout |
| **Value-by-Alpha** | Value drives hue, reliability drives opacity | Processing |
| **Cartogram** | Continuous-area distortion proportional to a value field | Processing |
| **Ridge Map** | Raster surface → stacked ridge lines | Processing |
| **Adaptive Classification** | Geometric Interval, Fisher-Jenks, Head/Tail Breaks | Processing |
| **Dot-Density Map** | Seeded, hole-aware dots inside polygons — one dot per N units of a count field | Processing |
| **Proportional Symbols** | Flannery-compensated graduated point symbols with nested-legend values | Processing |
| **Hexbin Aggregation** | Bin a point layer into a pointy-top hex grid — count / sum / mean, overplot-free | Processing |
| **Visual-Center Label Points** | Pole-of-inaccessibility (polylabel) anchors that always sit inside the shape | Processing |
| **Graticule / Reference Grid** | Meridians & parallels on nice intervals, each carrying a coordinate label | Processing |
| **Choropleth Normalization & Rates** | Rate, z-score, robust z, min-max, percentile rank, log — prep before classifying | Processing |
| **Layout Template Gallery** | 5 publication archetypes: Report Figure (16:9), Academic Journal (2-col), Exhibition Poster (A1/A2), Fact Sheet, Comparative Diptych | Dashboard → Layout Studio |
| **Auto Map Sheet** | Complete print layout from the current view — map, legend, scale bar, north arrow, grid, credits — in one click | Dashboard → Layout Studio |
| **Layout Manager** | List, open, duplicate, delete and export (PNG / PDF / SVG, 96–600 dpi) project layouts | Dashboard → Layout Studio |
| **Layout Decorators** | Native bivariate legends, 3D isometric layer stacks, idempotent minimalist grids, typography hierarchy, paper themes | Dashboard → Layout Studio |

---

## 🏢 2.5D Building Styling

The flagship module — a better, reusable version of the QML extrusion styles planners pass around:

- **Native renderer**, not a pasted QML block: stable across projects and QGIS versions.
- **Floor-count mode** for fields like `Kat_Sayisi`: rendered height = floors × floor height (default 3.5 map units).
- **Per-floor colour bands** with selectable palettes and **automatic maximum-floor detection** — every floor band gets its own colour *and its own QGIS legend entry*.
- Optional **floor-step snapping** for planning-height layers, soft shadows, directional wall shading.
- **One-click QML export** for reuse anywhere.

> Quick recipe: open **2.5D Styling**, pick the polygon layer and `Kat_Sayisi`, set *Height source* → *Floor count field*, enable *Colour each floor separately*, leave *Maximum floor bands* on *Auto from layer*. Done — extruded, banded, legend-ready.

---

## 🖼 Showcase

An interactive, GitHub Pages-ready showcase lives in [`docs/index.html`](docs/index.html) — 2.5D canvas scene, feature map, workflow narrative and publication-oriented positioning.

```text
GitHub Pages source →  Branch: master   Folder: /docs
```

More: [Documentation index](docs/README.md) · [Feature showcase](docs/SHOWCASE.md) · [Architecture](docs/ARCHITECTURE.md) · [Publishing notes](docs/PUBLISHING.md)

---

## 📦 Installation

**From QGIS Plugin Hub** *(recommended)*
> `Plugins → Manage and Install Plugins…` → search **0202CartoLab** → Install.

**From ZIP**
> Download the latest zip from [Releases](https://github.com/YusufEminoglu/zero2cartolab/releases) → `Plugins → Install from ZIP`.

| Requirement | Value |
|---|---|
| QGIS | **3.28 LTR → 4.x** |
| Python | 3.9+ |
| External dependencies | None — pure QGIS for all core operation |
| License | [GPL-3.0](LICENSE) |

```text
zero2cartolab/
  core/        # Symbology engines, 2.5D renderer helpers, math logic
  processing/  # QGIS Processing algorithms
  layout/      # Print Layout automation
  ui/          # Dashboard, 2.5D panel, feature inspector
  docs/        # GitHub Pages showcase (excluded from the Hub zip)
```

---

## 🇹🇷 Türkçe Özet

**0202CartoLab**, sıradan CBS katmanlarını **yayın kalitesinde analitik haritalara** dönüştüren bir QGIS eklentisidir:

- **2.5D bina stillemesi:** `Kat_Sayisi` gibi kat alanlarından yerli QGIS renderer ile ekstrüzyon; **kat başına renk bandı ve lejant satırı**, otomatik en yüksek kat tespiti, gölge/duvar gölgelemesi ve tek tıkla QML dışa aktarımı. Elden ele dolaşan kırılgan QML bloklarının kalıcı, yeniden kullanılabilir hâli.
- **İki değişkenli haritalar:** Bivariate koroplet (3×3 palet, özel köşe renkleri, eşkenar/dörtgen lejantlar) ve güvenilirliği saydamlıkla gösteren **Value-by-Alpha**.
- **Şehir verisine göre sınıflama:** Geometrik Aralık, Fisher-Jenks ve Head/Tail Breaks — çarpık dağılımlı kent göstergeleri için.
- **Kartogram ve sırt haritaları:** Değerle orantılı poligon bozulması; DEM/ısı/yoğunluk rasterlarından ridge-line haritalar.
- **Nokta ve yoğunluk haritaları:** Nokta-yoğunluk (dot-density), Flannery düzeltmeli orantılı semboller, altıgen (hexbin) toplama; ayrıca her zaman şeklin içinde kalan görsel-merkez etiket noktaları (polylabel) ve koordinat graticule'ü.
- **Doğru koroplet:** Tek adımda normalleştirme (kişi başına oran, z-skoru, dayanıklı MAD-z, yüzdelik, log) — nüfusu değil *oranı* haritalayın.
- **Otomatik sayfa düzeni:** Tek tıkla **Otomatik Harita Sayfası** — geçerli görünümden başlıklı harita çerçevesi, lejant, ölçek çubuğu, kuzey oku, koordinat ızgarası ve künye içeren tam bir baskı düzeni oluşturur ve Tasarımcı'da açar. Ayrıca **Düzen Yöneticisi** (aç, çoğalt, sil, PNG/PDF dışa aktar) ve dekoratörler: yerli bivariate lejantlar, izometrik katman istifi, tipografi hiyerarşisi.

Kurulum: QGIS → *Eklentiler → Eklentileri Yönet ve Kur* → **0202CartoLab** aratın. Pano: *Eklentiler → 0202CartoLab → 02CartoLab Dashboard*.

---

## 🧩 Part of the PlanX ecosystem

This plugin is one of 15 open-source QGIS plugins for urban planning by the same author:

| Planning & analysis | CAD & production | 3D & visualization |
|---|---|---|
| [PlanX](https://github.com/YusufEminoglu/PlanX) — spatial-planning suite | [PlanX CAD Toolset](https://github.com/YusufEminoglu/PlanX-CAD) — drafting-grade CAD | [PlanX 3D City](https://github.com/YusufEminoglu/planx_3d_city) — Three.js city viewer |
| [GeoStats Lab](https://github.com/YusufEminoglu/planx_geostats) — spatial statistics | [EasyFillet](https://github.com/YusufEminoglu/EasyFillet) — tangent-arc fillet | [3D OSM Model](https://github.com/YusufEminoglu/osm_3d_model) — OSM → 3D city in browser |
| [Suitability Lab](https://github.com/YusufEminoglu/planx_suitability_lab) — raster MCDA | [Settlement Toolset](https://github.com/YusufEminoglu/PlanX-Settlement) — 9-stage settlement plans | [OSM Quick 3D](https://github.com/YusufEminoglu/osm_quick_3d) — OSM → native QGIS 3D |
| [DataCube Lab](https://github.com/YusufEminoglu/planx_datacube) — spatiotemporal cubes | [UIP Toolset](https://github.com/YusufEminoglu/PlanX-UIP) — Turkish master-plan automation | [Urban Procedural 3D](https://github.com/YusufEminoglu/planx_urban_procedural_3d) — parametric zoning lab |
| [Urban Resilience](https://github.com/YusufEminoglu/planx_urban_resilience) — 28 resilience tools | [ParcelFlux](https://github.com/YusufEminoglu/parcelflux) — parcel subdivision | [02CartoLab](https://github.com/YusufEminoglu/zero2cartolab) — publication cartography |

---

## 🤝 Contributing & Support

- 🐛 **Bugs / requests** → [Issues](https://github.com/YusufEminoglu/zero2cartolab/issues)
- 📜 **Changelog** → [CHANGELOG.md](CHANGELOG.md) follows *Keep a Changelog*
- ✅ Before a PR: `py -3 tests/test_core.py` (headless, no QGIS required)

## 👤 Author

**Yusuf Eminoğlu** — urban planner & developer
Department of City and Regional Planning, Dokuz Eylül University
[GitHub](https://github.com/YusufEminoglu) · yusuf.eminoglu@deu.edu.tr

<div align="center">
<sub>Maps people pin to walls. If 02CartoLab elevates your output, a ⭐ helps others find it.</sub>
</div>
