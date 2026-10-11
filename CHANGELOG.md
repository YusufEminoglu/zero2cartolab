# Changelog - 02CartoLab

All notable changes to the **02CartoLab** plugin will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.0] - 2026-10-11

A full audit release: every finding below was reproduced first, then fixed
with a regression test.

### Fixed

- **QGIS 3.28 (the declared minimum) works again.** Auto Map Sheet and the
  Welcome sample map crashed (`QgsLegendStyle.textFormat` is 3.30+), every
  template had an empty map frame and a NaN scale (`zoomToExtent` on a new
  map item), 2.5D wall shading and Bivariate Matrix Export used 3.30/3.36
  enums, and template legend styling was silently skipped.
- **Cartographic math:**
  - Ridge maps read the raster transposed and past the block, flipped the
    scanlines and drew NoData as spikes.
  - Fisher-Jenks could drop the maximum from its sample and class it as
    lowest; its breaks were one value off. Breaks are now each class's upper
    bound, and Value-by-Alpha and bivariate use the same lo < v <= hi rule
    as QGIS ranges.
  - Bivariate custom corner colours were swapped. Presets were swapped with
    them, so maps look as before; the legend now matches the map.
  - Standard-deviation breaks were asymmetric for 7+ classes; class labels
    were wrong for anything but 5 classes.
  - Colour-blindness simulation is now Machado et al. (2009) in linear RGB,
    as documented.
- **Data handling:** re-running an algorithm on its own output kept the old
  values; NULL features were dropped by classification and bivariate,
  counted as 0 by Value-by-Alpha and diluted hexbin means; dot density
  placed too few dots in multipart polygons without saying so; cartograms
  crashed on cancel and on a single feature; percentile normalisation was
  quadratic.
- **Layouts:**
  - Long legends overflowed the map-sheet sidebar where Qt substitutes a
    wider font; the legend is now measured with QGIS's own renderer and
    shrunk or word-wrapped until it fits.
  - Style Legend renamed the project's layers, not just legend labels.
  - Scale bars, grids, scale text and Snap Scale attached to the locator
    inset instead of the main map.
  - Copy to Clipboard always failed; multi-page PNG/SVG exports left temp
    files and lost pages 2+; export failures are now reported.
  - Map sheets with a grid never got one; UTM and emergency templates put
    grid labels off the page; the bivariate legend drifted on every update;
    the isometric stack ignored its tilt, hid labels and clipped data; atlas
    setup overlapped titles and reported success with no pages; the QPT
    inspector mislabelled item types; subtitles were styled as titles;
    Auto-Balance left overlaps; the scale text did not follow the map.
- **Dashboard and plugin:**
  - Quick Style ran a different break method than the one chosen.
  - Unloading left the dashboard alive and each reload added another
    Layout Designer menu.
  - The Feature Inspector missed features in layers with a different CRS and
    picked hidden layers.
  - Sun angles used a fixed latitude and put the sun's height into the
    projection angle.
  - Non-spatial tables were offered for styling; the palette choice was lost
    on rebuild; the overview page was overwritten; Auto-Detect Floor Count
    detected nothing.

### Changed

- Documentation corrected: 16 Processing algorithms (not 21 or 14), 10
  layout templates (not 5), the 02CartoLab Studio menu entry, 150/300/600
  dpi export, no NumPy, and links to each PlanX plugin's own repository.

### Testing

- CI runs the core suite (601 tests) and, in the official QGIS 3.28, 3.34,
  3.44 and 4.2 images, an API check of every QGIS/Qt name the plugin uses,
  the Designer and dashboard smoke tests, and the end-to-end suite (356
  checks).

## [1.4.0] - 2026-09-29

### Added

- **Origin-Destination Flow Map** (`flow_map`): curved, arrowed desire lines
  from any OD layer or table, including a CSV without geometry. Repeated pairs
  are summed, self-flows dropped, and ids match as text (7, 7.0 and "7" are one
  zone); unmatched ids are reported. Curves bend to the right of travel, so
  A→B and B→A are two separate arcs. Width is linear in volume, colour classes
  are quantiles, large flows are drawn underneath small ones, and end gaps are
  measured along the curve. Two-way mode, minimum-volume and top-N filters.
- **Dorling Circle Cartogram** (`dorling_cartogram`): circles with area
  proportional to a value, separated until none overlap while a fading pull
  keeps them near home. Neighbour search on a median-radius hash grid keeps
  5,000 units at about 9 s; residual overlap is reported (< 0.5% of the mean
  radius by default) and the run is cancellable.
- **Monochrome print-safe patterns** in Quick Style (Processing and dashboard):
  polygon classes get black-and-white hatch and dot fills instead of colours.
  Graduated ramps darken strictly with the value (ink coverage is computed and
  tested); categories differ by texture and orientation (16 before a repeat).
- Reference manual sections 20 and 21, and a Quick Style section on the
  monochrome ramp.

### Fixed

- **Output symbology was lost for file outputs.** Ten algorithms styled their
  result inside `processAlgorithm`, which only reaches the project for
  temporary layers; a GeoPackage or Shapefile output arrived as a plain single
  symbol. Styling now also runs as a layer post-processor on whatever layer
  QGIS loads.
- **Bivariate Choropleth output was never styled**, not even as a temporary
  layer: its post-processor was garbage-collected before the layer loaded.
- The cartogram declared a Polygon sink but wrote MultiPolygons, producing a
  non-conformant GeoPackage; the sink is now multi-polygon.

## [1.3.3] - 2026-09-11

### Fixed

- Remove the QGIS-generated style database from version control and explicitly
  exclude it from Hub ZIP assembly.

## [1.3.2] - 2026-09-11

### Fixed

- Exclude the transient QGIS `symbology-style.db` test artefact from source and
  release packages.

## [1.3.1] - 2026-09-11

### Fixed

- Centre the north notation `N` and arrow on the same measured layout axis
  instead of using a font-dependent hard-coded offset.
- Auto-fit map-sheet legend typography, symbols, and spacing against the real
  sidebar width and height after publication themes are applied, preventing
  long layer/category labels from overflowing their allocated area.
- Add live 150 DPI long-label legend stress output and north-axis geometry
  regression checks on QGIS 3.44 and QGIS 4.2.

## [1.3.0] - 2026-09-10

### Added

- Add optional 02viz theme discovery to the Print Layout Designer. When 02viz
  is active, Add Graph gains its Studio Light, Ink Dark, Soft Pastel, and Bold
  Print palettes, surfaces, typography, and stroke presets; built-in themes
  remain available when 02viz is absent or disabled.
- Persist the theme provider, theme ID, font family, title/label sizes, and line
  width in every native chart specification so layouts remain reproducible
  without a runtime dependency on 02viz.

## [1.2.1] - 2026-09-10

### Fixed

- Resolve the two Flake8 E731 findings in the native chart renderer.
- Use Qt6-scoped Processing enums and compatibility-safe layout shape lookup so
  the Plugin Hub compatibility report is clean without dropping QGIS 3 support.

## [1.2.0] - 2026-09-10

### Added

- Added an independent native Print Layout chart engine, architecturally adapted
  from 02viz's data-source, transform, specification, and renderer separation.
  Bar, grouped/stacked bar, line, multi-series line, area, numeric scatter,
  pie, donut, and histogram charts can be
  built from vector-layer fields without a web view or optional dependency.
- Added an **Add Graph** workspace directly inside the Print Layout Designer,
  including aggregation, Top-N, title, frame size, automatic corner placement,
  custom millimetre coordinates, and complete chart removal.
- Added weighted least-overlap placement and persistent chart specifications;
  reopened layouts restore their chart list and settings for replacement edits.
- Added export-driven Pixel QA in the Designer: real 150 DPI raster inspection
  detects blank output, unsafe edge ink, low colour diversity, rendered content
  bounds, and minimum physical margins.
- Added chart palette and surface presets, live WCAG contrast feedback, value and
  legend switches, histogram bin control, and configurable print-safe margins.
- Added physical 150 DPI output coverage for every chart type on both QGIS 3.44
  and QGIS 4.2, plus page-boundary, native-item, preflight, and cleanup checks.

### Changed

- Expanded Print Preflight with coordinate-grid density/interval, scale-bar
  segment/width, legend size, north-arrow, and chart safe-margin checks.
- Made every Designer workspace vertically scrollable, removed horizontal form
  overflow, and compacted the tab/form hierarchy for narrow layout docks.
- Native charts are grouped so they can be selected and moved as one editable
  Designer object while remaining vector output in PDF and SVG.
- Constrained auto-sized map-sheet legends to their allocated sidebar.

### Fixed

- Made Layout Designer integration retry until newly opened QGIS windows are
  ready, support both QGIS window APIs, avoid duplicate docks after reload, and
  disconnect/remove its UI cleanly when the plugin unloads.

## [1.1.0] - 2026-09-06

### Fixed

- Made automatic scale bars geodesic for geographic CRS maps, unit-aware for
  projected maps, and physically fit their allotted layout space using readable
  metre or kilometre segments.
- Resolved template CRS and combined extents from their actual layers, including
  coordinate transformation for mixed-CRS inputs, instead of inheriting an empty
  headless project CRS.
- Made the Square map-sheet option create a genuinely square page.
- Corrected atlas filtering and sorting, which previously used a nonexistent QGIS
  sort method and could silently leave sorting disabled.
- Made repeated locator and atlas decoration idempotent, preventing duplicate
  generated furniture.
- Preserved map extent during layout optimization, recognized drawn north arrows,
  and constrained oversized legends.
- Made PNG, PDF, and SVG export atomic so a failed render cannot destroy an
  existing destination file.
- Corrected projected coordinate-grid detection for small extents and made grid
  annotation precision CRS-aware.
- Moved the Fact Sheet scale bar into a dedicated footer and tightened Report,
  Poster, Academic, and Diptych furniture sizing after live visual QA.
- Fixed a bare Qt cursor enum that crashed Dashboard construction on QGIS 4.
- Added dependency-aware QPT inspection that blocks unsafe Designer import when
  templates call unavailable external expression functions.
- Made sparse Value-by-Alpha inputs tolerate null and non-numeric reliability
  values consistently with larger datasets.
- Made the QGIS end-to-end harness portable and restored its missing exception
  suppression import.
- Corrected stale product naming, documentation links, branch names, and
  algorithm counts.

### Changed

- Added non-mutating Print Preflight actions to the Dashboard and Layout Designer
  dock, reporting duplicate IDs, page overflow, empty/tiny frames, broken map
  links, and other publication blockers.
- Added stable item IDs across templates, map sheets, title blocks, locator maps,
  legends, scale bars, and atlas furniture for reliable editing and automation.
- Expanded the gallery from 5 to 10 complete layouts with UTM Field Sheet,
  Planning Review Board, Spatial Data Story, Atlas Production Sheet, and
  Emergency Operations Brief workflows.
- Added 7 idempotent grid compositions: Minimal, UTM Engineering, layered UTM
  Field, Survey Crosshair, Marginal Ticks, WGS 84 Graticule, and dual UTM plus
  geographic reference.
- Added a full Grid and QPT Studio with automatic/manual intervals, annotation
  and replacement controls, QPT structural reports, guarded import, and one-click
  dependency-free UTM migration.
- Removed unused imports, variables, and a no-op compatibility branch from the
  shipped plugin and test harness.
- Added QGIS 3/4 live regression and screenshot coverage for all ten publication
  archetypes, preflight, layer CRS resolution, scale semantics, atlas behavior,
  geographic scale sizing, and sparse Value-by-Alpha null handling.

## [1.0.1] - 2026-08-21

### Fixed

- Fixed Isometric Layer Stacker resolving selected layers by non-unique display
  names. Selections now carry stable QGIS layer IDs, preserve the user's order,
  ignore stale/duplicate IDs, and never pull in an unselected same-name layer.
- Corrected the stale `CITATION.cff` release version and date.

### Changed

- Replaced the main plugin icon with a new text-free cartographic studio mark:
  four interlocking thematic-map tiles, contour lines and a bivariate matrix,
  with a transparent background and zero-margin `512 x 512` alpha bounds.

## [1.0.0] - 2026-08-20

### Initial Release
- **Unified Cartographic Studio & Print Layout Automation for QGIS**:
  - **Publication Layout Template Gallery**: 5 distinct publication archetypes (Report Figure 16:9, Academic Journal A4, Exhibition Poster A2, Fact Sheet A4, Comparative Diptych).
  - **Thematic Symbology Studio**: Bivariate Choropleths (3x3 and 4x4 matrices), Value-by-Alpha uncertainty maps, Continuous-Area Cartograms (Gastner-Newman), Joyplot Ridge Maps, Hole-aware Dot-Density, and Flannery Proportional Symbols.
  - **Architectural 2.5D Building Extrusion**: Oblique massing with solar angle lighting presets and stepped floor bands.
  - **Layout Designer Studio Dock**: Multi-segment Heckbert scalebars, modern north needles, automated coordinate graticules, and multi-page Map Book Atlas engine.
  - **Palette & Accessibility Inspector**: 5-mode Color Vision Deficiency (CVD) simulation (Normal, Deuteranopia, Protanopia, Tritanopia, Achromatopsia) and real-time WCAG 2.1 AAA contrast evaluation.
  - **14 Headless Processing Algorithms**: Modeler-ready, scriptable spatial pipeline algorithms.
  - **Zero External Dependencies**: Pure Python, NumPy, and QGIS core engine compatible with QGIS 3.28+ LTR and QGIS 4.x.
