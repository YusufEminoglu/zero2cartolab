# -*- coding: utf-8 -*-
"""Real-Qt smoke test for the Print Layout Designer dock lifecycle."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtGui import QFontDatabase
from qgis.PyQt.QtWidgets import QDockWidget, QMainWindow, QTabWidget


class _Signals(QObject):
    opened = pyqtSignal(object)


class _Designer:
    def __init__(self, window):
        self._window = window

    def window(self):
        return self._window


class _Iface:
    def __init__(self, designers):
        self._designers = designers
        self._signals = _Signals()
        self.layoutDesignerOpened = self._signals.opened

    def layoutDesigners(self):
        return list(self._designers)


def main() -> int:
    app = QgsApplication.instance() or QgsApplication([], False)
    windows_font = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts" / "segoeui.ttf"
    if windows_font.exists():
        QFontDatabase.addApplicationFont(str(windows_font))

    plugins_root = str(Path(__file__).resolve().parents[2])
    if plugins_root not in sys.path:
        sys.path.insert(0, plugins_root)

    from zero2cartolab.layout import designer_integration as integration

    first_window = QMainWindow()
    first_window.show()
    first_designer = _Designer(first_window)
    iface = _Iface([first_designer])

    integration.setup_designer_integration(iface)
    app.processEvents()
    first_docks = first_window.findChildren(QDockWidget, "CartoLabLayoutStudioDock")
    assert len(first_docks) == 1, "existing Designer did not receive exactly one dock"
    assert first_docks[0].isVisible(), "CartoLab dock was attached but not shown"
    tabs = first_docks[0].findChild(QTabWidget)
    assert tabs is not None and tabs.count() == 5, "Add Graph workspace is missing"
    assert "Add Graph" in tabs.tabText(4)
    first_window.resize(1400, 900)
    first_docks[0].resize(620, 840)
    tabs.setCurrentIndex(4)
    app.processEvents()
    screenshot = os.path.join(tempfile.gettempdir(), "cartolab_designer_add_graph_gui.png")
    assert first_docks[0].grab().save(screenshot), "Designer Add Graph screenshot failed"

    integration.attach_cartolab_to_designer(iface, first_designer)
    assert len(first_window.findChildren(QDockWidget, "CartoLabLayoutStudioDock")) == 1

    second_window = QMainWindow()
    second_window.show()
    second_designer = _Designer(second_window)
    iface.layoutDesignerOpened.emit(second_designer)
    app.processEvents()
    assert len(second_window.findChildren(QDockWidget, "CartoLabLayoutStudioDock")) == 1

    integration.teardown_designer_integration(iface)
    app.processEvents()
    assert not integration._INTEGRATED_DESIGNERS
    print("PASS: Print Layout Designer dock lifecycle")
    return 0


if __name__ == "__main__":
    result = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(result)
