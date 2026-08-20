# -*- coding: utf-8 -*-
"""QgsProcessingProvider for PlanX CartoLab."""
from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .alg_geometric_interval import GeometricIntervalAlgorithm
from .alg_bivariate import BivariateChoroplethAlgorithm
from .alg_cartogram import CartogramAlgorithm
from .alg_ridge_map import RidgeMapAlgorithm
from .alg_value_by_alpha import ValueByAlphaAlgorithm
from .alg_25d_style import Building25DStyleAlgorithm
from .alg_dot_density import DotDensityAlgorithm
from .alg_proportional_symbols import ProportionalSymbolsAlgorithm
from .alg_hexbin import HexbinAlgorithm
from .alg_label_points import LabelPointsAlgorithm
from .alg_graticule import GraticuleAlgorithm
from .alg_normalize_field import NormalizeFieldAlgorithm
from .alg_quick_style import QuickStyleAlgorithm
from .alg_bivariate_matrix_export import BivariateMatrixExportAlgorithm


class CartoLabProvider(QgsProcessingProvider):
    PROVIDER_ID = "zero2cartolab"
    PROVIDER_NAME = "02CartoLab"

    def id(self) -> str:
        return self.PROVIDER_ID

    def name(self) -> str:
        return self.PROVIDER_NAME

    def longName(self) -> str:
        return "02CartoLab — Cartography & Layout Studio"

    def icon(self) -> QIcon:
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "icons", "icon.png")
        return QIcon(path) if os.path.exists(path) else super().icon()

    def loadAlgorithms(self) -> None:
        self.addAlgorithm(GeometricIntervalAlgorithm())
        self.addAlgorithm(BivariateChoroplethAlgorithm())
        self.addAlgorithm(CartogramAlgorithm())
        self.addAlgorithm(RidgeMapAlgorithm())
        self.addAlgorithm(ValueByAlphaAlgorithm())
        self.addAlgorithm(Building25DStyleAlgorithm())
        self.addAlgorithm(DotDensityAlgorithm())
        self.addAlgorithm(ProportionalSymbolsAlgorithm())
        self.addAlgorithm(HexbinAlgorithm())
        self.addAlgorithm(LabelPointsAlgorithm())
        self.addAlgorithm(GraticuleAlgorithm())
        self.addAlgorithm(NormalizeFieldAlgorithm())
        self.addAlgorithm(QuickStyleAlgorithm())
        self.addAlgorithm(BivariateMatrixExportAlgorithm())
