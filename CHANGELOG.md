# Changelog - 02CartoLab

All notable changes to the **02CartoLab** plugin will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
