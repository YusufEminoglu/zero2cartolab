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

import json
from typing import Dict, List, Optional


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
