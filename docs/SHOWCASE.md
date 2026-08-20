# Feature Showcase

## 2.5D Building Styling

The 2.5D styling panel upgrades rough QML extrusion into a reusable production workflow:

- Select any loaded polygon layer.
- Choose a numeric height field or a floor-count field such as `Kat_Sayisi`.
- For floor counts, set Height source to Floor count field and choose the floor height, usually 3.5 map units per floor.
- Enable Colour each floor separately for sample-QML-style floor bands where each storey receives its own colour.
- Leave Maximum floor bands on Auto from layer to scan the selected floor-count field and match the real tallest building.
- Use the generated legend-friendly QML where every floor band is written as its own QGIS rule.
- Pick a material preset.
- Adjust projection angle, height scale, maximum height, and stepped-floor snapping.
- Control roof, wall, and shadow colors.
- Apply either the native QGIS `25dRenderer` or the generated rule-based floor-band renderer.
- Export the applied QML style for reuse.

## Bivariate Choropleth

Bivariate mapping classifies two numeric variables into an NxN matrix. CartoLab writes class fields to the output layer and applies categorized symbology automatically.

## Value-by-Alpha

Value-by-Alpha separates the primary thematic variable from the reliability variable. The primary variable remains visible, while low-confidence features fade through reduced opacity.

## Continuous-Area Cartogram

Cartogram output distorts polygon area to represent a numeric value while keeping a continuous planar surface.

## Ridge Maps

Ridge maps convert raster surfaces into vector scanlines. Use them for elevation, heat, accessibility, density, and other continuous urban surfaces.

## Layout Automation

CartoLab includes layout tools for:

- Isometric layer stacks.
- Bivariate matrix legends.
- Swiss-style typography hierarchy.
- Minimalist coordinate grids.
