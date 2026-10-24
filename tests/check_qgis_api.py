"""Static check: every QGIS / Qt class member the plugin names exists here.

The GUI and algorithm suites only reach the code paths they exercise. A Qt5
spelling such as ``Qt.AlignLeft`` or a QGIS 3 enum removed in QGIS 4 breaks
only when a user clicks the one button that uses it. This script parses every
shipped module, collects the names imported from ``qgis.*``, and resolves each
attribute chain written against them (``Qt.AlignmentFlag.AlignLeft``,
``QgsWkbTypes.LineStringZ``...) in the running QGIS. Run it under every QGIS
version in the CI matrix; it needs the QGIS Python bindings but no display.

Imports guarded by ``try: ... except ImportError`` are optional, and a chain
inside ``if hasattr(X, ...)`` / ``getattr(X, ...)`` fallbacks is skipped.
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
from typing import Dict, List, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", ".claude", "__pycache__", "node_modules", "e2e", "scratch", "docs", "media", "tests"}


def _shipped_files() -> List[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                found.append(os.path.join(dirpath, name))
    return found


def _guarded_by_import_error(node: ast.AST, parents: Dict[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.Try) and current in parent.body:
            for handler in parent.handlers:
                names = []
                if handler.type is None:
                    return True
                if isinstance(handler.type, ast.Tuple):
                    names = [getattr(e, "id", "") for e in handler.type.elts]
                else:
                    names = [getattr(handler.type, "id", "")]
                if {"ImportError", "ModuleNotFoundError", "Exception", "AttributeError"} & set(names):
                    return True
        current = parent
    return False


def _feature_tested(node: ast.AST, parents: Dict[ast.AST, ast.AST], base: str) -> bool:
    """True inside ``if hasattr(base, ...)`` / an ``else`` of one, or a guarded try."""
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, (ast.If, ast.IfExp)):
            for call in ast.walk(parent.test):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in {"hasattr", "getattr", "isinstance"}
                    and call.args
                    and isinstance(call.args[0], (ast.Name, ast.Attribute))
                    and ast.unparse(call.args[0]).split(".")[0] == base
                ):
                    return True
        if isinstance(parent, ast.Try) and current in parent.body:
            for handler in parent.handlers:
                text = ast.unparse(handler.type) if handler.type is not None else "Exception"
                if "AttributeError" in text or text in {"Exception", "BaseException"}:
                    return True
        current = parent
    return False


def _attribute_chain(node: ast.Attribute) -> Tuple[str, List[str]]:
    names: List[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        names.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        return current.id, list(reversed(names))
    return "", []


def check_file(path: str) -> Tuple[List[str], int]:
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    parents: Dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    rel = os.path.relpath(path, ROOT)
    problems: List[str] = []
    imported: Dict[str, object] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not (node.module == "qgis" or node.module.startswith("qgis.")):
            continue
        optional = _guarded_by_import_error(node, parents)
        try:
            module = importlib.import_module(node.module)
        except ImportError as exc:
            if not optional:
                problems.append(f"{rel}:{node.lineno}: cannot import {node.module} ({exc})")
            continue
        for alias in node.names:
            local = alias.asname or alias.name
            if not hasattr(module, alias.name):
                # "from qgis import processing": a submodule, loaded on import.
                try:
                    importlib.import_module(f"{node.module}.{alias.name}")
                except ImportError:
                    pass
            if hasattr(module, alias.name):
                # A name imported in two places (Qt5 / Qt6 fallbacks) keeps the
                # first one that resolves.
                imported.setdefault(local, getattr(module, alias.name))
            elif not optional:
                problems.append(f"{rel}:{node.lineno}: {node.module} has no {alias.name}")

    checked = 0
    seen: Set[Tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or isinstance(parents.get(node), ast.Attribute):
            continue  # only the outermost node of each chain
        base, chain = _attribute_chain(node)
        if base not in imported or not chain:
            continue
        key = (node.lineno, ast.unparse(node))
        if key in seen:
            continue
        seen.add(key)
        if _feature_tested(node, parents, base):
            continue
        obj = imported[base]
        resolved = base
        for name in chain:
            if not hasattr(obj, name):
                problems.append(f"{rel}:{node.lineno}: {resolved}.{name} does not exist")
                break
            obj = getattr(obj, name)
            resolved = f"{resolved}.{name}"
        checked += 1
    return problems, checked


def main() -> int:
    import qgis

    # "from qgis import processing" re-exports the Processing plugin, which
    # lives beside the qgis package (Windows) or in /usr/share (Linux).
    for plugins_dir in (os.path.join(os.path.dirname(qgis.__file__), "..", "plugins"),
                        "/usr/share/qgis/python/plugins"):
        if os.path.isdir(os.path.join(plugins_dir, "processing")):
            sys.path.insert(0, os.path.abspath(plugins_dir))
            break
    try:
        import processing  # noqa: F401 - patches run() etc. into qgis.processing
    except ImportError:
        pass
    from qgis.core import Qgis
    from qgis.PyQt.QtCore import QT_VERSION_STR

    problems: List[str] = []
    checked = 0
    files = _shipped_files()
    for path in files:
        found, count = check_file(path)
        problems.extend(found)
        checked += count
    print(f"QGIS {Qgis.version()} / Qt {QT_VERSION_STR}: {checked} member references in {len(files)} files")
    for line in problems:
        print("  " + line)
    if problems:
        print(f"FAIL: {len(problems)} reference(s) missing in this QGIS")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
