# -*- coding: utf-8 -*-
"""
Extract the live 02CartoLab Processing registry into JSON.

The Practical Guide's parameter tables are generated from the *running*
registry — descriptions, types, defaults, enum options and help text come
straight from the algorithm classes, so the guide can never drift from the
code.

Run:
    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat extract_registry.py
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent.parent
REPO_ROOT = PLUGIN_ROOT.parent

from qgis.core import QgsApplication  # noqa: E402

qgs = QgsApplication([], False)
qgs.initQgis()

import qgis  # noqa: E402

for _plugins_dir in (
    os.path.abspath(os.path.join(os.path.dirname(qgis.__file__), "..", "plugins")),
    "/usr/share/qgis/python/plugins",
):
    if os.path.isdir(os.path.join(_plugins_dir, "processing")):
        if _plugins_dir in sys.path:
            sys.path.remove(_plugins_dir)
        sys.path.insert(0, _plugins_dir)
        break

if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from zero2cartolab.processing.cartolab_provider import CartoLabProvider  # noqa: E402

provider = CartoLabProvider()
QgsApplication.processingRegistry().addProvider(provider)

TYPE_NAMES = {
    "boolean": "Boolean", "integer": "Integer", "double": "Double",
    "string": "String", "file": "File", "folder": "Folder",
    "featureSink": "Feature sink", "featureSource": "Feature source",
    "vectorLayer": "Vector layer", "rasterLayer": "Raster layer",
    "mapLayer": "Map layer", "enum": "Enumeration", "field": "Field",
    "extent": "Extent", "color": "Colour", "distance": "Distance",
    "area": "Area", "number": "Number", "point": "Point",
    "source": "Input layer", "sink": "Output layer",
    "vector": "Vector layer", "raster": "Raster layer",
}

registry = []
for alg in provider.algorithms():
    params = []
    for p in alg.parameterDefinitions():
        default = p.defaultValue()
        with suppress(Exception):
            if callable(default):
                default = default()
        raw_type = str(p.type())
        entry = {
            "name": p.name(),
            "description": p.description(),
            "type": TYPE_NAMES.get(raw_type, raw_type),
            "default": default if isinstance(default, (int, float, str, bool, type(None))) else str(default),
            "optional": bool(p.flags() & getattr(p, "FlagOptional", 0)),
        }
        if hasattr(p, "options"):
            entry["options"] = list(p.options())
        params.append(entry)

    outputs = []
    for o in alg.outputDefinitions():
        outputs.append({"name": o.name(), "description": o.description(),
                        "type": o.type()})

    registry.append({
        "id": alg.id(),
        "name": alg.displayName(),
        "group": alg.group(),
        "help": (alg.shortHelpString() or "").strip(),
        "params": params,
        "outputs": outputs,
    })

out = {
    "generated_by": "extract_registry.py",
    "qgis_version": qgis.core.Qgis.QGIS_VERSION,
    "algorithm_count": len(registry),
    "algorithms": registry,
}
dest = HERE / "manifest" / "algorithms.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"wrote {dest} — {len(registry)} algorithms")
sys.stdout.flush()
os._exit(0)
