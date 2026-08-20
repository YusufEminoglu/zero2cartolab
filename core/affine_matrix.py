# -*- coding: utf-8 -*-
"""
Affine Matrix — Axonometric / isometric coordinate transformer.

Converts 2D map coordinates into 2.5D isometric projections for
layout stacking without deforming geometry.
"""
from __future__ import annotations

import math
from typing import Tuple


class AffineMatrix:
    """
    2D affine transformation matrix for isometric projection.

    [ x' ]   [ a  b  tx ] [ x ]
    [ y' ] = [ c  d  ty ] [ y ]
    [ 1  ]   [ 0  0   1 ] [ 1 ]
    """

    __slots__ = ("a", "b", "c", "d", "tx", "ty")

    def __init__(
        self,
        a: float = 1.0, b: float = 0.0,
        c: float = 0.0, d: float = 1.0,
        tx: float = 0.0, ty: float = 0.0,
    ):
        self.a, self.b = a, b
        self.c, self.d = c, d
        self.tx, self.ty = tx, ty

    @classmethod
    def identity(cls) -> "AffineMatrix":
        return cls(1, 0, 0, 1, 0, 0)

    @classmethod
    def from_isometric_angles(
        cls,
        angle_deg: float = 30.0,
        z_offset: float = 100.0,
        elevation_deg: float = 35.264,
    ) -> "AffineMatrix":
        """
        Create an isometric (2.5D) projection matrix.

        Parameters
        ----------
        angle_deg : float
            Rotation around Z axis (yaw), in degrees.
        z_offset : float
            How far to offset along the pseudo-Z axis (in map units).
        elevation_deg : float
            Camera elevation angle (0=top-down, 90=side view).
            Classic isometric ≈ 35.264° (arctan(1/√2)).
        """
        alpha = math.radians(angle_deg)
        beta = math.radians(elevation_deg)

        # projection onto 2D plane
        a = math.cos(alpha)
        b = math.sin(alpha)
        c = -math.sin(alpha) * math.cos(beta)
        d = math.cos(alpha) * math.cos(beta)

        # Z offset contributes to Y shift
        ty = z_offset * math.sin(beta)

        return cls(a, b, c, d, 0.0, ty)

    def transform_point(self, x: float, y: float) -> Tuple[float, float]:
        """Apply affine transform to a single point."""
        nx = self.a * x + self.b * y + self.tx
        ny = self.c * x + self.d * y + self.ty
        return (nx, ny)

    def compose(self, other: "AffineMatrix") -> "AffineMatrix":
        """Multiply self × other."""
        return AffineMatrix(
            a=self.a * other.a + self.b * other.c,
            b=self.a * other.b + self.b * other.d,
            c=self.c * other.a + self.d * other.c,
            d=self.c * other.b + self.d * other.d,
            tx=self.a * other.tx + self.b * other.ty + self.tx,
            ty=self.c * other.tx + self.d * other.ty + self.ty,
        )

    def translate(self, dx: float, dy: float) -> "AffineMatrix":
        """Return a new matrix with added translation."""
        return AffineMatrix(self.a, self.b, self.c, self.d, self.tx + dx, self.ty + dy)

    def scale(self, sx: float, sy: float) -> "AffineMatrix":
        """Return a new matrix with scaling applied."""
        return AffineMatrix(
            self.a * sx, self.b * sy,
            self.c * sx, self.d * sy,
            self.tx, self.ty,
        )


def compute_isometric_layer_offsets(
    n_layers: int,
    base_spacing: float = 60.0,
    angle_deg: float = 30.0,
    elevation_deg: float = 35.264,
) -> list:
    """
    Pre-compute isometric offsets for `n_layers` stacked layers.

    Each layer is shifted along the pseudo-Z axis by base_spacing × i.
    Returns a list of (dx, dy) tuples, one per layer.
    """
    beta = math.radians(elevation_deg)
    offsets = []
    for i in range(n_layers):
        dz = i * base_spacing
        dy = dz * math.sin(beta)
        offsets.append((0.0, dy))
    return offsets
