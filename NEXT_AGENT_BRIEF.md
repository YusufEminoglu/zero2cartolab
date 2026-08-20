# 02CartoLab & PlanX CartoLab — Technical Handover & Future Roadmap

> **Author & Sole Contributor**: Yusuf Eminoğlu  
> **Repository**: [https://github.com/YusufEminoglu/zero2cartolab](https://github.com/YusufEminoglu/zero2cartolab)  
> **Documentation Portal**: [https://yusufeminoglu.github.io/zero2cartolab/](https://yusufeminoglu.github.io/zero2cartolab/)  
> **Reference Manual**: [https://yusufeminoglu.github.io/zero2cartolab/CARTOLAB_REFERENCE_MANUAL.html](https://yusufeminoglu.github.io/zero2cartolab/CARTOLAB_REFERENCE_MANUAL.html)  
> **Canonical Monorepo Rules**: [`AGENTS.md`](file:///C:/Users/YE/PyCharmMiscProject/qgis_plugins/AGENTS.md) (Rule 0: Absolute Yusuf Eminoğlu attribution, zero AI credits).

---

## 1. Executive System State & Architecture

`02CartoLab` (Python package: `zero2cartolab`) is a unified cartographic symbology and publication print layout automation studio for QGIS. It operates across two primary environments:

1. **Interactive Cartographic Studio (Dock & Dashboard)**:
   - **Symbology Studio**: Quick Style (Graduated/Categorized), 2.5D Architectural Building Extrusion with solar lighting, Advanced Thematic Suite (Bivariate 3×3/4×4 choropleths, Value-by-Alpha uncertainty maps, Continuous-Area Cartograms, Joyplot Ridge Maps, Dot-density, Flannery Proportional Symbols, Hexbin Aggregations), and Color/Accessibility Inspector (CVD simulation & WCAG 2.1 contrast scoring).
   - **Print Layout Automation**: Layout Template Gallery (Report Figure 16:9, Academic Journal A4, Exhibition Poster A2, Fact Sheet A4, Comparative Diptych), Custom Map Sheet Builder, 3D Isometric Layer Stacker, and embedded `02CartoLab Studio` dock inside QGIS Print Layout Designer.
2. **Headless Processing Provider (`zero2cartolab:*`)**:
   - 14 registered QGIS Processing algorithms callable via GUI dialogs, Graphical Modeler, and PyQGIS headless batch scripts.
   - Tested and verified 100% on both **QGIS 3.44 LTR** and **QGIS 4.2**.

---

## 2. Core Invariants & Guardrails (Mandatory for Incoming Agent)

| Invariant | Rule & Enforcement |
| :--- | :--- |
| **Rule 0 (Attribution)** | **No AI credits whatsoever**. Every commit, docstring, tag, and author field belongs solely to **Yusuf Eminoğlu**. Enforced by git hooks and `py -3 packaging/pf.py attribution`. |
| **Bandit B110 Security** | Never use `try: ... except: pass`. Always use `with contextlib.suppress(Exception):`. Bandit findings block QGIS Plugin Hub releases. |
| **Qt6 / QGIS 4 Compatibility** | Do not use bare `Qt.LeftButton`, `Qt.Key_*`, or deprecated Qt5 enums without forward-compat shims or safe getattr. |
| **Monorepo Registry** | [`plugins.toml`](file:///C:/Users/YE/PyCharmMiscProject/qgis_plugins/plugins.toml) is the single source of truth. Run `py -3 packaging/pf.py drift` to ensure 0 drift. |
| **Single Verification Command** | Always test with `py -3 packaging/pf.py verify zero2cartolab` before finalizing any release. |

---

## 3. High-Priority Bug Fixes & Edge-Case Refinements

### A. Non-Metric CRS Handling in Scalebars & Graticules
- **Current State**: Scalebar auto-calculation in `layout/layout_math.py` assumes projected map units (meters/feet).
- **Issue**: If the active map canvas is in geographic coordinates (e.g. `EPSG:4326` degrees), scale calculation must dynamically query ellipsoid geodesic distance (`QgsDistanceArea`) rather than Euclidean map units.
- **Task for Next Agent**:
  - In `layout/layout_math.py` and `layout/map_sheet.py`, inspect `map_item.crs()`. If `crs.isGeographic()`, compute scale using `QgsDistanceArea.measureLine()` between canvas corners to calculate true metric scalebar lengths.

### B. High-DPI & Multi-Monitor Layout Preview Rendering
- **Current State**: Visual template previews in the Dashboard and Layout Designer dock render at standard 96 DPI.
- **Task for Next Agent**:
  - Add device pixel ratio scaling (`devicePixelRatioF()`) to ensure crisp rendering of preview thumbnails and swatch gradients on 4K / Retina displays.

### C. Multi-Page Atlas Memory Management in Large Projects
- **Current State**: `layout/atlas_builder.py` sequentially renders pages.
- **Task for Next Agent**:
  - When exporting 50+ page atlas map books to PDF, ensure layer rendering cache is cleared between page iterations (`QgsMapSettings.clearCache()`) to avoid RAM bloat during batch export.

---

## 4. Advanced Algorithmic & Cartographic Enhancements

### 1. Dynamic 3D Terrain Draping & Analytical Hillshading
- **Objective**: Blend 2.5D building footprints with underlying DEM/DSM raster layers.
- **Implementation Path**:
  - In `core/sun_lighting.py` and `processing/alg_25d_style.py`, add optional raster DEM input.
  - Calculate terrain slope and aspect at building centroid to modulate base roof elevation and shadow skew angle dynamically.

### 2. Multi-Band Raster Bivariate Blending (Bivariate Raster Shader)
- **Objective**: Expand Bivariate Choropleth from vector polygons to dual continuous raster grids (e.g. Surface Temperature vs NDVI, Elevation vs Precipitation).
- **Implementation Path**:
  - Create new algorithm `processing/alg_bivariate_raster.py`.
  - Use NumPy 2D array histogram binning to generate an interpolated 3×3 or 4×4 RGBA raster layer.

### 3. Dorling & Non-Contiguous Circular Cartograms
- **Objective**: In addition to continuous Gastner-Newman diffusion cartograms (`core/cartogram_engine.py`), provide Dorling cartograms (graduated circles positioned via force-directed repulsion algorithms).
- **Implementation Path**:
  - Implement a 2D physics-based collision avoidance loop in `core/cartogram_engine.py` using spatial KD-tree indexing.

### 4. Origin-Destination (OD) Flow Map Router with Perceptual Bundling
- **Objective**: Automated desire lines and curved bezier flow arrows between geographic origins and destinations.
- **Implementation Path**:
  - Add algorithm `processing/alg_flow_map.py` with cubic Bezier curve generator and line weight modulated by flow volume.

---

## 5. Layout Automation & Publication Upgrades

### 1. Automated Map Book Table of Contents & Index Sheet
- **Objective**: Generate a clean introductory "Sheet 01: Table of Contents & District Grid Index" for atlas series.
- **Implementation Path**:
  - In `layout/atlas_builder.py`, generate a leading overview page featuring an interactive grid matrix with page numbers and district thumbnail insets.

### 2. Vector Hatching & Stipple Pattern Engine
- **Objective**: Support black-and-white academic printing with ISO-compliant cartographic patterns (diagonal stripes, crosshatch, stippling, dots) for colorblind/monochrome print resilience.
- **Implementation Path**:
  - Add pattern generator to `core/publication_styler.py` and integrate with `Quick Style` when "Monochrome Print Safe" is selected.

### 3. Preflight Layout Inspector & PDF/X CMYK Verification
- **Objective**: Pre-print automated diagnostics verifying:
  - Font embedding readiness.
  - Minimum line weight checks (e.g. hair lines < 0.25 pt warning).
  - Contrast ratios of annotation text over background map imagery.
  - Scalebar label precision and overlap detection.

---

## 6. Verification & Release Checklist for the Incoming Agent

When ready to commit and release:

```powershell
# 1. Run unit tests and both QGIS runtimes (LTR 3.44 + 4.2)
py -3 packaging/pf.py verify zero2cartolab

# 2. Check monorepo registry drift
py -3 packaging/pf.py drift

# 3. Check Rule 0 attribution compliance
py -3 packaging/pf.py attribution --offline

# 4. Build distribution zip
powershell -ExecutionPolicy Bypass -File packaging/Build-PluginZip.ps1 -PluginDir zero2cartolab

# 5. Push git commit and release tag
git push origin main --tags
```

---

*This document serves as the canonical technical brief for future engineering iterations on 02CartoLab.*
