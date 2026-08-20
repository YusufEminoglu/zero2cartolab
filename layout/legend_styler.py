# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Legend Styler Engine.

Provides publication-quality legend styling for QgsLayoutItemLegend items in QGIS Print Layouts.
"""
from __future__ import annotations

from typing import Optional

try:
    from qgis.core import (
        QgsLayout,
        QgsLayoutItemLegend,
        QgsLegendStyle,
        QgsUnitTypes,
    )
    from qgis.PyQt.QtGui import QColor, QFont
except ImportError:
    QgsLayout = QgsLayoutItemLegend = QgsLegendStyle = QgsUnitTypes = QColor = QFont = None

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0


def style_layout_legend(
    layout: QgsLayout,
    title: str = "LEGEND",
    columns: int = 1,
    font_family: str = "Inter",
    show_title: bool = True,
) -> Optional[QgsLayoutItemLegend]:
    """
    Format and style all QgsLayoutItemLegend items in the layout with publication-ready typography.

    Returns the first styled legend item or None if no legend exists.
    """
    if layout is None or QgsLayoutItemLegend is None:
        return None

    target_legend = None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemLegend):
            target_legend = item
            break

    if target_legend is None:
        # Create a new legend item if none exists
        target_legend = QgsLayoutItemLegend(layout)
        layout.addLayoutItem(target_legend)

    # Configure title and columns
    target_legend.setTitle(title if show_title else "")
    target_legend.setColumnCount(max(1, columns))

    # Configure fonts if QFont is available
    if QFont is not None:
        title_font = QFont(font_family, 10, QFont.Weight.Bold)
        group_font = QFont(font_family, 9, QFont.Weight.DemiBold)
        subgroup_font = QFont(font_family, 8, QFont.Weight.Medium)
        item_font = QFont(font_family, 8, QFont.Weight.Normal)

        if hasattr(target_legend, "setStyleFont"):
            _S = getattr(QgsLegendStyle, "Style", QgsLegendStyle)
            _Title = getattr(_S, "Title", getattr(QgsLegendStyle, "Title", 0))
            _Group = getattr(_S, "Group", getattr(QgsLegendStyle, "Group", 1))
            _Subgroup = getattr(_S, "Subgroup", getattr(QgsLegendStyle, "Subgroup", 2))
            _SymbolLabel = getattr(_S, "SymbolLabel", getattr(QgsLegendStyle, "SymbolLabel", 4))
            target_legend.setStyleFont(_Title, title_font)
            target_legend.setStyleFont(_Group, group_font)
            target_legend.setStyleFont(_Subgroup, subgroup_font)
            target_legend.setStyleFont(_SymbolLabel, item_font)

    target_legend.setSymbolWidth(6.0)
    target_legend.setSymbolHeight(4.0)
    target_legend.setBoxSpace(2.5)

    # Sanitize layer item titles automatically (e.g. ss_choice_median -> Choice Median)
    if hasattr(target_legend, "model"):
        model = target_legend.model()
        if model and hasattr(model, "rootGroup"):
            root = model.rootGroup()
            if root:
                for child in root.children():
                    if hasattr(child, "name") and hasattr(child, "setName"):
                        raw_name = child.name()
                        clean_name = raw_name.replace("_", " ").title()
                        clean_name = clean_name.replace("Ss ", "").replace("Gic ", "")
                        child.setName(clean_name)

    layout.refresh()
    return target_legend
