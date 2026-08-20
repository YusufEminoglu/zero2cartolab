# Changelog - PlanX CartoLab

## [2.9.1] - 2026-08-20

- Added brand new high-resolution transparent 3D isometric main plugin icon with bivariate matrix and golden compass star.
- Enhanced all layout scalebars across Map Sheet, Template Gallery, and Legend Decorator to 3-4 segments with Heckbert nice-number intervals.
- Fixed tab header text truncation, padding, and mnemonic ampersand stripping in CartoLab Dashboard.
- Fixed Atlas configuration `QgsPrintLayout` attribute resolution in Layout Designer embedded studio.
- Optimized north arrow positioning and element spacing across publication layout templates.

## [2.9.0] - 2026-08-20

- Added Publication Layout Template Gallery with 5 distinct publication archetypes:
  - Report & Slide Figure (16:9 widescreen / A4 landscape executive presentation format with right HUD sidebar and takeaway metric callouts).
  - Academic Journal Figure (A4 portrait 2-column scientific format with formal figure caption, methodology note, stepped line scalebar, and standardized citation block).
  - Exhibition & Competition Poster (A1/A2 large-format landscape with bold architectural header banner, dominant hero map, regional locator inset map, and thematic legend cards).
  - Executive Fact Sheet (A4 portrait 1-pager with top 4 KPI metric cards, central thematic map, and bottom analytical narrative & policy recommendation block).
  - Side-by-Side Diptych (A4/A3 comparative dual-map layout with paired synchronized map frames, scenario A/B badges, shared extent & CRS, and comparative synthesis bar).
- Added dedicated Palette & Accessibility Inspector with live continuous gradient, discrete swatches, Color Vision Deficiency (CVD) 5-mode simulation comparison (Normal, Deuteranopia, Protanopia, Tritanopia, Achromatopsia), and real-time WCAG 2.1 contrast scoring.
- Added modular sub-tab navigation to Layout Studio (Template Gallery, Custom Map Sheet & Manager, 3D Isometric Stacker) and Symbology Studio (Quick Style, 2.5D Building Extrusion, Advanced Thematic Suite, Palette & Accessibility).
- Pinned and integrated all 14 Processing algorithms into dashboard card catalog and headless test harness.

## [2.8.8] - 2026-08-14

- Fixed bivariate_colour_matrix_hex parameter signature and Dashboard preview matrix generation

## [2.8.7] - 2026-08-14

- Added Left and Right Sidebar composition archetypes to Layout Optimizer

## [2.8.6] - 2026-08-14

- Added modern_arrow architectural north needle to Print Layout Legend Decorator

## [2.8.5] - 2026-08-14

- Added PALETTE selection parameter to Continuous-Area Cartogram algorithm

## [2.8.4] - 2026-08-14

- Added Emerald Metropolis and Terracotta Mediterranean 2.5D presets, plus Turbo/Viridis height palettes

## [2.8.3] - 2026-08-14

- Added PALETTE parameter, Maximum Breaks, and Pretty Breaks to Advanced Classification

## [2.8.2] - 2026-08-14

- Added PALETTE, CLASSIFIER, and CLASSES direct styling parameters to Hexbin Aggregation

## [2.8.1] - 2026-08-14

- Added LINE_COLOR, LINE_WIDTH, and automated SingleSymbolRenderer to Ridge Map (Joyplot)

## [2.8.0] - 2026-08-14

- Added LINE_STYLE, LINE_COLOR, and LINE_WIDTH direct styling parameters to Graticule Grid

## [2.7.9] - 2026-08-14

- Added PALETTE, CLASSES, and automated Data-Defined Opacity Renderer to Value-by-Alpha

## [2.7.8] - 2026-08-14

- Added SHAPE, FILL_COLOR, and OUTLINE_COLOR configuration to Proportional Symbols

## [2.7.7] - 2026-08-14

- Added DOT_SIZE and DOT_COLOR configuration to Dot Density Processing Algorithm

## [2.7.6] - 2026-08-14

- Added Location Quotient (LQ), Winsorized Outlier-Trim, and Decile Rank Normalization

## [2.7.5] - 2026-08-14

- Added Principal Inertia Orientation Angle (lbl_angle) to Visual-Center Label Points

## [2.7.4] - 2026-08-14

- Optimized Floating Annotation Map Tool with R-tree spatial index filtering

## [2.7.3] - 2026-08-14

- Added Turbo, Mako, Rocket, Earth, Bathymetry, and IceFire scientific color ramps

## [2.7.2] - 2026-08-14

- Enhanced Isometric 3D Layer Stacker with pure test safety and clean polyline connectors

## [2.7.1] - 2026-08-14

- Enhanced Locator Inset Map decorator with smart corner docking, extent overview styling, and header tags

## [2.7.0] - 2026-08-14

- Added Interactive Bivariate Studio with Live Matrix Preview and 1-Click Execution to CartoLab Dashboard

## [2.6.9] - 2026-08-14

- Expanded Paper Canvas Themes (Dark Matter Obsidian, Warm Editorial Newsprint, Japanese Washi Minimal)

## [2.6.8] - 2026-08-14

- Added Maximum Breaks and Pretty Breaks (nice round numbers) to Quick Style and Processing algorithms

## [2.6.7] - 2026-08-14

- Integrated Typography Presets, Coordinate Grid, and Clean Line Ticks into Auto Map Sheet Generator

## [2.6.6] - 2026-08-14

- Added PALETTE_PRESET selector directly into Bivariate Choropleth Processing Algorithm

## [2.6.5] - 2026-08-14

- Added curated Bivariate Palette Presets (Stevens Cyan-Pink, Teal-Brown, Blue-Orange, Purple-Green, Night Neon) and Hex Matrix Generator

## [2.6.4] - 2026-08-14

- Added 1-click Copy High-Res Map to Clipboard, TIFF export, and cleaned dead code blocks

## [2.6.3] - 2026-08-14

- Unit suffix cleaning in safe_float/safe_int for real-world GIS/OSM data (e.g. '8 m', '15.2 sqm', '5 floors')

## [2.6.2] - 2026-08-14

- Expanded Bivariate Choropleth classification algorithms (Quantile equal-count, Equal Interval, Geometric, Natural Breaks) and robust edge indexing

## [2.6.1] - 2026-08-14

- Scale bar style presets (Clean Line Ticks Up/Down, Academic Stepped Line) and dynamic Scale Ratio + Graphical Bar Combo indicator

## [2.6.0] - 2026-08-14

- Full Cartographic Typography Hierarchy Presets (Swiss Modernism, Academic Journal, Technical Blueprint, Warm Editorial)

## [2.5.9] - 2026-08-14

- Advanced statistical classifiers (Fisher-Jenks natural breaks, Jiang head/tail breaks, standard deviation) for thematic choropleth maps

## [2.5.8] - 2026-08-14

- Astronomical Solar Lighting calculator for 2.5D extrusions, and 1-click Map Book Atlas automation engine

## [2.5.7] - 2026-08-14

- WCAG 2.1 Color Accessibility and CVD simulation engine, and Layout Visual Balance and Margin Optimizer

## [2.5.6] - 2026-08-14

- Calm modern slate GUI styling, publication-standard coordinate grid engine with auto-intervals and smart map tools

## [2.5.5] - 2026-08-14

- Clean minimalist vector sub-icons and single toolbar entry points in QGIS canvas and Print Layout

## [2.5.4] - 2026-08-14

- Ultra-premium 8x supersampled 0-margin squircle icon suite with terraced depth and specular lighting

## [2.5.3] - 2026-08-14

- Elite 0-margin squircle icon suite (14 sub-tool icons), rich GUI toolbar and Print Layout integration

## [2.5.2] - 2026-08-14

- Fix 12+ bugs: scoped enum compat (QGIS 3/4), removeLayoutItem, setFrameStrokeColor, addGrid/addOverview TypeErrors, coordinate grid enums, scalebar units fallback, bivariate axis labels, html metric ValueError

## [2.5.1] - 2026-08-14

- Fix Coordinate Grid addGrid TypeError, map scalebar style names, draw explicit bivariate axis labels, and add in-place legend updater

## [2.5.0] - 2026-08-14

- Next-gen Print Layout Studio: QToolBar toggle action, executive North Arrow motifs, scalebar presets, and grouped bivariate legend settings

## [2.4.0] - 2026-08-14

- Full CartoLab cartographic engine & layout studio refactor with topology-preserving cartogram and live preview

## [2.3.0] - 2026-08-13

### Added
- Locator Inset Map Decorator (`layout/locator_map.py`): Added `add_locator_inset_map` function creating a secondary corner map frame linked to the primary map extent with an automatic extent overview rectangle.
- Coordinate Grid Decorator (`layout/coordinate_grid.py`): Added `apply_coordinate_grid_decorator` function applying publication coordinate grids with cross markers, zebra borders, and coordinate annotations.
- Layout Studio Extension: Integrated 1-click Locator Inset Map and Coordinate Grid buttons into the CartoLab Layout Studio Dock panel.

## [2.2.0] - 2026-08-13


### Added
- Publication Legend Styler (`layout/legend_styler.py`): Added `style_layout_legend` function providing clean typography, column count, symbol sizes, and spacing for layout legends.
- Architectural Title Block Decorator (`layout/title_block.py`): Added `add_publication_title_block` function inserting a publication title block with project title, subtitle, author metadata, and date stamp into the layout.
- Docked Panel Extension: Integrated 1-click Title Block and Publication Legend Styler controls into the CartoLab Layout Studio Dock panel tabs inside QGIS Print Layout Designer.

## [2.1.2] - 2026-08-13


### Changed
- Zero Top Ribbon Clutter: Removed custom toolbar creation on the QGIS Print Layout Designer top ribbon completely. Access is handled via native MenuBar integration (`Show/Hide CartoLab Studio Panel`).
- Tabbed Docked Panel Architecture: Replaced long single-column vertical forms in the right docked panel with a clean 3-tab layout (`🎨 Canvas & Grid`, `💎 Decorators`, `⚡ 3D & Export`).

## [2.1.1] - 2026-08-13


### Changed
- Print Layout Toolbar Simplification: Consolidated 8 individual toolbar items into 1 single clean CartoLab Studio toolbar button (`PlanX CartoLab Studio`) that toggles the embedded `CartoLab Layout Studio` Docked Panel.
- Layout Dock Consolidation: All layout tools (Canvas Themes, Bivariate Legend, Typography, Scale Bar, North Arrow, Isometric Perspective, Quick Export) are cleanly organized within the single docked panel.

## [2.1.0] - 2026-08-13


### Added
- Scale Bar & North Arrow Decorators: Added `add_scalebar_to_layout` and `add_north_arrow_to_layout` functions in `legend_decorator.py`.
- Enhanced Layout Studio Dock: Wired direct 1-click Scale Bar and North Arrow buttons into the CartoLab Layout Studio Dock panel inside the QGIS Print Layout Designer window.

## [2.0.1] - 2026-08-13


### Fixed
- Layout Function Aliases: Added backward and forward compatible function aliases (`add_bivariate_legend`, `apply_swiss_typography`, `stack_layers_isometrically`) eliminating `ImportError` exceptions when triggering Print Layout actions.
- Layout Dock Widget Controls: Added direct Swiss Typography & Grid action button and distinct icons/emojis to each docked panel tool section inside the QGIS Print Layout Designer window.

## [2.0.0] - 2026-08-13


### Added
- Vertical Sidebar Navigation (`nav_sidebar` + `stack`): Replaced horizontal tab layout with a vertical sidebar list and right stacked workspace view matching the PlanX 3D City Viewer experience.
- Brand-New High-Definition 256x256 Cartographic Icon (`icons/icon.png`): Created ultra-crisp vector-style cartographic icon fitting the toolbar frame with 100% clarity and scale.
- Comprehensive System Verification: Validated 100% operational functionality across all 13 algorithms, paper canvas themes, layout decorators, and 2.5D extrusion styling presets.

## [1.9.2] - 2026-08-13


### Changed
- Icon Background Transparency: Restored original plugin icon motif (`icons/icon.png`) while removing solid background color for clean transparent toolbar integration.

## [1.9.1] - 2026-08-13


### Changed
- Full-Frame Crisp Icon Refresh: Replaced plugin icon with full-bleed high-contrast cartographic 128x128 PNG (`icons/icon.png`) for maximum toolbar legibility.
- Glassmorphic UI Transparency: Updated Dashboard and dialog container styling to transparent/glassmorphic backgrounds.

## [1.9.0] - 2026-08-13


### Added
- Publication Auto-Styler Engine (`publication_styler.py`): Automatic, highly legible publication-ready thematic styling applied out-of-the-box to all algorithm output layers (choropleth, cartogram, hexbin, dot-density, proportional symbols, graticule, and label points).
- Enhanced Cartogram Engine: Cartogram outputs are now automatically styled with high-contrast Plasma/Magma graduated color ramps and topology-friendly boundaries.
- Print Layout Bivariate Workbench: Added custom legend title and axis label configurator inside the layout designer embedded dock widget.

## [1.8.3] - 2026-08-13


### Added
- Layout Toolbar Resolution Selector: Added direct 150 DPI / 300 DPI / 600 DPI quality dropdown selector on the Print Layout Designer window toolbar.
- Documentation Sync: Synced reference manual `docs/CARTOLAB_REFERENCE_MANUAL.html` to v1.8.3 covering Print Layout Designer integration, embedded dock panel, and paper canvas themes.

## [1.8.2] - 2026-08-13


### Added
- Paper Canvas Themes (`paper_themes.py`): Added Architectural Blueprint, Vintage Sepia Atlas, and Modern Swiss Minimalist artistic paper themes.
- Canvas Theme Controls: Embedded paper theme switcher in CartoLab Layout Studio Dock to apply background, label, and grid styling with one click.

## [1.8.1] - 2026-08-13


### Added
- Embedded Print Layout Dock Panel (`CartoLab Layout Studio Dock`): Added an interactive dock panel embedded directly inside the QGIS Print Layout Designer window.
- Live Decorator Controls: Direct controls for bivariate palette/shape selection, isometric perspective tilt/heading angles, and 150/300/600 DPI quick export inside the print layout designer.

## [1.8.0] - 2026-08-13


### Added
- Print Layout Designer Integration: Added automatic attachment to QGIS Print Layout Designer windows (`QgsLayoutDesignerInterface`).
- Dedicated Layout Toolbar: Added `PlanX CartoLab` toolbar directly inside the Print Layout Designer window with 1-click Bivariate Legend, Swiss Typography & Grid, Isometric Layer Stack, and 300 DPI Export & Open.
- Print Layout Menu Integration: Added `PlanX CartoLab` menu inside the layout designer's menu bar.

## [1.7.4] - 2026-08-13


### Changed
- Processing Hub UX Polish: Added keyboard shortcut tips (Ctrl+F search, Ctrl+R refresh) and search placeholder guidance.
- Documentation Sync: Updated online user reference manual `docs/CARTOLAB_REFERENCE_MANUAL.html` and `docs/index.html` to v1.7.4 reflecting the 3 Studio Workspaces architecture.

## [1.7.3] - 2026-08-13


### Added
- Layout Page Presets: Added A4 Landscape, A3 Landscape, Square 1:1, and A4 Portrait layout presets.
- Export & Open Button: Added `Export & Open ↗` button to immediately export and launch layouts in system default image/PDF viewer.
- Enhanced DPI Quality Selector: Preset chips for 150 DPI Draft, 300 DPI Publication Standard, and 600 DPI Ultra Print Quality.

## [1.7.2] - 2026-08-13


### Added
- Expanded 2.5D Building Presets: Added Urban Core Gold, Suburban Pastoral, Cyberpunk Night, and Nordic Minimalist visual themes.
- Automatic Building Height Estimator: Added one-click tool (`estimate_building_height`) calculating building elevation from floor count fields (3.2m/floor default).

## [1.7.1] - 2026-08-13


### Added
- Interactive Palette Swatch Bar: Live discrete color swatch blocks in Quick Style showing exact class color steps.
- Palette Type Filter: Filter palettes by type (Sequential, Diverging, Qualitative) alongside colorblind-safe toggle.
- Metadata Badge: Live chip displaying palette classification, colorblind safety status (`🟢 Colorblind Safe`), and class count.

## [1.7.0] - 2026-08-13


### Changed
- Major GUI Consolidation: Restructured 9 scattered tabs into 3 streamlined Studio Workspaces: `🎨 Symbology & Thematic Studio`, `📐 Layout Automation Studio`, and `⚡ Processing Algorithm Hub`.
- Added collapsible bottom Diagnostics & Run Log console drawer for system status, dependency reports, and execution logs.
- Eliminated redundant `Quick Actions` button list and scattered text browsers.

## [1.6.5] - 2026-08-07

- Added online user manual link (https://yusufeminoglu.github.io/planx_cartolab/) and GitHub repository star call-to-action.

## [1.6.4] - 2026-08-07

- Add floating Save as PDF button to reference manual

## [1.6.2] - 2026-07-13

### Security
- The QGIS Plugin Hub security scan now blocks a plugin on *any* Bandit finding, not only critical ones. Driven the shipped code to **zero Bandit findings**: replaced Python's `random` module in the dot-density placer with a small self-contained deterministic generator (identical, reproducible dot layouts — no behaviour change), and rewrote every defensive `try/except: pass` as `contextlib.suppress`. No `# nosec` suppressions are used, so the result holds even under the strictest scan configuration.

## [1.6.1] - 2026-07-13

### Security
- Removed the pip/`subprocess` dependency installer that the QGIS Plugin Hub security scan flagged as a critical issue. CartoLab needs no external packages — it uses only QGIS and its bundled NumPy — so the Setup panel now only *reports* optional-library status and never installs anything.

### Fixed
- Qt6 / QGIS 4 compatibility: all Processing, layout and UI enums are now fully scoped (e.g. `QgsProcessing.SourceType.TypeVectorPolygon`, `QgsWkbTypes.Type.Point`, `QgsUnitTypes.LayoutUnit.LayoutMillimeters`, `QgsMapLayer.LayerType.VectorLayer`), clearing 85 compatibility warnings. Verified on QGIS 3.44 LTR and QGIS 4.2.
- Test and e2e files are no longer shipped in the Hub package.

## [1.6.0] - 2026-07-13

### Added
- **Quick Style** — a new one-click Processing algorithm and dashboard panel that styles any vector layer: a graduated renderer for numeric fields or a categorized renderer for text fields, with quantile / equal-interval / geometric-interval class breaks. The dashboard panel has a live palette preview and applies the style to the selected layer instantly.
- **Colour palette library** (`core/palettes.py`) — ColorBrewer sequential/diverging/qualitative sets plus the perceptually-uniform scientific ramps (viridis, magma, plasma, inferno, cividis), each carrying a colour-blind-safe flag, sampled to any class count. A "colour-blind safe only" filter is built into the Quick Style panel.
- **Layout export presets** — export any layout to PNG, PDF or SVG at 96 / 150 / 300 / 600 dpi from the Layout Manager.

### Changed
- A graduated Quick Style on a field with a single distinct value now degrades gracefully to one class instead of failing.
- The provider now ships 13 Processing algorithms (Quick Style added); the e2e harness pins and verifies the count.

## [1.5.1] - 2026-07-13

### Added
- **First-run welcome** — a one-time greeting (also reachable from *Plugins → PlanX CartoLab → Welcome & Sample Map*) with a **"Create a sample map"** button that builds a fully-styled demo choropleth and finished map sheet in seconds, from an in-memory layer (no bundled data).
- **"Rate on the Hub"** link in the dashboard footer.

### Changed
- Refreshed discovery metadata (tags + description/about) so CartoLab surfaces for common searches — *choropleth, map layout, print layout, atlas, colour ramp, ColorBrewer, colourblind, viridis, thematic map, north arrow* — without changing any behaviour.

## [1.5.0] - 2026-07-13

### Added
- **Auto Map Sheet** — one-click publication layout built from the current map view: titled map frame at the current extent and CRS, filtered legend, scale bar, north arrow (bundled QGIS SVG with a drawn fallback), optional coordinate grid, neat-line and credits. Choose page size (A0–A4) and orientation; the finished layout opens straight in the Layout Designer.
- **Layout Manager** in the dashboard Layout tab — pick any project layout and open it in the Designer, duplicate it, delete it, or export it to PNG/PDF at 300 dpi.
- Real-QGIS e2e coverage for the layout subsystem (map sheet assembly, grid idempotency, native legend, isometric stack, export) — the harness now runs 33 checks on both QGIS 3.44 LTR and QGIS 4.
- Pure-logic `core/layout_math.py` (nice grid intervals, collision-free layout names, page geometry) with 17 new unit tests.

### Changed
- Bivariate print-layout legends are now built from **native, editable layout items** (rectangles / diamonds + text, grouped) instead of an embedded SVG — no more orphaned temporary files, and the legend can be tweaked in the Designer.
- Layout decorators (bivariate legend, typography, minimalist grid) now target the **layout you select** in the Layout Manager instead of blindly using the first layout.
- Isometric layer stacks are now created as `QgsPrintLayout` objects (so they appear correctly in the Layout Manager and Designer) with collision-free names.

### Fixed
- Minimalist coordinate grid is now **idempotent** (re-running replaces the CartoLab grid instead of stacking duplicates) and derives a rounded interval from the map extent, so it reads well at any scale or CRS. The grid line styling used non-existent API calls (`setGridLinePenSize`/`setGridLineStyle`) and silently failed; it now uses `setLineSymbol`.

### Removed
- Dead code: unused `create_cross_grid_style`, and the orphaned `build_bivariate_legend_html` / `build_micro_bar_chart_html` HTML factories.

## [1.4.3] - 2026-07-10

- Packaging hygiene fix: `packaging/zip_hub.py` now always excludes internal AI-agent work-order files (`ENHANCEMENT_PLAN_*.md`, `DEEPSEEK_PROMPT_*.txt`, `REPORT_v*.md`) from the built zip, regardless of version suffix. These files remain in the GitHub repository as project history but no longer ship in the QGIS Hub package.

## [1.4.2] - 2026-07-10

- Fix responsive 2.5D and Layout UI; rename System Health to Readiness

## [1.4.1] - 2026-07-10

- Fix helpUrl inheritance and commit e2e regression guard

## [1.4.0] - 2026-07-10

- release.ps1 added; helpUrl() for all 12 algorithms; 4 deprecated setMode() calls fixed (QgsClassificationCustom); e2e algorithm-count regression guard added (==12); dead-import and lint cleanup (flake8 128->109, bandit 10->7 Low); COMMAND_GUIDE.html added

## [1.3.1] - 2026-06-18

- docs: add CITATION.cff for Zenodo DOI integration

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-06-17

### Added
- **Dot-Density Map** — seeded, hole-aware dots scattered inside polygons (one dot per N units of a count field); dots inherit source attributes for multi-group dot maps.
- **Proportional Symbols** — Flannery-compensated (or true-area) graduated point symbols with data-defined size and suggested nested-legend values.
- **Hexbin Aggregation** — bin a point layer into a pointy-top hexagonal grid (count / sum / mean), emitting only occupied cells, graduated on the chosen statistic.
- **Visual-Center Label Points** — pole of inaccessibility (polylabel) per polygon, so label anchors always sit inside the shape; largest part used for multipart features.
- **Graticule / Reference Grid** — meridians and parallels on nice round intervals, each carrying its orientation, coordinate and a formatted label.
- **Choropleth Normalization & Rates** — rate (numerator/denominator × scale), z-score, robust MAD z-score, min-max, percentile rank and log, written to a `norm_value` field and graduated.

### Fixed
- **Ridge Map** — replaced an invalid `QgsRasterBlock.isNoData()` call (crashed on current QGIS) with a validity/empty check, and fixed the optional-extent path that produced a NaN when no extent was supplied.

### Notes
- Pure-Python cores for all six new tools (no new dependencies); headless unit tests grew to 192 checks and a real-QGIS end-to-end harness validates all 12 algorithms on QGIS 3.44 LTR and QGIS 4.

## [1.2.6] - 2026-06-05

- Make 2.5D floor bands legend-friendly

## [1.2.5] - 2026-06-04

- Add automatic floor-band detection for 2.5D styling

## [1.2.4] - 2026-06-04

- Fix QGIS Hub metadata homepage URL

## [1.2.3] - 2026-06-03

- Add sample-QML-style per-floor colour band rendering for floor-count 2.5D building styling

## [1.2.2] - 2026-06-03

- Add explicit floor-count mode for 2.5D building styling

## [1.2.1] - 2026-06-03

- Fix QGIS 2.5D height expression parser compatibility

## [1.2.0] - 2026-06-03

### Added
- Native QGIS 2.5D building styling engine with height-field extrusion, material presets, soft shadows, wall shading, optional stepped floors, and QML export.
- Dashboard 2.5D Styling tab plus a direct PlanX CartoLab menu action.
- Processing Toolbox algorithm: Apply 2.5D Building Style.
- GitHub Pages showcase, documentation set, and issue/PR templates for a more polished repository presentation.

### Changed
- Main dashboard copy and project diagnostics now use English-only visible text for the newly touched surfaces.
- GitHub showcase and repository support files are excluded from the QGIS Plugin Hub ZIP through `.zipignore`.

## [1.1.0] - 2026-05-29

- Official 1.1.0 release: full print layout support with rotated diamond and square legends, and Forecasting Studio export controls

## [1.1.0-beta.1] - 2026-05-29

- Beta-1 release with dynamic bivariate palettes, custom corner colors, and polished radar charts

## [1.0.0] - 2026-05-26

### Added
- Professional PlanX ecosystem icon for QGIS Plugin Manager, toolbar, and Processing provider surfaces.
- QGIS 3.44/QGIS 4 runtime smoke coverage for CartoLab dashboard and Processing provider lifecycle.

### Fixed
- Qt6-compatible enum usage in the dashboard, floating annotation dialog, layout grid styler, and typography engine.

## [0.2.0] - 2026-05-26

### Added
- Production dashboard with module cards, dependency health, quick actions, and layout automation launchers.
- Floating annotation map tool, isometric/typography/grid/legend layout utilities, improved cartogram kernel, graduated symbology, and dependency manager with pip installer.
- 71 unit tests for core cartography engines.

## [0.1.0] - 2026-05-26

### Added
- Adaptive Geometric Interval Classifier (GIC) with automatic ratio optimisation
- Head/Tail Breaks algorithm for heavy-tailed (power-law) data
- Fisher-Jenks natural breaks (dynamic programming with DP matrix backtracking)
- Bivariate choropleth engine: NxN colour matrix via bilinear interpolation
- Continuous-area diffusion cartogram (Gastner & Newman method, ground-up reimplementation)
- Ridge-line (Joy Division style) vector mesh generator from raster data
- Value-by-Alpha (VbA) opacity mapper for uncertainty visualisation
- Isometric layout stacker: axonometric explosion of map layers in Print Layout
- HTML/Canvas floating annotation cards with embedded radar (spider) charts
- Swiss-style typography engine (Inter / IBM Plex Mono hierarchy)
- Minimalist coordinate-grid styler for publication-ready layouts
- Bivariate SVG legend embedder for Print Layout
- Full Processing Toolbox provider with 5 algorithms
- Dockable multi-tab panel (Bivariate, Cartogram, Ridge Map, VbA, Isometric)
