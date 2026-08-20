# PlanX CartoLab Documentation

PlanX CartoLab is a QGIS-native cartography suite for analytical urban planning maps.

## Start Here

- [GitHub Pages showcase](index.html)
- [Feature showcase](SHOWCASE.md)
- [Architecture](ARCHITECTURE.md)
- [Publishing notes](PUBLISHING.md)

## Main Plugin Surfaces

| Surface | Purpose |
|---------|---------|
| CartoLab Dashboard | Central module launcher, system health, layout tools, and 2.5D styling panel. |
| 2.5D Styling Panel | Native QGIS building extrusion workflow plus per-floor colour bands, legend-friendly rules, material presets, and QML export. |
| Processing Toolbox | Repeatable algorithm execution inside QGIS models and batch workflows. |
| Floating Inspector | Click a feature to inspect numeric attributes through a compact radar chart. |

## Recommended Test Data

Use polygon layers with numeric height fields for 2.5D styling. Good candidate field names include:

- `Hmax`
- `Height`
- `Heights`
- `building_height`
- `Kat_Sayisi`

The plugin UI remains English-only; field names can come from the user's source data.

For floor-count fields, select the field and set **Height source** to **Floor count field**. With `Floor height = 3.5`, a feature with `Kat_Sayisi = 5` renders as `17.5` map units high. Enable **Colour each floor separately** when you want the generated QML to colour every floor band individually and expose each band as a separate QGIS legend rule. Leave **Maximum floor bands** at **Auto from layer** to scan the layer and match the tallest feature automatically.
