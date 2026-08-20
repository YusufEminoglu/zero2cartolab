# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Print Layout Designer Window Integration & Embedded Studio Dock.

Hooks directly into QGIS QgsLayoutDesignerInterface instances so that users
have access to CartoLab cartographic tools, presets, decorators, and 1-click
export & open right inside the QGIS Print Layout Designer window.
"""
from __future__ import annotations

import math
import os
from contextlib import suppress
from typing import Optional

try:
    from qgis.core import QgsProject, QgsLayoutItemMap
    from qgis.PyQt.QtCore import Qt, QUrl, QSize
    from qgis.PyQt.QtGui import QDesktopServices, QIcon
    from qgis.PyQt.QtWidgets import (
        QAction,
        QCheckBox,
        QComboBox,
        QDockWidget,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMenu,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QTabWidget,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QgsProject = QgsLayoutItemMap = None
    Qt = QUrl = QSize = QDesktopServices = QIcon = QAction = QCheckBox = QComboBox = QDockWidget = QDoubleSpinBox = QFileDialog = QFormLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QMenu = QMessageBox = QPushButton = QScrollArea = QTabWidget = QToolBar = QVBoxLayout = QWidget = None




_INTEGRATED_DESIGNERS = set()


def setup_designer_integration(iface) -> None:
    """Connect to layoutDesignerOpened signal and attach to active designers."""
    if not iface:
        return

    def _on_opened(designer):
        attach_cartolab_to_designer(iface, designer)

    with suppress(Exception):
        if hasattr(iface, "layoutDesignerOpened"):
            iface.layoutDesignerOpened.connect(_on_opened)

    # Attach to existing open layout designers
    with suppress(Exception):
        if hasattr(iface, "layoutDesigners"):
            for designer in iface.layoutDesigners():
                attach_cartolab_to_designer(iface, designer)


def attach_cartolab_to_designer(iface, designer) -> None:
    """Attach PlanX CartoLab embedded studio dock panel inside a QgsLayoutDesignerInterface window."""
    if designer is None or id(designer) in _INTEGRATED_DESIGNERS:
        return
    _INTEGRATED_DESIGNERS.add(id(designer))

    main_win = None
    with suppress(Exception):
        if hasattr(designer, "view") and hasattr(designer.view(), "window"):
            main_win = designer.view().window()
        elif hasattr(designer, "mainWindow"):
            main_win = designer.mainWindow()

    if main_win is None:
        return

    # Clean up any existing CartoLab dock widgets in this designer window
    with suppress(Exception):
        for existing in main_win.findChildren(QDockWidget):
            if existing.objectName() == "CartoLabLayoutStudioDock":
                main_win.removeDockWidget(existing)
                existing.deleteLater()

    icon_dir = os.path.join(os.path.dirname(__file__), "..", "icons")
    icon_path = os.path.join(icon_dir, "icon.png")
    icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    # 1. Create 1 Embedded Dock Panel inside Print Layout Window
    dock = create_cartolab_layout_dock(iface, designer, main_win)
    dock.setWindowIcon(icon)
    _RightDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "RightDockWidgetArea", getattr(Qt, "RightDockWidgetArea", 2))
    with suppress(Exception):
        if hasattr(designer, "addDockWidget"):
            designer.addDockWidget(_RightDock, dock)
        elif hasattr(main_win, "addDockWidget"):
            main_win.addDockWidget(_RightDock, dock)

    # 2. Add single 02CartoLab Menu item and QToolBar Action Button
    with suppress(Exception):
        act_toggle = dock.toggleViewAction()
        act_toggle.setText("02CartoLab Studio")
        act_toggle.setIcon(icon)
        act_toggle.setCheckable(True)

        menubar = main_win.menuBar()
        if menubar:
            menu = QMenu("&02CartoLab", menubar)
            menu.addAction(act_toggle)
            menubar.addMenu(menu)

        # Add toggle action directly to the Print Layout Designer's primary toolbar
        toolbars = main_win.findChildren(QToolBar)
        target_tb = None
        for tb in toolbars:
            tb_name = tb.objectName().lower()
            if "layout" in tb_name or "main" in tb_name:
                target_tb = tb
                break
        if target_tb is None and toolbars:
            target_tb = toolbars[0]
        if target_tb:
            target_tb.addAction(act_toggle)


def _get_cartolab_icon(name: str = "icon.png") -> QIcon:
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "icons", name)
    if os.path.exists(path):
        return QIcon(path)
    fallback = os.path.join(base, "icons", "icon.png")
    return QIcon(fallback) if os.path.exists(fallback) else QIcon()


def create_cartolab_layout_dock(iface, designer, parent_win) -> QDockWidget:
    """Create embedded CartoLab Layout Studio Dock Widget for the layout designer."""
    dock = QDockWidget("CartoLab Layout Studio", parent_win)
    dock.setObjectName("CartoLabLayoutStudioDock")
    dock.setWindowIcon(_get_cartolab_icon("icon.png"))
    _LeftDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "LeftDockWidgetArea", getattr(Qt, "LeftDockWidgetArea", 1))
    _RightDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "RightDockWidgetArea", getattr(Qt, "RightDockWidgetArea", 2))
    dock.setAllowedAreas(_LeftDock | _RightDock)

    container = QWidget()
    main_lyt = QVBoxLayout(container)
    main_lyt.setContentsMargins(4, 4, 4, 4)
    main_lyt.setSpacing(6)

    tabs = QTabWidget()
    tabs.setIconSize(QSize(16, 16))
    tabs.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: #ffffff;
        }
        QTabBar::tab {
            background: #f1f5f9;
            color: #475569;
            padding: 8px 18px 8px 22px;
            font-weight: 600;
            font-size: 11px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
            border: 1px solid #e2e8f0;
        }
        QTabBar::tab:selected {
            background: #ffffff;
            color: #0f172a;
            font-weight: 600;
            border-bottom: 2px solid #2563eb;
        }
        QGroupBox {
            font-weight: 700;
            font-size: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-top: 8px;
            padding: 10px 8px 8px 8px;
            background: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #0f172a;
        }
        QPushButton {
            background-color: #0f172a;
            color: #ffffff;
            border-radius: 6px;
            padding: 7px 12px;
            font-weight: 600;
            font-size: 11px;
            border: 1px solid #0f172a;
        }
        QPushButton:hover {
            background-color: #1e293b;
            border-color: #1e293b;
        }
        QPushButton#ghost {
            background-color: #ffffff;
            color: #334155;
            border: 1px solid #cbd5e1;
        }
        QPushButton#ghost:hover {
            background-color: #f8fafc;
            color: #0f172a;
        }
        QLineEdit, QComboBox, QDoubleSpinBox {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 4px 6px;
            color: #0f172a;
            font-size: 11px;
        }
    """)

    # -----------------------------------------------------------------
    # TAB 0: Template Gallery (Publication Archetypes)
    # -----------------------------------------------------------------
    tab_tpl = QWidget()
    lyt_tpl = QVBoxLayout(tab_tpl)
    lyt_tpl.setContentsMargins(8, 8, 8, 8)
    lyt_tpl.setSpacing(10)

    gb_archetype = QGroupBox("Publication Layout Archetypes")
    fl_arch = QFormLayout(gb_archetype)

    tpl_combo = QComboBox()
    tpl_combo.addItem("Report & Slide Figure (16:9 Landscape)", "report_figure")
    tpl_combo.addItem("Academic Journal Figure (A4 Portrait 2-Col)", "academic_journal")
    tpl_combo.addItem("Exhibition Poster (A1/A2 Large-Format)", "poster_exhibition")
    tpl_combo.addItem("Executive Fact Sheet (A4 Portrait)", "fact_sheet")
    tpl_combo.addItem("Side-by-Side Diptych (A4/A3 Comparative)", "side_by_side_diptych")
    fl_arch.addRow("Archetype:", tpl_combo)

    tpl_desc_lbl = QLabel("Widescreen 16:9 layout with prominent figure title, hero map frame, and compact right HUD card.")
    tpl_desc_lbl.setWordWrap(True)
    tpl_desc_lbl.setStyleSheet("color: #475569; font-size: 10.5px; padding: 2px 0;")
    fl_arch.addRow(tpl_desc_lbl)

    tpl_title_input = QLineEdit()
    tpl_title_input.setPlaceholderText("Layout Title (optional)")
    fl_arch.addRow("Title:", tpl_title_input)

    tpl_sub_input = QLineEdit()
    tpl_sub_input.setPlaceholderText("Subtitle / Context (optional)")
    fl_arch.addRow("Subtitle:", tpl_sub_input)

    def _on_tpl_combo_changed():
        tid = tpl_combo.currentData()
        descs = {
            "report_figure": "Widescreen 16:9 layout with prominent figure title, hero map frame, and compact right HUD card.",
            "academic_journal": "Formal 2-column scientific layout with double-column map, caption box, formal citation, and methodology block.",
            "poster_exhibition": "Large-format presentation poster with bold banner, hero map frame, regional locator map, and thematic legend cards.",
            "fact_sheet": "Executive summary with top KPI metric cards, central thematic map, and bottom analytical narrative block.",
            "side_by_side_diptych": "Comparative dual-map layout with paired synchronized map frames for before/after or scenario comparison.",
        }
        tpl_desc_lbl.setText(descs.get(tid, ""))

    tpl_combo.currentIndexChanged.connect(_on_tpl_combo_changed)

    btn_create_tpl = QPushButton("Create New Template Layout ⚡")
    btn_create_tpl.setIcon(_get_cartolab_icon("layout.png"))

    def _create_template_clicked():
        tid = tpl_combo.currentData() or "report_figure"
        title = tpl_title_input.text().strip()
        sub = tpl_sub_input.text().strip()
        try:
            from .template_gallery import create_template_layout
            new_layout = create_template_layout(
                tid,
                iface=iface,
                title=title or "CartoLab Map",
                subtitle=sub or "",
            )
            if new_layout:
                if hasattr(iface, "openLayoutDesigner"):
                    iface.openLayoutDesigner(new_layout)
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"Template layout '{new_layout.name()}' created.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Template Error", str(exc))

    btn_create_tpl.clicked.connect(_create_template_clicked)
    fl_arch.addRow(btn_create_tpl)
    lyt_tpl.addWidget(gb_archetype)

    gb_quick_tpl = QGroupBox("Quick 1-Click Launchers")
    lyt_quick_tpl = QVBoxLayout(gb_quick_tpl)

    for q_name, q_tid in [
        ("Report Figure (16:9)", "report_figure"),
        ("Academic Journal (A4)", "academic_journal"),
        ("Exhibition Poster (A1)", "poster_exhibition"),
        ("Executive Fact Sheet (A4)", "fact_sheet"),
        ("Side-by-Side Diptych (A4)", "side_by_side_diptych"),
    ]:
        btn_q = QPushButton(f"+ New {q_name}")
        btn_q.setObjectName("ghost")
        btn_q.setIcon(_get_cartolab_icon("layout.png"))
        def _make_launcher(t_id):
            def _launch():
                try:
                    from .template_gallery import create_template_layout
                    nl = create_template_layout(t_id, iface=iface)
                    if nl and hasattr(iface, "openLayoutDesigner"):
                        iface.openLayoutDesigner(nl)
                except Exception as exc:
                    QMessageBox.critical(parent_win, "Template Error", str(exc))
            return _launch
        btn_q.clicked.connect(_make_launcher(q_tid))
        lyt_quick_tpl.addWidget(btn_q)

    lyt_tpl.addWidget(gb_quick_tpl)
    lyt_tpl.addStretch()

    tabs.addTab(tab_tpl, "  Templates  ")

    # -----------------------------------------------------------------
    # TAB 1: Canvas & Grid
    # -----------------------------------------------------------------
    tab_canvas = QWidget()
    lyt_canvas = QVBoxLayout(tab_canvas)
    lyt_canvas.setContentsMargins(8, 8, 8, 8)
    lyt_canvas.setSpacing(10)

    gb_theme = QGroupBox("Paper Canvas Theme")
    fl_theme = QFormLayout(gb_theme)
    theme_combo = QComboBox()
    theme_combo.addItem("Modern Swiss Minimalist", "swiss_modern")
    theme_combo.addItem("Architectural Blueprint", "blueprint")
    theme_combo.addItem("Dark Matter / Obsidian Urban", "dark_matter")
    theme_combo.addItem("Vintage Sepia Atlas", "sepia_atlas")
    theme_combo.addItem("Warm Editorial Newsprint", "warm_editorial")
    theme_combo.addItem("Japanese Washi Minimal", "japanese_washi")
    fl_theme.addRow("Theme:", theme_combo)
    btn_apply_theme = QPushButton("Apply Canvas Theme")
    btn_apply_theme.setIcon(_get_cartolab_icon("style.png"))

    def _apply_theme():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .paper_themes import apply_paper_theme
            tkey = theme_combo.currentData()
            if apply_paper_theme(layout, tkey):
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"Applied '{theme_combo.currentText()}' paper theme.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Paper Theme Error", str(exc))

    btn_apply_theme.clicked.connect(_apply_theme)
    fl_theme.addRow(btn_apply_theme)
    lyt_canvas.addWidget(gb_theme)

    gb_typo = QGroupBox("Cartographic Typography Hierarchy")
    fl_typo = QFormLayout(gb_typo)

    typo_preset_combo = QComboBox()
    typo_preset_combo.addItem("Swiss Modernism (Inter / Clean Sans)", "swiss_modern")
    typo_preset_combo.addItem("Academic Journal (Merriweather / Serif)", "academic_serif")
    typo_preset_combo.addItem("Technical Blueprint (IBM Plex Mono)", "technical_blueprint")
    typo_preset_combo.addItem("Warm Editorial (Palatino / Georgia)", "warm_editorial")
    fl_typo.addRow("Font Stack Preset:", typo_preset_combo)

    btn_dock_typo = QPushButton("Apply Typography Hierarchy")
    btn_dock_typo.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_typo():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .typography_engine import apply_typography_hierarchy
            preset = typo_preset_combo.currentData() or "swiss_modern"
            apply_typography_hierarchy(layout, preset=preset)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", f"Applied '{typo_preset_combo.currentText()}' typography.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Typography Error", str(exc))

    btn_dock_typo.clicked.connect(_dock_typo)
    fl_typo.addRow(btn_dock_typo)

    btn_dock_title = QPushButton("Add Publication Title Block")
    btn_dock_title.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_title():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .title_block import add_publication_title_block
            add_publication_title_block(layout)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Publication title block added to layout.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Title Block Error", str(exc))

    btn_dock_title.clicked.connect(_dock_title)
    fl_typo.addRow(btn_dock_title)

    btn_dock_balance = QPushButton("Auto-Balance Margins & Alignment")
    btn_dock_balance.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_balance():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .layout_optimizer import optimize_layout_visual_balance
            if optimize_layout_visual_balance(layout):
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", "Layout visual balance & golden margins applied.")
            else:
                QMessageBox.information(parent_win, "Auto-Balance", "No map item found to balance.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Auto-Balance Error", str(exc))

    btn_dock_balance.clicked.connect(_dock_balance)
    fl_typo.addRow(btn_dock_balance)

    lyt_canvas.addWidget(gb_typo)
    lyt_canvas.addStretch()

    tabs.addTab(tab_canvas, "  Canvas & Grid  ")


    # -----------------------------------------------------------------
    # TAB 2: Decorators (Bivariate, Scale Bar, North Arrow)
    # -----------------------------------------------------------------
    tab_dec = QWidget()
    lyt_dec = QVBoxLayout(tab_dec)
    lyt_dec.setContentsMargins(8, 8, 8, 8)
    lyt_dec.setSpacing(10)

    gb_bivar = QGroupBox("Bivariate Legend Settings")
    fl_bivar = QFormLayout(gb_bivar)

    xlabel_input = QLineEdit("Variable X")
    fl_bivar.addRow("X Axis Label:", xlabel_input)

    ylabel_input = QLineEdit("Variable Y")
    fl_bivar.addRow("Y Axis Label:", ylabel_input)

    palette_combo = QComboBox()
    palette_combo.addItem("Teal-Brown", ("#e8e8e8", "#5ab4ac", "#d8b365", "#8c510a"))
    palette_combo.addItem("Purple-Green", ("#e8e8e8", "#7fbf7b", "#af8dc3", "#762a83"))
    palette_combo.addItem("Blue-Orange", ("#e8e8e8", "#fdae61", "#abd9e9", "#2c7bb6"))
    palette_combo.addItem("Pink-Green", ("#e8e8e8", "#a1d76a", "#e9a3c9", "#c51b7d"))
    fl_bivar.addRow("Palette:", palette_combo)

    shape_combo = QComboBox()
    shape_combo.addItem("Diamond", "diamond")
    shape_combo.addItem("Square", "square")
    fl_bivar.addRow("Shape:", shape_combo)

    btn_add_bivar = QPushButton("Add Bivariate Legend")
    btn_add_bivar.setIcon(_get_cartolab_icon("bivariate.png"))

    def _add_bivar():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        colors = palette_combo.currentData()
        ltype = shape_combo.currentData()
        x_lbl = xlabel_input.text().strip() or "Variable X"
        y_lbl = ylabel_input.text().strip() or "Variable Y"
        try:
            from .legend_decorator import add_bivariate_legend
            add_bivariate_legend(layout, colors=colors, legend_type=ltype, x_label=x_lbl, y_label=y_lbl)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", f"Bivariate legend added ({x_lbl} vs {y_lbl}).")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Bivariate Legend Error", str(exc))

    btn_add_bivar.clicked.connect(_add_bivar)
    fl_bivar.addRow(btn_add_bivar)

    btn_update_bivar = QPushButton("Update Selected Legend in Layout")
    btn_update_bivar.setIcon(_get_cartolab_icon("bivariate.png"))

    def _update_bivar():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        selected = layout.selectedItems()
        if not selected:
            QMessageBox.information(parent_win, "Update Legend", "Please select a bivariate legend group in the layout canvas first.")
            return

        # Record position of first selected item in layout mm coordinates
        first = selected[0]
        pos_x, pos_y = 12.0, 12.0  # fallback default
        with suppress(Exception):
            if hasattr(first, "positionWithUnits"):
                pt = first.positionWithUnits()
                pos_x = pt.x()
                pos_y = pt.y()
            elif hasattr(first, "pos"):
                # pos() returns scene points; approximate as mm
                pos_x = first.pos().x()
                pos_y = first.pos().y()

        # Remove selected items using the correct PyQGIS method
        for item in list(selected):
            with suppress(Exception):
                layout.removeLayoutItem(item)

        colors = palette_combo.currentData()
        ltype = shape_combo.currentData()
        x_lbl = xlabel_input.text().strip() or "Variable X"
        y_lbl = ylabel_input.text().strip() or "Variable Y"
        try:
            from .legend_decorator import add_bivariate_legend
            add_bivariate_legend(layout, colors=colors, legend_type=ltype, position=(pos_x, pos_y), x_label=x_lbl, y_label=y_lbl)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Bivariate legend updated in-place.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Update Legend Error", str(exc))

    btn_update_bivar.clicked.connect(_update_bivar)
    fl_bivar.addRow(btn_update_bivar)
    lyt_dec.addWidget(gb_bivar)

    gb_map_elem = QGroupBox("Map Elements & Motifs")
    fl_elem = QFormLayout(gb_map_elem)

    scalebar_combo = QComboBox()
    scalebar_combo.addItem("Clean Line (Ticks Up)", "Clean Line (Ticks Up)")
    scalebar_combo.addItem("Clean Line (Ticks Down)", "Clean Line (Ticks Down)")
    scalebar_combo.addItem("Line Ticks Middle", "Line Ticks Middle")
    scalebar_combo.addItem("Single Box (Modern)", "Single Box (Modern)")
    scalebar_combo.addItem("Double Box (Classic)", "Double Box (Classic)")
    scalebar_combo.addItem("Stepped Line (Academic)", "Stepped Line (Academic)")
    fl_elem.addRow("Scalebar Style:", scalebar_combo)

    btn_dock_scalebar = QPushButton("Add Executive Scale Bar")
    btn_dock_scalebar.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_scalebar():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .legend_decorator import add_scalebar_to_layout
            sname = scalebar_combo.currentData() or "Clean Line (Ticks Up)"
            add_scalebar_to_layout(layout, style_name=sname)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", f"Executive scale bar '{sname}' added.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Scale Bar Error", str(exc))

    btn_dock_scalebar.clicked.connect(_dock_scalebar)
    fl_elem.addRow(btn_dock_scalebar)

    btn_dock_scale_combo = QPushButton("Add Scale Bar + Ratio Combo (1:N)")
    btn_dock_scale_combo.setObjectName("ghost")
    btn_dock_scale_combo.setIcon(_get_cartolab_icon("compass.png"))

    def _dock_scale_combo():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .legend_decorator import add_scale_combo_to_layout
            sname = scalebar_combo.currentData() or "Clean Line (Ticks Up)"
            add_scale_combo_to_layout(layout, style_name=sname)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Combined scale ratio & bar added.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Scale Combo Error", str(exc))

    btn_dock_scale_combo.clicked.connect(_dock_scale_combo)
    fl_elem.addRow(btn_dock_scale_combo)

    north_combo = QComboBox()
    north_combo.addItem("Architectural Compass Rose", "compass_rose")
    north_combo.addItem("Swiss Minimalist Needle", "swiss_minimal")
    north_combo.addItem("Nautical Star 4-Point", "nautical_star")
    fl_elem.addRow("North Arrow Motif:", north_combo)

    btn_dock_north = QPushButton("Add Publication North Arrow")
    btn_dock_north.setIcon(_get_cartolab_icon("compass.png"))

    def _dock_north():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .legend_decorator import add_north_arrow_to_layout
            npreset = north_combo.currentData() or "compass_rose"
            add_north_arrow_to_layout(layout, preset=npreset)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", f"Publication north arrow '{north_combo.currentText()}' added.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "North Arrow Error", str(exc))

    btn_dock_north.clicked.connect(_dock_north)
    fl_elem.addRow(btn_dock_north)

    btn_dock_locator = QPushButton("Add Overview Locator Inset Map")
    btn_dock_locator.setObjectName("ghost")
    btn_dock_locator.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_locator():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .locator_map import add_locator_inset_map
            add_locator_inset_map(layout)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Overview locator inset map frame added.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Locator Map Error", str(exc))

    btn_dock_locator.clicked.connect(_dock_locator)
    fl_elem.addRow(btn_dock_locator)

    btn_dock_legend_style = QPushButton("Style Legend (Clean Publication)")
    btn_dock_legend_style.setIcon(_get_cartolab_icon("style.png"))

    def _dock_legend_style():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .legend_styler import style_layout_legend
            style_layout_legend(layout)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Publication legend styling applied.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Legend Style Error", str(exc))

    btn_dock_legend_style.clicked.connect(_dock_legend_style)
    fl_elem.addRow(btn_dock_legend_style)

    btn_dock_filter_legend = QPushButton("Filter Legend to Map Extent")
    btn_dock_filter_legend.setObjectName("ghost")
    btn_dock_filter_legend.setIcon(_get_cartolab_icon("style.png"))

    def _dock_filter_legend():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        main_map = None
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                main_map = item
                break
        if not main_map:
            QMessageBox.warning(parent_win, "Filter Legend", "No map item found in layout.")
            return

        from qgis.core import QgsLayoutItemLegend
        applied = False
        for item in layout.items():
            if isinstance(item, QgsLayoutItemLegend):
                item.setAutoUpdateModel(False)
                if hasattr(item, "setLinkedMap"):
                    item.setLinkedMap(main_map)
                if hasattr(item, "setLegendFilterByMapEnabled"):
                    item.setLegendFilterByMapEnabled(True)
                item.updateLegend()
                applied = True

        if applied:
            layout.refresh()
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Legend filtered to visible map extent.")
        else:
            QMessageBox.information(parent_win, "Filter Legend", "No legend found in layout.")

    btn_dock_filter_legend.clicked.connect(_dock_filter_legend)
    fl_elem.addRow(btn_dock_filter_legend)

    btn_dock_locator = QPushButton("Add Locator / Inset Map")
    btn_dock_locator.setIcon(_get_cartolab_icon("grid.png"))

    def _dock_locator():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .locator_map import add_locator_inset_map
            add_locator_inset_map(layout)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Locator inset map frame added to layout.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Locator Map Error", str(exc))

    btn_dock_locator.clicked.connect(_dock_locator)
    fl_elem.addRow(btn_dock_locator)

    lyt_dec.addWidget(gb_map_elem)

    # Dedicated Publication Coordinate Grid Group
    gb_grid = QGroupBox("Publication Coordinate Grid")
    fl_grid = QFormLayout(gb_grid)

    grid_density_combo = QComboBox()
    grid_density_combo.addItem("Standard (5-6 divisions)", (6, 5))
    grid_density_combo.addItem("Coarse / Clean (3-4 divisions)", (4, 3))
    grid_density_combo.addItem("Dense (7-9 divisions)", (8, 6))
    fl_grid.addRow("Grid Density:", grid_density_combo)

    grid_style_combo = QComboBox()
    grid_style_combo.addItem("Solid Lines", "Solid")
    grid_style_combo.addItem("Crosshairs (+)", "Cross")
    grid_style_combo.addItem("Border Ticks Only", "FrameAndAnnotationsOnly")
    fl_grid.addRow("Grid Style:", grid_style_combo)

    grid_frame_combo = QComboBox()
    grid_frame_combo.addItem("Academic Zebra Border", "Zebra")
    grid_frame_combo.addItem("Clean Line Border", "LineBorder")
    grid_frame_combo.addItem("Frame-Free (Minimal)", "NoFrame")
    fl_grid.addRow("Frame Border:", grid_frame_combo)

    btn_dock_grid = QPushButton("Apply Publication Grid")
    btn_dock_grid.setIcon(_get_cartolab_icon("grid.png"))

    def _dock_grid():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .coordinate_grid import apply_coordinate_grid_decorator
            divs = grid_density_combo.currentData() or (6, 5)
            gstyle = grid_style_combo.currentData() or "Solid"
            fstyle = grid_frame_combo.currentData() or "Zebra"
            apply_coordinate_grid_decorator(
                layout,
                target_divisions_x=divs[0],
                target_divisions_y=divs[1],
                grid_style=gstyle,
                frame_style=fstyle,
                show_annotations=True,
            )
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Publication coordinate grid applied.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Coordinate Grid Error", str(exc))

    btn_dock_grid.clicked.connect(_dock_grid)
    fl_grid.addRow(btn_dock_grid)

    lyt_dec.addWidget(gb_grid)

    # Smart Map Utilities
    gb_smart = QGroupBox("Smart Map Tools")
    fl_smart = QFormLayout(gb_smart)

    btn_snap_scale = QPushButton("Snap to Standard Scale (1:10k, 1:25k…)")
    btn_snap_scale.setIcon(_get_cartolab_icon("compass.png"))

    def _dock_snap_scale():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        for item in layout.items():
            if isinstance(item, QgsLayoutItemMap):
                curr = item.scale()
                scales = [500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000, 200000, 250000, 500000, 1000000]
                best = min(scales, key=lambda s: abs(math.log(s) - math.log(max(1.0, curr))))
                item.setScale(best)
                item.updateBoundingRect()
                layout.refresh()
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"Map scale snapped to 1:{best:,}")
                return
        QMessageBox.warning(parent_win, "Snap Scale", "No map item found in layout.")

    btn_snap_scale.clicked.connect(_dock_snap_scale)
    fl_smart.addRow(btn_snap_scale)
    lyt_dec.addWidget(gb_smart)

    lyt_dec.addStretch()

    tabs.addTab(tab_dec, "  Decorators  ")

    # -----------------------------------------------------------------
    # TAB 3: 3D Perspective & Quick Export
    # -----------------------------------------------------------------
    tab_exp = QWidget()
    lyt_exp = QVBoxLayout(tab_exp)
    lyt_exp.setContentsMargins(8, 8, 8, 8)
    lyt_exp.setSpacing(10)

    gb_iso = QGroupBox("2.5D Isometric Stack")
    fl_iso = QFormLayout(gb_iso)

    tilt_spin = QDoubleSpinBox()
    tilt_spin.setRange(0, 89)
    tilt_spin.setValue(30.0)
    tilt_spin.setSuffix(" °")
    fl_iso.addRow("Tilt Angle:", tilt_spin)

    heading_spin = QDoubleSpinBox()
    heading_spin.setRange(0, 359)
    heading_spin.setValue(100.0)
    heading_spin.setSuffix(" °")
    fl_iso.addRow("Heading Angle:", heading_spin)

    btn_apply_iso = QPushButton("Apply Isometric Perspective")
    btn_apply_iso.setIcon(_get_cartolab_icon("isometric.png"))

    def _apply_iso():
        layout = _get_designer_layout(designer)
        if not layout or not QgsProject or not QgsProject.instance():
            return
        layers = [lyr for lyr in QgsProject.instance().mapLayers().values() if hasattr(lyr, "geometryType")]
        if len(layers) < 2:
            QMessageBox.warning(parent_win, "Isometric Stack", "Need at least 2 layers.")
            return
        try:
            from .isometric_stacker import stack_layers_isometrically
            stack_layers_isometrically(layout, layers[:3], tilt_angle=tilt_spin.value(), heading=heading_spin.value())
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Isometric stack applied.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Isometric Stack", str(exc))

    btn_apply_iso.clicked.connect(_apply_iso)
    fl_iso.addRow(btn_apply_iso)
    lyt_exp.addWidget(gb_iso)

    gb_atlas = QGroupBox("Map Book & Atlas Automation")
    fl_atlas = QFormLayout(gb_atlas)

    atlas_layer_combo = QComboBox()
    if QgsProject and QgsProject.instance():
        for lyr in QgsProject.instance().mapLayers().values():
            if hasattr(lyr, "geometryType"):
                atlas_layer_combo.addItem(lyr.name(), lyr)
    fl_atlas.addRow("Coverage Layer:", atlas_layer_combo)

    atlas_banner_check = QCheckBox("Add Styled Header Banner")
    atlas_banner_check.setChecked(True)
    fl_atlas.addRow(atlas_banner_check)

    atlas_locator_check = QCheckBox("Add Overview Locator Inset Map")
    atlas_locator_check.setChecked(False)
    fl_atlas.addRow(atlas_locator_check)

    atlas_margin_spin = QDoubleSpinBox()
    atlas_margin_spin.setRange(4.0, 50.0)
    atlas_margin_spin.setValue(12.0)
    atlas_margin_spin.setSuffix(" mm")
    fl_atlas.addRow("Page Margin:", atlas_margin_spin)

    btn_setup_atlas = QPushButton("Configure Map Book Atlas (1-Click)")
    btn_setup_atlas.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_setup_atlas():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        cov_layer = atlas_layer_combo.currentData()
        if not cov_layer:
            QMessageBox.warning(parent_win, "Atlas Setup", "Select a coverage layer first.")
            return
        try:
            from .atlas_builder import setup_layout_atlas
            if setup_layout_atlas(
                layout,
                cov_layer,
                page_margin_mm=atlas_margin_spin.value(),
                add_header_banner=atlas_banner_check.isChecked(),
                add_overview_locator=atlas_locator_check.isChecked(),
            ):
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"Map Book Atlas configured for '{cov_layer.name()}'.")
            else:
                QMessageBox.warning(parent_win, "Atlas Setup", "Could not configure atlas on layout.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Atlas Setup Error", str(exc))

    btn_setup_atlas.clicked.connect(_dock_setup_atlas)
    fl_atlas.addRow(btn_setup_atlas)
    lyt_exp.addWidget(gb_atlas)

    gb_exp = QGroupBox("Quick Export")
    fl_exp = QFormLayout(gb_exp)

    dpi_combo = QComboBox()
    dpi_combo.addItem("150 DPI (Draft)", 150)
    dpi_combo.addItem("300 DPI (Publication)", 300)
    dpi_combo.addItem("600 DPI (Ultra)", 600)
    dpi_combo.setCurrentIndex(1)
    fl_exp.addRow("Quality:", dpi_combo)

    btn_dock_copy = QPushButton("Copy Image to Clipboard")
    btn_dock_copy.setObjectName("ghost")
    btn_dock_copy.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_copy():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        dpi = dpi_combo.currentData() or 300
        try:
            from .layout_utils import copy_layout_to_clipboard
            if copy_layout_to_clipboard(layout, dpi=int(dpi)):
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"High-resolution map ({dpi} DPI) copied to clipboard.")
            else:
                QMessageBox.warning(parent_win, "Copy to Clipboard", "Could not render layout to clipboard.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Clipboard Error", str(exc))

    btn_dock_copy.clicked.connect(_dock_copy)
    fl_exp.addRow(btn_dock_copy)

    btn_dock_export = QPushButton("Export & Open ↗")
    btn_dock_export.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_export():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        dpi = dpi_combo.currentData()
        safe = "".join(c if c.isalnum() else "_" for c in layout.name())
        default = os.path.join(os.path.expanduser("~"), f"{safe}.png")
        path, _ = QFileDialog.getSaveFileName(
            parent_win,
            "Export Layout",
            default,
            "PNG Image (*.png);;PDF Document (*.pdf);;TIFF Image (*.tif *.tiff);;SVG Vector (*.svg)",
        )
        if not path:
            return
        try:
            from .layout_utils import export_layout
            if export_layout(layout, path, dpi=int(dpi)) and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                if hasattr(iface, "messageBar"):
                    iface.messageBar().pushSuccess("CartoLab", f"Exported & Opened: {path}")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Export Error", str(exc))

    btn_dock_export.clicked.connect(_dock_export)
    fl_exp.addRow(btn_dock_export)
    lyt_exp.addWidget(gb_exp)
    lyt_exp.addStretch()

    tabs.addTab(tab_exp, "  3D & Export  ")

    main_lyt.addWidget(tabs)
    dock.setWidget(container)
    return dock



def _get_designer_layout(designer):
    """Retrieve the QgsPrintLayout from a designer instance safely."""
    if designer is None:
        return None
    layout = None
    for attr in ("masterLayout", "currentLayout", "layout"):
        if hasattr(designer, attr):
            val = getattr(designer, attr)
            if callable(val):
                with suppress(Exception):
                    res = val()
                    if res:
                        layout = res
                        break
            elif val:
                layout = val
                break
    if layout is not None:
        if hasattr(layout, "atlas"):
            return layout
        if hasattr(layout, "name") and QgsProject and QgsProject.instance():
            with suppress(Exception):
                resolved = QgsProject.instance().layoutManager().layoutByName(layout.name())
                if resolved:
                    return resolved
    return layout
