# -*- coding: utf-8 -*-
"""
HTML Graph Factory — Zero-dependency JS/HTML dump generator.

Produces self-contained HTML fragments for:
  - Floating radar (spider) chart annotations
  - Bar/line micro-charts
  - Bivariate legend matrices

All fragments are inline, single-file, and styled with Tailwind-CSS-like
utility classes — no network dependency.
"""
from __future__ import annotations

import html
import json
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


HTML_CARD_THEMES: Dict[str, Dict[str, str]] = {
    "swiss_modern": {
        "bg": "#ffffff",
        "panel_bg": "#f8fafc",
        "border": "#cbd5e1",
        "text": "#0f172a",
        "muted": "#475569",
        "accent": "#2563eb",
        "row_alt": "#f1f5f9",
        "font": "Segoe UI, Inter, Arial, sans-serif",
    },
    "dark_matter": {
        "bg": "#0f172a",
        "panel_bg": "#1e293b",
        "border": "#334155",
        "text": "#f8fafc",
        "muted": "#94a3b8",
        "accent": "#38bdf8",
        "row_alt": "#1e293b",
        "font": "Segoe UI, Inter, Arial, sans-serif",
    },
    "blueprint": {
        "bg": "#0b2545",
        "panel_bg": "#134074",
        "border": "#38bdf8",
        "text": "#e0f2fe",
        "muted": "#bae6fd",
        "accent": "#38bdf8",
        "row_alt": "#134074",
        "font": "Consolas, Segoe UI, monospace",
    },
    "warm_editorial": {
        "bg": "#fdfbf7",
        "panel_bg": "#f5f0e6",
        "border": "#d6d3d1",
        "text": "#292524",
        "muted": "#57534e",
        "accent": "#b45309",
        "row_alt": "#f5f0e6",
        "font": "Georgia, Segoe UI, serif",
    },
    "sepia_atlas": {
        "bg": "#f4ebd9",
        "panel_bg": "#eadbc0",
        "border": "#a89078",
        "text": "#3d2612",
        "muted": "#6e473b",
        "accent": "#8c510a",
        "row_alt": "#eadbc0",
        "font": "Georgia, Times New Roman, serif",
    },
}


def _resolve_card_theme(theme: str = "swiss_modern", accent_override: Optional[str] = None) -> Dict[str, str]:
    base = dict(HTML_CARD_THEMES.get(theme, HTML_CARD_THEMES["swiss_modern"]))
    if accent_override and isinstance(accent_override, str) and accent_override.startswith("#"):
        base["accent"] = accent_override
    return base


def _esc(val: Any) -> str:
    """Escape plain text while preserving QGIS `[% ... %]` expressions intact."""
    raw = "" if val is None else str(val)
    if "[%" in raw and "%]" in raw:
        return raw
    return html.escape(raw)


def build_kpi_summary_html(
    title: str,
    metrics: Sequence[Dict[str, Any]],
    subtitle: str = "",
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
) -> str:
    """
    Build a Qt-rich-text & HTML5 compatible KPI summary card for Print Layouts.

    Each item in ``metrics`` may contain:
      - ``label`` (str): Metric title
      - ``value`` (str | float | int): Primary formatted value or QGIS expression
      - ``unit`` (str, optional): Suffix unit (e.g., '%', 'km²', 'ha')
      - ``pct`` (float, optional): 0..100 bar fill percentage
    """
    pal = _resolve_card_theme(theme, accent_color)
    safe_title = _esc(title or "KEY INDICATORS")
    safe_sub = _esc(subtitle)

    rows_html = []
    clean_metrics = list(metrics or [])
    if not clean_metrics:
        clean_metrics = [{"label": "Features", "value": "[% @atlas_totalfeatures %]", "unit": ""}]

    for idx in range(0, len(clean_metrics), 2):
        pair = clean_metrics[idx : idx + 2]
        cells = []
        for m in pair:
            lbl = _esc(m.get("label", "Metric"))
            val = _esc(m.get("value", "—"))
            unit = _esc(m.get("unit", ""))
            unit_span = f" <span style='font-size:7pt;color:{pal['muted']};'>{unit}</span>" if unit else ""
            pct = m.get("pct")
            bar_html = ""
            if isinstance(pct, (int, float)) and math.isfinite(pct):
                clamped = max(4, min(100, int(round(float(pct)))))
                bar_html = (
                    f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-top:2px;'>"
                    f"<tr><td width='{clamped}%' bgcolor='{pal['accent']}' style='font-size:2pt;'>&nbsp;</td>"
                    f"<td width='{100 - clamped}%' bgcolor='{pal['border']}' style='font-size:2pt;'>&nbsp;</td></tr>"
                    f"</table>"
                )
            cells.append(
                f"<td width='50%' valign='top' bgcolor='{pal['panel_bg']}' "
                f"style='padding:5px 7px;border:1px solid {pal['border']};'>"
                f"<div style='font-size:6.5pt;color:{pal['muted']};font-weight:600;text-transform:uppercase;'>{lbl}</div>"
                f"<div style='font-size:10.5pt;color:{pal['text']};font-weight:700;margin-top:1px;'>{val}{unit_span}</div>"
                f"{bar_html}"
                f"</td>"
            )
        if len(cells) == 1:
            cells.append(f"<td width='50%' bgcolor='{pal['bg']}'></td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    sub_block = (
        f"<div style='font-size:6.8pt;color:{pal['muted']};margin-top:1px;'>{safe_sub}</div>"
        if safe_sub
        else ""
    )

    return (
        f"<div style='font-family:{pal['font']};background-color:{pal['bg']};color:{pal['text']};"
        f"padding:6px;border:1px solid {pal['border']};'>"
        f"<div style='border-left:3px solid {pal['accent']};padding-left:6px;margin-bottom:5px;'>"
        f"<div style='font-size:8.5pt;font-weight:700;color:{pal['text']};letter-spacing:0.4px;'>{safe_title}</div>"
        f"{sub_block}"
        f"</div>"
        f"<table width='100%' cellspacing='3' cellpadding='0'>"
        f"{''.join(rows_html)}"
        f"</table>"
        f"</div>"
    )


def build_attribute_table_html(
    title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    subtitle: str = "",
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
    highlight_first: bool = True,
) -> str:
    """
    Build a publication-styled HTML table for Print Layout summary frames.
    """
    pal = _resolve_card_theme(theme, accent_color)
    safe_title = _esc(title or "ATTRIBUTE SUMMARY TABLE")
    safe_sub = _esc(subtitle)

    hdr_cells = []
    for h_idx, h_text in enumerate(headers or ("Category", "Value")):
        align = "right" if h_idx > 0 and h_idx == len(headers) - 1 else "left"
        hdr_cells.append(
            f"<th align='{align}' bgcolor='{pal['accent']}' "
            f"style='padding:4px 6px;color:#ffffff;font-size:7pt;font-weight:700;'>"
            f"{_esc(h_text)}</th>"
        )

    body_rows = []
    for r_idx, row in enumerate(rows or []):
        bg = pal["row_alt"] if r_idx % 2 == 1 else pal["bg"]
        weight = "700" if (highlight_first and r_idx == 0) else "400"
        row_cells = []
        for c_idx, cell_val in enumerate(row):
            align = "right" if c_idx > 0 and c_idx == len(row) - 1 else "left"
            row_cells.append(
                f"<td align='{align}' bgcolor='{bg}' "
                f"style='padding:3px 6px;font-size:7.2pt;color:{pal['text']};font-weight:{weight};"
                f"border-bottom:1px solid {pal['border']};'>{_esc(cell_val)}</td>"
            )
        body_rows.append("<tr>" + "".join(row_cells) + "</tr>")

    if not body_rows:
        colspan = max(1, len(headers or (1,)))
        body_rows.append(
            f"<tr><td colspan='{colspan}' style='padding:6px;font-size:7pt;color:{pal['muted']};'>"
            f"No records available</td></tr>"
        )

    sub_block = (
        f"<div style='font-size:6.5pt;color:{pal['muted']};margin-bottom:4px;'>{safe_sub}</div>"
        if safe_sub
        else ""
    )

    return (
        f"<div style='font-family:{pal['font']};background-color:{pal['bg']};color:{pal['text']};"
        f"padding:6px;border:1px solid {pal['border']};'>"
        f"<div style='font-size:8.5pt;font-weight:700;color:{pal['text']};margin-bottom:2px;'>{safe_title}</div>"
        f"{sub_block}"
        f"<table width='100%' cellspacing='0' cellpadding='0' style='border-collapse:collapse;'>"
        f"<thead><tr>{''.join(hdr_cells)}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table>"
        f"</div>"
    )


def build_atlas_profile_html(
    title_expr: str = "[% @atlas_pagename %]",
    fields: Sequence[Tuple[str, str]] = (),
    subtitle: str = "ATLAS FEATURE DOSSIER",
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
) -> str:
    """
    Build a dynamic QGIS-expression-driven HTML card for Atlas pages.

    Each tuple in ``fields`` is ``(display_label, field_name_or_expression)``.
    If the second item does not contain ``[%``, it is automatically wrapped in
    ``[% "field_name" %]``.
    """
    pal = _resolve_card_theme(theme, accent_color)
    safe_sub = _esc(subtitle)
    safe_title = _esc(title_expr or "[% @atlas_pagename %]")

    field_rows = []
    items = list(fields or [])
    if not items:
        items = [
            ("Feature ID", "[% @atlas_featureid %]"),
            ("Sheet Index", "[% @atlas_featurenumber %] / [% @atlas_totalfeatures %]"),
        ]

    for idx, (label, field_or_expr) in enumerate(items):
        raw_expr = str(field_or_expr).strip()
        if "[%" not in raw_expr:
            escaped_field = raw_expr.replace('"', '""')
            expr_str = f'[% "{escaped_field}" %]'
        else:
            expr_str = raw_expr
        bg = pal["row_alt"] if idx % 2 == 1 else pal["bg"]
        field_rows.append(
            f"<tr>"
            f"<td width='42%' bgcolor='{bg}' style='padding:3px 6px;font-size:7pt;color:{pal['muted']};font-weight:600;'>"
            f"{_esc(label)}</td>"
            f"<td width='58%' align='right' bgcolor='{bg}' style='padding:3px 6px;font-size:7.4pt;color:{pal['text']};font-weight:700;'>"
            f"{expr_str}</td>"
            f"</tr>"
        )

    return (
        f"<div style='font-family:{pal['font']};background-color:{pal['bg']};color:{pal['text']};"
        f"padding:6px;border:1px solid {pal['border']};'>"
        f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:4px;'>"
        f"<tr>"
        f"<td style='border-left:3px solid {pal['accent']};padding-left:6px;'>"
        f"<div style='font-size:6.2pt;color:{pal['accent']};font-weight:700;letter-spacing:0.6px;'>{safe_sub}</div>"
        f"<div style='font-size:9.5pt;color:{pal['text']};font-weight:700;'>{safe_title}</div>"
        f"</td>"
        f"<td align='right' valign='top'>"
        f"<span style='background-color:{pal['panel_bg']};color:{pal['muted']};font-size:6.5pt;"
        f"padding:2px 5px;border:1px solid {pal['border']};font-weight:700;'>"
        f"#[% @atlas_featurenumber %]/[% @atlas_totalfeatures %]</span>"
        f"</td>"
        f"</tr>"
        f"</table>"
        f"<table width='100%' cellspacing='0' cellpadding='0' style='border-top:1px solid {pal['border']};'>"
        f"{''.join(field_rows)}"
        f"</table>"
        f"</div>"
    )


def build_metadata_badge_html(
    title: str = "CARTOGRAPHIC METADATA",
    author: str = "Yusuf Eminoğlu",
    crs_authid: str = "EPSG:4326",
    scale_text: str = "Auto",
    source: str = "PlanX CartoLab",
    extra_rows: Sequence[Tuple[str, str]] = (),
    theme: str = "swiss_modern",
    accent_color: Optional[str] = None,
) -> str:
    """
    Build a structured publication metadata & citation HTML card.
    """
    pal = _resolve_card_theme(theme, accent_color)
    base_rows = [
        ("Author", author or "Yusuf Eminoğlu"),
        ("CRS", crs_authid or "EPSG:4326"),
        ("Scale", scale_text or "Auto"),
        ("Date", "[% format_date(now(), 'yyyy-MM-dd') %]"),
        ("Source", source or "PlanX CartoLab"),
    ]
    for k, v in (extra_rows or ()):
        base_rows.append((k, v))

    tr_list = []
    for idx, (k, v) in enumerate(base_rows):
        bg = pal["row_alt"] if idx % 2 == 1 else pal["bg"]
        tr_list.append(
            f"<tr>"
            f"<td width='36%' bgcolor='{bg}' style='padding:2.5px 5px;font-size:6.6pt;color:{pal['muted']};font-weight:600;'>"
            f"{_esc(k)}</td>"
            f"<td width='64%' bgcolor='{bg}' style='padding:2.5px 5px;font-size:6.8pt;color:{pal['text']};'>"
            f"{_esc(v)}</td>"
            f"</tr>"
        )

    return (
        f"<div style='font-family:{pal['font']};background-color:{pal['bg']};color:{pal['text']};"
        f"padding:5px;border:1px solid {pal['border']};'>"
        f"<div style='font-size:7.5pt;font-weight:700;color:{pal['accent']};margin-bottom:3px;"
        f"letter-spacing:0.5px;border-bottom:1px solid {pal['border']};padding-bottom:2px;'>"
        f"{_esc(title)}</div>"
        f"<table width='100%' cellspacing='0' cellpadding='0'>"
        f"{''.join(tr_list)}"
        f"</table>"
        f"</div>"
    )



# ---------------------------------------------------------------------------
# CSS (embedded, Tailwind-inspired)
# ---------------------------------------------------------------------------

_FLOATING_CARD_CSS = """
<style>
  .planx-card {
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,.12), 0 1px 4px rgba(0,0,0,.08);
    padding: 16px;
    min-width: 220px;
    max-width: 320px;
    color: #1a1a2e;
    font-size: 13px;
    line-height: 1.5;
  }
  .planx-card h3 {
    margin: 0 0 8px;
    font-size: 15px;
    font-weight: 600;
    color: #16213e;
    border-bottom: 2px solid #e94560;
    padding-bottom: 6px;
  }
  .planx-card .metric-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid #f0f0f0;
  }
  .planx-card .metric-label { color: #555; }
  .planx-card .metric-value { font-weight: 600; }
  .planx-card canvas { display: block; margin: 8px auto; }
</style>
"""


# ---------------------------------------------------------------------------
# Radar chart builder (pure JS/Canvas, no Plotly dependency)
# ---------------------------------------------------------------------------

def _radar_chart_js(variable_id: str, labels: List[str], values: List[float]) -> str:
    """Generate inline JS that draws a radar/spider chart on a <canvas>."""
    labels_js = json.dumps(labels)
    values_js = json.dumps(values)
    return f"""
<script>
(function() {{
  var canvas = document.getElementById('{variable_id}');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var labels = {labels_js};
  var values = {values_js};
  var n = labels.length;
  var cx = canvas.width / 2, cy = canvas.height / 2;
  var maxR = Math.min(cx, cy) - 20;
  var maxVal = Math.max.apply(null, values.concat([1]));

  // background grid
  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 0.5;
  for (var l = 0; l < 4; l++) {{
    var r = maxR * (l + 1) / 4;
    ctx.beginPath();
    for (var i = 0; i <= n; i++) {{
      var angle = Math.PI * 2 * i / n - Math.PI / 2;
      var x = cx + r * Math.cos(angle), y = cy + r * Math.sin(angle);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }}
    ctx.closePath();
    ctx.stroke();
  }}

  // axes
  ctx.strokeStyle = '#ccc';
  ctx.lineWidth = 1;
  for (var i = 0; i < n; i++) {{
    var angle = Math.PI * 2 * i / n - Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + maxR * Math.cos(angle), cy + maxR * Math.sin(angle));
    ctx.stroke();
  }}

  // data polygon
  ctx.fillStyle = 'rgba(233, 69, 96, 0.25)';
  ctx.strokeStyle = '#e94560';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (var i = 0; i < n; i++) {{
    var angle = Math.PI * 2 * i / n - Math.PI / 2;
    var r = maxR * values[i] / maxVal;
    var x = cx + r * Math.cos(angle), y = cy + r * Math.sin(angle);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }}
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  // labels
  ctx.fillStyle = '#333';
  ctx.font = '10px Inter, sans-serif';
  ctx.textAlign = 'center';
  for (var i = 0; i < n; i++) {{
    var angle = Math.PI * 2 * i / n - Math.PI / 2;
    var x = cx + (maxR + 16) * Math.cos(angle);
    var y = cy + (maxR + 16) * Math.sin(angle) + 4;
    ctx.fillText(labels[i], x, y);
  }}
}})();
</script>
"""


# ---------------------------------------------------------------------------
# Floating card factory
# ---------------------------------------------------------------------------

def build_floating_card(
    title: str,
    metrics: Dict[str, float],
    indicator_labels: Optional[List[str]] = None,
    indicator_values: Optional[List[float]] = None,
    width: int = 260,
    height: int = 220,
) -> str:
    """
    Build a self-contained HTML floating card with optional radar chart.

    Parameters
    ----------
    title : str
        Card header (e.g. feature name).
    metrics : dict
        Key/value pairs shown as rows in the card.
    indicator_labels : list[str] | None
        If given together with indicator_values, a radar chart is drawn.
    indicator_values : list[float] | None
        Corresponding values 0..1.
    width, height : int
        Canvas dimensions for the chart.

    Returns
    -------
    str — complete HTML fragment ready for QWebEngineView or QWebView.
    """
    def _fmt_val(v):
        try:
            return f"{float(v):.2f}"
        except (ValueError, TypeError):
            return str(v)

    rows_html = "\n".join(
        f'<div class="metric-row"><span class="metric-label">{k}</span>'
        f'<span class="metric-value">{_fmt_val(v)}</span></div>'
        for k, v in metrics.items()
    )

    chart_html = ""
    if indicator_labels and indicator_values and len(indicator_labels) > 2:
        chart_id = f"radar_{abs(hash(title))}"
        chart_html = (
            f'<canvas id="{chart_id}" width="{width}" height="{height}"></canvas>\n'
            + _radar_chart_js(chart_id, indicator_labels, indicator_values)
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
{_FLOATING_CARD_CSS}
</head><body style="margin:0;background:transparent;">
<div class="planx-card">
  <h3>{title}</h3>
  {rows_html}
  {chart_html}
</div>
</body></html>"""
