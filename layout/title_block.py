# -*- coding: utf-8 -*-
"""
PlanX CartoLab — Layout Title Block Decorator.

Provides clean architectural & Swiss-style title block headers for QGIS Print Layouts.
"""
from __future__ import annotations

import datetime
from typing import List, Optional
from contextlib import suppress

try:
    from qgis.core import (
        QgsFillSymbol,
        QgsLayout,
        QgsLayoutItemGroup,
        QgsLayoutItemLabel,
        QgsLayoutItemShape,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
    )
    from qgis.PyQt.QtGui import QColor
except ImportError:
    QgsLayout = QgsLayoutItemGroup = QgsLayoutItemLabel = QgsLayoutItemShape = QgsUnitTypes = QgsFillSymbol = QColor = None

_MM = QgsUnitTypes.LayoutUnit.LayoutMillimeters if QgsUnitTypes else 0

from .map_sheet import _font


def add_publication_title_block(
    layout: QgsLayout,
    title: str = "URBAN ANALYTICS STUDIO",
    subtitle: str = "Spatial Dynamics & Cartographic Synthesis",
    author: str = "Yusuf Eminoğlu",
    position: tuple = (15.0, 15.0),
    width_mm: float = 120.0,
) -> Optional[QgsLayoutItemGroup]:
    """
    Insert a publication title block header group with title, subtitle, author, and date.
    """
    if layout is None or QgsLayoutItemLabel is None:
        return None

    x0, y0 = position
    items: List = []

    # Background Panel Shape
    panel = QgsLayoutItemShape(layout)
    panel.setId("cartolab_title_block_panel")
    rectangle = getattr(
        getattr(QgsLayoutItemShape, "Shape", QgsLayoutItemShape),
        "Rectangle",
        getattr(QgsLayoutItemShape, "Rectangle", None),
    )
    if rectangle is not None:
        panel.setShapeType(rectangle)
    panel.attemptMove(QgsLayoutPoint(x0, y0, _MM))
    panel.attemptResize(QgsLayoutSize(width_mm, 28.0, _MM))

    symbol = QgsFillSymbol.createSimple({
        "color": "#ffffff",
        "outline_color": "#0f172a",
        "outline_width": "0.4",
    })
    panel.setSymbol(symbol)
    layout.addLayoutItem(panel)
    items.append(panel)

    # Title Label
    title_label = QgsLayoutItemLabel(layout)
    title_label.setId("cartolab_title")
    title_label.setText(title.upper())
    title_label.setFont(_font(12, bold=True))
    title_label.setFontColor(QColor("#0f172a"))
    title_label.attemptMove(QgsLayoutPoint(x0 + 4.0, y0 + 3.0, _MM))
    title_label.adjustSizeToText()
    layout.addLayoutItem(title_label)
    items.append(title_label)

    # Subtitle Label
    sub_label = QgsLayoutItemLabel(layout)
    sub_label.setId("cartolab_subtitle")
    sub_label.setText(subtitle)
    sub_label.setFont(_font(8))
    sub_label.setFontColor(QColor("#475569"))
    sub_label.attemptMove(QgsLayoutPoint(x0 + 4.0, y0 + 11.0, _MM))
    sub_label.adjustSizeToText()
    layout.addLayoutItem(sub_label)
    items.append(sub_label)

    # Metadata Strip (Author & Date)
    now_str = datetime.date.today().strftime("%Y-%m-%d")
    meta_text = f"AUTHOR: {author}  |  DATE: {now_str}  |  PLANX CARTOLAB"
    meta_label = QgsLayoutItemLabel(layout)
    meta_label.setId("cartolab_title_metadata")
    meta_label.setText(meta_text)
    meta_label.setFont(_font(7, family="Consolas"))
    meta_label.setFontColor(QColor("#64748b"))
    meta_label.attemptMove(QgsLayoutPoint(x0 + 4.0, y0 + 19.0, _MM))
    meta_label.adjustSizeToText()
    layout.addLayoutItem(meta_label)
    items.append(meta_label)

    group = layout.groupItems(items)
    with suppress(Exception):
        group.setId("cartolab_title_block")
    layout.refresh()
    return group
