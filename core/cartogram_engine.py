# -*- coding: utf-8 -*-
"""
Continuous-Area Cartogram Engine.

Diffusion method (Gastner & Newman 2004) — iteratively displaces polygon
boundaries until each region's area is proportional to a chosen variable.

Cross-version compatible with QGIS 3.14+ and QGIS 4.x.
"""
from __future__ import annotations

import math
import re
from typing import List, Tuple, Optional

from qgis.core import (
    QgsFeature, QgsGeometry, QgsVectorLayer,
)

from .utils import safe_float


# ---------------------------------------------------------------------------
# WKT coordinate parsing — version-agnostic
# ---------------------------------------------------------------------------

_COORD_RE = re.compile(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def _extract_wkt_coords(wkt: str) -> List[Tuple[float, float]]:
    """Parse all coordinate pairs from a WKT string in order."""
    return [(float(m.group(1)), float(m.group(2)))
            for m in _COORD_RE.finditer(wkt)]


def _rebuild_wkt(wkt: str, new_coords: List[Tuple[float, float]]) -> str:
    """Replace coordinate pairs in a WKT string with new values."""
    result = []
    last_end = 0
    idx = 0
    for m in _COORD_RE.finditer(wkt):
        if idx >= len(new_coords):
            break
        # copy WKT text before the X coordinate
        result.append(wkt[last_end:m.start(1)])
        # insert new coordinate pair
        nx, ny = new_coords[idx]
        result.append(f"{nx:.12f} {ny:.12f}")
        last_end = m.end(2)
        idx += 1
    # copy any remaining WKT text
    result.append(wkt[last_end:])
    return "".join(result)


# ---------------------------------------------------------------------------
# CartogramFeature — lightweight pickle-able polygon
# ---------------------------------------------------------------------------

class CartogramFeature:
    """Minimal pickle-able polygon representation for parallel processing."""

    __slots__ = (
        "id", "wkt_str", "value", "area", "radius",
        "cx", "cy", "mass", "size_error",
        "coords", "_area_value_ratio",
    )

    def __init__(self, feature_id: int, geometry, value):
        self.id = feature_id
        if geometry is None or (hasattr(geometry, "isNull") and geometry.isNull()):
            raise ValueError(f"Feature {feature_id}: geometry is None or null")
        self.wkt_str = geometry.asWkt()
        self.value = max(float(value or 0.0), 1e-12)
        self.area = 0.0
        self.radius = 0.0
        self.cx = 0.0
        self.cy = 0.0
        self.mass = 0.0
        self.size_error = 1.0
        self.coords: List[Tuple[float, float]] = []
        self._area_value_ratio = 1.0

    @property
    def area_value_ratio(self):
        return self._area_value_ratio

    @area_value_ratio.setter
    def area_value_ratio(self, val):
        self._area_value_ratio = val

    def recompute_properties(self) -> None:
        """Calculate area, radius, and centroid from current WKT."""
        geom = QgsGeometry.fromWkt(self.wkt_str)
        self.area = geom.area()
        self.radius = math.sqrt(self.area / math.pi) if self.area > 0 else 1e-12
        centroid = geom.centroid().asPoint()
        self.cx = centroid.x()
        self.cy = centroid.y()

    def extract_coords(self) -> None:
        """Parse all vertex coordinates from WKT."""
        self.coords = _extract_wkt_coords(self.wkt_str)

    def displace_coords(self, dx: float, dy: float) -> None:
        """Displace all vertices uniformly (used in repulsion step)."""
        self.coords = [(x + dx, y + dy) for x, y in self.coords]

    def writeback_coords(self) -> None:
        """Rebuild WKT from displaced coordinates."""
        self.wkt_str = _rebuild_wkt(self.wkt_str, self.coords)


# ---------------------------------------------------------------------------
# CartogramEngine
# ---------------------------------------------------------------------------

class CartogramEngine:
    """
    Continuous-area cartogram solver (Gastner & Newman diffusion algorithm).

    Transforms polygon geometries so that each polygon's area is proportional to
    a specified numeric attribute.

    Usage
    -----
    ::

        engine = CartogramEngine(source_layer, "population", max_iterations=30)
        iterations, error = engine.run(feedback=...)
        engine.write_to_layer(output_layer)
    """

    def __init__(
        self,
        source_layer: QgsVectorLayer,
        field_name: str,
        max_iterations: int = 30,
        max_average_error_pct: float = 5.0,
    ):
        self.source = source_layer
        self.field = field_name
        self.max_iter = max_iterations
        self.max_error = 1.0 + max_average_error_pct / 100.0
        self.features: List[CartogramFeature] = []
        self._total_area = 0.0
        self._total_value = 0.0
        self._area_value_ratio = 1.0

    def _load_features(self) -> None:
        for feat in self.source.getFeatures():
            geom = feat.geometry()
            if geom.isEmpty() or geom.isNull():
                continue
            val = safe_float(feat[self.field], 1e-12)
            if val <= 0:
                val = 1e-12
            cf = CartogramFeature(feat.id(), geom, val)
            cf.recompute_properties()
            cf.extract_coords()
            self.features.append(cf)

        if len(self.features) < 2:
            raise ValueError("Cartogram requires at least 2 valid features.")

        self._total_area = sum(f.area for f in self.features)
        self._total_value = sum(f.value for f in self.features)
        self._area_value_ratio = self._total_area / max(self._total_value, 1e-12)

        for f in self.features:
            f.area_value_ratio = self._area_value_ratio

    def run(self, feedback=None) -> Tuple[int, float]:
        """Execute the diffusion cartogram algorithm. Returns (iterations, avg_error)."""
        self._load_features()
        n = len(self.features)
        if n < 2:
            return 0, 1.0

        # precompute max radius for distance cutoff
        max_radius = max(f.radius for f in self.features)
        cutoff = max_radius * 6.0  # ignore features farther than 6x max radius
        sigma2 = (max_radius * 2.0) ** 2  # Gaussian sigma squared

        prev_error = float("inf")
        damping = 0.3

        for iteration in range(self.max_iter):
            if feedback and feedback.isCanceled():
                break

            # compute masses and size errors
            for f in self.features:
                target_area = f.value * self._area_value_ratio
                if target_area > 0:
                    f.mass = math.sqrt(target_area / math.pi) - f.radius
                else:
                    f.mass = 0.0
                if min(f.area, target_area) > 0:
                    f.size_error = max(f.area, target_area) / min(f.area, target_area)
                else:
                    f.size_error = 1.0

            avg_error = sum(f.size_error for f in self.features) / n

            if feedback:
                progress_pct = int(100 * iteration / self.max_iter)
                feedback.setProgress(progress_pct)
                if iteration % 3 == 0 or avg_error <= self.max_error:
                    feedback.pushInfo(
                        f"Cartogram iter {iteration + 1}/{self.max_iter}, "
                        f"avg error: {(avg_error - 1) * 100:.2f}%"
                    )

            if avg_error <= self.max_error:
                break

            # adaptive damping: reduce if error stagnates
            if avg_error >= prev_error * 0.995:
                damping *= 0.85
                damping = max(damping, 0.05)
            prev_error = avg_error

            self._diffusion_step(damping, cutoff, sigma2)

            # recompute areas from rebuilt WKT
            for f in self.features:
                f.recompute_properties()

        return min(iteration + 1, self.max_iter), avg_error

    def _diffusion_step(self, damping: float, cutoff: float, sigma2: float) -> None:
        """
        Single diffusion step with Gaussian-weighted force kernel.
        Deforms vertices using a shared topological node map to ensure 100% boundary
        contiguity without gaps or tears between neighboring polygons.
        """
        n = len(self.features)
        if n == 0:
            return

        avg_radius = sum(f.radius for f in self.features) / float(n)
        max_disp = avg_radius * 0.25

        # 1. Collect unique topological nodes across all polygon vertices
        # Node key rounded to 5 decimal places (~1mm tolerance)
        nodes = {}  # node_key -> (vx, vy, [fx, fy])
        for f in self.features:
            for vx, vy in f.coords:
                key = (round(vx, 5), round(vy, 5))
                if key not in nodes:
                    nodes[key] = (vx, vy, [0.0, 0.0])

        # 2. Spatial hash grid for feature centroids using cell_size = cutoff
        grid = {}
        cell_size = max(cutoff, 1e-5)
        for j, f_j in enumerate(self.features):
            if abs(f_j.mass) < 1e-15:
                continue
            gx = int(math.floor(f_j.cx / cell_size))
            gy = int(math.floor(f_j.cy / cell_size))
            key = (gx, gy)
            if key not in grid:
                grid[key] = []
            grid[key].append((j, f_j))

        # 3. Compute displacement ONCE for each unique topological node
        for key, node_data in nodes.items():
            vx, vy, f_vec = node_data
            fx, fy = 0.0, 0.0
            vgx = int(math.floor(vx / cell_size))
            vgy = int(math.floor(vy / cell_size))

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cell_features = grid.get((vgx + dx, vgy + dy))
                    if not cell_features:
                        continue
                    for j, f_j in cell_features:
                        dist = math.hypot(vx - f_j.cx, vy - f_j.cy)
                        if dist > cutoff:
                            continue
                        if dist < 1e-12:
                            dist = 1e-12
                        weight = math.exp(-dist * dist / (2.0 * sigma2))
                        influence = f_j.mass * f_j.radius * damping * weight
                        dir_x = (vx - f_j.cx) / dist
                        dir_y = (vy - f_j.cy) / dist
                        fx += influence * dir_x
                        fy += influence * dir_y

            # Clamp node displacement uniformly
            disp = math.hypot(fx, fy)
            if disp > max_disp:
                scale = max_disp / disp
                fx *= scale
                fy *= scale
            f_vec[0] = fx
            f_vec[1] = fy

        # 4. Map displaced node coordinates back into each feature's vertex array
        for f in self.features:
            new_coords = []
            for vx, vy in f.coords:
                key = (round(vx, 5), round(vy, 5))
                fx, fy = nodes[key][2]
                new_coords.append((vx + fx, vy + fy))
            f.coords = new_coords
            f.writeback_coords()

    def write_to_layer(self, output_layer: QgsVectorLayer) -> None:
        """Write distorted geometries into an existing memory layer."""
        lookup = {f.id: f for f in self.features}
        output_layer.startEditing()
        for feat in output_layer.getFeatures():
            if feat.id() in lookup:
                cf = lookup[feat.id()]
                new_geom = QgsGeometry.fromWkt(cf.wkt_str)
                if not new_geom.isNull():
                    output_layer.changeGeometry(feat.id(), new_geom)
        output_layer.commitChanges()
