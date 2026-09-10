# Architecture

02CartoLab is QGIS-native and keeps print production independent from browser or
third-party chart runtimes.

```text
zero2cartolab/
  __init__.py
  main_plugin.py
  metadata.txt
  core/
  processing/
  layout/
    charts/
    designer_integration.py
    pixel_qa.py
  ui/
  docs/
```

## Core

The `core/` package contains reusable logic:

- `qgis_25d_style.py` builds and applies native 2.5D renderer configuration plus rule-based per-floor colour band renderers.
- `bivariate_engine.py` handles classification, colour matrices, and alpha calculations.
- `cartogram_engine.py` performs polygon distortion logic.
- `affine_matrix.py` supports isometric transformations.
- `html_graph_factory.py` generates self-contained HTML charts.

## Print layout

`layout/` owns the publication workflow: map-sheet construction, template and
grid galleries, decorators, preflight, atomic export, and the dock embedded in
the QGIS Print Layout Designer.

`layout/charts/` follows the proven zero2viz pipeline (data source -> transform
-> declarative specification -> renderer) but is an independent implementation.
It converts vector-layer attributes into editable native QGIS layout items. No
zero2viz installation, web view, JavaScript runtime, or external Python package
is required. Chart specifications and source-layer IDs are stored on the layout
group so graphs can be listed, edited, regenerated, and removed.

The optional `theme_adapter` discovers an active zero2viz instance through the
QGIS plugin registry and consumes its versioned, plain-data theme catalog. It
does not import zero2viz package internals. Theme snapshots are persisted in the
CartoLab chart specification, so disabling zero2viz never makes an existing
layout unreadable and built-in themes always remain available.

`layout/pixel_qa.py` validates the rendered result rather than only item
geometry. It measures ink coverage, colour diversity, content bounds, minimum
page-edge clearance, and ink entering a configurable safe margin. Structural
preflight remains separate so both model-level and output-level defects are
reported.

## Processing

The Processing provider exposes repeatable QGIS algorithms for symbology,
classification, cartograms, ridge maps, density/symbol maps, normalization,
label anchors, and reference grids. The provider is the authoritative runtime
catalog; documentation deliberately does not duplicate its algorithm IDs.

## UI

The dashboard is a QDialog-based production console. The Print Layout Designer
integration is a lifecycle-managed dock with compact, scrollable tabs for
templates, grids, decoration, export/preflight, and Add Graph. It does not
require external web services and keeps runtime dependencies inside QGIS and
PyQt.

## Validation

Pure-Python tests cover transformations, specifications, contrast rules, and
preflight logic. The QGIS E2E suite creates real layouts and exports every chart
family to PNG at 150 DPI on both supported runtimes. A Designer smoke test also
opens the real layout window and exercises dock attachment and teardown.

## Packaging

The plugin ZIP is built through the shared PlanX packaging scripts from the physical plugin root:

```powershell
.\packaging\Build-PluginZip.ps1 -PluginDir zero2cartolab
```

The `.zipignore` file excludes GitHub showcase files from the Plugin Hub ZIP.
