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
import tempfile
from contextlib import suppress

try:
    from qgis.core import QgsProject, QgsLayoutItemMap
    from qgis.PyQt.QtCore import Qt, QUrl, QSize, QTimer
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
        QSpinBox,
        QTabWidget,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QgsProject = QgsLayoutItemMap = None
    Qt = QUrl = QSize = QTimer = QDesktopServices = QIcon = QAction = QCheckBox = QComboBox = QDockWidget = QDoubleSpinBox = QFileDialog = QFormLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QMenu = QMessageBox = QPushButton = QScrollArea = QSpinBox = QTabWidget = QToolBar = QVBoxLayout = QWidget = None




_INTEGRATED_DESIGNERS = {}
_DESIGNER_MENUS = {}  # designer id -> (menubar, "&02CartoLab" QMenu) for teardown
_SIGNAL_HANDLERS = {}


def _designer_window(designer):
    """Return the QMainWindow owned by a layout designer across QGIS versions."""
    for attr in ("window", "mainWindow"):
        candidate = getattr(designer, attr, None)
        if callable(candidate):
            with suppress(Exception):
                window = candidate()
                if window is not None and hasattr(window, "addDockWidget"):
                    return window

    view = getattr(designer, "view", None)
    if callable(view):
        with suppress(Exception):
            view = view()
    if view is not None:
        window_getter = getattr(view, "window", None)
        if callable(window_getter):
            with suppress(Exception):
                window = window_getter()
                if window is not None and hasattr(window, "addDockWidget"):
                    return window
    return None


def _attach_when_ready(iface, designer, attempts: int = 5) -> None:
    """Retry attachment because QGIS can emit opened before the window is ready."""
    if attach_cartolab_to_designer(iface, designer) or attempts <= 1 or QTimer is None:
        return
    QTimer.singleShot(
        100,
        lambda: _attach_when_ready(iface, designer, attempts - 1),
    )


def setup_designer_integration(iface) -> None:
    """Connect to layoutDesignerOpened signal and attach to active designers."""
    if not iface:
        return

    # Plugin reloads must not accumulate callbacks on the application iface.
    teardown_designer_integration(iface, remove_docks=False)

    def _on_opened(designer):
        _attach_when_ready(iface, designer)

    signal = getattr(iface, "layoutDesignerOpened", None)
    if signal is not None:
        signal.connect(_on_opened)
        _SIGNAL_HANDLERS[id(iface)] = (iface, _on_opened)

    # Attach to existing open layout designers
    with suppress(Exception):
        if hasattr(iface, "layoutDesigners"):
            for designer in iface.layoutDesigners():
                _attach_when_ready(iface, designer)


def teardown_designer_integration(iface, remove_docks: bool = True) -> None:
    """Disconnect the application hook and remove CartoLab-owned Designer UI."""
    registered = _SIGNAL_HANDLERS.pop(id(iface), None) if iface is not None else None
    if registered:
        registered_iface, callback = registered
        signal = getattr(registered_iface, "layoutDesignerOpened", None)
        if signal is not None:
            with suppress(Exception):
                signal.disconnect(callback)

    if not remove_docks:
        return
    for designer_id, dock in list(_INTEGRATED_DESIGNERS.items()):
        with suppress(Exception):
            dock.close()
            dock.deleteLater()
        _INTEGRATED_DESIGNERS.pop(designer_id, None)
    for designer_id, (menubar, menu) in list(_DESIGNER_MENUS.items()):
        with suppress(Exception):
            menubar.removeAction(menu.menuAction())
        with suppress(Exception):
            menu.deleteLater()
        _DESIGNER_MENUS.pop(designer_id, None)


def attach_cartolab_to_designer(iface, designer) -> bool:
    """Attach PlanX CartoLab embedded studio dock panel inside a QgsLayoutDesignerInterface window."""
    if designer is None:
        return False
    designer_id = id(designer)
    if designer_id in _INTEGRATED_DESIGNERS:
        return True

    main_win = _designer_window(designer)

    if main_win is None:
        return False

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
    main_win.addDockWidget(_RightDock, dock)
    dock.show()
    _INTEGRATED_DESIGNERS[designer_id] = dock
    with suppress(Exception):
        dock.destroyed.connect(
            lambda _obj=None, key=designer_id: _INTEGRATED_DESIGNERS.pop(key, None)
        )

    # 2. Add single 02CartoLab Menu item and QToolBar Action Button
    with suppress(Exception):
        act_toggle = dock.toggleViewAction()
        act_toggle.setText("02CartoLab Studio")
        act_toggle.setIcon(icon)
        act_toggle.setCheckable(True)

        menubar = main_win.menuBar()
        if menubar:
            menu = QMenu("&02CartoLab", menubar)
            menu.setObjectName("CartoLabDesignerMenu")
            menu.addAction(act_toggle)
            menubar.addMenu(menu)
            _DESIGNER_MENUS[designer_id] = (menubar, menu)

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
    return True


_STANDARD_SCALES = (500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000,
                    100000, 200000, 250000, 500000, 1000000)


def snap_to_standard_scale(scale: float) -> int:
    """Nearest standard scale denominator (log distance)."""
    return min(_STANDARD_SCALES, key=lambda s: abs(math.log(s) - math.log(max(1.0, scale))))


def export_layout_and_report(layout, path: str, dpi: int) -> tuple:
    """Export for the dock's "Export & Open" button: ``(ok, message)``.

    A failed export returns ``False`` with the reason so the dock can show it
    instead of silently doing nothing.
    """
    from .layout_utils import export_layout, last_export_error
    if export_layout(layout, path, dpi=int(dpi)) and os.path.exists(path):
        return True, path
    return False, last_export_error() or f"The layout could not be exported to {path}."


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
            padding: 7px 9px;
            font-weight: 600;
            font-size: 10px;
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

    def _add_scroll_tab(widget, label):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame if hasattr(QScrollArea, "Shape") else 0)
        no_horizontal = getattr(
            getattr(Qt, "ScrollBarPolicy", Qt), "ScrollBarAlwaysOff",
            getattr(Qt, "ScrollBarAlwaysOff", 1),
        )
        scroll.setHorizontalScrollBarPolicy(no_horizontal)
        scroll.setWidget(widget)
        return tabs.addTab(scroll, label)

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

    _add_scroll_tab(tab_tpl, "Templates")

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

    btn_dock_preflight = QPushButton("Run Print Preflight")
    btn_dock_preflight.setObjectName("ghost")
    btn_dock_preflight.setIcon(_get_cartolab_icon("layout.png"))

    def _dock_preflight():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .preflight import format_preflight_report, preflight_layout
            issues = preflight_layout(layout)
            report = format_preflight_report(layout, issues)
            if any(issue["severity"] == "error" for issue in issues):
                QMessageBox.warning(parent_win, "Print Preflight", report)
            else:
                QMessageBox.information(parent_win, "Print Preflight", report)
        except Exception as exc:
            QMessageBox.critical(parent_win, "Print Preflight Error", str(exc))

    btn_dock_preflight.clicked.connect(_dock_preflight)
    fl_typo.addRow(btn_dock_preflight)

    pixel_status = QLabel("Pixel QA · export not checked yet")
    pixel_status.setWordWrap(True)
    pixel_status.setStyleSheet(
        "background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;"
        "border-radius:6px;padding:7px;font-weight:600;"
    )
    fl_typo.addRow(pixel_status)

    layout_safe_margin = QDoubleSpinBox()
    layout_safe_margin.setRange(0.0, 25.0)
    layout_safe_margin.setValue(3.0)
    layout_safe_margin.setSuffix(" mm")
    fl_typo.addRow("Pixel safe edge:", layout_safe_margin)

    btn_pixel_qa = QPushButton("Render & Validate Pixels · 150 DPI")
    btn_pixel_qa.setIcon(_get_cartolab_icon("layout.png"))

    def _run_pixel_qa():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        descriptor, path = tempfile.mkstemp(prefix="cartolab_pixel_qa_", suffix=".png")
        os.close(descriptor)
        with suppress(OSError):
            os.remove(path)
        try:
            from .layout_utils import export_layout
            from .pixel_qa import analyze_export, format_pixel_report, validate_pixels
            if not export_layout(layout, path, dpi=150):
                raise RuntimeError("QGIS could not render the layout for pixel inspection.")
            safe_margin = layout_safe_margin.value()
            metrics = analyze_export(path, dpi=150, safe_margin_mm=safe_margin)
            issues = validate_pixels(metrics, safe_margin_mm=safe_margin)
            report = format_pixel_report(metrics, issues)
            has_error = any(issue["severity"] == "error" for issue in issues)
            pixel_status.setText(
                f"Pixel QA · {'BLOCKED' if has_error else 'READY' if not issues else 'CHECK'} · "
                f"edge ink {metrics.edge_ink_ratio * 100:.2f}% · "
                f"{metrics.unique_color_buckets} colour buckets"
            )
            pixel_status.setStyleSheet(
                ("background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;" if has_error
                 else "background:#fef3c7;color:#92400e;border:1px solid #fcd34d;" if issues
                 else "background:#dcfce7;color:#166534;border:1px solid #86efac;")
                + "border-radius:6px;padding:7px;font-weight:700;"
            )
            if issues:
                QMessageBox.warning(parent_win, "Pixel QA", report)
            else:
                QMessageBox.information(parent_win, "Pixel QA", report)
        except Exception as exc:
            pixel_status.setText("Pixel QA · render failed")
            QMessageBox.critical(parent_win, "Pixel QA Error", str(exc))
        finally:
            with suppress(OSError):
                os.remove(path)

    btn_pixel_qa.clicked.connect(_run_pixel_qa)
    fl_typo.addRow(btn_pixel_qa)

    lyt_canvas.addWidget(gb_typo)
    lyt_canvas.addStretch()

    _add_scroll_tab(tab_canvas, "Grid")


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
    # Corner colours (ll, lh, hl, hh) come from the engine's presets so the
    # legend always matches the bivariate renderer's corner meaning.
    from ..core.bivariate_engine import BIVARIATE_PALETTE_PRESETS
    for _preset in BIVARIATE_PALETTE_PRESETS.values():
        palette_combo.addItem(
            _preset.get("label", "Palette"),
            (_preset["ll"], _preset["lh"], _preset["hl"], _preset["hh"]),
        )
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

        colors = palette_combo.currentData()
        ltype = shape_combo.currentData()
        x_lbl = xlabel_input.text().strip() or "Variable X"
        y_lbl = ylabel_input.text().strip() or "Variable Y"
        try:
            # Rebuild at the old group's top-left corner so updates never drift.
            from .legend_decorator import replace_bivariate_legend
            replace_bivariate_legend(layout, selected, colors=colors, legend_type=ltype,
                                     x_label=x_lbl, y_label=y_lbl)
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
        from .layout_utils import main_map_item
        main_map = main_map_item(layout)
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

    lyt_dec.addWidget(gb_map_elem)

    # Dedicated Publication Coordinate Grid Group
    gb_grid = QGroupBox("Publication Coordinate Grid")
    fl_grid = QFormLayout(gb_grid)

    grid_preset_combo = QComboBox()
    from .grid_presets import list_grid_presets
    for preset_meta in list_grid_presets():
        grid_preset_combo.addItem(
            f"{preset_meta['name']} · {preset_meta['category']}", preset_meta["id"]
        )
    fl_grid.addRow("Preset Gallery:", grid_preset_combo)

    btn_apply_grid_preset = QPushButton("Apply Selected Grid Composition")
    btn_apply_grid_preset.setIcon(_get_cartolab_icon("grid.png"))

    def _dock_grid_preset():
        layout = _get_designer_layout(designer)
        if not layout:
            return
        try:
            from .grid_presets import apply_grid_preset
            grids = apply_grid_preset(layout, grid_preset_combo.currentData())
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess(
                    "CartoLab", f"Applied {len(grids)} grid layer(s): {grid_preset_combo.currentText()}"
                )
        except Exception as exc:
            QMessageBox.critical(parent_win, "Grid Preset Error", str(exc))

    btn_apply_grid_preset.clicked.connect(_dock_grid_preset)
    fl_grid.addRow(btn_apply_grid_preset)

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

    btn_dock_grid = QPushButton("Apply Custom Grid Settings")
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
        from .layout_utils import main_map_item
        item = main_map_item(layout)
        if item is None:
            QMessageBox.warning(parent_win, "Snap Scale", "No map item found in layout.")
            return
        best = snap_to_standard_scale(item.scale())
        item.setScale(best)
        item.updateBoundingRect()
        layout.refresh()
        if hasattr(iface, "messageBar"):
            iface.messageBar().pushSuccess("CartoLab", f"Map scale snapped to 1:{best:,}")

    btn_snap_scale.clicked.connect(_dock_snap_scale)
    fl_smart.addRow(btn_snap_scale)
    lyt_dec.addWidget(gb_smart)

    lyt_dec.addStretch()

    _add_scroll_tab(tab_dec, "Decorate")

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
                QMessageBox.warning(parent_win, "Atlas Setup", "Could not configure the atlas: the layout has no atlas support, the filter "
                                    "is invalid, or the coverage layer has no matching features.")
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
            ok, message = export_layout_and_report(layout, path, int(dpi or 300))
        except Exception as exc:
            QMessageBox.critical(parent_win, "Export Error", str(exc))
            return
        if not ok:
            QMessageBox.warning(parent_win, "Export Error", message)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        if hasattr(iface, "messageBar"):
            iface.messageBar().pushSuccess("CartoLab", f"Exported & Opened: {path}")

    btn_dock_export.clicked.connect(_dock_export)
    fl_exp.addRow(btn_dock_export)
    lyt_exp.addWidget(gb_exp)
    lyt_exp.addStretch()

    _add_scroll_tab(tab_exp, "Export")

    # -----------------------------------------------------------------
    # TAB 4: Native Print Layout Charts
    # -----------------------------------------------------------------
    tab_graph = QWidget()
    lyt_graph = QVBoxLayout(tab_graph)
    lyt_graph.setContentsMargins(8, 8, 8, 8)
    lyt_graph.setSpacing(10)

    gb_graph_data = QGroupBox("Add Graph · Layer Data")
    fl_graph_data = QFormLayout(gb_graph_data)
    graph_layer_combo = QComboBox()
    if QgsProject and QgsProject.instance():
        for layer in QgsProject.instance().mapLayers().values():
            if hasattr(layer, "fields") and hasattr(layer, "getFeatures"):
                graph_layer_combo.addItem(layer.name(), layer)
    fl_graph_data.addRow("Layer:", graph_layer_combo)

    graph_type_combo = QComboBox()
    for key, label in (
        ("bar", "Bar"), ("grouped_bar", "Grouped Bar"),
        ("stacked_bar", "Stacked Bar"), ("line", "Line"),
        ("multi_line", "Multi-series Line"), ("area", "Area"),
        ("scatter", "Scatter"), ("pie", "Pie"), ("donut", "Donut"),
        ("histogram", "Histogram"),
    ):
        graph_type_combo.addItem(label, key)
    fl_graph_data.addRow("Chart:", graph_type_combo)

    graph_category_combo = QComboBox()
    graph_series_combo = QComboBox()
    graph_value_combo = QComboBox()
    graph_aggregation_combo = QComboBox()
    for key, label in (
        ("count", "Count"), ("sum", "Sum"), ("mean", "Mean"),
        ("median", "Median"), ("min", "Minimum"), ("max", "Maximum"),
    ):
        graph_aggregation_combo.addItem(label, key)
    fl_graph_data.addRow("Category / X:", graph_category_combo)
    fl_graph_data.addRow("Series:", graph_series_combo)
    fl_graph_data.addRow("Value / Y:", graph_value_combo)
    fl_graph_data.addRow("Summary:", graph_aggregation_combo)

    def _refresh_graph_fields():
        layer = graph_layer_combo.currentData()
        graph_category_combo.clear()
        graph_series_combo.clear()
        graph_series_combo.addItem("(single series)", "")
        graph_value_combo.clear()
        graph_value_combo.addItem("(not required for count)", "")
        if layer is None:
            return
        for field in layer.fields():
            graph_category_combo.addItem(field.name(), field.name())
            graph_series_combo.addItem(field.name(), field.name())
            with suppress(Exception):
                if field.isNumeric():
                    graph_value_combo.addItem(field.name(), field.name())

    graph_layer_combo.currentIndexChanged.connect(_refresh_graph_fields)
    _refresh_graph_fields()
    lyt_graph.addWidget(gb_graph_data)

    gb_graph_layout = QGroupBox("Frame and Publication Settings")
    fl_graph_layout = QFormLayout(gb_graph_layout)
    graph_title = QLineEdit("Layer summary")
    fl_graph_layout.addRow("Title:", graph_title)

    graph_top_n = QSpinBox()
    graph_top_n.setRange(1, 50)
    graph_top_n.setValue(10)
    fl_graph_layout.addRow("Top N:", graph_top_n)

    graph_bins = QSpinBox()
    graph_bins.setRange(3, 40)
    graph_bins.setValue(8)
    fl_graph_layout.addRow("Histogram bins:", graph_bins)

    from .charts import PALETTES, discover_zero2viz_themes
    graph_theme = QComboBox()
    built_in_themes = [
        {"id": "editorial", "label": "Editorial", "provider": "02CartoLab",
         "palette": PALETTES["Editorial"], "surface": ("#ffffff", "#0f172a", "#e2e8f0"),
         "font_family": "Segoe UI", "title_size_pt": 9.0, "label_size_pt": 5.6,
         "line_width_mm": 0.65},
        {"id": "dark_ink", "label": "Dark Ink", "provider": "02CartoLab",
         "palette": PALETTES["Colorblind Safe"], "surface": ("#0f172a", "#f8fafc", "#334155"),
         "font_family": "Segoe UI", "title_size_pt": 9.5, "label_size_pt": 5.7,
         "line_width_mm": 0.72},
    ]
    for theme in built_in_themes:
        graph_theme.addItem(f"CartoLab · {theme['label']}", theme)
    external_themes, theme_status_text = discover_zero2viz_themes()
    for theme in external_themes:
        graph_theme.addItem(f"02viz · {theme['label']}", theme)
    fl_graph_layout.addRow("Theme:", graph_theme)

    graph_theme_status = QLabel(theme_status_text)
    graph_theme_status.setWordWrap(True)
    graph_theme_status.setStyleSheet(
        ("background:#dcfce7;color:#166534;border:1px solid #86efac;"
         if external_themes else
         "background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;")
        + "border-radius:5px;padding:5px;"
    )
    fl_graph_layout.addRow("Theme source:", graph_theme_status)

    graph_palette = QComboBox()
    for palette_name, colors in PALETTES.items():
        graph_palette.addItem(palette_name, colors)
    fl_graph_layout.addRow("Palette:", graph_palette)

    graph_surface = QComboBox()
    graph_surface.addItem("Paper White", ("#ffffff", "#0f172a", "#e2e8f0"))
    graph_surface.addItem("Warm Editorial", ("#fffbeb", "#292524", "#e7e5e4"))
    graph_surface.addItem("Soft Gray", ("#f8fafc", "#0f172a", "#cbd5e1"))
    graph_surface.addItem("Dark Ink", ("#0f172a", "#f8fafc", "#334155"))
    fl_graph_layout.addRow("Surface:", graph_surface)

    graph_color_status = QLabel()
    graph_color_status.setStyleSheet(
        "background:#dcfce7;color:#166534;border:1px solid #86efac;"
        "border-radius:5px;padding:5px;font-weight:700;"
    )
    fl_graph_layout.addRow("Color QA:", graph_color_status)

    def _refresh_graph_color_status():
        from .pixel_qa import contrast_ratio
        background, text_color, _grid_color = graph_surface.currentData()
        ratio = contrast_ratio(text_color, background)
        palette_min = min(contrast_ratio(color, background) for color in graph_palette.currentData())
        graph_color_status.setText(f"AA {ratio:.1f}:1 · palette min {palette_min:.1f}:1")

    def _ensure_combo_value(combo, label, value):
        index = combo.findData(value)
        if index < 0:
            combo.addItem(label, value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    def _apply_graph_theme(_index=0):
        theme = graph_theme.currentData() or built_in_themes[0]
        prefix = theme.get("provider", "02CartoLab")
        _ensure_combo_value(
            graph_palette, f"{prefix} · {theme['label']}", tuple(theme["palette"]),
        )
        _ensure_combo_value(
            graph_surface, f"{prefix} · {theme['label']}", tuple(theme["surface"]),
        )
        _refresh_graph_color_status()

    graph_palette.currentIndexChanged.connect(_refresh_graph_color_status)
    graph_surface.currentIndexChanged.connect(_refresh_graph_color_status)
    graph_theme.currentIndexChanged.connect(_apply_graph_theme)
    _apply_graph_theme()

    graph_show_values = QCheckBox("Show value labels")
    graph_show_values.setChecked(True)
    graph_show_legend = QCheckBox("Show chart legend")
    graph_show_legend.setChecked(True)
    fl_graph_layout.addRow(graph_show_values)
    fl_graph_layout.addRow(graph_show_legend)

    graph_safe_margin = QDoubleSpinBox()
    graph_safe_margin.setRange(0.0, 25.0)
    graph_safe_margin.setValue(3.0)
    graph_safe_margin.setSuffix(" mm")
    fl_graph_layout.addRow("Safe margin:", graph_safe_margin)

    graph_position = QComboBox()
    graph_position.addItem("Best available (least overlap)", "best")
    graph_position.addItem("Bottom-right", "bottom_right")
    graph_position.addItem("Bottom-left", "bottom_left")
    graph_position.addItem("Top-right", "top_right")
    graph_position.addItem("Top-left", "top_left")
    graph_position.addItem("Custom", "custom")
    fl_graph_layout.addRow("Position:", graph_position)

    graph_x = QDoubleSpinBox(); graph_x.setRange(0, 2000); graph_x.setValue(15); graph_x.setSuffix(" mm")
    graph_y = QDoubleSpinBox(); graph_y.setRange(0, 2000); graph_y.setValue(15); graph_y.setSuffix(" mm")
    graph_w = QDoubleSpinBox(); graph_w.setRange(35, 500); graph_w.setValue(90); graph_w.setSuffix(" mm")
    graph_h = QDoubleSpinBox(); graph_h.setRange(30, 500); graph_h.setValue(60); graph_h.setSuffix(" mm")
    fl_graph_layout.addRow("X:", graph_x)
    fl_graph_layout.addRow("Y:", graph_y)
    fl_graph_layout.addRow("Width:", graph_w)
    fl_graph_layout.addRow("Height:", graph_h)
    lyt_graph.addWidget(gb_graph_layout)

    graph_ids = QComboBox()
    with suppress(Exception):
        from .charts import list_charts
        active_layout = _get_designer_layout(designer)
        for chart_meta in list_charts(active_layout):
            title = chart_meta["spec"].get("title", "Chart")
            graph_ids.addItem(f"{title} · {chart_meta['id'][-10:]}", chart_meta["id"])

    def _graph_geometry(layout):
        page = layout.pageCollection().page(0)
        size = page.pageSize()
        page_w, page_h = float(size.width()), float(size.height())
        width, height = graph_w.value(), graph_h.value()
        margin = max(3.0, graph_safe_margin.value())
        preset = graph_position.currentData()
        x = graph_x.value()
        y = graph_y.value()
        if preset == "best":
            from .charts import best_position
            occupied = []
            for item in layout.items():
                item_id = item.id() if hasattr(item, "id") else ""
                if item_id.startswith("cartolab_chart_"):
                    continue
                with suppress(Exception):
                    class_name = type(item).__name__.lower()
                    if "page" in class_name:
                        continue
                    rect = item.sceneBoundingRect()
                    if rect.width() <= 0 or rect.height() <= 0:
                        continue
                    weight = 1.0 if "map" in class_name else 4.0
                    occupied.append(((rect.x(), rect.y(), rect.width(), rect.height()), weight))
            x, y = best_position(page_w, page_h, width, height, occupied, margin)
        elif preset == "bottom_right":
            x, y = page_w - margin - width, page_h - margin - height
        elif preset == "bottom_left":
            x, y = margin, page_h - margin - height
        elif preset == "top_right":
            x, y = page_w - margin - width, margin
        elif preset == "top_left":
            x, y = margin, margin
        return x, y, width, height

    btn_add_graph = QPushButton("Add Graph")
    btn_add_graph.setIcon(_get_cartolab_icon("chart.png"))

    def _add_graph():
        layout = _get_designer_layout(designer)
        layer = graph_layer_combo.currentData()
        if layout is None or layer is None:
            QMessageBox.warning(parent_win, "Add Graph", "Open a layout and select a vector layer first.")
            return
        try:
            from .charts import ChartSpec, add_chart_to_layout
            x, y, width, height = _graph_geometry(layout)
            theme = graph_theme.currentData() or built_in_themes[0]
            spec = ChartSpec(
                chart_type=graph_type_combo.currentData() or "bar",
                category_field=graph_category_combo.currentData() or "",
                value_field=graph_value_combo.currentData() or "",
                series_field=graph_series_combo.currentData() or "",
                aggregation=graph_aggregation_combo.currentData() or "count",
                title=graph_title.text().strip() or "Layer summary",
                x=x, y=y, width=width, height=height,
                top_n=graph_top_n.value(), bins=graph_bins.value(),
                show_values=graph_show_values.isChecked(),
                show_legend=graph_show_legend.isChecked(),
                palette=tuple(graph_palette.currentData()),
                background_color=graph_surface.currentData()[0],
                text_color=graph_surface.currentData()[1],
                grid_color=graph_surface.currentData()[2],
                theme_provider=theme.get("provider", "02CartoLab"),
                theme_id=theme.get("id", "editorial"),
                font_family=theme.get("font_family", "Segoe UI"),
                title_size_pt=theme.get("title_size_pt", 9.0),
                label_size_pt=theme.get("label_size_pt", 5.6),
                line_width_mm=theme.get("line_width_mm", 0.65),
                safe_margin_mm=graph_safe_margin.value(),
            )
            chart_id = add_chart_to_layout(layout, layer, spec)
            graph_ids.addItem(f"{graph_title.text().strip() or 'Chart'} · {chart_id[-10:]}", chart_id)
            if hasattr(iface, "messageBar"):
                iface.messageBar().pushSuccess("CartoLab", "Native chart added to Print Layout.")
        except Exception as exc:
            QMessageBox.critical(parent_win, "Add Graph Error", str(exc))

    btn_add_graph.clicked.connect(_add_graph)
    fl_graph_layout.addRow(btn_add_graph)

    btn_update_graph = QPushButton("Update Selected Graph")
    btn_update_graph.setObjectName("ghost")

    def _update_graph():
        layout = _get_designer_layout(designer)
        layer = graph_layer_combo.currentData()
        old_id = graph_ids.currentData()
        if layout is None or layer is None or not old_id:
            QMessageBox.warning(parent_win, "Update Graph", "Select an existing graph first.")
            return
        try:
            from .charts import ChartSpec, add_chart_to_layout, remove_chart
            x, y, width, height = _graph_geometry(layout)
            theme = graph_theme.currentData() or built_in_themes[0]
            spec = ChartSpec(
                chart_type=graph_type_combo.currentData() or "bar",
                category_field=graph_category_combo.currentData() or "",
                value_field=graph_value_combo.currentData() or "",
                series_field=graph_series_combo.currentData() or "",
                aggregation=graph_aggregation_combo.currentData() or "count",
                title=graph_title.text().strip() or "Layer summary",
                x=x, y=y, width=width, height=height,
                top_n=graph_top_n.value(), bins=graph_bins.value(),
                show_values=graph_show_values.isChecked(),
                show_legend=graph_show_legend.isChecked(),
                palette=tuple(graph_palette.currentData()),
                background_color=graph_surface.currentData()[0],
                text_color=graph_surface.currentData()[1],
                grid_color=graph_surface.currentData()[2],
                theme_provider=theme.get("provider", "02CartoLab"),
                theme_id=theme.get("id", "editorial"),
                font_family=theme.get("font_family", "Segoe UI"),
                title_size_pt=theme.get("title_size_pt", 9.0),
                label_size_pt=theme.get("label_size_pt", 5.6),
                line_width_mm=theme.get("line_width_mm", 0.65),
                safe_margin_mm=graph_safe_margin.value(),
            )
            new_id = add_chart_to_layout(layout, layer, spec)
            remove_chart(layout, old_id)
            index = graph_ids.currentIndex()
            graph_ids.setItemText(index, f"{spec.title} · {new_id[-10:]}")
            graph_ids.setItemData(index, new_id)
            layout.refresh()
        except Exception as exc:
            QMessageBox.critical(parent_win, "Update Graph Error", str(exc))

    btn_update_graph.clicked.connect(_update_graph)
    fl_graph_layout.addRow(btn_update_graph)

    btn_remove_graph = QPushButton("Remove Graph")
    btn_remove_graph.setObjectName("ghost")

    def _remove_graph():
        layout = _get_designer_layout(designer)
        chart_id = graph_ids.currentData()
        if layout is None or not chart_id:
            return
        from .charts import remove_chart
        if remove_chart(layout, chart_id):
            graph_ids.removeItem(graph_ids.currentIndex())
            layout.refresh()

    btn_remove_graph.clicked.connect(_remove_graph)
    fl_graph_layout.addRow("Added charts:", graph_ids)
    fl_graph_layout.addRow(btn_remove_graph)

    def _select_combo_data(combo, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _load_graph_settings(_index=0):
        chart_id = graph_ids.currentData()
        layout = _get_designer_layout(designer)
        if not chart_id or layout is None:
            return
        from .charts import list_charts
        meta = next((entry for entry in list_charts(layout) if entry["id"] == chart_id), None)
        if not meta:
            return
        for index in range(graph_layer_combo.count()):
            layer = graph_layer_combo.itemData(index)
            if layer is not None and hasattr(layer, "id") and layer.id() == meta["layer_id"]:
                graph_layer_combo.setCurrentIndex(index)
                break
        spec = meta["spec"]
        _select_combo_data(graph_type_combo, spec.get("chart_type", "bar"))
        _select_combo_data(graph_category_combo, spec.get("category_field", ""))
        _select_combo_data(graph_series_combo, spec.get("series_field", ""))
        _select_combo_data(graph_value_combo, spec.get("value_field", ""))
        _select_combo_data(graph_aggregation_combo, spec.get("aggregation", "count"))
        graph_title.setText(spec.get("title", "Chart"))
        graph_top_n.setValue(int(spec.get("top_n", 10)))
        graph_bins.setValue(int(spec.get("bins", 8)))
        graph_show_values.setChecked(bool(spec.get("show_values", True)))
        graph_show_legend.setChecked(bool(spec.get("show_legend", True)))
        graph_safe_margin.setValue(float(spec.get("safe_margin_mm", 3.0)))
        for theme_index in range(graph_theme.count()):
            theme = graph_theme.itemData(theme_index) or {}
            if (theme.get("provider") == spec.get("theme_provider", "02CartoLab")
                    and theme.get("id") == spec.get("theme_id", "editorial")):
                graph_theme.setCurrentIndex(theme_index)
                break
        palette = tuple(spec.get("palette", ()))
        _select_combo_data(graph_palette, palette)
        surface = (spec.get("background_color", "#ffffff"), spec.get("text_color", "#0f172a"), spec.get("grid_color", "#e2e8f0"))
        _select_combo_data(graph_surface, surface)
        graph_x.setValue(float(spec.get("x", 15.0)))
        graph_y.setValue(float(spec.get("y", 15.0)))
        graph_w.setValue(float(spec.get("width", 90.0)))
        graph_h.setValue(float(spec.get("height", 60.0)))
        _select_combo_data(graph_position, "custom")

    graph_ids.currentIndexChanged.connect(_load_graph_settings)
    if graph_ids.count():
        _load_graph_settings()
    lyt_graph.addStretch()
    _add_scroll_tab(tab_graph, "Add Graph")

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
