# -*- coding: utf-8 -*-
"""Visual-Center Label Points (polylabel) — Processing algorithm."""
from __future__ import annotations

from qgis.core import (
    QgsFeature, QgsFeatureSink, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from ..core.label_points import polylabel, polygon_orientation_angle
from ._help_mixin import CartoLabHelpMixin


def _shoelace_area(ring):
    area = 0.0
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        area += xj * yi - xi * yj
        j = i
    return abs(area) / 2.0


def _largest_part_rings(geom):
    """Return [exterior, holes...] of the largest polygon part as (x, y) tuples."""
    if geom is None or geom.isEmpty():
        return None
    if geom.isMultipart():
        polygons = geom.asMultiPolygon()
    else:
        polygons = [geom.asPolygon()]
    best_rings = None
    best_area = -1.0
    for poly in polygons:
        if not poly:
            continue
        rings = [[(p.x(), p.y()) for p in ring] for ring in poly]
        area = _shoelace_area(rings[0])
        if area > best_area:
            best_area = area
            best_rings = rings
    return best_rings


class LabelPointsAlgorithm(CartoLabHelpMixin, QgsProcessingAlgorithm):
    _ICON_NAME = "compass.png"
    INPUT = "INPUT"
    PRECISION = "PRECISION"
    OUTPUT = "OUTPUT"

    def name(self) -> str:
        return "label_points"

    def displayName(self) -> str:
        return "Visual-Center Label Points"

    def group(self) -> str:
        return "Labeling"

    def groupId(self) -> str:
        return "labeling"

    def createInstance(self):
        return LabelPointsAlgorithm()

    def shortHelpString(self) -> str:
        return (
            "Compute each polygon's pole of inaccessibility (polylabel) — the "
            "interior point furthest from any edge. Unlike a centroid, it always "
            "falls inside the polygon, even for C-shaped or doughnut features, so "
            "labels never spill outside the shape.\n\n"
            "For multipart features the largest part is used.\n"
            "• 'lbl_dist': Inscribed-circle radius in map units (available label room proxy).\n"
            "• 'lbl_angle': Principal inertia orientation angle in degrees [-90..+90] for rotating labels along elongated shapes.\n\n"
            "Precision 0 = auto (scaled from each polygon's size)."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input polygon layer", [QgsProcessing.SourceType.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterNumber(
            self.PRECISION, "Precision (map units, 0 = auto)",
            type=QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Label points output", QgsProcessing.SourceType.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        precision = self.parameterAsDouble(parameters, self.PRECISION, context)

        out_fields = QgsFields()
        for f in source.fields():
            out_fields.append(QgsField(f.name(), f.type()))
        out_fields.append(QgsField("lbl_dist", QVariant.Double))
        out_fields.append(QgsField("lbl_angle", QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            out_fields, QgsWkbTypes.Type.Point, source.sourceCrs(),
        )

        total = source.featureCount() or 1
        written = 0
        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            rings = _largest_part_rings(feat.geometry())
            if not rings or len(rings[0]) < 3:
                continue
            prec = precision
            if prec <= 0:
                bb = feat.geometry().boundingBox()
                prec = max(min(bb.width(), bb.height()) / 100.0, 1e-9)
            x, y, dist = polylabel(rings, prec)
            angle = polygon_orientation_angle(rings[0])
            attrs = feat.attributes()[:]
            attrs.append(dist)
            attrs.append(angle)
            nf = QgsFeature(out_fields)
            nf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            nf.setAttributes(attrs)
            sink.addFeature(nf, QgsFeatureSink.Flag.FastInsert)
            written += 1
            feedback.setProgress(int(100 * current / total))

        feedback.pushInfo(f"Computed {written} visual-center label points with distance and orientation angles.")
        return {self.OUTPUT: dest_id}
