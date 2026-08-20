# -*- coding: utf-8 -*-
"""
CartoLab Dashboard — Professional QDialog following PlanX Suitability Lab pattern.

Provides a production console for PlanX CartoLab with:
  - Hero header with gradient branding
  - Tabbed interface: Overview, Modules (card grid), Setup, Quick Actions
  - Processing algorithm cards with Run/Fav buttons
  - System health monitoring and dependency management
"""
from __future__ import annotations

import os
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import processing
except ImportError:
    processing = None
try:
    from qgis.PyQt.QtCore import QSettings, Qt, QSize
    from qgis.PyQt.QtGui import QColor, QFont, QIcon
    from qgis.PyQt.QtWidgets import (
        QApplication,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QListWidget,
        QMessageBox,
        QAbstractItemView,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QStackedWidget,
        QListWidgetItem,
        QTabWidget,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
    from qgis.core import Qgis, QgsApplication, QgsProject, QgsMapLayer
except ImportError:
    QSettings = Qt = QSize = QColor = QFont = QApplication = QCheckBox = QColorDialog = QComboBox = QDialog = QDoubleSpinBox = QFileDialog = QFrame = QGridLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QPushButton = QListWidget = QMessageBox = QAbstractItemView = QScrollArea = QSizePolicy = QSpinBox = QStackedWidget = QListWidgetItem = QTabWidget = QTextBrowser = QVBoxLayout = QWidget = Qgis = QgsApplication = QgsProject = QgsMapLayer = None


from ..core.qgis_25d_style import (
    FLOOR_BAND_PALETTES,
    HEIGHT_MODE_FLOOR_COUNT,
    HEIGHT_MODE_HEIGHT,
    RENDER_MODE_FLOOR_BANDS,
    RENDER_MODE_NATIVE,
    STYLE_25D_PRESETS,
    Style25DConfig,
    apply_25d_renderer,
    build_style_summary,
    field_is_numeric,
    looks_like_floor_count_field,
    normalise_hex_color,
)


IS_QGIS4 = int(getattr(Qgis, "QGIS_VERSION_INT", 0)) >= 40000
DASHBOARD_SIZE = (1160, 760) if IS_QGIS4 else (1220, 800)
DEFAULT_CARD_COLUMNS = 2 if IS_QGIS4 else 3


def _device_pixel_ratio(widget=None) -> float:
    dpr = 1.0
    with suppress(Exception):
        if widget is not None and hasattr(widget, "devicePixelRatioF"):
            dpr = float(widget.devicePixelRatioF())
    if dpr <= 1.0 and QApplication is not None:
        with suppress(Exception):
            screen = QApplication.primaryScreen()
            if screen is not None:
                dpr = float(screen.devicePixelRatio())
    return max(1.0, dpr)


def _hidpi_icon_pixmap(icon: QIcon, width: int, height: int, widget=None):
    dpr = _device_pixel_ratio(widget)
    pixel_w = max(1, int(round(width * dpr)))
    pixel_h = max(1, int(round(height * dpr)))
    pixmap = icon.pixmap(QSize(pixel_w, pixel_h)) if QSize is not None else icon.pixmap(pixel_w, pixel_h)
    with suppress(Exception):
        pixmap.setDevicePixelRatio(dpr)
    return pixmap

# ── Algorithm catalogue ─────────────────────────────────────────────

ALGO_GROUPS = [
    (
        "Quick Style",
        "#2b8a6f",
        [
            ("Quick Style (auto choropleth / categories)", "zero2cartolab:quick_style",
             "One-click graduated or categorized renderer with ColorBrewer / colour-blind-safe palettes."),
        ],
    ),
    (
        "2.5D Styling",
        "#9b6b43",
        [
            ("Apply 2.5D Building Style", "zero2cartolab:building_25d_style",
             "Native QGIS 2.5D extrusion from a height field with CartoLab lighting presets and shadows."),
        ],
    ),
    (
        "Classification",
        "#2f7aa8",
        [
            ("Geometric Interval Classification", "zero2cartolab:geometric_interval_classification",
             "Adaptive GIC, Head/Tail Breaks, Fisher-Jenks - optimal for skewed and heavy-tailed distributions."),
        ],
    ),
    (
        "Thematic Mapping",
        "#357a5f",
        [
            ("Bivariate Choropleth Map", "zero2cartolab:bivariate_choropleth",
             "NxN colour matrix from two numeric fields with bilinear interpolation."),
            ("Value-by-Alpha (VbA) Map", "zero2cartolab:value_by_alpha",
             "Encode reliability/uncertainty as opacity - unreliable data fades into background."),
            ("Ridge Map (Joyplot)", "zero2cartolab:ridge_map",
             "Raster-to-vector scanline deformation - Joy Division style wave profiles."),
            ("Dot-Density Map", "zero2cartolab:dot_density",
             "Seeded, hole-aware dots inside polygons - one dot per N units of a count field."),
            ("Proportional Symbols (Flannery)", "zero2cartolab:proportional_symbols",
             "Perceptually compensated graduated point symbols with nested-legend values."),
            ("Bivariate Matrix Export", "zero2cartolab:bivariate_matrix_export",
             "Export high-resolution standalone NxN bivariate legend matrices as SVG/PNG image."),
        ],
    ),
    (
        "Cartogram",
        "#7359a8",
        [
            ("Continuous-Area Cartogram", "zero2cartolab:compute_cartogram",
             "Diffusion method (Gastner & Newman) - polygon areas proportional to field value."),
        ],
    ),
    (
        "Aggregation",
        "#b6772f",
        [
            ("Hexbin Aggregation", "zero2cartolab:hexbin_aggregate",
             "Bin a point layer into a pointy-top hex grid - count, sum or mean, overplot-free."),
        ],
    ),
    (
        "Labeling",
        "#3f8e8a",
        [
            ("Visual-Center Label Points", "zero2cartolab:label_points",
             "Pole of inaccessibility (polylabel) - label anchors that always sit inside the shape."),
        ],
    ),
    (
        "Map Reference",
        "#5a6f9b",
        [
            ("Graticule / Reference Grid", "zero2cartolab:graticule_grid",
             "Meridians and parallels on nice round intervals, each carrying a coordinate label."),
        ],
    ),
    (
        "Data Preparation",
        "#9b466e",
        [
            ("Choropleth Normalization & Rates", "zero2cartolab:normalize_field",
             "Rates, z-score, robust z, min-max, percentile rank and log - prep before classifying."),
        ],
    ),
]

REQUIRED_IDS = [aid for _, _, items in ALGO_GROUPS for _, aid, _ in items]

CATEGORY_GROUPS = {
    "Quick Style": [
        "zero2cartolab:quick_style",
    ],
    "2.5D Styling": [
        "zero2cartolab:building_25d_style",
    ],
    "Classification Engine": [
        "zero2cartolab:geometric_interval_classification",
    ],
    "Thematic Mapping": [
        "zero2cartolab:bivariate_choropleth",
        "zero2cartolab:value_by_alpha",
        "zero2cartolab:ridge_map",
        "zero2cartolab:dot_density",
        "zero2cartolab:proportional_symbols",
        "zero2cartolab:bivariate_matrix_export",
    ],
    "Cartogram Engine": [
        "zero2cartolab:compute_cartogram",
    ],
    "Aggregation": [
        "zero2cartolab:hexbin_aggregate",
    ],
    "Labeling": [
        "zero2cartolab:label_points",
    ],
    "Map Reference": [
        "zero2cartolab:graticule_grid",
    ],
    "Data Preparation": [
        "zero2cartolab:normalize_field",
    ],
}


def _cartolab_icon(name: str = "icon.png") -> QIcon:
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "icons", name)
    if os.path.exists(path):
        return QIcon(path)
    fallback = os.path.join(base, "icons", "icon.png")
    return QIcon(fallback) if os.path.exists(fallback) else QIcon()


_QDialogBase = QDialog if QDialog is not None else object

class CartoLabDashboard(_QDialogBase):

    """Production console for PlanX CartoLab."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QSettings()
        self.recent_runs: list[str] = []
        self.card_widgets: list[QFrame] = []
        self._current_card_columns = DEFAULT_CARD_COLUMNS
        self.favorites: set[str] = set(
            self.settings.value("zero2cartolab/favorites", [], type=list) or []
        )

        self.setWindowTitle("02CartoLab — Cartography & Layout Studio")
        self.resize(*DASHBOARD_SIZE)
        self._apply_style()
        self._build_ui()
        self._connect_project_signals()
        self._refresh()

    def _connect_project_signals(self) -> None:
        with suppress(Exception):
            proj = QgsProject.instance()
            if proj:
                proj.layersAdded.connect(self._on_layers_changed)
                proj.layersRemoved.connect(self._on_layers_changed)

    def _on_layers_changed(self, *args) -> None:
        self._refresh_all_layer_combos()
        self._refresh()

    def _refresh_all_layer_combos(self) -> None:
        """Refresh all layer comboboxes across every tab when project layers change."""
        with suppress(Exception):
            self._refresh_qs_layers()
        with suppress(Exception):
            self._refresh_25d_layers()
        with suppress(Exception):
            self._refresh_bivar_layers()
        with suppress(Exception):
            self._refresh_inspector_layers()
        with suppress(Exception):
            self._refresh_layout_combo()

    # ── Styling ──────────────────────────────────────────────────────

    def _apply_style(self) -> None:
        r = 8 if IS_QGIS4 else 10
        btn_r = 6 if IS_QGIS4 else 7
        title_sz = 20 if IS_QGIS4 else 22
        self.setStyleSheet(f"""
            QDialog {{ background: #f8fafc; font-family: "Segoe UI", "Inter", sans-serif; }}
            QFrame#heroCard {{
                background: #ffffff;
                border-radius: {r}px;
                border: 1px solid #e2e8f0;
            }}
            QLabel#heroTitle {{ color: #0f172a; font-weight: 700; font-size: {title_sz}px; }}
            QLabel#heroSub {{ color: #64748b; font-size: 12px; }}
            QLabel#statusChip {{
                color: #065f46; background: #ecfdf5; border: 1px solid #a7f3d0;
                border-radius: 6px; padding: 4px 10px; font-weight: 600; font-size: 11px;
            }}
            QTabWidget::pane {{ border: 1px solid #e2e8f0; border-radius: {r}px; background: #ffffff; margin-top: -1px; }}
            QTabBar::tab {{
                background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-bottom: none;
                padding: 7px 18px 7px 18px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px;
                font-weight: 600; font-size: 12px; min-height: 26px;
            }}
            QTabBar::tab:selected {{ background: #ffffff; color: #1d4ed8; font-weight: 700; border: 1px solid #94a3b8; border-bottom: 2px solid #2563eb; }}
            QTabBar::tab:hover:!selected {{ background: #e2e8f0; color: #0f172a; }}
            QListWidget#sidebarNav {{
                background: #ffffff; color: #334155; border: 1px solid #e2e8f0;
                border-radius: {r}px; padding: 6px; outline: none;
            }}
            QListWidget#sidebarNav::item {{
                padding: 12px 14px; border-radius: 6px; font-weight: 600;
                font-size: 13px; color: #475569; margin-bottom: 4px;
            }}
            QListWidget#sidebarNav::item:selected {{
                background: #eff6ff;
                color: #1d4ed8;
                font-weight: 700;
                border: 1px solid #bfdbfe;
            }}
            QListWidget#sidebarNav::item:hover:!selected {{
                background: #f8fafc; color: #0f172a;
            }}

            QTextBrowser {{
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: {r}px;
                padding: 10px; color: #334155; font-size: 12px;
            }}
            QPushButton {{
                background: #0f172a; color: #ffffff; border: 1px solid #0f172a;
                border-radius: {btn_r}px; padding: 7px 14px; font-weight: 600; font-size: 12px;
            }}
            QPushButton:hover {{ background: #1e293b; border-color: #1e293b; }}
            QPushButton#ghost {{
                background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
            }}
            QPushButton#ghost:hover {{ background: #f8fafc; color: #0f172a; border-color: #94a3b8; }}
            QPushButton#favBtn {{
                background: #ffffff; color: #ef4444; border: 1px solid #fecaca;
                border-radius: 6px; padding: 2px 8px; font-weight: 600;
            }}
            QPushButton#favBtn:checked {{
                background: #fef2f2; color: #dc2626; border: 1px solid #ef4444;
            }}
            QLineEdit {{
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 8px; color: #0f172a;
            }}
            QLineEdit:focus {{ border-color: #3b82f6; }}
            QComboBox {{
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; color: #0f172a;
            }}
            QComboBox:focus {{ border-color: #3b82f6; }}
            QDoubleSpinBox, QSpinBox {{
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; color: #0f172a;
            }}
            QCheckBox {{ color: #334155; font-size: 12px; padding: 2px; }}
            QFrame[classCard="true"] {{
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: {r}px;
            }}
            QFrame[classCard="true"]:hover {{ background: #f8fafc; border: 1px solid #cbd5e1; }}
            QLabel[classTitle="true"] {{ color: #0f172a; font-weight: 700; font-size: 13px; }}
            QLabel[classMeta="true"] {{ color: #64748b; font-size: 11px; }}
            QLabel[classChip="ok"] {{
                color: #065f46; background: #ecfdf5; border: 1px solid #a7f3d0;
                border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: 600;
            }}
            QLabel[classChip="warn"] {{
                color: #92400e; background: #fffbeb; border: 1px solid #fde68a;
                border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: 600;
            }}
            QLabel[classChip="err"] {{
                color: #991b1b; background: #fef2f2; border: 1px solid #fecaca;
                border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: 600;
            }}
            QLabel#cardCount {{ color: #64748b; font-size: 11px; padding: 0 4px; }}
        """)

    # ── Build UI ─────────────────────────────────────────────────────

    def _make_group(self, title: str) -> QGroupBox:
        gb = QGroupBox(title)
        gb.setFont(QFont("Inter, Segoe UI", 9, QFont.Weight.Bold))
        gb.setStyleSheet(
            "QGroupBox { border: 1px solid #cbd5e1; border-radius: 8px; "
            "margin-top: 16px; padding-top: 14px; padding-left: 10px; padding-right: 10px; padding-bottom: 10px; background: #ffffff; }"
            "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; "
            "padding: 0 6px; background: #ffffff; color: #0f172a; font-weight: 700; }"
        )
        return gb

    def _build_ui(self) -> None:
        m = 10 if IS_QGIS4 else 12
        root = QVBoxLayout(self)
        root.setContentsMargins(m, m, m, m)
        root.setSpacing(m)

        # ── Hero header ──
        hero = QFrame()
        hero.setObjectName("heroCard")
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(14, 12, 14, 12)
        ttl = QVBoxLayout()
        title = QLabel("02CartoLab")
        title.setObjectName("heroTitle")
        sub = QLabel(
            "Unified cartographic studio and print layout automation: "
            "publication-grade thematic styling, bivariate maps, 2.5D extrusion, and one-click layout generation."
        )
        sub.setObjectName("heroSub")
        ttl.addWidget(title)
        ttl.addWidget(sub)
        hl.addLayout(ttl, 1)
        self.status_chip = QLabel("System Status: checking...")
        self.status_chip.setObjectName("statusChip")
        hl.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(hero)

        # ── Vertical Workspace Navigation (Sidebar List + Stacked Pages) ──
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(12)

        self.nav_sidebar = QListWidget()
        self.nav_sidebar.setObjectName("sidebarNav")
        self.nav_sidebar.setFixedWidth(205)

        item_symb = QListWidgetItem(_cartolab_icon("style.png"), " Symbology Studio")
        item_layout = QListWidgetItem(_cartolab_icon("layout.png"), " Layout Studio")
        item_hub = QListWidgetItem(_cartolab_icon("icon.png"), " Processing Hub")
        self.nav_sidebar.addItem(item_symb)
        self.nav_sidebar.addItem(item_layout)
        self.nav_sidebar.addItem(item_hub)

        self.stack = QStackedWidget()
        self.tabs = self.stack  # alias for backward compatibility

        # Workspace 1: Symbology & Thematic Studio
        self._build_symbology_studio_tab()

        # Workspace 2: Layout Automation Studio
        self._build_layout_tab()

        # Workspace 3: Processing Algorithm Hub
        self._build_modules_tab()

        workspace_layout.addWidget(self.nav_sidebar, 0)
        workspace_layout.addWidget(self.stack, 1)
        root.addLayout(workspace_layout, 1)

        self.nav_sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_sidebar.setCurrentRow(0)

        # Collapsible Bottom Drawer: Diagnostics & Run Log
        self._build_diagnostics_drawer(root)

        self._on_check_deps()


    def _build_symbology_studio_tab(self) -> None:
        """Workspace 1: Unified Symbology & Thematic Studio (Quick Style, 2.5D, Advanced Suite, Palette Inspector)."""
        studio_widget = QWidget()
        layout = QVBoxLayout(studio_widget)
        layout.setContentsMargins(6, 6, 6, 6)

        self.symbology_sub_tabs = QTabWidget()
        self.symbology_sub_tabs.setUsesScrollButtons(True)
        with suppress(Exception):
            _ElideNone = getattr(getattr(Qt, "TextElideMode", Qt), "ElideNone", getattr(Qt, "ElideNone", 0))
            self.symbology_sub_tabs.tabBar().setElideMode(_ElideNone)
            self.symbology_sub_tabs.tabBar().setExpanding(False)

        # Sub-tab 1: Quick Style
        qs_widget = QWidget()
        qs_layout = QVBoxLayout(qs_widget)
        qs_layout.setContentsMargins(12, 16, 12, 12)
        self._build_quick_style_contents(qs_layout)
        self.symbology_sub_tabs.addTab(qs_widget, _cartolab_icon("style.png"), "Quick Style")
        self.symbology_sub_tabs.setTabToolTip(0, "Quick Style: One-click graduated & categorized thematic styling")

        # Sub-tab 2: 2.5D Building Extrusion
        self.tab_25d = QScrollArea()
        self.tab_25d.setWidgetResizable(True)
        self.tab_25d.setFrameShape(QFrame.Shape.NoFrame)
        tab_body = QWidget()
        self.tab_25d.setWidget(tab_body)
        self._build_25d_contents(tab_body)
        self.symbology_sub_tabs.addTab(self.tab_25d, _cartolab_icon("isometric.png"), "2.5D Buildings")
        self.symbology_sub_tabs.setTabToolTip(1, "2.5D Building Extrusion: Native height extrusion, lighting & floor bands")

        # Sub-tab 3: Advanced Thematic Suite
        thematic_widget = self._build_thematic_suite_subwidget()
        self.symbology_sub_tabs.addTab(thematic_widget, _cartolab_icon("bivariate.png"), "Thematic Maps")
        self.symbology_sub_tabs.setTabToolTip(2, "Thematic Maps: Bivariate choropleth, Value-by-Alpha, Cartogram, Ridge maps")

        # Sub-tab 4: Palette & Accessibility Inspector
        palette_widget = self._build_palette_inspector_subwidget()
        self.symbology_sub_tabs.addTab(palette_widget, _cartolab_icon("inspector.png"), "Palette & Accessibility")
        self.symbology_sub_tabs.setTabToolTip(3, "Palette & Accessibility Inspector: CVD simulation & WCAG 2.1 contrast scoring")

        layout.addWidget(self.symbology_sub_tabs)
        self.stack.addWidget(studio_widget)


    def _build_thematic_suite_subwidget(self) -> QWidget:
        """Interactive studio for Bivariate mapping with live matrix preview and quick launcher for thematic suite."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(14)

        # ── 1. Interactive Bivariate Choropleth Studio ──
        gb_bivar = self._make_group("Interactive Bivariate Choropleth Studio (2-Variable Relationship)")
        fl_bivar = QGridLayout(gb_bivar)
        fl_bivar.setContentsMargins(12, 12, 12, 12)
        fl_bivar.setSpacing(8)

        fl_bivar.addWidget(QLabel("Polygon layer:"), 0, 0)
        self.bivar_layer_combo = QComboBox()
        self.bivar_layer_combo.currentIndexChanged.connect(self._refresh_bivar_fields)
        fl_bivar.addWidget(self.bivar_layer_combo, 0, 1)

        btn_refresh_bivar_layers = QPushButton("Refresh Layers")
        btn_refresh_bivar_layers.setObjectName("ghost")
        btn_refresh_bivar_layers.clicked.connect(self._refresh_bivar_layers)
        fl_bivar.addWidget(btn_refresh_bivar_layers, 0, 2)

        fl_bivar.addWidget(QLabel("Variable X (Field 1):"), 1, 0)
        self.bivar_field_x_combo = QComboBox()
        fl_bivar.addWidget(self.bivar_field_x_combo, 1, 1, 1, 2)

        fl_bivar.addWidget(QLabel("Variable Y (Field 2):"), 2, 0)
        self.bivar_field_y_combo = QComboBox()
        fl_bivar.addWidget(self.bivar_field_y_combo, 2, 1, 1, 2)

        fl_bivar.addWidget(QLabel("Palette Preset:"), 3, 0)
        self.bivar_preset_combo = QComboBox()
        self.bivar_preset_combo.addItem("Teal - Brown (Resilience & Hazard)", "teal_brown")
        self.bivar_preset_combo.addItem("Stevens Pink - Cyan (Demography & Health)", "stevens_pink_cyan")
        self.bivar_preset_combo.addItem("Blue - Orange (Density & Income)", "blue_orange")
        self.bivar_preset_combo.addItem("Purple - Green (Land Use & Vegetation)", "purple_green")
        self.bivar_preset_combo.addItem("Night Neon (Dark Theme & Massing)", "night_neon")
        self.bivar_preset_combo.currentIndexChanged.connect(self._update_bivar_preview_matrix)
        fl_bivar.addWidget(self.bivar_preset_combo, 3, 1, 1, 2)

        fl_bivar.addWidget(QLabel("Classification method:"), 4, 0)
        self.bivar_method_combo = QComboBox()
        self.bivar_method_combo.addItems([
            "Quantile (Equal Count - Recommended)",
            "Geometric Interval (Power/Skewed)",
            "Natural Breaks (Fisher-Jenks)",
            "Equal Interval",
        ])
        fl_bivar.addWidget(self.bivar_method_combo, 4, 1, 1, 2)

        fl_bivar.addWidget(QLabel("Matrix Resolution:"), 5, 0)
        self.bivar_classes_spin = QSpinBox()
        self.bivar_classes_spin.setRange(2, 4)
        self.bivar_classes_spin.setValue(3)
        self.bivar_classes_spin.valueChanged.connect(self._update_bivar_preview_matrix)
        fl_bivar.addWidget(self.bivar_classes_spin, 5, 1, 1, 2)

        # Live visual matrix preview container
        fl_bivar.addWidget(QLabel("Live Color Matrix:"), 6, 0)
        self.bivar_matrix_host = QWidget()
        self.bivar_matrix_layout = QGridLayout(self.bivar_matrix_host)
        self.bivar_matrix_layout.setContentsMargins(0, 0, 0, 0)
        self.bivar_matrix_layout.setSpacing(3)
        fl_bivar.addWidget(self.bivar_matrix_host, 6, 1, 1, 2)

        btn_apply_bivar = QPushButton("Apply Bivariate Symbology ⚡")
        btn_apply_bivar.setIcon(_cartolab_icon("bivariate.png"))
        btn_apply_bivar.clicked.connect(self._on_apply_bivariate_studio)
        fl_bivar.addWidget(btn_apply_bivar, 7, 0, 1, 3)

        lyt.addWidget(gb_bivar)

        # ── 2. Other Thematic Mapping Algorithms Quick Launcher ──
        gb_others = self._make_group("Other Cartographic Thematic Algorithms")
        grid = QGridLayout(gb_others)
        grid.setSpacing(10)

        algos = [
            ("Value-by-Alpha (VbA)", "zero2cartolab:value_by_alpha", "Encode data reliability or uncertainty directly into polygon opacity.", "vba.png"),
            ("Ridge Map (Joyplot)", "zero2cartolab:ridge_map", "Raster-to-vector scanline elevation profiles (Joy Division style).", "ridge.png"),
            ("Dot-Density Map", "zero2cartolab:dot_density", "Seeded, hole-aware discrete dots inside polygons — one dot per N units.", "dot_density.png"),
            ("Proportional Symbols (Flannery)", "zero2cartolab:proportional_symbols", "Perceptually compensated graduated point symbols.", "proportional.png"),
            ("Hexbin Aggregation", "zero2cartolab:hexbin_aggregate", "Bin point layers into regular pointy-top hexagonal cells with metrics.", "hexbin.png"),
            ("Cartogram Transform", "zero2cartolab:compute_cartogram", "Continuous area cartogram polygon deformation by attribute weight.", "cartogram.png"),
        ]

        for i, (name, aid, desc, ic_name) in enumerate(algos):
            card = QFrame()
            card.setProperty("classCard", "true")
            cv = QVBoxLayout(card)
            cv.setContentsMargins(10, 10, 10, 10)
            
            thdr = QHBoxLayout()
            ic_lbl = QLabel()
            ic_lbl.setPixmap(_hidpi_icon_pixmap(_cartolab_icon(ic_name), 22, 22, ic_lbl))
            thdr.addWidget(ic_lbl)
            title = QLabel(f"<b>{name}</b>")
            title.setStyleSheet("color:#0f172a; font-size:12px;")
            thdr.addWidget(title, 1)
            cv.addLayout(thdr)

            d_lbl = QLabel(desc)
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet("color:#475569; font-size:11px;")
            btn = QPushButton("Launch Tool")
            btn.setObjectName("ghost")
            btn.setIcon(_cartolab_icon(ic_name))
            btn.clicked.connect(lambda _, x=aid, n=name: self._run_algorithm(x, n))
            cv.addWidget(d_lbl, 1)
            cv.addWidget(btn, 0, Qt.AlignmentFlag.AlignRight)
            r, c = divmod(i, 2)
            grid.addWidget(card, r, c)

        lyt.addWidget(gb_others)
        lyt.addStretch()

        self._refresh_bivar_layers()
        self._update_bivar_preview_matrix()
        return scroll

    def _refresh_bivar_layers(self) -> None:
        if not hasattr(self, "bivar_layer_combo"):
            return
        current = self.bivar_layer_combo.currentData()
        self.bivar_layer_combo.blockSignals(True)
        self.bivar_layer_combo.clear()
        for layer in self._polygon_layers():
            self.bivar_layer_combo.addItem(layer.name(), layer.id())
        if current is not None:
            idx = self.bivar_layer_combo.findData(current)
            if idx >= 0:
                self.bivar_layer_combo.setCurrentIndex(idx)
        self.bivar_layer_combo.blockSignals(False)
        self._refresh_bivar_fields()

    def _refresh_bivar_fields(self) -> None:
        if not hasattr(self, "bivar_field_x_combo"):
            return
        self.bivar_field_x_combo.clear()
        self.bivar_field_y_combo.clear()
        layer = self._layer_by_id(self.bivar_layer_combo.currentData())
        if layer is None:
            return
        fields = [f.name() for f in layer.fields()]
        for f in fields:
            self.bivar_field_x_combo.addItem(f)
            self.bivar_field_y_combo.addItem(f)
        if len(fields) >= 2:
            self.bivar_field_y_combo.setCurrentIndex(1)

    def _update_bivar_preview_matrix(self) -> None:
        if not hasattr(self, "bivar_matrix_layout"):
            return
        from ..core.bivariate_engine import bivariate_colour_matrix_hex
        preset_key = self.bivar_preset_combo.currentData() or "teal_brown"
        n = self.bivar_classes_spin.value()
        matrix = bivariate_colour_matrix_hex(size=n, preset=preset_key)

        # Clear old items
        while self.bivar_matrix_layout.count():
            item = self.bivar_matrix_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Render rows from top (High Y) to bottom (Low Y)
        for r in range(n):
            row_idx = n - 1 - r  # display highest Y at top
            for c in range(n):
                color_hex = matrix[row_idx][c]
                box = QFrame()
                box.setFixedSize(28, 28)
                box.setToolTip(f"X: {c+1}/{n}, Y: {row_idx+1}/{n} ({color_hex})")
                box.setStyleSheet(f"background: {color_hex}; border: 1px solid #94a3b8; border-radius: 3px;")
                self.bivar_matrix_layout.addWidget(box, r, c)

    def _on_apply_bivariate_studio(self) -> None:
        if processing is None:
            QMessageBox.warning(self, "Bivariate Studio", "Processing framework is not available.")
            return
        layer = self._layer_by_id(self.bivar_layer_combo.currentData())
        if layer is None:
            QMessageBox.information(self, "Bivariate Studio", "Please select a vector polygon layer.")
            return
        fx = self.bivar_field_x_combo.currentText()
        fy = self.bivar_field_y_combo.currentText()
        if not fx or not fy or fx == fy:
            QMessageBox.information(self, "Bivariate Studio", "Select two distinct numerical fields for Variable X and Variable Y.")
            return

        preset_idx = self.bivar_preset_combo.currentIndex()
        method_idx = self.bivar_method_combo.currentIndex()
        classes = self.bivar_classes_spin.value()

        params = {
            "INPUT": layer,
            "FIELD_X": fx,
            "FIELD_Y": fy,
            "CLASSES": classes,
            "PALETTE_PRESET": preset_idx,
            "METHOD": method_idx,
            "OUTPUT": "TEMPORARY_OUTPUT",
        }
        try:
            res = processing.run("zero2cartolab:bivariate_choropleth", params)
            out_layer = res.get("OUTPUT")
            if out_layer:
                QgsProject.instance().addMapLayer(out_layer)
            if hasattr(self, "iface") and self.iface:
                self.iface.messageBar().pushSuccess(
                    "CartoLab",
                    f"Bivariate Choropleth layer '{out_layer.name() if out_layer else layer.name()}' created successfully."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Bivariate Error", f"Failed to execute bivariate analysis:\n{exc}")

    def _build_palette_inspector_subwidget(self) -> QWidget:
        """Sub-tab 4: Dedicated Palette & Accessibility Inspector with live CVD simulation & WCAG scoring."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(12)

        # ── Group 1: Palette Selection & Configuration ──
        gb_sel = self._make_group("Palette Library & Class Configuration")
        fl_sel = QGridLayout(gb_sel)
        fl_sel.setContentsMargins(12, 12, 12, 12)
        fl_sel.setSpacing(8)

        fl_sel.addWidget(QLabel("Palette:"), 0, 0)
        self.inspector_palette_combo = QComboBox()
        self.inspector_palette_combo.currentIndexChanged.connect(self._update_inspector_preview)
        fl_sel.addWidget(self.inspector_palette_combo, 0, 1, 1, 3)

        fl_sel.addWidget(QLabel("Palette Type Filter:"), 1, 0)
        self.inspector_kind_combo = QComboBox()
        self.inspector_kind_combo.addItems(["All Palette Types", "Sequential", "Diverging", "Qualitative"])
        self.inspector_kind_combo.currentIndexChanged.connect(self._populate_inspector_palettes)
        fl_sel.addWidget(self.inspector_kind_combo, 1, 1)

        fl_sel.addWidget(QLabel("Classes:"), 1, 2)
        self.inspector_classes_spin = QSpinBox()
        self.inspector_classes_spin.setRange(2, 12)
        self.inspector_classes_spin.setValue(5)
        self.inspector_classes_spin.valueChanged.connect(self._update_inspector_preview)
        fl_sel.addWidget(self.inspector_classes_spin, 1, 3)

        opt_row = QHBoxLayout()
        self.inspector_cbsafe_check = QCheckBox("Colour-blind safe only 🟢")
        self.inspector_cbsafe_check.toggled.connect(self._populate_inspector_palettes)
        self.inspector_reverse_check = QCheckBox("Reverse Palette Direction ⇄")
        self.inspector_reverse_check.toggled.connect(self._update_inspector_preview)
        opt_row.addWidget(self.inspector_cbsafe_check)
        opt_row.addWidget(self.inspector_reverse_check)
        opt_row.addStretch()
        fl_sel.addLayout(opt_row, 2, 0, 1, 4)

        lyt.addWidget(gb_sel)

        # ── Group 2: Live Palette & CVD Simulation Inspector ──
        gb_cvd = self._make_group("Perceptual Color Vision Deficiency (CVD) Simulation Matrix")
        fl_cvd = QVBoxLayout(gb_cvd)
        fl_cvd.setContentsMargins(12, 12, 12, 12)
        fl_cvd.setSpacing(8)

        fl_cvd.addWidget(QLabel("<b>Continuous Linear Gradient:</b>"))
        self.inspector_gradient_bar = QFrame()
        self.inspector_gradient_bar.setFixedHeight(24)
        self.inspector_gradient_bar.setStyleSheet("border-radius: 4px; border: 1px solid #94a3b8;")
        fl_cvd.addWidget(self.inspector_gradient_bar)

        fl_cvd.addWidget(QLabel("<b>CVD Simulation Comparison:</b>"))
        self.inspector_cvd_grid = QGridLayout()
        self.inspector_cvd_grid.setSpacing(6)
        fl_cvd.addLayout(self.inspector_cvd_grid)

        # Metrics Card Box
        self.inspector_metrics_box = QFrame()
        self.inspector_metrics_box.setStyleSheet("background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px;")
        mb_lyt = QVBoxLayout(self.inspector_metrics_box)
        mb_lyt.setContentsMargins(8, 6, 8, 6)
        self.inspector_metrics_label = QLabel("Accessibility Metrics: Calculating...")
        self.inspector_metrics_label.setWordWrap(True)
        self.inspector_metrics_label.setStyleSheet("color: #0f172a; font-size: 12px;")
        mb_lyt.addWidget(self.inspector_metrics_label)
        fl_cvd.addWidget(self.inspector_metrics_box)

        lyt.addWidget(gb_cvd)

        # ── Group 3: Quick Apply & Export ──
        gb_act = self._make_group("Apply & Export Palette")
        fl_act = QGridLayout(gb_act)
        fl_act.setContentsMargins(12, 12, 12, 12)
        fl_act.setSpacing(8)

        fl_act.addWidget(QLabel("Target Vector Layer:"), 0, 0)
        self.inspector_layer_combo = QComboBox()
        fl_act.addWidget(self.inspector_layer_combo, 0, 1)

        btn_apply_pal = QPushButton("Apply to Layer ⚡")
        btn_apply_pal.setIcon(_cartolab_icon("style.png"))
        btn_apply_pal.clicked.connect(self._on_inspector_apply_to_layer)
        fl_act.addWidget(btn_apply_pal, 0, 2)

        btn_copy_hex = QPushButton("Copy Hex Codes 📋")
        btn_copy_hex.setObjectName("ghost")
        btn_copy_hex.clicked.connect(self._on_inspector_copy_hex)
        fl_act.addWidget(btn_copy_hex, 1, 1)

        btn_export_json = QPushButton("Export Palette JSON 💾")
        btn_export_json.setObjectName("ghost")
        btn_export_json.clicked.connect(self._on_inspector_export_json)
        fl_act.addWidget(btn_export_json, 1, 2)

        lyt.addWidget(gb_act)
        lyt.addStretch()

        self._populate_inspector_palettes()
        self._refresh_inspector_layers()
        return scroll

    def _populate_inspector_palettes(self) -> None:
        from ..core import palettes as _pal
        if not hasattr(self, "inspector_palette_combo"):
            return
        current = self.inspector_palette_combo.currentData()
        cb_only = self.inspector_cbsafe_check.isChecked()
        kind_filter = (self.inspector_kind_combo.currentText() or "").lower()

        names = []
        for n in _pal.ordered_names():
            meta = _pal.PALETTES.get(n, {})
            p_kind = meta.get("kind", "").lower()
            p_cb = meta.get("cb_safe", False)
            if cb_only and not p_cb:
                continue
            if kind_filter in ("sequential", "diverging", "qualitative") and p_kind != kind_filter:
                continue
            names.append(n)

        self.inspector_palette_combo.blockSignals(True)
        self.inspector_palette_combo.clear()
        for n in names:
            meta = _pal.PALETTES.get(n, {})
            badge = "🟢 Safe" if meta.get("cb_safe") else "⚠️ Normal"
            kind_txt = meta.get("kind", "sequential").capitalize()
            self.inspector_palette_combo.addItem(f"{n}  ({kind_txt} · {badge})", n)

        if current is not None:
            idx = self.inspector_palette_combo.findData(current)
            if idx >= 0:
                self.inspector_palette_combo.setCurrentIndex(idx)
        self.inspector_palette_combo.blockSignals(False)
        self._update_inspector_preview()

    def _update_inspector_preview(self) -> None:
        if not hasattr(self, "inspector_gradient_bar") or not hasattr(self, "inspector_cvd_grid"):
            return
        from ..core import palettes as _pal
        from ..core.color_accessibility import evaluate_palette_accessibility, simulate_cvd_hex
        pname = self.inspector_palette_combo.currentData() or "Viridis"
        meta = _pal.PALETTES.get(pname, {})
        n = max(2, self.inspector_classes_spin.value())
        cols = _pal.get_palette(pname, n)
        if self.inspector_reverse_check.isChecked():
            cols = list(reversed(cols))

        # 1. Update continuous gradient
        stops = ", ".join(f"stop:{i / (len(cols) - 1):.3f} {c}" for i, c in enumerate(cols))
        self.inspector_gradient_bar.setStyleSheet(
            f"border-radius: 4px; border: 1px solid #94a3b8; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,{stops});"
        )

        # 2. Clear and rebuild CVD grid
        while self.inspector_cvd_grid.count():
            item = self.inspector_cvd_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cvd_modes = [
            ("Normal Vision (Standard Trichromacy)", None),
            ("Deuteranopia (Green-blind · ~6% of males)", "deuteranopia"),
            ("Protanopia (Red-blind · ~2% of males)", "protanopia"),
            ("Tritanopia (Blue-blind · rare)", "tritanopia"),
            ("Achromatopsia (Monochromacy / Greyscale)", "achromatopsia"),
        ]

        for row_idx, (label_txt, cvd_type) in enumerate(cvd_modes):
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #334155;")
            self.inspector_cvd_grid.addWidget(lbl, row_idx, 0)

            swatch_container = QWidget()
            s_layout = QHBoxLayout(swatch_container)
            s_layout.setContentsMargins(0, 0, 0, 0)
            s_layout.setSpacing(3)

            for c_hex in cols:
                sim_hex = simulate_cvd_hex(c_hex, cvd_type) if cvd_type else c_hex
                block = QFrame()
                block.setFixedHeight(18)
                block.setToolTip(f"{c_hex} -> {sim_hex} ({label_txt})")
                block.setStyleSheet(f"background: {sim_hex}; border: 1px solid #64748b; border-radius: 2px;")
                s_layout.addWidget(block, 1)

            self.inspector_cvd_grid.addWidget(swatch_container, row_idx, 1)

        # 3. Compute accessibility metrics
        eval_res = evaluate_palette_accessibility(cols)
        rating_str = eval_res.get("rating", "Standard")
        end_contrast = eval_res.get("endpoint_contrast", 1.0)
        min_step = eval_res.get("min_step_contrast", 1.0)
        cvd_info = eval_res.get("cvd_distinct", {})
        cb_badge = "🟢 <b>Colorblind Safe</b>" if meta.get("cb_safe") else "⚠️ <b>General Audience (May require review for CVD)</b>"
        kind_str = meta.get("kind", "sequential").capitalize()

        metrics_html = (
            f"<b>Palette:</b> {pname} ({kind_str})  ·  {cb_badge}<br>"
            f"<b>WCAG 2.1 Contrast Rating:</b> <span style='color:#1d4ed8; font-weight:bold;'>{rating_str}</span> "
            f"(Endpoint: <b>{end_contrast}:1</b> · Min Step: <b>{min_step}:1</b>)<br>"
            f"<b>CVD Step Distinctness:</b> Deuteranopia: <b>{cvd_info.get('deuteranopia', 1.0)}:1</b> · "
            f"Protanopia: <b>{cvd_info.get('protanopia', 1.0)}:1</b> · "
            f"Tritanopia: <b>{cvd_info.get('tritanopia', 1.0)}:1</b>"
        )
        self.inspector_metrics_label.setText(metrics_html)

    def _refresh_inspector_layers(self) -> None:
        if not hasattr(self, "inspector_layer_combo"):
            return
        current = self.inspector_layer_combo.currentData()
        self.inspector_layer_combo.blockSignals(True)
        self.inspector_layer_combo.clear()
        for lyr in self._vector_layers():
            self.inspector_layer_combo.addItem(lyr.name(), lyr.id())
        if current is not None:
            idx = self.inspector_layer_combo.findData(current)
            if idx >= 0:
                self.inspector_layer_combo.setCurrentIndex(idx)
        self.inspector_layer_combo.blockSignals(False)

    def _on_inspector_apply_to_layer(self) -> None:
        if processing is None:
            QMessageBox.warning(self, "Apply Palette", "Processing framework is not available.")
            return
        layer = self._layer_by_id(self.inspector_layer_combo.currentData())
        if layer is None:
            QMessageBox.information(self, "Apply Palette", "Select a vector layer first.")
            return
        fields = [f.name() for f in layer.fields()]
        if not fields:
            QMessageBox.warning(self, "Apply Palette", "Selected layer has no fields to style.")
            return
        pname = self.inspector_palette_combo.currentData() or "Viridis"
        from ..core import palettes as _pal
        try:
            pidx = _pal.ordered_names().index(pname)
        except ValueError:
            pidx = 0

        # Choose first numeric field or first field
        field = fields[0]
        for f in layer.fields():
            if field_is_numeric(f):
                field = f.name()
                break

        params = {
            "INPUT": layer,
            "FIELD": field,
            "MODE": 1,  # Graduated
            "CLASSES": self.inspector_classes_spin.value(),
            "METHOD": 0,  # Quantile
            "PALETTE": pidx,
            "REVERSE": self.inspector_reverse_check.isChecked(),
            "OUTLINE": True,
        }
        try:
            res = processing.run("zero2cartolab:quick_style", params)
            with suppress(Exception):
                if hasattr(self.iface, "layerTreeView"):
                    self.iface.layerTreeView().refreshLayerSymbology(layer.id())
            layer.triggerRepaint()
            if hasattr(self, "iface") and self.iface:
                self.iface.messageBar().pushSuccess(
                    "CartoLab", f"Applied palette '{pname}' to layer '{layer.name()}' on field '{field}'."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Apply Palette Error", str(exc))

    def _on_inspector_copy_hex(self) -> None:
        from ..core import palettes as _pal
        pname = self.inspector_palette_combo.currentData() or "Viridis"
        n = max(2, self.inspector_classes_spin.value())
        cols = _pal.get_palette(pname, n)
        if self.inspector_reverse_check.isChecked():
            cols = list(reversed(cols))
        hex_text = ", ".join(cols)
        QApplication.clipboard().setText(hex_text)
        if hasattr(self, "iface") and self.iface:
            self.iface.messageBar().pushSuccess("CartoLab", f"Copied {len(cols)} hex colors to clipboard: {hex_text}")

    def _on_inspector_export_json(self) -> None:
        import json
        from ..core import palettes as _pal
        from ..core.color_accessibility import evaluate_palette_accessibility
        pname = self.inspector_palette_combo.currentData() or "Viridis"
        meta = _pal.PALETTES.get(pname, {})
        n = max(2, self.inspector_classes_spin.value())
        cols = _pal.get_palette(pname, n)
        if self.inspector_reverse_check.isChecked():
            cols = list(reversed(cols))
        eval_res = evaluate_palette_accessibility(cols)

        data = {
            "palette_name": pname,
            "kind": meta.get("kind", "sequential"),
            "colorblind_safe": meta.get("cb_safe", False),
            "classes": len(cols),
            "colors": cols,
            "accessibility": eval_res,
        }
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Palette JSON", f"{pname.lower()}_{n}_classes.json", "JSON Files (*.json)"
        )
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                if hasattr(self, "iface") and self.iface:
                    self.iface.messageBar().pushSuccess("CartoLab", f"Palette JSON saved to {filename}")
            except Exception as exc:
                QMessageBox.critical(self, "Export JSON Error", str(exc))

    def _build_modules_tab(self) -> None:
        """Workspace 3: Searchable Card Catalog for Processing Algorithms."""
        mod_tab = QWidget()
        ml = QVBoxLayout(mod_tab)
        ml.setContentsMargins(8, 8, 8, 8)

        filter_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter processing algorithms… (Ctrl+F search, Ctrl+R refresh)")

        self.search.textChanged.connect(self._filter_cards)
        filter_row.addWidget(self.search, 1)
        self.group_filter = QComboBox()
        self.group_filter.addItem("All Groups", "")
        for g, _, _ in ALGO_GROUPS:
            self.group_filter.addItem(g, g)
        self.group_filter.currentIndexChanged.connect(self._filter_cards)
        filter_row.addWidget(self.group_filter)
        self.fav_only = QPushButton("Favorites")
        self.fav_only.setObjectName("ghost")
        self.fav_only.setCheckable(True)
        self.fav_only.toggled.connect(self._filter_cards)
        filter_row.addWidget(self.fav_only)
        self.card_count = QLabel("0/0")
        self.card_count.setObjectName("cardCount")
        filter_row.addWidget(self.card_count, 0, Qt.AlignmentFlag.AlignRight)
        ml.addLayout(filter_row)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        cards_host = QWidget()
        self.cards_grid = QGridLayout(cards_host)
        self.cards_grid.setContentsMargins(4, 4, 4, 4)
        self.cards_grid.setHorizontalSpacing(8)
        self.cards_grid.setVerticalSpacing(8)
        self.cards_scroll.setWidget(cards_host)
        ml.addWidget(self.cards_scroll, 1)
        self.stack.addWidget(mod_tab)


        self._build_cards()

    def _build_diagnostics_drawer(self, root_layout: QVBoxLayout) -> None:
        """Collapsible Bottom Console for Diagnostics, Run Logs, and System Status."""
        drawer_frame = QFrame()
        drawer_frame.setStyleSheet("background: #e4eeef; border: 1px solid #cbd8dc; border-radius: 6px;")
        drawer_layout = QVBoxLayout(drawer_frame)
        drawer_layout.setContentsMargins(8, 4, 8, 4)

        hdr_row = QHBoxLayout()
        self.drawer_toggle_btn = QPushButton("📊 Diagnostics && Run Log (Collapsible)")
        self.drawer_toggle_btn.setObjectName("ghost")
        self.drawer_toggle_btn.setCheckable(True)
        self.drawer_toggle_btn.setChecked(False)
        self.drawer_toggle_btn.clicked.connect(self._toggle_diagnostics_drawer)
        hdr_row.addWidget(self.drawer_toggle_btn)

        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.setObjectName("ghost")
        refresh_btn.clicked.connect(self._refresh)
        hdr_row.addWidget(refresh_btn)
        hdr_row.addStretch(1)

        rate = QLabel(
            '<a href="https://plugins.qgis.org/plugins/zero2cartolab/" '
            'style="color:#3182bd;text-decoration:none;">Enjoying 02CartoLab? '
            'Rate it on the Hub&nbsp;&#9733;</a>'
        )
        rate.setOpenExternalLinks(True)
        rate.setStyleSheet("font-size:11px;")
        hdr_row.addWidget(rate, 0, Qt.AlignmentFlag.AlignRight)
        drawer_layout.addLayout(hdr_row)

        self.drawer_body = QTabWidget()
        self.drawer_body.setVisible(False)
        self.drawer_body.setMaximumHeight(180)

        # Sub-tab 1: Dependency Setup
        setup_w = QWidget()
        sl = QVBoxLayout(setup_w)
        sl.setContentsMargins(6, 6, 6, 6)
        self.setup_status = QTextBrowser()
        sl.addWidget(self.setup_status, 1)
        self.drawer_body.addTab(setup_w, "System Dependencies")

        # Sub-tab 2: Run Log
        rl_w = QWidget()
        rl = QVBoxLayout(rl_w)
        rl.setContentsMargins(6, 6, 6, 6)
        self.runlog = QTextBrowser()
        rl.addWidget(self.runlog, 1)
        clear_btn = QPushButton("Clear Log")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._clear_runlog)
        rl.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.drawer_body.addTab(rl_w, "Recent Run Log")

        # Sub-tab 3: System Overview & Readiness
        self.overview = QTextBrowser()
        self.readiness = self.overview  # alias
        self.drawer_body.addTab(self.overview, "Readiness & Coverage")

        drawer_layout.addWidget(self.drawer_body)
        root_layout.addWidget(drawer_frame)

    def _toggle_diagnostics_drawer(self) -> None:
        visible = self.drawer_toggle_btn.isChecked()
        self.drawer_body.setVisible(visible)


    # ── Module cards ─────────────────────────────────────────────────

    def _build_cards(self) -> None:
        for w in self.card_widgets:
            w.setParent(None)
        self.card_widgets = []
        columns = self._cards_column_count()
        self._current_card_columns = columns
        idx = 0
        ICON_MAP = {
            "zero2cartolab:bivariate_choropleth": "bivariate.png",
            "zero2cartolab:compute_cartogram": "cartogram.png",
            "zero2cartolab:ridge_map": "ridge.png",
            "zero2cartolab:value_by_alpha": "vba.png",
            "zero2cartolab:building_25d_style": "isometric.png",
            "zero2cartolab:quick_style": "style.png",
            "zero2cartolab:dot_density": "dot_density.png",
            "zero2cartolab:proportional_symbols": "proportional.png",
            "zero2cartolab:hexbin_aggregate": "hexbin.png",
            "zero2cartolab:geometric_interval_classification": "bivariate.png",
            "zero2cartolab:graticule_grid": "grid.png",
            "zero2cartolab:label_points": "compass.png",
            "zero2cartolab:normalize_field": "style.png",
        }

        for group, accent, items in ALGO_GROUPS:
            for title_txt, aid, desc in items:
                ic_name = ICON_MAP.get(aid, "icon.png")
                card = QFrame()
                card.setProperty("classCard", "true")
                card.setStyleSheet(f"border-left: 3px solid {accent};")
                v = QVBoxLayout(card)
                v.setContentsMargins(10, 10, 10, 10)

                hdr = QHBoxLayout()
                ic_lbl = QLabel()
                ic_lbl.setPixmap(_hidpi_icon_pixmap(_cartolab_icon(ic_name), 22, 22, ic_lbl))
                hdr.addWidget(ic_lbl)
                t = QLabel(title_txt)
                t.setProperty("classTitle", "true")
                hdr.addWidget(t, 1)
                status_lbl = QLabel("Checking")
                status_lbl.setProperty("classChip", "warn")
                hdr.addWidget(status_lbl, 0, Qt.AlignmentFlag.AlignRight)
                v.addLayout(hdr)

                m = QLabel(f"{group}  |  {aid}")
                m.setProperty("classMeta", "true")
                d = QLabel(desc)
                d.setWordWrap(True)
                d.setStyleSheet("color:#294e58; font-size:12px;")
                v.addWidget(m)
                v.addWidget(d, 1)

                fav = QPushButton("Fav")
                fav.setObjectName("favBtn")
                fav.setCheckable(True)
                fav.setChecked(aid in self.favorites)
                fav.clicked.connect(lambda checked, x=aid: self._toggle_favorite(x, checked))

                run = QPushButton("Run")
                run.setIcon(_cartolab_icon(ic_name))
                run.clicked.connect(lambda _, x=aid, n=title_txt: self._run_algorithm(x, n))

                br = QHBoxLayout()
                br.addWidget(fav, 0, Qt.AlignmentFlag.AlignLeft)
                br.addStretch()
                br.addWidget(run, 0, Qt.AlignmentFlag.AlignRight)
                v.addLayout(br)

                card.meta = (group.lower(), title_txt.lower(), aid.lower(), desc.lower())
                card.algo_id = aid
                card.status_lbl = status_lbl
                r, c = divmod(idx, columns)
                self.cards_grid.addWidget(card, r, c)
                self.card_widgets.append(card)
                idx += 1

    def _cards_column_count(self) -> int:
        if not hasattr(self, "cards_scroll"):
            return DEFAULT_CARD_COLUMNS
        vp = self.cards_scroll.viewport()
        width = vp.width() if vp else self.width() - 120
        if width <= 0:
            width = 1
        target = 420 if IS_QGIS4 else 380
        max_cols = 2 if IS_QGIS4 else 3
        return max(1, min(max_cols, width // target))

    def _filter_cards(self) -> None:
        q = (self.search.text() or "").strip().lower()
        grp = (self.group_filter.currentData() or "").lower()
        fav_only = self.fav_only.isChecked()
        for card in self.card_widgets:
            mg, mt, ma, md = card.meta
            ok_q = (q in mg or q in mt or q in ma or q in md) if q else True
            ok_g = (mg == grp) if grp else True
            ok_f = (card.algo_id in self.favorites) if fav_only else True
            card.setVisible(ok_q and ok_g and ok_f)
        visible = sum(1 for c in self.card_widgets if c.isVisible())
        self.card_count.setText(f"Visible: {visible}/{len(self.card_widgets)}")

    def _toggle_favorite(self, algo_id: str, checked: bool) -> None:
        if checked:
            self.favorites.add(algo_id)
        else:
            self.favorites.discard(algo_id)
        self.settings.setValue("zero2cartolab/favorites", sorted(self.favorites))
        self._filter_cards()

    # ── Algorithm execution ──────────────────────────────────────────

    def _run_algorithm(self, algo_id: str, label: str) -> None:
        if processing is None:
            QMessageBox.warning(
                self, "Processing Unavailable",
                "The QGIS Processing framework is not available in this session. "
                "Enable the Processing plugin and restart QGIS."
            )
            return
        reg = QgsApplication.processingRegistry()
        if reg.algorithmById(algo_id) is None:
            QMessageBox.warning(
                self, "Algorithm Not Found",
                f"The algorithm '{algo_id}' is not registered.\n\n"
                "The Processing provider may not have loaded correctly. "
                "Try restarting QGIS or reinstalling the plugin."
            )
            return
        try:
            processing.execAlgorithmDialog(algo_id)
        except Exception as exc:
            QMessageBox.critical(
                self, "Algorithm Error",
                f"Failed to open '{label}':\n{exc}"
            )
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.recent_runs.insert(0, f"[{ts}] {label} ({algo_id})")
        self.recent_runs = self.recent_runs[:30]
        self._refresh_runlog()

    def _refresh_runlog(self) -> None:
        if not self.recent_runs:
            self.runlog.setHtml("<h3>Recent Runs</h3><p>No runs yet.</p>")
            return
        html = "<h3>Recent Runs</h3><ul>" + "".join(f"<li>{r}</li>" for r in self.recent_runs) + "</ul>"
        self.runlog.setHtml(html)

    def _clear_runlog(self) -> None:
        self.recent_runs = []
        self._refresh_runlog()

    def _on_copy_diagnostics(self) -> None:
        """Copy project diagnostics to clipboard."""
        from ..core.dependency_manager import check_packages, CARTO_LAB_DEPS
        avail, miss_req, miss_opt = check_packages(CARTO_LAB_DEPS)
        layers = list(QgsProject.instance().mapLayers().values())
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]
        txt = (
            "PlanX CartoLab - Project Diagnostics\n"
            "=====================================\n"
            f"QGIS layers: {len(layers)}\n"
            f"Algorithms ready: {len(REQUIRED_IDS) - len(missing)}/{len(REQUIRED_IDS)}\n"
            f"Missing: {', '.join(missing) if missing else 'None'}\n"
            f"Packages OK: {', '.join(avail)}\n"
            f"Missing required: {', '.join(miss_req) if miss_req else 'None'}\n"
            f"Missing optional: {', '.join(miss_opt) if miss_opt else 'None'}\n"
        )
        QApplication.clipboard().setText(txt)
        self.iface.messageBar().pushSuccess("CartoLab", "Diagnostics copied to clipboard.")

    def _on_activate_annotation(self) -> None:
        """Activate the floating annotation map tool."""
        from ..ui.floating_annotation import FloatingAnnotationTool
        canvas = self.iface.mapCanvas()
        tool = FloatingAnnotationTool(self.iface, canvas)
        canvas.setMapTool(tool)
        self.iface.messageBar().pushInfo(
            "CartoLab", "Click any feature on the map to inspect its attributes."
        )

    # ── Layout Tools ──────────────────────────────────────────────────

    # 2.5D Styling

    def _build_25d_tab(self) -> None:
        self.tab_25d = QScrollArea()
        self.tab_25d.setWidgetResizable(True)
        self.tab_25d.setFrameShape(QFrame.Shape.NoFrame)
        tab_body = QWidget()
        self.tab_25d.setWidget(tab_body)
        lyt = QVBoxLayout(tab_body)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        source_group = self._make_group("Layer and Height")
        source_layout = QGridLayout(source_group)
        source_layout.setColumnMinimumWidth(0, 150)
        source_layout.setColumnStretch(1, 1)
        source_layout.setColumnStretch(2, 0)
        source_layout.addWidget(QLabel("Polygon layer:"), 0, 0)
        self.layer25d_combo = QComboBox()
        self.layer25d_combo.currentIndexChanged.connect(self._refresh_25d_fields)
        source_layout.addWidget(self.layer25d_combo, 0, 1)
        refresh_layers = QPushButton("Refresh Layers")
        refresh_layers.setObjectName("ghost")
        refresh_layers.clicked.connect(self._refresh_25d_layers)
        source_layout.addWidget(refresh_layers, 0, 2)

        source_layout.addWidget(QLabel("Height field:"), 1, 0)
        self.height25d_combo = QComboBox()
        self.height25d_combo.currentIndexChanged.connect(self._on_25d_height_field_changed)
        source_layout.addWidget(self.height25d_combo, 1, 1, 1, 2)

        source_layout.addWidget(QLabel("Height source:"), 2, 0)
        self.mode25d_combo = QComboBox()
        self.mode25d_combo.addItem("Height field is already in metres/map units", HEIGHT_MODE_HEIGHT)
        self.mode25d_combo.addItem("Floor count field (floors x floor height)", HEIGHT_MODE_FLOOR_COUNT)
        self.mode25d_combo.currentIndexChanged.connect(self._on_25d_mode_changed)
        source_layout.addWidget(self.mode25d_combo, 2, 1, 1, 2)

        source_layout.addWidget(QLabel("Visual preset:"), 3, 0)
        self.preset25d_combo = QComboBox()
        for key, preset in STYLE_25D_PRESETS.items():
            self.preset25d_combo.addItem(preset["label"], key)
        self.preset25d_combo.currentIndexChanged.connect(self._on_25d_preset_changed)
        source_layout.addWidget(self.preset25d_combo, 3, 1, 1, 2)
        lyt.addWidget(source_group)

        geom_group = self._make_group("Extrusion Geometry")
        geom_layout = QGridLayout(geom_group)
        geom_layout.setColumnMinimumWidth(0, 125)
        geom_layout.setColumnMinimumWidth(2, 125)
        geom_layout.setColumnStretch(1, 1)
        geom_layout.setColumnStretch(3, 1)
        self.angle25d_spin = self._make_double_spin(0, 359, 110, 1, " degrees")
        self.scale25d_spin = self._make_double_spin(0.01, 100, 1, 0.1, "x")
        self.floor_height25d_spin = self._make_double_spin(0.01, 100, 3.5, 0.1, " map units/floor")
        self.max25d_spin = self._make_double_spin(0, 1000000, 0, 1, " map units")
        self.step25d_check = QCheckBox("Snap heights to stepped floors")
        self.step25d_spin = self._make_double_spin(0.01, 100000, 3.5, 0.1, " map units")

        geom_layout.addWidget(QLabel("Projection angle:"), 0, 0)
        geom_layout.addWidget(self.angle25d_spin, 0, 1)
        geom_layout.addWidget(QLabel("Vertical scale:"), 0, 2)
        geom_layout.addWidget(self.scale25d_spin, 0, 3)
        self.floor_height25d_label = QLabel("Floor height:")
        geom_layout.addWidget(self.floor_height25d_label, 1, 0)
        geom_layout.addWidget(self.floor_height25d_spin, 1, 1)
        geom_layout.addWidget(QLabel("Maximum height:"), 1, 2)
        geom_layout.addWidget(self.max25d_spin, 1, 3)
        geom_layout.addWidget(self.step25d_check, 2, 0, 1, 2)
        geom_layout.addWidget(self.step25d_spin, 2, 2, 1, 2)
        lyt.addWidget(geom_group)

        floor_group = self._make_group("Floor Colour Bands")
        floor_layout = QGridLayout(floor_group)
        floor_layout.setColumnMinimumWidth(0, 150)
        floor_layout.setColumnMinimumWidth(2, 150)
        floor_layout.setColumnStretch(1, 1)
        floor_layout.setColumnStretch(3, 1)
        self.floor_bands25d_check = QCheckBox("Colour each floor separately")
        self.floor_bands25d_check.toggled.connect(self._on_25d_floor_bands_changed)
        self.floor_palette25d_label = QLabel("Floor palette:")
        self.floor_palette25d_combo = QComboBox()
        for key, palette in FLOOR_BAND_PALETTES.items():
            self.floor_palette25d_combo.addItem(palette["label"], key)
        self.floor_palette25d_combo.currentIndexChanged.connect(self._update_25d_status_preview)
        self.max_floors25d_label = QLabel("Maximum floor bands:")
        self.max_floors25d_spin = QSpinBox()
        self.max_floors25d_spin.setRange(0, 80)
        self.max_floors25d_spin.setSpecialValueText("Auto from layer")
        self.max_floors25d_spin.setValue(0)
        self.max_floors25d_spin.setToolTip("Use 0 to scan the selected floor-count field and match the layer automatically.")
        self.max_floors25d_spin.valueChanged.connect(self._update_25d_status_preview)

        floor_layout.addWidget(self.floor_bands25d_check, 0, 0, 1, 2)
        floor_layout.addWidget(self.floor_palette25d_label, 1, 0)
        floor_layout.addWidget(self.floor_palette25d_combo, 1, 1)
        floor_layout.addWidget(self.max_floors25d_label, 1, 2)
        floor_layout.addWidget(self.max_floors25d_spin, 1, 3)
        lyt.addWidget(floor_group)

        light_group = self._make_group("Lighting and Materials")
        light_layout = QGridLayout(light_group)
        light_layout.setColumnMinimumWidth(0, 110)
        light_layout.setColumnMinimumWidth(2, 125)
        light_layout.setColumnStretch(1, 1)
        light_layout.setColumnStretch(3, 1)
        self.roof25d_btn = self._make_color_button("#f2cf96")
        self.wall25d_btn = self._make_color_button("#b36f43")
        self.shadow25d_btn = self._make_color_button("#202833")
        self.shadow25d_check = QCheckBox("Enable soft shadow")
        self.shadow25d_check.setChecked(True)
        self.wall_shading25d_check = QCheckBox("Enable directional wall shading")
        self.wall_shading25d_check.setChecked(True)
        self.shadow_spread25d_spin = self._make_double_spin(0, 100000, 3.5, 0.5, " map units")

        self.roof25d_btn.clicked.connect(lambda: self._pick_25d_color(self.roof25d_btn, "Roof Color"))
        self.wall25d_btn.clicked.connect(lambda: self._pick_25d_color(self.wall25d_btn, "Wall Color"))
        self.shadow25d_btn.clicked.connect(lambda: self._pick_25d_color(self.shadow25d_btn, "Shadow Color"))

        light_layout.addWidget(QLabel("Roof color:"), 0, 0)
        light_layout.addWidget(self.roof25d_btn, 0, 1)
        light_layout.addWidget(QLabel("Wall color:"), 0, 2)
        light_layout.addWidget(self.wall25d_btn, 0, 3)
        light_layout.addWidget(QLabel("Shadow color:"), 1, 0)
        light_layout.addWidget(self.shadow25d_btn, 1, 1)
        light_layout.addWidget(QLabel("Shadow spread:"), 1, 2)
        light_layout.addWidget(self.shadow_spread25d_spin, 1, 3)
        light_layout.addWidget(self.shadow25d_check, 2, 0, 1, 2)
        light_layout.addWidget(self.wall_shading25d_check, 2, 2, 1, 2)
        lyt.addWidget(light_group)

        action_row = QHBoxLayout()
        apply_btn = QPushButton("Apply 2.5D Style")
        apply_btn.clicked.connect(self._on_apply_25d_style)
        action_row.addWidget(apply_btn)
        save_btn = QPushButton("Save QML Style")
        save_btn.setObjectName("ghost")
        save_btn.clicked.connect(self._on_save_25d_qml)
        action_row.addWidget(save_btn)
        copy_btn = QPushButton("Copy Style Summary")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._on_copy_25d_summary)
        action_row.addWidget(copy_btn)
        for button in (apply_btn, save_btn, copy_btn):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        action_row.addStretch()
        lyt.addLayout(action_row)

        self.style25d_status = QTextBrowser()
        self.style25d_status.setMaximumHeight(150)
        lyt.addWidget(self.style25d_status)
        lyt.addStretch()

        self._refresh_25d_layers()
        self._on_25d_preset_changed()
        self._on_25d_mode_changed()

    def _build_25d_contents(self, tab_body: QWidget) -> None:
        lyt = QVBoxLayout(tab_body)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        source_group = self._make_group("Layer and Height")
        source_layout = QGridLayout(source_group)
        source_layout.setColumnMinimumWidth(0, 150)
        source_layout.setColumnStretch(1, 1)
        source_layout.setColumnStretch(2, 0)
        source_layout.addWidget(QLabel("Polygon layer:"), 0, 0)
        self.layer25d_combo = QComboBox()
        self.layer25d_combo.currentIndexChanged.connect(self._refresh_25d_fields)
        source_layout.addWidget(self.layer25d_combo, 0, 1)
        refresh_layers = QPushButton("Refresh Layers")
        refresh_layers.setObjectName("ghost")
        refresh_layers.clicked.connect(self._refresh_25d_layers)
        source_layout.addWidget(refresh_layers, 0, 2)

        source_layout.addWidget(QLabel("Height field:"), 1, 0)
        self.height25d_combo = QComboBox()
        self.height25d_combo.currentIndexChanged.connect(self._on_25d_height_field_changed)
        source_layout.addWidget(self.height25d_combo, 1, 1, 1, 2)

        source_layout.addWidget(QLabel("Height source:"), 2, 0)
        self.mode25d_combo = QComboBox()
        self.mode25d_combo.addItem("Height field is already in metres/map units", HEIGHT_MODE_HEIGHT)
        self.mode25d_combo.addItem("Floor count field (floors x floor height)", HEIGHT_MODE_FLOOR_COUNT)
        self.mode25d_combo.currentIndexChanged.connect(self._on_25d_mode_changed)
        source_layout.addWidget(self.mode25d_combo, 2, 1, 1, 2)

        source_layout.addWidget(QLabel("Visual preset:"), 3, 0)
        self.preset25d_combo = QComboBox()
        for key, preset in STYLE_25D_PRESETS.items():
            self.preset25d_combo.addItem(preset["label"], key)
        self.preset25d_combo.currentIndexChanged.connect(self._on_25d_preset_changed)
        source_layout.addWidget(self.preset25d_combo, 3, 1, 1, 2)

        calc_row = QHBoxLayout()
        calc_btn = QPushButton("Auto-Detect Floor Count & Estimate Height (3.2m/floor)")
        calc_btn.setObjectName("ghost")
        calc_btn.clicked.connect(self._on_25d_auto_estimate_height)
        calc_row.addWidget(calc_btn)
        source_layout.addLayout(calc_row, 4, 0, 1, 3)

        lyt.addWidget(source_group)


        geom_group = self._make_group("Extrusion Geometry")
        geom_layout = QGridLayout(geom_group)
        geom_layout.setColumnMinimumWidth(0, 125)
        geom_layout.setColumnMinimumWidth(2, 125)
        geom_layout.setColumnStretch(1, 1)
        geom_layout.setColumnStretch(3, 1)
        self.angle25d_spin = self._make_double_spin(0, 359, 110, 1, " degrees")
        self.scale25d_spin = self._make_double_spin(0.01, 100, 1, 0.1, "x")
        self.floor_height25d_spin = self._make_double_spin(0.01, 100, 3.5, 0.1, " map units/floor")
        self.max25d_spin = self._make_double_spin(0, 1000000, 0, 1, " map units")
        self.step25d_check = QCheckBox("Snap heights to stepped floors")
        self.step25d_spin = self._make_double_spin(0.01, 100000, 3.5, 0.1, " map units")

        geom_layout.addWidget(QLabel("Projection angle:"), 0, 0)
        geom_layout.addWidget(self.angle25d_spin, 0, 1)
        geom_layout.addWidget(QLabel("Vertical scale:"), 0, 2)
        geom_layout.addWidget(self.scale25d_spin, 0, 3)
        self.floor_height25d_label = QLabel("Floor height:")
        geom_layout.addWidget(self.floor_height25d_label, 1, 0)
        geom_layout.addWidget(self.floor_height25d_spin, 1, 1)
        geom_layout.addWidget(QLabel("Maximum height:"), 1, 2)
        geom_layout.addWidget(self.max25d_spin, 1, 3)
        geom_layout.addWidget(self.step25d_check, 2, 0, 1, 2)
        geom_layout.addWidget(self.step25d_spin, 2, 2, 1, 2)
        lyt.addWidget(geom_group)

        floor_group = self._make_group("Floor Colour Bands")
        floor_layout = QGridLayout(floor_group)
        floor_layout.setColumnMinimumWidth(0, 150)
        floor_layout.setColumnMinimumWidth(2, 150)
        floor_layout.setColumnStretch(1, 1)
        floor_layout.setColumnStretch(3, 1)
        self.floor_bands25d_check = QCheckBox("Colour each floor separately")
        self.floor_bands25d_check.toggled.connect(self._on_25d_floor_bands_changed)
        self.floor_palette25d_label = QLabel("Floor palette:")
        self.floor_palette25d_combo = QComboBox()
        for key, palette in FLOOR_BAND_PALETTES.items():
            self.floor_palette25d_combo.addItem(palette["label"], key)
        self.floor_palette25d_combo.currentIndexChanged.connect(self._update_25d_status_preview)
        self.max_floors25d_label = QLabel("Maximum floor bands:")
        self.max_floors25d_spin = QSpinBox()
        self.max_floors25d_spin.setRange(0, 80)
        self.max_floors25d_spin.setSpecialValueText("Auto from layer")
        self.max_floors25d_spin.setValue(0)
        self.max_floors25d_spin.setToolTip("Use 0 to scan the selected floor-count field and match the layer automatically.")
        self.max_floors25d_spin.valueChanged.connect(self._update_25d_status_preview)

        floor_layout.addWidget(self.floor_bands25d_check, 0, 0, 1, 2)
        floor_layout.addWidget(self.floor_palette25d_label, 1, 0)
        floor_layout.addWidget(self.floor_palette25d_combo, 1, 1)
        floor_layout.addWidget(self.max_floors25d_label, 1, 2)
        floor_layout.addWidget(self.max_floors25d_spin, 1, 3)
        lyt.addWidget(floor_group)

        light_group = self._make_group("Lighting and Materials")
        light_layout = QGridLayout(light_group)
        light_layout.setColumnMinimumWidth(0, 110)
        light_layout.setColumnMinimumWidth(2, 125)
        light_layout.setColumnStretch(1, 1)
        light_layout.setColumnStretch(3, 1)
        self.roof25d_btn = self._make_color_button("#f2cf96")
        self.wall25d_btn = self._make_color_button("#b36f43")
        self.shadow25d_btn = self._make_color_button("#202833")
        self.shadow25d_check = QCheckBox("Enable soft shadow")
        self.shadow25d_check.setChecked(True)
        self.wall_shading25d_check = QCheckBox("Enable directional wall shading")
        self.wall_shading25d_check.setChecked(True)
        self.shadow_spread25d_spin = self._make_double_spin(0, 100000, 3.5, 0.5, " map units")

        self.roof25d_btn.clicked.connect(lambda: self._pick_25d_color(self.roof25d_btn, "Roof Color"))
        self.wall25d_btn.clicked.connect(lambda: self._pick_25d_color(self.wall25d_btn, "Wall Color"))
        self.shadow25d_btn.clicked.connect(lambda: self._pick_25d_color(self.shadow25d_btn, "Shadow Color"))

        light_layout.addWidget(QLabel("Roof color:"), 0, 0)
        light_layout.addWidget(self.roof25d_btn, 0, 1)
        light_layout.addWidget(QLabel("Wall color:"), 0, 2)
        light_layout.addWidget(self.wall25d_btn, 0, 3)
        light_layout.addWidget(QLabel("Shadow color:"), 1, 0)
        light_layout.addWidget(self.shadow25d_btn, 1, 1)
        light_layout.addWidget(QLabel("Shadow spread:"), 1, 2)
        light_layout.addWidget(self.shadow_spread25d_spin, 1, 3)
        light_layout.addWidget(self.shadow25d_check, 2, 0, 1, 2)
        light_layout.addWidget(self.wall_shading25d_check, 2, 2, 1, 2)
        lyt.addWidget(light_group)

        solar_group = self._make_group("Astronomical Sun & Shadow Calculator")
        solar_layout = QGridLayout(solar_group)
        solar_layout.addWidget(QLabel("Sun Time Preset:"), 0, 0)
        self.solar_time_combo = QComboBox()
        self.solar_time_combo.addItem("Afternoon Studio (15:00) — Classic High Contrast", "afternoon_studio")
        self.solar_time_combo.addItem("Morning Crisp (09:00) — Low Morning Sun", "morning_crisp")
        self.solar_time_combo.addItem("Midday Zenith (12:30) — Bright High Sun", "midday_zenith")
        self.solar_time_combo.addItem("Golden Hour (17:30) — Dramatic Low Shadows", "golden_hour")
        solar_layout.addWidget(self.solar_time_combo, 0, 1)

        btn_calc_sun = QPushButton("Calculate & Apply Sun Angles")
        btn_calc_sun.setIcon(_cartolab_icon("isometric.png"))
        btn_calc_sun.clicked.connect(self._on_apply_sun_lighting)
        solar_layout.addWidget(btn_calc_sun, 0, 2)
        lyt.addWidget(solar_group)

        action_row = QHBoxLayout()
        apply_btn = QPushButton("Apply 2.5D Style")
        apply_btn.clicked.connect(self._on_apply_25d_style)
        action_row.addWidget(apply_btn)
        save_btn = QPushButton("Save QML Style")
        save_btn.setObjectName("ghost")
        save_btn.clicked.connect(self._on_save_25d_qml)
        action_row.addWidget(save_btn)
        copy_btn = QPushButton("Copy Style Summary")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._on_copy_25d_summary)
        action_row.addWidget(copy_btn)
        for button in (apply_btn, save_btn, copy_btn):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        action_row.addStretch()
        lyt.addLayout(action_row)

        self.style25d_status = QTextBrowser()
        self.style25d_status.setMaximumHeight(150)
        lyt.addWidget(self.style25d_status)
        lyt.addStretch()

        self._refresh_25d_layers()
        self._on_25d_preset_changed()
        self._on_25d_mode_changed()

    def _make_double_spin(self, minimum: float, maximum: float, value: float, step: float, suffix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.valueChanged.connect(self._update_25d_status_preview)
        return spin

    def _make_color_button(self, color: str) -> QPushButton:
        btn = QPushButton()
        btn.setMinimumWidth(118)
        self._set_color_button(btn, color)
        return btn

    def _set_color_button(self, button: QPushButton, color: str) -> None:
        color = normalise_hex_color(color, "#888888")
        qcolor = QColor(color)
        luminance = qcolor.red() * 0.299 + qcolor.green() * 0.587 + qcolor.blue() * 0.114
        text_color = "#ffffff" if luminance < 150 else "#17232a"
        button.setProperty("hexColor", color)
        button.setText(color.upper())
        button.setStyleSheet(
            f"background:{color}; color:{text_color}; border:1px solid #203040; border-radius:8px; padding:7px 12px;"
        )

    def _pick_25d_color(self, button: QPushButton, title: str) -> None:
        current = QColor(button.property("hexColor") or "#888888")
        color = QColorDialog.getColor(current, self, title)
        if color.isValid():
            self._set_color_button(button, color.name())

    def show_25d_panel(self) -> None:
        self.show_panel("2.5d")

    def show_panel(self, tab_name: str) -> None:
        name = tab_name.lower()
        if "template" in name or "gallery" in name:
            self.tabs.setCurrentIndex(1)
            if hasattr(self, "layout_sub_tabs"):
                self.layout_sub_tabs.setCurrentIndex(0)
        elif "isometric" in name:
            self.tabs.setCurrentIndex(1)
            if hasattr(self, "layout_sub_tabs"):
                self.layout_sub_tabs.setCurrentIndex(2)
        elif "layout" in name or "sheet" in name or "manager" in name:
            self.tabs.setCurrentIndex(1)
            if hasattr(self, "layout_sub_tabs"):
                self.layout_sub_tabs.setCurrentIndex(1)
        elif "processing" in name or "module" in name or "hub" in name:
            self.tabs.setCurrentIndex(2)
        else:
            self.tabs.setCurrentIndex(0)
            if hasattr(self, "symbology_sub_tabs"):
                if "2.5d" in name:
                    self.symbology_sub_tabs.setCurrentIndex(1)
                    self._refresh_25d_layers()
                elif "thematic" in name or "bivariate" in name:
                    self.symbology_sub_tabs.setCurrentIndex(2)
                elif "palette" in name or "accessibility" in name or "inspector" in name:
                    self.symbology_sub_tabs.setCurrentIndex(3)
                else:
                    self.symbology_sub_tabs.setCurrentIndex(0)
                    self._refresh_qs_layers()

    # ── Quick Style panel ─────────────────────────────────────────────

    def _vector_layers(self):
        return [lyr for lyr in QgsProject.instance().mapLayers().values()
                if lyr.type() == QgsMapLayer.LayerType.VectorLayer]

    def _build_quick_style_contents(self, outer: QVBoxLayout) -> None:
        gb = self._make_group("Quick Style — one-click thematic styling")
        g = QGridLayout(gb)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)

        intro = QLabel(
            "Style any vector layer instantly: pick a field and a palette, and "
            "CartoLab classifies numeric fields into a graduated map or text "
            "fields into categories — with colour-blind-safe palettes built in."
        )
        intro.setWordWrap(True)
        g.addWidget(intro, 0, 0, 1, 2)

        g.addWidget(QLabel("Layer:"), 1, 0)
        self.qs_layer_combo = QComboBox()
        self.qs_layer_combo.currentIndexChanged.connect(self._refresh_qs_fields)
        g.addWidget(self.qs_layer_combo, 1, 1)

        g.addWidget(QLabel("Field:"), 2, 0)
        self.qs_field_combo = QComboBox()
        g.addWidget(self.qs_field_combo, 2, 1)

        g.addWidget(QLabel("Style as:"), 3, 0)
        self.qs_mode_combo = QComboBox()
        self.qs_mode_combo.addItems(["Auto", "Graduated (numeric)", "Categorized (unique)"])
        g.addWidget(self.qs_mode_combo, 3, 1)

        g.addWidget(QLabel("Classes:"), 4, 0)
        self.qs_classes_spin = QSpinBox()
        self.qs_classes_spin.setRange(2, 12)
        self.qs_classes_spin.setValue(5)
        self.qs_classes_spin.valueChanged.connect(self._update_qs_preview)
        g.addWidget(self.qs_classes_spin, 4, 1)

        g.addWidget(QLabel("Break method:"), 5, 0)
        self.qs_method_combo = QComboBox()
        self.qs_method_combo.addItems([
            "Quantile (equal count)",
            "Equal interval",
            "Geometric interval",
            "Natural Breaks (Fisher-Jenks)",
            "Head/Tail Breaks (power-law)",
            "Standard Deviation",
            "Maximum Breaks (largest gaps)",
            "Pretty Breaks (nice round numbers)",
        ])
        g.addWidget(self.qs_method_combo, 5, 1)

        g.addWidget(QLabel("Palette type:"), 6, 0)
        self.qs_kind_combo = QComboBox()
        self.qs_kind_combo.addItems(["All Palette Types", "Sequential", "Diverging", "Qualitative"])
        self.qs_kind_combo.currentIndexChanged.connect(self._populate_qs_palettes)
        g.addWidget(self.qs_kind_combo, 6, 1)

        g.addWidget(QLabel("Palette:"), 7, 0)
        self.qs_palette_combo = QComboBox()
        self.qs_palette_combo.currentIndexChanged.connect(self._update_qs_preview)
        g.addWidget(self.qs_palette_combo, 7, 1)

        # Discrete Swatch Bar & Metadata Badge
        preview_container = QWidget()
        pv_layout = QVBoxLayout(preview_container)
        pv_layout.setContentsMargins(0, 0, 0, 0)
        pv_layout.setSpacing(4)

        self.qs_preview_info = QLabel("Palette Info: -")
        self.qs_preview_info.setStyleSheet("color: #2b4d57; font-size: 11px; font-weight: bold;")
        pv_layout.addWidget(self.qs_preview_info)

        self.qs_swatch_host = QWidget()
        self.qs_swatch_layout = QHBoxLayout(self.qs_swatch_host)
        self.qs_swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.qs_swatch_layout.setSpacing(2)

        self.qs_preview = QFrame()
        self.qs_preview.setMinimumHeight(24)
        self.qs_preview.setStyleSheet("border-radius:4px;border:1px solid #cfdee2;")
        pv_layout.addWidget(self.qs_preview)
        pv_layout.addWidget(self.qs_swatch_host)

        g.addWidget(preview_container, 8, 1)

        opts = QHBoxLayout()
        self.qs_cbsafe_check = QCheckBox("Colour-blind safe only 🟢")
        self.qs_cbsafe_check.toggled.connect(self._populate_qs_palettes)
        self.qs_reverse_check = QCheckBox("Reverse")
        self.qs_reverse_check.toggled.connect(self._update_qs_preview)
        self.qs_outline_check = QCheckBox("White outline")
        self.qs_outline_check.setChecked(True)
        self.qs_live_check = QCheckBox("Live Auto-Apply ⚡")
        self.qs_live_check.toggled.connect(self._on_live_check_toggled)
        opts.addWidget(self.qs_cbsafe_check)
        opts.addWidget(self.qs_reverse_check)
        opts.addWidget(self.qs_outline_check)
        opts.addWidget(self.qs_live_check)
        opts.addStretch()
        g.addLayout(opts, 9, 0, 1, 2)

        btn_box = QHBoxLayout()
        btn = QPushButton("Apply Quick Style")
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(self._on_apply_quick_style)
        btn_box.addWidget(btn, 2)

        btn_qml = QPushButton("💾 Export QML Style")
        btn_qml.setObjectName("ghost")
        btn_qml.clicked.connect(self._on_export_qml_style)
        btn_box.addWidget(btn_qml, 1)

        g.addLayout(btn_box, 10, 0, 1, 2)

        outer.addWidget(gb)
        outer.addStretch()

        self._populate_qs_palettes()
        self._refresh_qs_layers()


    def _populate_qs_palettes(self) -> None:
        from ..core import palettes as _pal
        if not hasattr(self, "qs_palette_combo"):
            return
        current = self.qs_palette_combo.currentText()
        cb_only = self.qs_cbsafe_check.isChecked()
        kind_filter = (self.qs_kind_combo.currentText() or "").lower()

        names = []
        for n in _pal.ordered_names():
            meta = _pal.PALETTES.get(n, {})
            p_kind = meta.get("kind", "").lower()
            p_cb = meta.get("cb_safe", False)
            if cb_only and not p_cb:
                continue
            if kind_filter in ("sequential", "diverging", "qualitative") and p_kind != kind_filter:
                continue
            names.append(n)

        self.qs_palette_combo.blockSignals(True)
        self.qs_palette_combo.clear()
        for n in names:
            meta = _pal.PALETTES.get(n, {})
            badge = "🟢 Safe" if meta.get("cb_safe") else "⚠️ Normal"
            kind_txt = meta.get("kind", "sequential").capitalize()
            self.qs_palette_combo.addItem(f"{n}  ({kind_txt} · {badge})", n)

        for i in range(self.qs_palette_combo.count()):
            if self.qs_palette_combo.itemData(i) == current:
                self.qs_palette_combo.setCurrentIndex(i)
                break
        self.qs_palette_combo.blockSignals(False)
        self._update_qs_preview()

    def _on_live_check_toggled(self, checked: bool) -> None:
        if checked:
            self._on_apply_quick_style()

    def _on_export_qml_style(self) -> None:
        layer = self._layer_by_id(self.qs_layer_combo.currentData())
        if layer is None:
            QMessageBox.information(self, "Export QML", "Select a vector layer first.")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Layer Style (.qml)", f"{layer.name()}_style.qml", "QGIS Layer Style (*.qml)"
        )
        if filename:
            msg, ok = layer.saveNamedStyle(filename)
            if ok:
                if hasattr(self, "iface") and self.iface:
                    self.iface.messageBar().pushSuccess("CartoLab", f"Layer style saved -> {filename}")
            else:
                QMessageBox.warning(self, "Export QML", f"Failed to save style: {msg}")

    def _update_qs_preview(self) -> None:
        from ..core import palettes as _pal
        if not hasattr(self, "qs_preview"):
            return
        name = self.qs_palette_combo.currentData()
        if not name:
            return
        meta = _pal.PALETTES.get(name, {})
        n = max(2, self.qs_classes_spin.value())
        cols = _pal.get_palette(name, n)
        if self.qs_reverse_check.isChecked():
            cols = list(reversed(cols))

        stops = ", ".join(
            f"stop:{i / (len(cols) - 1):.3f} {c}" for i, c in enumerate(cols))
        self.qs_preview.setStyleSheet(
            "border-radius:4px;border:1px solid #cfdee2;"
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,{stops});")

        # Update metadata badge info
        cb_badge = "🟢 Colorblind Safe" if meta.get("cb_safe") else "⚠️ General Use"
        kind_str = meta.get("kind", "Sequential").capitalize()

        from ..core.color_accessibility import evaluate_palette_accessibility
        eval_acc = evaluate_palette_accessibility(cols)
        rating_str = eval_acc.get("rating", "Standard")
        end_contrast = eval_acc.get("endpoint_contrast", 1.0)

        self.qs_preview_info.setText(
            f"Palette: <b>{name}</b> ({kind_str})  ·  {cb_badge}  ·  "
            f"WCAG: <b>{rating_str}</b> ({end_contrast}:1)  ·  <b>{len(cols)} classes</b>"
        )

        # Populate discrete swatch blocks
        while self.qs_swatch_layout.count():
            item = self.qs_swatch_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for c in cols:
            block = QFrame()
            block.setFixedHeight(12)
            block.setToolTip(c)
            block.setStyleSheet(f"background: {c}; border-radius: 2px; border: 1px solid #778899;")
            self.qs_swatch_layout.addWidget(block, 1)

        if hasattr(self, "qs_live_check") and self.qs_live_check.isChecked():
            self._on_apply_quick_style()


    def _on_25d_auto_estimate_height(self) -> None:
        """Automatically detect floor count field and set floor mode with 3.2m default floor height."""
        from ..core.qgis_25d_style import looks_like_floor_count_field, HEIGHT_MODE_FLOOR_COUNT
        field_name = self.height25d_combo.currentData() or ""
        idx = self.mode25d_combo.findData(HEIGHT_MODE_FLOOR_COUNT)
        if idx >= 0:
            self.mode25d_combo.setCurrentIndex(idx)
        self.floor_height25d_spin.setValue(3.2)
        if hasattr(self, "iface") and self.iface:
            self.iface.messageBar().pushInfo(
                "CartoLab",
                f"Floor mode activated: estimating 3.2 map units per floor for field '{field_name}'."
            )
        self._update_25d_status_preview()

    def _refresh_qs_layers(self) -> None:

        if not hasattr(self, "qs_layer_combo"):
            return
        current = self.qs_layer_combo.currentData()
        self.qs_layer_combo.blockSignals(True)
        self.qs_layer_combo.clear()
        for lyr in self._vector_layers():
            self.qs_layer_combo.addItem(lyr.name(), lyr.id())
        if current is not None:
            idx = self.qs_layer_combo.findData(current)
            if idx >= 0:
                self.qs_layer_combo.setCurrentIndex(idx)
        self.qs_layer_combo.blockSignals(False)
        self._refresh_qs_fields()

    def _refresh_qs_fields(self) -> None:
        if not hasattr(self, "qs_field_combo"):
            return
        self.qs_field_combo.clear()
        layer = self._layer_by_id(self.qs_layer_combo.currentData())
        if layer is None:
            return
        for f in layer.fields():
            self.qs_field_combo.addItem(f.name())

    def _on_apply_quick_style(self) -> None:
        from ..core import palettes as _pal
        if processing is None:
            QMessageBox.warning(self, "Quick Style", "Processing framework unavailable.")
            return
        layer = self._layer_by_id(self.qs_layer_combo.currentData())
        if layer is None:
            QMessageBox.information(self, "Quick Style", "Load and select a vector layer.")
            return
        field = self.qs_field_combo.currentText()
        if not field:
            QMessageBox.information(self, "Quick Style", "Select a field to style.")
            return
        palette = self.qs_palette_combo.currentData() or _pal.default_palette()
        try:
            pidx = _pal.ordered_names().index(palette)
        except ValueError:
            pidx = 0
        params = {
            "INPUT": layer,
            "FIELD": field,
            "MODE": self.qs_mode_combo.currentIndex(),
            "CLASSES": self.qs_classes_spin.value(),
            "METHOD": self.qs_method_combo.currentIndex(),
            "PALETTE": pidx,
            "REVERSE": self.qs_reverse_check.isChecked(),
            "OUTLINE": self.qs_outline_check.isChecked(),
        }
        try:
            res = processing.run("zero2cartolab:quick_style", params)
        except Exception as exc:
            QMessageBox.critical(self, "Quick Style", str(exc))
            return
        with suppress(Exception):
            if hasattr(self.iface, "layerTreeView"):
                self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        layer.triggerRepaint()
        self.iface.messageBar().pushSuccess(
            "02CartoLab", res.get("SUMMARY", "Quick Style applied."))

    def _polygon_layers(self):
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if (layer.type() == QgsMapLayer.LayerType.VectorLayer
                    and hasattr(layer, "geometryType")
                    and layer.geometryType() == 2):
                layers.append(layer)
        return layers

    def _layer_by_id(self, layer_id: str):
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    def _selected_25d_layer(self):
        if not hasattr(self, "layer25d_combo"):
            return None
        return self._layer_by_id(self.layer25d_combo.currentData())

    def _refresh_25d_layers(self) -> None:
        if not hasattr(self, "layer25d_combo"):
            return
        current = self.layer25d_combo.currentData()
        self.layer25d_combo.blockSignals(True)
        self.layer25d_combo.clear()
        for layer in self._polygon_layers():
            self.layer25d_combo.addItem(layer.name(), layer.id())
        if current:
            idx = self.layer25d_combo.findData(current)
            if idx >= 0:
                self.layer25d_combo.setCurrentIndex(idx)
        self.layer25d_combo.blockSignals(False)
        self._refresh_25d_fields()

    def _refresh_25d_fields(self) -> None:
        if not hasattr(self, "height25d_combo"):
            return
        layer = self._selected_25d_layer()
        current = self.height25d_combo.currentData()
        self.height25d_combo.blockSignals(True)
        self.height25d_combo.clear()
        if layer:
            fields = list(layer.fields())
            numeric_fields = [f for f in fields if field_is_numeric(f)]
            floor_fields = [f for f in fields if looks_like_floor_count_field(f.name())]
            candidate_fields = []
            for field in numeric_fields + floor_fields:
                if field.name() not in [existing.name() for existing in candidate_fields]:
                    candidate_fields.append(field)
            for field in candidate_fields or fields:
                self.height25d_combo.addItem(field.name(), field.name())
            preferred = [
                "Kat_Sayisi", "KatSayisi", "kat_sayisi", "floors", "floor_count",
                "Hmax", "Height", "height", "Heights", "building_height", "Yukseklik",
            ]
            target = current if current else next((name for name in preferred if self.height25d_combo.findData(name) >= 0), None)
            if target:
                idx = self.height25d_combo.findData(target)
                if idx >= 0:
                    self.height25d_combo.setCurrentIndex(idx)
        self.height25d_combo.blockSignals(False)
        self._on_25d_height_field_changed()
        self._update_25d_status_preview()

    def _on_25d_height_field_changed(self) -> None:
        if not hasattr(self, "mode25d_combo"):
            return
        field_name = self.height25d_combo.currentData() or ""
        if looks_like_floor_count_field(field_name):
            idx = self.mode25d_combo.findData(HEIGHT_MODE_FLOOR_COUNT)
            if idx >= 0:
                self.mode25d_combo.setCurrentIndex(idx)
        self._update_25d_status_preview()

    def _on_25d_mode_changed(self) -> None:
        if not hasattr(self, "floor_height25d_label"):
            return
        is_floor_mode = self.mode25d_combo.currentData() == HEIGHT_MODE_FLOOR_COUNT
        self.floor_height25d_label.setVisible(is_floor_mode)
        self.floor_height25d_spin.setVisible(is_floor_mode)
        if hasattr(self, "floor_bands25d_check"):
            self.floor_bands25d_check.setEnabled(is_floor_mode)
            if not is_floor_mode:
                self.floor_bands25d_check.setChecked(False)
            self._on_25d_floor_bands_changed()
        if is_floor_mode:
            self.step25d_check.setChecked(False)
        self._update_25d_status_preview()

    def _on_25d_floor_bands_changed(self) -> None:
        if not hasattr(self, "floor_palette25d_combo"):
            return
        is_floor_mode = self.mode25d_combo.currentData() == HEIGHT_MODE_FLOOR_COUNT
        enabled = bool(self.floor_bands25d_check.isChecked() and is_floor_mode)
        self.floor_palette25d_label.setVisible(enabled)
        self.floor_palette25d_combo.setVisible(enabled)
        self.max_floors25d_label.setVisible(enabled)
        self.max_floors25d_spin.setVisible(enabled)
        self.step25d_check.setEnabled(not enabled)
        self.step25d_spin.setEnabled(not enabled)
        if enabled:
            self.step25d_check.setChecked(False)
        self._update_25d_status_preview()

    def _on_25d_preset_changed(self) -> None:
        if not hasattr(self, "preset25d_combo"):
            return
        preset_key = self.preset25d_combo.currentData() or "warm_civic"
        preset = STYLE_25D_PRESETS.get(preset_key, STYLE_25D_PRESETS["warm_civic"])
        self._set_color_button(self.roof25d_btn, preset["roof"])
        self._set_color_button(self.wall25d_btn, preset["wall"])
        self._set_color_button(self.shadow25d_btn, preset["shadow"])
        self.shadow_spread25d_spin.setValue(float(preset["shadow_spread"]))
        self._update_25d_status_preview()

    def _current_25d_config(self) -> Style25DConfig:
        height_field = self.height25d_combo.currentData()
        if not height_field:
            raise ValueError("Select a numeric height field.")
        return Style25DConfig(
            height_field=height_field,
            preset=self.preset25d_combo.currentData() or "warm_civic",
            roof_color=normalise_hex_color(self.roof25d_btn.property("hexColor"), "#f2cf96"),
            wall_color=normalise_hex_color(self.wall25d_btn.property("hexColor"), "#b36f43"),
            shadow_color=normalise_hex_color(self.shadow25d_btn.property("hexColor"), "#202833"),
            angle=self.angle25d_spin.value(),
            height_scale=self.scale25d_spin.value(),
            max_height=self.max25d_spin.value(),
            stepped=self.step25d_check.isChecked(),
            step_height=self.step25d_spin.value(),
            shadow_enabled=self.shadow25d_check.isChecked(),
            shadow_spread=self.shadow_spread25d_spin.value(),
            wall_shading=self.wall_shading25d_check.isChecked(),
            height_mode=self.mode25d_combo.currentData() or HEIGHT_MODE_HEIGHT,
            floor_height=self.floor_height25d_spin.value(),
            render_mode=RENDER_MODE_FLOOR_BANDS if self.floor_bands25d_check.isChecked() else RENDER_MODE_NATIVE,
            floor_palette=self.floor_palette25d_combo.currentData() or "civic_spectrum",
            max_floors=self.max_floors25d_spin.value(),
        )

    def _update_25d_status_preview(self) -> None:
        if not hasattr(self, "style25d_status"):
            return
        layer = self._selected_25d_layer()
        if not layer:
            self.style25d_status.setPlainText("Load or select a polygon layer to apply 2.5D styling.")
            return
        try:
            summary = build_style_summary(layer.name(), self._current_25d_config())
        except Exception as exc:
            summary = str(exc)
        self.style25d_status.setPlainText(summary)

    def _on_apply_sun_lighting(self) -> None:
        try:
            from ..core.sun_lighting import solar_to_25d_lighting
            preset = self.solar_time_combo.currentData() or "afternoon_studio"
            res = solar_to_25d_lighting(latitude_deg=38.4, season="equinox", time_preset=preset)
            self.angle25d_spin.setValue(res["solar_altitude_deg"])
            self.shadow_spread25d_spin.setValue(res["shadow_length_mult"])
            self._update_25d_status_preview()
            if hasattr(self, "iface") and self.iface:
                self.iface.messageBar().pushSuccess("CartoLab", f"Applied {res['description']}.")
        except Exception as exc:
            QMessageBox.critical(self, "Solar Calculation Error", str(exc))

    def _on_apply_25d_style(self) -> None:
        layer = self._selected_25d_layer()
        try:
            summary = apply_25d_renderer(layer, self._current_25d_config())
            if hasattr(self.iface, "layerTreeView"):
                self.iface.layerTreeView().refreshLayerSymbology(layer.id())
            self.style25d_status.setPlainText(summary)
            self.iface.messageBar().pushSuccess("CartoLab", f"2.5D style applied to {layer.name()}.")
        except Exception as exc:
            QMessageBox.critical(self, "2.5D Styling Error", str(exc))

    def _on_save_25d_qml(self) -> None:
        layer = self._selected_25d_layer()
        if not layer:
            QMessageBox.warning(self, "Save QML Style", "Select a polygon layer first.")
            return
        default_name = f"{layer.name()}_planx_25d.qml".replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save QGIS Layer Style",
            os.path.join(os.path.expanduser("~"), "Desktop", default_name),
            "QGIS Layer Style (*.qml)",
        )
        if not path:
            return
        if not path.lower().endswith(".qml"):
            path += ".qml"
        try:
            apply_25d_renderer(layer, self._current_25d_config())
            message, ok = layer.saveNamedStyle(path)
            if not ok:
                raise RuntimeError(message)
            self.iface.messageBar().pushSuccess("CartoLab", f"QML style saved: {path}")
            self.style25d_status.append(f"\nSaved QML style: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save QML Style", str(exc))

    def _on_copy_25d_summary(self) -> None:
        self._update_25d_status_preview()
        QApplication.clipboard().setText(self.style25d_status.toPlainText())
        self.iface.messageBar().pushSuccess("CartoLab", "2.5D style summary copied to clipboard.")

    def _build_layout_tab(self) -> None:
        """Workspace 2: Layout Automation Studio (Templates Gallery, Custom Map Sheet, Isometric Stacker)."""
        studio_widget = QWidget()
        layout = QVBoxLayout(studio_widget)
        layout.setContentsMargins(6, 6, 6, 6)

        self.layout_sub_tabs = QTabWidget()
        self.layout_sub_tabs.setUsesScrollButtons(True)
        with suppress(Exception):
            _ElideNone = getattr(getattr(Qt, "TextElideMode", Qt), "ElideNone", getattr(Qt, "ElideNone", 0))
            self.layout_sub_tabs.tabBar().setElideMode(_ElideNone)
            self.layout_sub_tabs.tabBar().setExpanding(False)

        # Sub-tab 1: Layout Templates Gallery
        templates_widget = self._build_template_gallery_subwidget()
        self.layout_sub_tabs.addTab(templates_widget, _cartolab_icon("layout.png"), "Template Gallery")
        self.layout_sub_tabs.setTabToolTip(0, "Publication Layout Templates: Report Figure, Academic Journal, Poster, Fact Sheet, Diptych")

        # Sub-tab 2: Custom Map Sheet & Manager
        mapsheet_widget = self._build_custom_mapsheet_subwidget()
        self.layout_sub_tabs.addTab(mapsheet_widget, _cartolab_icon("grid.png"), "Map Sheet Studio")
        self.layout_sub_tabs.setTabToolTip(1, "Auto Map Sheet Builder, Layout Manager & Decorators")

        # Sub-tab 3: Isometric 3D Stacker
        iso_widget = self._build_isometric_stacker_subwidget()
        self.layout_sub_tabs.addTab(iso_widget, _cartolab_icon("isometric.png"), "3D Isometric Stacker")
        self.layout_sub_tabs.setTabToolTip(2, "3D Isometric Layer Stacker: Multi-layer perspective assembly")

        layout.addWidget(self.layout_sub_tabs)
        self.stack.addWidget(studio_widget)
        self._refresh_layout_combo()

    def _build_template_gallery_subwidget(self) -> QWidget:
        """Workspace 2 (Sub-tab 1): Interactive Layout Template Gallery with visual archetype cards."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(14)

        intro = QLabel(
            "<b>PlanX CartoLab Layout Template Gallery</b> — Select a publication archetype below to generate "
            "a complete, mathematically balanced print layout ready for report publishing, peer-reviewed journals, "
            "exhibitions, briefings, or comparative urban analysis in one click."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; font-size: 12px; margin-bottom: 4px;")
        lyt.addWidget(intro)

        self.template_card_inputs = {}

        from ..layout.template_gallery import TEMPLATE_GALLERY

        for tkey, tmeta in TEMPLATE_GALLERY.items():
            card = QGroupBox()
            card.setObjectName(f"templateCard_{tkey}")
            card.setStyleSheet(
                "QGroupBox { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; "
                "margin-top: 10px; padding: 12px; }"
                "QGroupBox:hover { border: 1px solid #94a3b8; }"
            )
            cv = QVBoxLayout(card)
            cv.setContentsMargins(10, 10, 10, 10)
            cv.setSpacing(8)

            # Header row: Icon + Title + Category Chip
            hdr = QHBoxLayout()
            ic_lbl = QLabel()
            ic_lbl.setPixmap(_hidpi_icon_pixmap(_cartolab_icon(tmeta.get("icon", "layout.png")), 24, 24, ic_lbl))
            hdr.addWidget(ic_lbl)

            t_name = QLabel(f"<b>{tmeta['name']}</b>")
            t_name.setStyleSheet("font-size: 14px; color: #0f172a;")
            hdr.addWidget(t_name, 1)

            chip = QLabel(tmeta.get("category", "Layout"))
            chip.setStyleSheet(
                "background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; "
                "border-radius: 4px; padding: 2px 8px; font-weight: 700; font-size: 10px;"
            )
            hdr.addWidget(chip, 0, Qt.AlignmentFlag.AlignRight)
            cv.addLayout(hdr)

            # Tagline & Description
            tagline = QLabel(f"<i>{tmeta['tagline']}</i>")
            tagline.setStyleSheet("color: #475569; font-size: 11px;")
            cv.addWidget(tagline)

            desc = QLabel(tmeta["description"])
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #334155; font-size: 11px;")
            cv.addWidget(desc)

            # Features Bullet Row
            feat_txt = "  •  ".join(tmeta.get("features", []))
            feat_lbl = QLabel(f"<span style='color:#059669;'>✓</span> {feat_txt}")
            feat_lbl.setStyleSheet("color: #059669; font-size: 10.5px; font-weight: 600;")
            feat_lbl.setWordWrap(True)
            cv.addWidget(feat_lbl)

            # Configuration Form Grid
            cfg_grid = QGridLayout()
            cfg_grid.setSpacing(6)

            cfg_grid.addWidget(QLabel("Title:"), 0, 0)
            in_title = QLineEdit(tmeta["name"])
            cfg_grid.addWidget(in_title, 0, 1, 1, 3)

            cfg_grid.addWidget(QLabel("Subtitle:"), 1, 0)
            in_sub = QLineEdit(tmeta["tagline"])
            cfg_grid.addWidget(in_sub, 1, 1, 1, 3)

            cfg_grid.addWidget(QLabel("Credits:"), 2, 0)
            in_cred = QLineEdit("PlanX CartoLab · Urban Analytics Studio")
            cfg_grid.addWidget(in_cred, 2, 1, 1, 3)

            cfg_grid.addWidget(QLabel("Page Size:"), 3, 0)
            combo_size = QComboBox()
            combo_size.addItems(["A4", "A3", "A2", "A1", "A0"])
            def_page = tmeta.get("default_page", "A4")
            s_idx = combo_size.findText(def_page)
            if s_idx >= 0:
                combo_size.setCurrentIndex(s_idx)
            cfg_grid.addWidget(combo_size, 3, 1)

            cfg_grid.addWidget(QLabel("Orientation:"), 3, 2)
            combo_orient = QComboBox()
            combo_orient.addItems(["Landscape", "Portrait"])
            combo_orient.setCurrentIndex(0 if tmeta.get("default_landscape", True) else 1)
            cfg_grid.addWidget(combo_orient, 3, 3)

            cfg_grid.addWidget(QLabel("Paper Theme:"), 4, 0)
            combo_theme = QComboBox()
            combo_theme.addItem("Modern Swiss Minimalist", "swiss_modern")
            combo_theme.addItem("Architectural Blueprint", "blueprint")
            combo_theme.addItem("Dark Matter / Obsidian Urban", "dark_matter")
            combo_theme.addItem("Vintage Sepia Atlas", "sepia_atlas")
            combo_theme.addItem("Warm Editorial Newsprint", "warm_editorial")
            combo_theme.addItem("Japanese Washi Minimal", "japanese_washi")
            def_theme = tmeta.get("theme", "swiss_modern")
            t_idx = combo_theme.findData(def_theme)
            if t_idx >= 0:
                combo_theme.setCurrentIndex(t_idx)
            cfg_grid.addWidget(combo_theme, 4, 1, 1, 3)

            cv.addLayout(cfg_grid)

            # Action Button
            btn_create = QPushButton(f"Create {tmeta['name']} ⚡")
            btn_create.setIcon(_cartolab_icon(tmeta.get("icon", "layout.png")))
            btn_create.clicked.connect(lambda _, k=tkey: self._on_create_template_from_card(k))
            cv.addWidget(btn_create, 0, Qt.AlignmentFlag.AlignRight)

            self.template_card_inputs[tkey] = {
                "title": in_title,
                "subtitle": in_sub,
                "credits": in_cred,
                "page_size": combo_size,
                "orientation": combo_orient,
                "theme": combo_theme,
            }

            lyt.addWidget(card)

        lyt.addStretch()
        return scroll

    def _on_create_template_from_card(self, template_id: str) -> None:
        if not QgsProject.instance().mapLayers():
            QMessageBox.warning(
                self, "Layout Template",
                "No layers are loaded — the map frame would be empty. Load a layer first."
            )
            return
        inputs = self.template_card_inputs.get(template_id, {})
        title = inputs.get("title").text().strip() if inputs.get("title") else ""
        subtitle = inputs.get("subtitle").text().strip() if inputs.get("subtitle") else ""
        credits = inputs.get("credits").text().strip() if inputs.get("credits") else ""
        page_size = inputs.get("page_size").currentText() if inputs.get("page_size") else "A4"
        landscape = (inputs.get("orientation").currentText() == "Landscape") if inputs.get("orientation") else True
        theme = inputs.get("theme").currentData() if inputs.get("theme") else "swiss_modern"

        try:
            from ..layout.template_gallery import create_template_layout
            layout = create_template_layout(
                template_id=template_id,
                iface=self.iface,
                project=QgsProject.instance(),
                title=title,
                subtitle=subtitle,
                credits=credits,
                page_size=page_size,
                landscape=landscape,
                theme=theme,
            )
            self._refresh_layout_combo()
            if hasattr(self, "layout_combo"):
                self.layout_combo.setCurrentText(layout.name())
            self._open_in_designer(layout)
            if hasattr(self, "iface") and self.iface:
                self.iface.messageBar().pushSuccess(
                    "CartoLab", f"Template '{layout.name()}' created and opened in Layout Designer."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Template Error", f"Failed to create template layout:\n{exc}")

    def _build_custom_mapsheet_subwidget(self) -> QWidget:
        """Workspace 2 (Sub-tab 2): Granular Custom Map Sheet builder, Layout Manager & Decorators."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        # ── Group 1: Auto Map Sheet ──────────────────────────────────
        gb_sheet = self._make_group("Auto Map Sheet — one-click publication layout")
        gs = QVBoxLayout(gb_sheet)
        intro = QLabel(
            "Build a finished print layout from the current map view: titled "
            "map frame at the current extent, legend, scale bar, north arrow, "
            "grid and credits. Opens straight in the Layout Designer."
        )
        intro.setWordWrap(True)
        gs.addWidget(intro)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.addWidget(QLabel("Title:"), 0, 0)
        self.mapsheet_title = QLineEdit()
        self.mapsheet_title.setPlaceholderText("(defaults to the project title)")
        form.addWidget(self.mapsheet_title, 0, 1, 1, 3)

        form.addWidget(QLabel("Credits:"), 1, 0)
        self.mapsheet_credits = QLineEdit()
        self.mapsheet_credits.setPlaceholderText("Data source, author, date…")
        form.addWidget(self.mapsheet_credits, 1, 1, 1, 3)

        form.addWidget(QLabel("Page Preset:"), 2, 0)
        self.mapsheet_preset_combo = QComboBox()
        self.mapsheet_preset_combo.addItem("A4 Landscape (Publication Standard)", ("A4", "Landscape"))
        self.mapsheet_preset_combo.addItem("A3 Landscape (Masterplan Scale)", ("A3", "Landscape"))
        self.mapsheet_preset_combo.addItem("Square 1:1 (Portfolio & Social Media)", ("A4", "Square"))
        self.mapsheet_preset_combo.addItem("A4 Portrait (Technical Report)", ("A4", "Portrait"))
        self.mapsheet_preset_combo.currentIndexChanged.connect(self._on_layout_preset_changed)
        form.addWidget(self.mapsheet_preset_combo, 2, 1, 1, 3)

        form.addWidget(QLabel("Size:"), 3, 0)
        self.mapsheet_page_combo = QComboBox()
        self.mapsheet_page_combo.addItems(["A4", "A3", "A2", "A1", "A0"])
        form.addWidget(self.mapsheet_page_combo, 3, 1)
        form.addWidget(QLabel("Orientation:"), 3, 2)
        self.mapsheet_orient_combo = QComboBox()
        self.mapsheet_orient_combo.addItems(["Landscape", "Portrait", "Square"])
        form.addWidget(self.mapsheet_orient_combo, 3, 3)
        gs.addLayout(form)

        el_row = QHBoxLayout()
        el_row.addWidget(QLabel("Include:"))
        self.cb_title = QCheckBox("Title")
        self.cb_legend = QCheckBox("Legend")
        self.cb_scalebar = QCheckBox("Scale bar")
        self.cb_north = QCheckBox("North arrow")
        self.cb_grid = QCheckBox("Grid")
        for cb in (self.cb_title, self.cb_legend, self.cb_scalebar, self.cb_north):
            cb.setChecked(True)
            el_row.addWidget(cb)
        self.cb_grid.setChecked(False)
        el_row.addWidget(self.cb_grid)
        el_row.addStretch()
        gs.addLayout(el_row)

        btn_sheet = QPushButton("Create Map Sheet from Current View")
        btn_sheet.setIcon(_cartolab_icon("layout.png"))
        btn_sheet.setToolTip("Assemble a complete print layout and open it in the designer")
        btn_sheet.clicked.connect(self._on_create_map_sheet)
        gs.addWidget(btn_sheet)
        lyt.addWidget(gb_sheet)

        # ── Group 2: Layout Manager ──────────────────────────────────
        gb_mgr = self._make_group("Layout Manager")
        gm = QVBoxLayout(gb_mgr)
        pick = QHBoxLayout()
        pick.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pick.addWidget(self.layout_combo, 1)
        btn_refresh_layouts = QPushButton("↻")
        btn_refresh_layouts.setToolTip("Refresh layout list")
        btn_refresh_layouts.setMaximumWidth(36)
        btn_refresh_layouts.clicked.connect(self._refresh_layout_combo)
        pick.addWidget(btn_refresh_layouts)
        gm.addLayout(pick)

        actions = QHBoxLayout()
        btn_open = QPushButton("Open in Designer")
        btn_open.setIcon(_cartolab_icon("layout.png"))
        btn_open.clicked.connect(self._on_open_designer)
        btn_dup = QPushButton("Duplicate")
        btn_dup.clicked.connect(self._on_duplicate_layout)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._on_delete_layout)
        for b in (btn_open, btn_dup, btn_del):
            actions.addWidget(b)
        gm.addLayout(actions)

        exports = QHBoxLayout()
        exports.addWidget(QLabel("Export:"))
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItem("PNG (Image)", "png")
        self.export_format_combo.addItem("PDF (Vector Document)", "pdf")
        self.export_format_combo.addItem("SVG (Scalable Vector)", "svg")
        exports.addWidget(self.export_format_combo, 1)
        exports.addWidget(QLabel("Quality / DPI:"))
        self.export_dpi_combo = QComboBox()
        for lbl, val in (("150 DPI · Quick Draft", 150),
                         ("300 DPI · Publication Standard", 300),
                         ("600 DPI · Ultra High Print", 600)):
            self.export_dpi_combo.addItem(lbl, val)
        self.export_dpi_combo.setCurrentIndex(1)
        exports.addWidget(self.export_dpi_combo)

        btn_export = QPushButton("Export File…")
        btn_export.setIcon(_cartolab_icon("layout.png"))
        btn_export.clicked.connect(self._on_export_layout)
        exports.addWidget(btn_export)

        btn_export_open = QPushButton("Export & Open ↗")
        btn_export_open.setIcon(_cartolab_icon("layout.png"))
        btn_export_open.setObjectName("ghost")
        btn_export_open.setToolTip("Export layout and open immediately in system default viewer")
        btn_export_open.clicked.connect(self._on_export_and_open_layout)
        exports.addWidget(btn_export_open)

        gm.addLayout(exports)
        lyt.addWidget(gb_mgr)

        # ── Group 3: Decorators (apply to the selected layout) ───────
        gb_dec = self._make_group("Decorators — enhance the selected layout")
        gd = QVBoxLayout(gb_dec)

        bivar_row = QHBoxLayout()
        bivar_row.addWidget(QLabel("Bivariate legend:"))
        self.bivar_palette_combo = QComboBox()
        self.bivar_palette_combo.addItem("Teal-Brown", "teal_brown")
        self.bivar_palette_combo.addItem("Purple-Green", "purple_green")
        self.bivar_palette_combo.addItem("Blue-Orange", "blue_orange")
        self.bivar_palette_combo.addItem("Pink-Green", "pink_green")
        bivar_row.addWidget(self.bivar_palette_combo, 1)
        self.bivar_legend_type_combo = QComboBox()
        self.bivar_legend_type_combo.addItem("Diamond", "diamond")
        self.bivar_legend_type_combo.addItem("Square", "square")
        bivar_row.addWidget(self.bivar_legend_type_combo, 1)
        gd.addLayout(bivar_row)
        btn_legend = QPushButton("Add Bivariate Legend to Selected Layout")
        btn_legend.setIcon(_cartolab_icon("bivariate.png"))
        btn_legend.clicked.connect(self._on_bivariate_legend)
        gd.addWidget(btn_legend)

        deco_row = QHBoxLayout()
        btn_typo = QPushButton("Apply Swiss Typography")
        btn_typo.setIcon(_cartolab_icon("layout.png"))
        btn_typo.clicked.connect(self._on_typography)
        btn_grid = QPushButton("Add / Refresh Minimalist Grid")
        btn_grid.setIcon(_cartolab_icon("grid.png"))
        btn_grid.clicked.connect(self._on_grid_style)
        btn_balance = QPushButton("Auto-Balance Margins")
        btn_balance.setIcon(_cartolab_icon("layout.png"))
        btn_balance.clicked.connect(self._on_balance_layout)
        deco_row.addWidget(btn_typo)
        deco_row.addWidget(btn_grid)
        deco_row.addWidget(btn_balance)
        gd.addLayout(deco_row)
        lyt.addWidget(gb_dec)

        for button in (btn_sheet, btn_legend, btn_typo, btn_grid, btn_balance):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lyt.addStretch()
        scroll.setWidget(w)
        return scroll

    def _build_isometric_stacker_subwidget(self) -> QWidget:
        """Workspace 2 (Sub-tab 3): Dedicated 3D Isometric Layer Stacker studio."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        gb_iso = self._make_group("3D Isometric Layer Stacking Studio")
        gd = QVBoxLayout(gb_iso)

        gd.addWidget(QLabel("Select 2+ layers from your project to assemble a layered isometric 3D stack:"))
        self.iso_layer_list = QListWidget()
        self.iso_layer_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.iso_layer_list.setMinimumHeight(140)
        gd.addWidget(self.iso_layer_list)

        btn_iso = QPushButton("Assemble 3D Isometric Print Layout ⚡")
        btn_iso.setIcon(_cartolab_icon("isometric.png"))
        btn_iso.clicked.connect(self._on_isometric_stack)
        btn_iso.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        gd.addWidget(btn_iso)

        lyt.addWidget(gb_iso)
        lyt.addStretch()
        scroll.setWidget(w)
        return scroll


    # ── Layout Manager helpers ───────────────────────────────────────

    def _refresh_layout_combo(self) -> None:
        """Repopulate the layout picker, preserving the current selection."""
        if not hasattr(self, "layout_combo"):
            return
        current = self.layout_combo.currentText()
        self.layout_combo.blockSignals(True)
        self.layout_combo.clear()
        names = [lay.name() for lay in QgsProject.instance().layoutManager().layouts()]
        self.layout_combo.addItems(sorted(names))
        if current in names:
            self.layout_combo.setCurrentText(current)
        self.layout_combo.blockSignals(False)

    def _selected_layout(self):
        """Return the QgsPrintLayout chosen in the picker, or None."""
        if not hasattr(self, "layout_combo"):
            return None
        name = self.layout_combo.currentText()
        if not name:
            return None
        return QgsProject.instance().layoutManager().layoutByName(name)

    def _require_layout(self, title: str):
        """Return the selected layout or show a helpful message and return None."""
        layout = self._selected_layout()
        if layout is None:
            QMessageBox.information(
                self, title,
                "No layout selected. Create a Map Sheet above, or pick an "
                "existing layout in the Layout Manager list.",
            )
        return layout

    def _bivar_colors(self):
        preset = self.bivar_palette_combo.currentData()
        return {
            "teal_brown": ("#e8e8e8", "#5ab4ac", "#d8b365", "#8c510a"),
            "purple_green": ("#e8e8e8", "#7fbf7b", "#af8dc3", "#762a83"),
            "blue_orange": ("#e8e8e8", "#fdae61", "#abd9e9", "#2c7bb6"),
            "pink_green": ("#e8e8e8", "#a1d76a", "#e9a3c9", "#c51b7d"),
        }.get(preset, ("#e8e8e8", "#5ab4ac", "#d8b365", "#8c510a"))

    def _open_in_designer(self, layout) -> None:
        with suppress(Exception):
            if hasattr(self.iface, "openLayoutDesigner"):
                self.iface.openLayoutDesigner(layout)

    # ── Layout Studio actions ────────────────────────────────────────

    def _on_create_map_sheet(self) -> None:
        if not QgsProject.instance().mapLayers():
            QMessageBox.warning(
                self, "Auto Map Sheet",
                "No layers are loaded — the map frame would be empty. "
                "Load a layer first.",
            )
            return
        try:
            from ..layout.map_sheet import create_map_sheet
            layout = create_map_sheet(
                iface=self.iface,
                title=self.mapsheet_title.text().strip(),
                credits=self.mapsheet_credits.text().strip(),
                page_size=self.mapsheet_page_combo.currentText(),
                landscape=(self.mapsheet_orient_combo.currentText() == "Landscape"),
                add_title=self.cb_title.isChecked(),
                add_legend=self.cb_legend.isChecked(),
                add_scalebar=self.cb_scalebar.isChecked(),
                add_north_arrow=self.cb_north.isChecked(),
                add_grid=self.cb_grid.isChecked(),
            )
            self._refresh_layout_combo()
            self.layout_combo.setCurrentText(layout.name())
            self._open_in_designer(layout)
            self.iface.messageBar().pushSuccess(
                "CartoLab", f"Map sheet '{layout.name()}' created.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Map Sheet Error", str(exc))

    def _on_open_designer(self) -> None:
        layout = self._require_layout("Open in Designer")
        if layout is not None:
            self._open_in_designer(layout)

    def _on_duplicate_layout(self) -> None:
        layout = self._require_layout("Duplicate Layout")
        if layout is None:
            return
        manager = QgsProject.instance().layoutManager()
        new_name = manager.generateUniqueTitle()
        try:
            dup = manager.duplicateLayout(layout, new_name)
        except Exception as exc:
            QMessageBox.critical(self, "Duplicate Layout", str(exc))
            return
        self._refresh_layout_combo()
        if dup is not None:
            self.layout_combo.setCurrentText(dup.name())
        self.iface.messageBar().pushSuccess("CartoLab", f"Duplicated to '{new_name}'.")

    def _on_delete_layout(self) -> None:
        layout = self._require_layout("Delete Layout")
        if layout is None:
            return
        name = layout.name()
        if QMessageBox.question(
            self, "Delete Layout",
            f"Delete layout '{name}'? This cannot be undone.",
        ) != QMessageBox.StandardButton.Yes:
            return
        QgsProject.instance().layoutManager().removeLayout(layout)
        self._refresh_layout_combo()
        self.iface.messageBar().pushSuccess("CartoLab", f"Deleted layout '{name}'.")

    def _on_layout_preset_changed(self) -> None:
        data = self.mapsheet_preset_combo.currentData()
        if not data:
            return
        page, orient = data
        idx_p = self.mapsheet_page_combo.findText(page)
        if idx_p >= 0:
            self.mapsheet_page_combo.setCurrentIndex(idx_p)
        idx_o = self.mapsheet_orient_combo.findText(orient)
        if idx_o >= 0:
            self.mapsheet_orient_combo.setCurrentIndex(idx_o)

    def _on_export_layout(self, _checked: bool = False) -> str | None:
        layout = self._require_layout("Export Layout")
        if layout is None:
            return None
        ext = self.export_format_combo.currentData()
        dpi = self.export_dpi_combo.currentData()
        filt = {
            "png": "PNG image (*.png)",
            "pdf": "PDF document (*.pdf)",
            "svg": "SVG image (*.svg)",
        }.get(ext, "PNG image (*.png)")
        safe = "".join(c if c.isalnum() else "_" for c in layout.name())
        default = os.path.join(os.path.expanduser("~"), f"{safe}.{ext}")
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export {ext.upper()}", default, filt)
        if not path:
            return None
        if not path.lower().endswith("." + ext):
            path += "." + ext
        try:
            from ..layout.layout_utils import export_layout
            success = export_layout(layout, path, dpi=int(dpi))
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return None
        if success:
            self.iface.messageBar().pushSuccess("CartoLab", f"Exported: {path}")
            return path
        else:
            QMessageBox.warning(self, "Export", "Export did not complete successfully.")
            return None

    def _on_export_and_open_layout(self, _checked: bool = False) -> None:
        path = self._on_export_layout()
        if path and os.path.exists(path):
            from qgis.PyQt.QtCore import QUrl
            from qgis.PyQt.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))


    def _on_isometric_stack(self) -> None:
        selected_items = self.iso_layer_list.selectedItems()
        if len(selected_items) < 2:
            QMessageBox.warning(
                self, "Isometric Stack",
                "Select at least 2 layers from the list above.",
            )
            return
        selected_names = [item.text() for item in selected_items]
        all_layers = QgsProject.instance().mapLayers()
        layers = [lyr for name, lyr in all_layers.items() if lyr.name() in selected_names]
        try:
            from ..layout.isometric_stacker import create_isometric_stack_layout
            layout = create_isometric_stack_layout(layers[:8])
            self._refresh_layout_combo()
            self.layout_combo.setCurrentText(layout.name())
            self._open_in_designer(layout)
            self.iface.messageBar().pushSuccess(
                "CartoLab", f"Isometric stack '{layout.name()}' created.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Layout Error", str(exc))

    def _on_bivariate_legend(self) -> None:
        layout = self._require_layout("Bivariate Legend")
        if layout is None:
            return
        colors = self._bivar_colors()
        try:
            from ..layout.legend_decorator import add_bivariate_legend_to_layout
            add_bivariate_legend_to_layout(
                layout,
                color_ll=colors[0], color_lh=colors[1],
                color_hl=colors[2], color_hh=colors[3],
                legend_type=self.bivar_legend_type_combo.currentData(),
            )
            self.iface.messageBar().pushSuccess(
                "CartoLab", f"Bivariate legend added to '{layout.name()}'.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Legend Error", str(exc))

    def _on_typography(self) -> None:
        layout = self._require_layout("Typography")
        if layout is None:
            return
        try:
            from ..layout.typography_engine import apply_typography_hierarchy
            apply_typography_hierarchy(layout)
            self.iface.messageBar().pushSuccess(
                "CartoLab", f"Typography applied to '{layout.name()}'.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Typography Error", str(exc))

    def _on_grid_style(self) -> None:
        layout = self._require_layout("Minimalist Grid")
        if layout is None:
            return
        try:
            from ..layout.grid_styler import apply_minimalist_grid
            if apply_minimalist_grid(layout):
                self.iface.messageBar().pushSuccess(
                    "CartoLab", f"Minimalist grid applied to '{layout.name()}'.",
                )
            else:
                QMessageBox.information(
                    self, "Minimalist Grid",
                    f"Layout '{layout.name()}' has no map frame to grid.",
                )
        except Exception as exc:
            QMessageBox.critical(self, "Grid Error", str(exc))

    def _on_balance_layout(self) -> None:
        layout = self._require_layout("Auto-Balance Margins")
        if layout is None:
            return
        try:
            from ..layout.layout_optimizer import optimize_layout_visual_balance
            if optimize_layout_visual_balance(layout):
                self.iface.messageBar().pushSuccess(
                    "CartoLab", f"Visual balance and margins optimized for '{layout.name()}'."
                )
            else:
                QMessageBox.information(
                    self, "Auto-Balance", f"Layout '{layout.name()}' has no primary map frame."
                )
        except Exception as exc:
            QMessageBox.critical(self, "Auto-Balance Error", str(exc))

    # ── System health / refresh ──────────────────────────────────────

    def _refresh(self) -> None:
        layers = list(QgsProject.instance().mapLayers().values())
        reg = QgsApplication.processingRegistry()
        missing = [aid for aid in REQUIRED_IDS if reg.algorithmById(aid) is None]

        # repopulate layer lists for style/layout tabs
        if hasattr(self, "layer25d_combo"):
            self._refresh_25d_layers()
        if hasattr(self, "iso_layer_list"):
            self.iso_layer_list.clear()
            for layer in layers:
                self.iso_layer_list.addItem(layer.name())
        if hasattr(self, "layout_combo"):
            self._refresh_layout_combo()
        if hasattr(self, "qs_layer_combo"):
            self._refresh_qs_layers()
        if hasattr(self, "bivar_layer_combo"):
            self._refresh_bivar_layers()
        if hasattr(self, "inspector_layer_combo"):
            self._refresh_inspector_layers()

        for card in self.card_widgets:
            is_ready = reg.algorithmById(card.algo_id) is not None
            card.status_lbl.setText("Ready" if is_ready else "Missing")
            card.status_lbl.setProperty("classChip", "ok" if is_ready else "warn")
            card.status_lbl.style().unpolish(card.status_lbl)
            card.status_lbl.style().polish(card.status_lbl)

        ready = len(missing) == 0
        status = "ALL READY" if ready else f"MISSING: {len(missing)}"
        self.status_chip.setText(f"System: {status}")
        if ready:
            self.status_chip.setStyleSheet(
                "color:#0f2d3a;background:#9fdfbf;border:1px solid #6fc995;border-radius:8px;padding:4px 10px;font-weight:700;"
            )
        else:
            self.status_chip.setStyleSheet(
                "color:#0f2d3a;background:#f8d37a;border:1px solid #e8bf58;border-radius:8px;padding:4px 10px;font-weight:700;"
            )

        # Build category health table
        cat_rows = []
        cat_ok_total = 0
        cat_total = 0
        for gname, ids in CATEGORY_GROUPS.items():
            found = sum(1 for aid in ids if reg.algorithmById(aid) is not None)
            total = len(ids)
            cat_ok_total += found
            cat_total += total
            pct = 100 * found / total if total else 0
            cat_rows.append((gname, found, total, pct))
        score = 100 * cat_ok_total / cat_total if cat_total else 0

        # Layer type counts for compatibility hints
        polygons = sum(1 for lyr in layers
                       if lyr.type() == QgsMapLayer.LayerType.VectorLayer
                       and hasattr(lyr, 'geometryType')
                       and lyr.geometryType() == 2)
        rasters = sum(1 for lyr in layers
                      if lyr.type() == QgsMapLayer.LayerType.RasterLayer)
        vectors = sum(1 for lyr in layers
                      if lyr.type() == QgsMapLayer.LayerType.VectorLayer)

        compat_lines = []
        if polygons:
            compat_lines.append(f"{polygons} polygon -> 2.5D Styling, Cartogram, Bivariate, Classification, VbA")
        if rasters:
            compat_lines.append(f"{rasters} raster -> Ridge Map")
        if vectors and not polygons:
            compat_lines.append(f"{vectors} vector -> Classification, Bivariate, VbA")
        if not compat_lines:
            compat_lines.append("No layers loaded - load data to use algorithms.")

        self.overview.setHtml(
            "<h2>PlanX CartoLab</h2>"
            "<p><b>Advanced cartography suite for QGIS.</b> 2.5D building styling, bivariate choropleth, "
            "continuous-area cartograms, ridge maps, Value-by-Alpha uncertainty "
            "visualisation, and isometric layout stacking.</p>"
            f"<p><b>Loaded layers:</b> {len(layers)} "
            f"(polygon: {polygons}, raster: {rasters}, vector: {vectors})</p>"
            "<p><b>Compatibility:</b><br>&nbsp;&nbsp;"
            + "<br>&nbsp;&nbsp;".join(compat_lines)
            + "</p>"
            f"<p><b>Readiness:</b> {score:.0f}% ({cat_ok_total}/{cat_total} algorithms)</p>"
            + (f"<p><b>Missing:</b> {', '.join(missing)}</p>" if missing else "<p>All modules ready.</p>")
            + "<p><b>Get started:</b> Open the <b>Modules</b> tab, pick an algorithm, and click <b>Run</b>.</p>"
        )

        cat_table = [
            "<table style='border-collapse:collapse;width:100%'>",
            "<tr><th style='text-align:left;border:1px solid #d7e3e6;padding:6px'>Category</th>"
            "<th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Coverage</th>"
            "<th style='text-align:right;border:1px solid #d7e3e6;padding:6px'>Score</th></tr>",
        ]
        for gname, found, total, pct in cat_rows:
            cat_table.append(
                f"<tr><td style='border:1px solid #d7e3e6;padding:6px'>{gname}</td>"
                f"<td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{found}/{total}</td>"
                f"<td style='text-align:right;border:1px solid #d7e3e6;padding:6px'>{pct:.0f}%</td></tr>"
            )
        cat_table.append("</table>")

        readiness_title = "Ready to use" if not missing else "Needs attention"
        readiness_note = ("All CartoLab tools are available in QGIS." if not missing
                          else "Some tools are unavailable. Review Setup, then refresh the dashboard.")
        self.readiness.setHtml(
            f"<h2>{readiness_title}</h2>"
            f"<p>{readiness_note}</p>"
            f"<p><b>Available tools:</b> {len(REQUIRED_IDS) - len(missing)}/{len(REQUIRED_IDS)}</p>"
            f"<p><b>Readiness score:</b> {score:.0f}%</p>"
            f"<p><b>Unavailable tools:</b> {len(missing)}</p>"
            "<h3>Tool coverage</h3>"
            + "".join(cat_table)
        )

        self._refresh_runlog()
        self._filter_cards()

    # ── Dependency management ────────────────────────────────────────

    def _on_check_deps(self) -> None:
        from ..core.dependency_manager import get_status_report, CARTO_LAB_DEPS
        report = get_status_report(CARTO_LAB_DEPS, "CartoLab Dependencies")
        self.setup_status.setPlainText(report)

    # ── Resize / keyboard ────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "cards_grid"):
            return
        desired = self._cards_column_count()
        if desired != self._current_card_columns:
            self._build_cards()
            self._refresh()

    def keyPressEvent(self, event) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_R:
                self._refresh()
                return
            if event.key() == Qt.Key.Key_F:
                self.search.setFocus()
                return
        super().keyPressEvent(event)
