"""Render the real CartoLabDashboard headlessly (offscreen) and grab a
genuine screenshot -- no mock-ups, no AI-generated fakes.

docs/assets/{hero,bivariate,layout,modules}.jpg are AI-generated: fictional
duplicate neighbourhood labels ("Downtown" next to a mangled "Dorntown"),
a fabricated "J. Smith, Urban Research Unit" attribution that has nothing
to do with this plugin, garbled captions, and a museum-gallery frame around
the whole thing. This script captures the actual dashboard dialog so a real
image can sit next to them.

Run:
    C:\\OSGeo4W\\bin\\python-qgis.bat zero2cartolab\\docs\\build_screenshots.py

Output: docs/img/real_*.png.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
IMAGES = HERE / "img"

sys.path.insert(0, r"C:\OSGeo4W\apps\qgis\python\plugins")
if str(PLUGIN_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT.parent))

from qgis.core import QgsApplication  # noqa: E402

qgs = QgsApplication([], True)
qgs.initQgis()

from qgis.PyQt.QtGui import QFont, QFontDatabase  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication  # noqa: E402

_font_id = QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")
if _font_id != -1:
    _family = QFontDatabase.applicationFontFamilies(_font_id)[0]
    QgsApplication.setFont(QFont(_family, 9))

from zero2cartolab.ui.cartolab_dashboard import CartoLabDashboard  # noqa: E402


class _Iface:
    def mainWindow(self):
        return None

    def mapCanvas(self):
        return None

    def layerTreeView(self):
        return None


def grab_png(widget, name: str) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    path = IMAGES / f"{name}.png"
    widget.grab().save(str(path), "PNG")
    print(f"wrote {path.relative_to(PLUGIN_ROOT)} ({path.stat().st_size // 1024} KB)", flush=True)


def main() -> None:
    dashboard = CartoLabDashboard(_Iface(), parent=None)
    dashboard.resize(1180, 800)
    dashboard.show()
    for _ in range(10):
        QCoreApplication.processEvents()
    grab_png(dashboard, "real_dashboard")

    qgs.exitQgis()


if __name__ == "__main__":
    main()
