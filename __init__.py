# -*- coding: utf-8 -*-
"""
02CartoLab — Unified Cartographic Studio & Print Layout Automation for QGIS.

classFactory returns the O2CartoLabPlugin instance.
"""


def classFactory(iface):
    from .main_plugin import O2CartoLabPlugin
    return O2CartoLabPlugin(iface)

