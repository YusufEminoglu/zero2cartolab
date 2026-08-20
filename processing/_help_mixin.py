# -*- coding: utf-8 -*-
"""Shared helpUrl() and icon() mixin for all PlanX CartoLab Processing algorithms."""
from __future__ import annotations

import os

from qgis.PyQt.QtGui import QIcon


class CartoLabHelpMixin:
    """Mixin providing default helpUrl() and dynamic custom icon() for algorithms."""

    _HELP_BASE = "https://github.com/YusufEminoglu/zero2cartolab#module-catalog"
    _ICON_NAME = "icon.png"

    def helpUrl(self) -> str:
        return self._HELP_BASE

    def icon(self) -> QIcon:
        icon_name = getattr(self, "_ICON_NAME", "icon.png")
        base = os.path.dirname(os.path.dirname(__file__))
        path = os.path.join(base, "icons", icon_name)
        if os.path.exists(path):
            return QIcon(path)
        fallback = os.path.join(base, "icons", "icon.png")
        return QIcon(fallback) if os.path.exists(fallback) else QIcon()
