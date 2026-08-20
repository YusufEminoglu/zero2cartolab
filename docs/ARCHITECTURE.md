# Architecture

PlanX CartoLab is intentionally small and QGIS-native.

```text
planx_cartolab/
  __init__.py
  main_plugin.py
  metadata.txt
  core/
  processing/
  layout/
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

## Processing

The Processing provider exposes repeatable QGIS algorithms. The current provider includes:

- `planx_cartolab:building_25d_style`
- `planx_cartolab:bivariate_choropleth`
- `planx_cartolab:value_by_alpha`
- `planx_cartolab:ridge_map`
- `planx_cartolab:compute_cartogram`
- `planx_cartolab:geometric_interval_classification`

## UI

The dashboard is a QDialog-based production console. It does not require external web services and keeps runtime dependencies inside QGIS and PyQt.

## Packaging

The plugin ZIP is built through the shared PlanX packaging scripts from the physical plugin root:

```powershell
.\packaging\Build-PluginZip.ps1 -PluginDir planx_cartolab
```

The `.zipignore` file excludes GitHub showcase files from the Plugin Hub ZIP.
