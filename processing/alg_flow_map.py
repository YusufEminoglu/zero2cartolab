# -*- coding: utf-8 -*-
"""Origin-Destination Flow Map — Processing algorithm."""
from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature, QgsFeatureRequest, QgsFeatureSink, QgsField, QgsFields,
    QgsGeometry, QgsPointXY, QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingException, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
    QgsProcessingParameterNumber, QgsProperty, QgsWkbTypes,
)

from ..core import flow_map as fm
from ..core.palettes import get_palette
from ..core.quick_style import quantile_breaks
from ..core.utils import symbol_layer_property
from ._help_mixin import CartoLabHelpMixin
from ._styling import style_output


def flow_line_symbol(color: QColor, arrows: bool):
    """Line symbol with data-defined width and an optional scaled arrowhead."""
    from qgis.core import (
        QgsLineSymbol, QgsMarkerLineSymbolLayer, QgsMarkerSymbol,
    )
    symbol = QgsLineSymbol.createSimple({
        "line_color": f"{color.red()},{color.green()},{color.blue()},225",
        "line_width": "0.6", "capstyle": "round", "joinstyle": "round",
    })
    symbol.symbolLayer(0).setDataDefinedProperty(
        symbol_layer_property("StrokeWidth"), QgsProperty.fromField("flow_width"))
    if arrows:
        head = QgsMarkerSymbol.createSimple({
            "name": "filled_arrowhead",
            "color": f"{color.red()},{color.green()},{color.blue()},245",
            "outline_style": "no", "size": "2.4",
        })
        head.symbolLayer(0).setDataDefinedProperty(
            symbol_layer_property("Size"),
            QgsProperty.fromExpression('"flow_width" * 1.7 + 1.2'))
        marker_line = QgsMarkerLineSymbolLayer.create({
            "placement": "lastvertex", "placements": "LastVertex", "rotate": "1",
        })
        marker_line.setSubSymbol(head)
        symbol.appendSymbolLayer(marker_line)
    return symbol


def apply_flow_renderer(layer, breaks, colours, arrows: bool) -> None:
    """Graduated colour by volume; small flows drawn above large ones."""
    from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange

    ranges = []
    for i in range(len(breaks) - 1):
        lo, hi = breaks[i], breaks[i + 1]
        col = QColor(colours[min(i, len(colours) - 1)])
        ranges.append(QgsRendererRange(lo, hi, flow_line_symbol(col, arrows), f"{lo:,.0f} – {hi:,.0f}"))
    if not ranges:
        return
    renderer = QgsGraduatedSymbolRenderer("flow_vol", ranges)
    renderer.setOrderBy(QgsFeatureRequest.OrderBy([
        QgsFeatureRequest.OrderByClause("flow_vol", False),
    ]))
    renderer.setOrderByEnabled(True)
    layer.setRenderer(renderer)


class FlowMapAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "flow.png"
    ZONES = "ZONES"
    ZONE_ID = "ZONE_ID"
    FLOWS = "FLOWS"
    ORIGIN = "ORIGIN"
    DEST = "DEST"
    VOLUME = "VOLUME"
    DIRECTED = "DIRECTED"
    MIN_VOLUME = "MIN_VOLUME"
    TOP_N = "TOP_N"
    CURVATURE = "CURVATURE"
    MAX_WIDTH = "MAX_WIDTH"
    MIN_WIDTH = "MIN_WIDTH"
    END_GAP = "END_GAP"
    ARROWS = "ARROWS"
    PALETTE = "PALETTE"
    OUTPUT = "OUTPUT"

    PALETTES_LIST = ["YlOrRd", "Blues", "Viridis", "Plasma", "Magma", "Purples", "Greys"]

    def name(self) -> str:
        return "flow_map"

    def displayName(self) -> str:
        return "Origin-Destination Flow Map"

    def group(self) -> str:
        return "Thematic Mapping"

    def groupId(self) -> str:
        return "thematic_mapping"

    def createInstance(self):
        return FlowMapAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Draw desire lines between zones from an origin-destination table "
            "(commuting, migration, trade, trips).\n\n"
            "• Zones: any layer with an id field; polygons are represented by a "
            "point guaranteed to lie inside them.\n"
            "• Flows: any table or layer with origin id, destination id and "
            "volume fields — a CSV without geometry works. Repeated pairs are "
            "summed; ids match as text, so 7, 7.0 and \"7\" are the same zone.\n"
            "• Curved flows bend to the right of travel, so A→B and B→A become "
            "two separate arcs. Curvature 0 draws straight lines. Merge the "
            "directions to map total two-way volume instead.\n"
            "• Line width is linear in volume; colour classes are quantiles. "
            "Large flows are drawn underneath small ones so nothing is hidden.\n"
            "• Filter with a minimum volume and/or keep only the top N flows.\n\n"
            "Output fields: flow_o, flow_d, flow_vol, flow_rank (1 = largest), "
            "flow_share (% of mapped volume), flow_width (mm), flow_len "
            "(map units)."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.ZONES, "Zones layer", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField(
            self.ZONE_ID, "Zone id field", parentLayerParameterName=self.ZONES))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.FLOWS, "Origin-destination table", [QgsProcessing.SourceType.TypeVector]))
        self.addParameter(QgsProcessingParameterField(
            self.ORIGIN, "Origin id field", parentLayerParameterName=self.FLOWS))
        self.addParameter(QgsProcessingParameterField(
            self.DEST, "Destination id field", parentLayerParameterName=self.FLOWS))
        self.addParameter(QgsProcessingParameterField(
            self.VOLUME, "Volume field", parentLayerParameterName=self.FLOWS,
            type=QgsProcessingParameterField.DataType.Numeric))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DIRECTED, "Keep directions separate (A→B and B→A)", defaultValue=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_VOLUME, "Minimum volume to draw",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOP_N, "Keep only the N largest flows (0 = all)",
            type=QgsProcessingParameterNumber.Type.Integer, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.CURVATURE, "Curvature (0 = straight lines)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.2,
            minValue=0.0, maxValue=1.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_WIDTH, "Maximum line width (mm)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=5.0, minValue=0.1))
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_WIDTH, "Minimum line width (mm)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.3, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.END_GAP, "Gap at each end (% of flow length)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=4.0,
            minValue=0.0, maxValue=40.0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ARROWS, "Draw arrowheads", defaultValue=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, "Colour ramp", options=self.PALETTES_LIST, defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Flow lines", QgsProcessing.SourceType.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):
        zones = self.parameterAsSource(parameters, self.ZONES, context)
        if zones is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.ZONES))
        flows_src = self.parameterAsSource(parameters, self.FLOWS, context)
        if flows_src is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.FLOWS))

        zone_field = self.parameterAsString(parameters, self.ZONE_ID, context)
        o_field = self.parameterAsString(parameters, self.ORIGIN, context)
        d_field = self.parameterAsString(parameters, self.DEST, context)
        v_field = self.parameterAsString(parameters, self.VOLUME, context)
        directed = self.parameterAsBool(parameters, self.DIRECTED, context)
        min_volume = self.parameterAsDouble(parameters, self.MIN_VOLUME, context)
        top_n = self.parameterAsInt(parameters, self.TOP_N, context)
        curvature = self.parameterAsDouble(parameters, self.CURVATURE, context)
        max_w = self.parameterAsDouble(parameters, self.MAX_WIDTH, context)
        min_w = min(self.parameterAsDouble(parameters, self.MIN_WIDTH, context), max_w)
        gap = self.parameterAsDouble(parameters, self.END_GAP, context) / 100.0
        arrows = self.parameterAsBool(parameters, self.ARROWS, context)
        pal_idx = self.parameterAsEnum(parameters, self.PALETTE, context)
        pal_name = self.PALETTES_LIST[pal_idx] if 0 <= pal_idx < len(self.PALETTES_LIST) else "YlOrRd"

        # zone points
        pairs = []
        for feat in zones.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            pt = geom.centroid() if geom.type() == QgsWkbTypes.PointGeometry \
                else geom.pointOnSurface()
            if pt is None or pt.isEmpty():
                continue
            p = pt.asPoint()
            pairs.append((feat[zone_field], (p.x(), p.y())))
        lookup, duplicates = fm.zone_lookup(pairs)
        if not lookup:
            raise QgsProcessingException("The zones layer has no features with a usable id and geometry.")
        if duplicates:
            feedback.pushWarning(
                f"{len(duplicates)} zone ids occur more than once; the first feature is used "
                f"(e.g. {', '.join(duplicates[:5])}).")

        # OD records
        records = []
        missing = set()
        for feat in flows_src.getFeatures():
            if feedback.isCanceled():
                break
            o = fm.normalise_zone_id(feat[o_field])
            d = fm.normalise_zone_id(feat[d_field])
            if o is None or d is None:
                continue
            if o not in lookup:
                missing.add(o)
                continue
            if d not in lookup:
                missing.add(d)
                continue
            records.append((o, d, feat[v_field]))
        if missing:
            sample = ", ".join(sorted(missing)[:8])
            feedback.pushWarning(
                f"{len(missing)} zone ids in the OD table have no matching zone and were skipped "
                f"(e.g. {sample}).")

        totals = fm.aggregate_flows(records, directed=directed, drop_self=True)
        selected = fm.select_flows(totals, min_volume=min_volume, top_n=top_n)
        if not selected:
            raise QgsProcessingException(
                "No flows left to draw: check the id fields, the volume field and the filters.")

        v_max = selected[0][1]
        mapped_total = sum(v for _, v in selected) or 1.0

        out_fields = QgsFields()
        out_fields.append(QgsField("flow_o", QVariant.String))
        out_fields.append(QgsField("flow_d", QVariant.String))
        out_fields.append(QgsField("flow_vol", QVariant.Double))
        out_fields.append(QgsField("flow_rank", QVariant.Int))
        out_fields.append(QgsField("flow_share", QVariant.Double))
        out_fields.append(QgsField("flow_width", QVariant.Double))
        out_fields.append(QgsField("flow_len", QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            QgsWkbTypes.Type.LineString, zones.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # two-way merged flows are drawn without a direction bias
        arc_curvature = curvature if directed else 0.0
        written = 0
        for rank, ((o, d), volume) in enumerate(selected, start=1):
            if feedback.isCanceled():
                break
            pts = fm.flow_arc(lookup[o], lookup[d], curvature=arc_curvature,
                              segments=32, trim_start=gap, trim_end=gap)
            if len(pts) < 2:
                continue
            nf = QgsFeature(out_fields)
            nf.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in pts]))
            nf.setAttributes([
                o, d, float(volume), rank,
                round(100.0 * volume / mapped_total, 4),
                round(fm.flow_width(volume, v_max, max_w, min_w), 4),
                fm.polyline_length(pts),
            ])
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
            written += 1
            feedback.setProgress(int(100 * rank / len(selected)))

        feedback.pushInfo(
            f"Drew {written} flows from {len(records)} OD records "
            f"({len(totals)} distinct {'directed' if directed else 'two-way'} pairs); "
            f"largest = {v_max:,.2f}.")

        volumes = [v for _, v in selected]
        n_classes = min(5, max(1, len(set(volumes))))
        breaks = sorted(set(quantile_breaks(volumes, n_classes))) if n_classes > 1 else []
        if len(breaks) < 2:
            breaks = [min(volumes), max(volumes)]
        # skip the ramp's lightest step: a pale thin line vanishes on a light map
        colours = get_palette(pal_name, len(breaks))[1:]
        style_output(
            context, dest_id,
            lambda layer: apply_flow_renderer(layer, breaks, colours, arrows and directed),
            feedback,
        )
        return {self.OUTPUT: dest_id}
