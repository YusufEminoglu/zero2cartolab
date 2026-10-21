# -*- coding: utf-8 -*-
"""02CartoLab — Main plugin (Processing provider + studio dashboard + annotation tool + layout designer)."""
from __future__ import annotations

import os
from contextlib import suppress

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .processing.cartolab_provider import CartoLabProvider


IS_QGIS4 = int(getattr(Qgis, "QGIS_VERSION_INT", 0)) >= 40000


class O2CartoLabPlugin:
    """Top-level QGIS plugin: toolbar icon + menu + Processing provider + dashboard + annotation tool."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action_dashboard = None
        self.action_25d = None
        self.action_annotate = None
        self.action_welcome = None
        self.dialog = None
        self.welcome = None
        self.annotation_tool = None

    def initProcessing(self) -> None:
        if self.provider is not None:
            return
        self.provider = CartoLabProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self) -> None:
        self.initProcessing()
        if not self.iface:
            return

        icon_dir = os.path.join(os.path.dirname(__file__), "icons")
        icon_path = os.path.join(icon_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        # 1 Single Primary Action on QGIS Toolbar & Menu (Opens Full Canvas Studio GUI)
        self.action_dashboard = QAction(icon, "02CartoLab Studio", self.iface.mainWindow())
        self.action_dashboard.setToolTip("02CartoLab — Unified Cartography & Layout Studio")
        self.action_dashboard.triggered.connect(self.open_dashboard)
        self.iface.addToolBarIcon(self.action_dashboard)
        self.iface.addPluginToMenu("&02CartoLab", self.action_dashboard)

        # Additional quick entries in Menu only (clean, no toolbar pollution)
        self.action_25d = QAction("2.5D Building Extrusions", self.iface.mainWindow())
        self.action_25d.triggered.connect(self.open_25d_panel)
        self.iface.addPluginToMenu("&02CartoLab", self.action_25d)

        self.action_annotate = QAction("Inspect Features (Radar Chart)", self.iface.mainWindow())
        self.action_annotate.setCheckable(True)
        # triggered (user clicks only), not toggled: the map tool itself also flips the
        # checked state via setAction() when another tool replaces it.
        self.action_annotate.triggered.connect(self._toggle_annotation_tool)
        self.iface.addPluginToMenu("&02CartoLab", self.action_annotate)

        self.action_welcome = QAction("Welcome & Sample Datasets", self.iface.mainWindow())
        self.action_welcome.triggered.connect(self.open_welcome)
        self.iface.addPluginToMenu("&02CartoLab", self.action_welcome)

        # First run only: greet the user shortly after startup completes.
        QTimer.singleShot(1200, self._maybe_show_welcome)

        # Print Layout Designer window integration (1 single toggle icon & dock in layout windows)
        with suppress(Exception):
            from .layout.designer_integration import setup_designer_integration
            setup_designer_integration(self.iface)

    def _maybe_show_welcome(self) -> None:
        with suppress(Exception):
            from .ui.onboarding import should_show
            if should_show():
                self.open_welcome()

    def open_welcome(self) -> None:
        from .ui.onboarding import WelcomeDialog
        self._dispose_dialog(self.welcome)
        self.welcome = WelcomeDialog(self.iface, self.iface.mainWindow(),
                                     open_dashboard=self.open_dashboard)
        self.welcome.show()
        self.welcome.raise_()
        self.welcome.activateWindow()

    def open_dashboard(self) -> None:
        if self.dialog is None or not self.dialog.isVisible():
            self._dispose_dialog(self.dialog)
            from .ui.cartolab_dashboard import CartoLabDashboard
            self.dialog = CartoLabDashboard(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def open_25d_panel(self) -> None:
        self.open_dashboard()
        if self.dialog and hasattr(self.dialog, "show_25d_panel"):
            self.dialog.show_25d_panel()

    def _toggle_annotation_tool(self, checked: bool) -> None:
        if checked:
            from .ui.floating_annotation import FloatingAnnotationTool
            canvas = self.iface.mapCanvas()
            if self.annotation_tool is None:
                self.annotation_tool = FloatingAnnotationTool(self.iface, canvas)
                # Ties the action's checked state to the tool: QGIS unchecks it
                # when another map tool takes over the canvas.
                self.annotation_tool.setAction(self.action_annotate)
            if canvas.mapTool() is not self.annotation_tool:
                canvas.setMapTool(self.annotation_tool)
        elif self.annotation_tool is not None:
            canvas = self.iface.mapCanvas()
            if canvas.mapTool() is self.annotation_tool:
                canvas.unsetMapTool(self.annotation_tool)

    @staticmethod
    def _dispose_dialog(dlg) -> None:
        """Disconnect, close and schedule deletion of a plugin dialog."""
        if dlg is None:
            return
        with suppress(Exception):
            if hasattr(dlg, "disconnect_project_signals"):
                dlg.disconnect_project_signals()
        with suppress(Exception):
            dlg.close()
        with suppress(Exception):
            dlg.deleteLater()

    def unload(self) -> None:
        with suppress(Exception):
            from .layout.designer_integration import teardown_designer_integration
            teardown_designer_integration(self.iface)

        # Close and delete plugin dialogs (incl. any stray dashboards) and detach
        # their QgsProject signal connections so a reload does not duplicate them.
        dialogs = [self.dialog, self.welcome]
        with suppress(Exception):
            from .ui.cartolab_dashboard import CartoLabDashboard
            from .ui.onboarding import WelcomeDialog
            dialogs += self.iface.mainWindow().findChildren(CartoLabDashboard)
            dialogs += self.iface.mainWindow().findChildren(WelcomeDialog)
        seen = set()
        for dlg in dialogs:
            if dlg is not None and id(dlg) not in seen:
                seen.add(id(dlg))
                self._dispose_dialog(dlg)
        self.dialog = None
        self.welcome = None

        # unset map tool if active
        if self.annotation_tool:
            with suppress(Exception):
                self.annotation_tool.setAction(None)
            with suppress(Exception):
                self.iface.mapCanvas().unsetMapTool(self.annotation_tool)
            with suppress(Exception):
                self.annotation_tool.deleteLater()
            self.annotation_tool = None
        if self.iface:
            if self.action_dashboard:
                self.iface.removePluginMenu("&02CartoLab", self.action_dashboard)
                self.iface.removeToolBarIcon(self.action_dashboard)
            if self.action_25d:
                self.iface.removePluginMenu("&02CartoLab", self.action_25d)
            if self.action_annotate:
                self.iface.removePluginMenu("&02CartoLab", self.action_annotate)
            if self.action_welcome:
                self.iface.removePluginMenu("&02CartoLab", self.action_welcome)
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
