# -*- coding: utf-8 -*-
"""
Dependency status reporter.

CartoLab ships with **no external dependencies** — it uses only QGIS and the
NumPy that QGIS already bundles. This module simply *reports* which optional
libraries are present; it never installs anything (no ``pip``/subprocess), so
the plugin stays inside the QGIS sandbox and passes the Plugin Hub security
scan.
"""
from __future__ import annotations

import importlib
from typing import Dict, List, Tuple


# ── Package definitions ──────────────────────────────────────────────

# Format:  pypi_name : (import_name, required, purpose_description)

CARTO_LAB_DEPS: Dict[str, Tuple[str, bool, str]] = {
    "numpy": ("numpy", True, "Numerical array operations (GIC, cartogram, ridge maps)"),
    "matplotlib": ("matplotlib", False, "Colour ramp generation and chart previews"),
}

DATA_CUBE_DEPS: Dict[str, Tuple[str, bool, str]] = {
    "numpy": ("numpy", True, "Multi-dimensional array backbone for data cubes"),
    "netCDF4": ("netCDF4", True, "Read/write netCDF4 climate/earth-science data cubes"),
    "statsmodels": ("statsmodels", True, "ARIMA / SARIMAX time-series models"),
    "scikit-learn": ("sklearn", True, "Random Forest and ML-based time-series forecasting"),
    "xarray": ("xarray", False, "Labelled multi-dimensional array analysis"),
    "dask": ("dask", False, "Parallel out-of-core computation for large cubes"),
    "zarr": ("zarr", False, "Chunked compressed storage format for netCDF alternatives"),
}


# ── Core logic ───────────────────────────────────────────────────────

def check_packages(
    deps: Dict[str, Tuple[str, bool, str]]
) -> Tuple[List[str], List[str], List[str]]:
    """
    Check which packages are available.

    Returns (available, missing_required, missing_optional).
    Each entry is the PyPI package name.
    """
    available: List[str] = []
    missing_required: List[str] = []
    missing_optional: List[str] = []

    for pypi_name, (import_name, required, _purpose) in deps.items():
        try:
            importlib.import_module(import_name)
            available.append(pypi_name)
        except ImportError:
            if required:
                missing_required.append(pypi_name)
            else:
                missing_optional.append(pypi_name)

    return available, missing_required, missing_optional


def get_status_report(
    deps: Dict[str, Tuple[str, bool, str]],
    title: str = "Dependency Status",
) -> str:
    """Build a human-readable status report."""
    available, missing_req, missing_opt = check_packages(deps)
    lines = [f"=== {title} ===", ""]

    if available:
        lines.append("Installed:")
        for pkg in available:
            _, _, purpose = deps[pkg]
            lines.append(f"  [OK] {pkg} — {purpose}")

    if missing_req:
        lines.append("\nMISSING (required — plugin may not work correctly):")
        for pkg in missing_req:
            _, _, purpose = deps[pkg]
            lines.append(f"  [!!] {pkg} — {purpose}")

    if missing_opt:
        lines.append("\nMISSING (optional — enhanced features unavailable):")
        for pkg in missing_opt:
            _, _, purpose = deps[pkg]
            lines.append(f"  [--] {pkg} — {purpose}")

    if not missing_req and not missing_opt:
        lines.append("\nAll dependencies satisfied.")

    return "\n".join(lines)
