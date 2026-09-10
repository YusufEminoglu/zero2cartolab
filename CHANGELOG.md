# Changelog - 02CartoLab

All notable changes to the **02CartoLab** plugin will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
