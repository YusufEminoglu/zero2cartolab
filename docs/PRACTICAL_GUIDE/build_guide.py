#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the 02CartoLab Practical Guide (interactive + print-ready).

Inputs
------
manifest/guide_content.json   authored copy (EN + TR) for every module
manifest/algorithms.json      live Processing registry metadata
manifest/screenshots.json     what the runner captured, and with which parameters

Outputs
-------
practical_guide.html            interactive guide (English, browser)
practical_guide_static.html     print/PDF guide (Turkish)
practical_guide_static_en.html  print/PDF guide (English)

Usage:
    python build_guide.py
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The public manual lives in the portal repository (geophilo_project), not
# in this plugin repository or its Hub zip. GEOPHILO_MANUALS overrides it.
MANUALS = Path(os.environ.get("GEOPHILO_MANUALS") or HERE.parents[1].parents[1] / "geophilo_project" / "_manual_sources") / "zero2cartolab" / "PRACTICAL_GUIDE"
MANIFEST = HERE / "manifest"

GROUP_ORDER = [
    "Getting started",
    "Symbology Studio",
    "Data Preparation",
    "Classification Engine",
    "Thematic Mapping",
    "Cartogram Engine",
    "Aggregation",
    "Labeling",
    "Map Reference",
    "Layout Studio",
]

GROUP_LABEL = {
    "Getting started": ("Getting started", "Başlangıç"),
    "Symbology Studio": ("Symbology Studio", "Sembolji Stüdyosu"),
    "Data Preparation": ("Data Preparation", "Veri Hazırlığı"),
    "Classification Engine": ("Classification Engine", "Sınıflama Motoru"),
    "Thematic Mapping": ("Thematic Mapping", "Tematik Haritalama"),
    "Cartogram Engine": ("Cartogram Engine", "Kartogram Motoru"),
    "Aggregation": ("Aggregation", "Toplulaştırma"),
    "Labeling": ("Labeling", "Etiketleme"),
    "Map Reference": ("Map Reference", "Harita Referansı"),
    "Layout Studio": ("Layout Studio", "Düzen Stüdyosu"),
}

# Modules that are documented in the copy but are captured through another
# module's screenshot set.
SCREENSHOT_ALIAS = {
    "palette_accessibility": ("gui_dashboard", "dashboard_palette"),
}


def load(name):
    path = MANIFEST / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


WEB_ROOT = HERE / "screenshots" / "web"


def web_img(path: str) -> str:
    """Prefer the optimised JPEG copy when optimize_images.py has produced one."""
    rel = Path(path)
    try:
        rel = rel.relative_to("screenshots")
    except ValueError:
        pass
    candidate = WEB_ROOT / rel.with_suffix(".jpg")
    if candidate.exists():
        return candidate.relative_to(HERE).as_posix()
    return path


def esc(text):
    return html.escape(str(text or ""))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


# ══════════════════════════════════════════════════════════════════════════
#  DATA ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════
class Guide:
    def __init__(self):
        self.content = load("guide_content.json")
        self.algos = load("algorithms.json")
        self.shots = load("screenshots.json")
        self.algo_by_id = {a["id"]: a for a in self.algos.get("algorithms", [])}
        self.meta = self.content.get("_meta", {})

    # ── ordering ────────────────────────────────────────────────────
    def ordered_modules(self):
        out = []
        for group in GROUP_ORDER:
            for key, entry in self.content.items():
                if key.startswith("_"):
                    continue
                if entry.get("group") == group:
                    out.append((group, key, entry))
        # anything left over
        for key, entry in self.content.items():
            if key.startswith("_"):
                continue
            if not any(k == key for _, k, _ in out):
                out.append((entry.get("group", "Other"), key, entry))
        return out

    # ── screenshots for a module ────────────────────────────────────
    def module_figures(self, module_id):
        """Return [(path, caption)] for a documented module."""
        entry = self.shots.get("modules", {}).get(module_id, {})
        figures = []
        if entry.get("gui_pages"):
            for p in entry["gui_pages"]:
                figures.append((p["path"], p["title"]))
        elif entry.get("templates"):
            for p in entry["templates"]:
                figures.append((p["path"], p["title"]))
        elif entry.get("screenshot"):
            figures.append((entry["screenshot"], entry.get("display", module_id)))
        if module_id in SCREENSHOT_ALIAS:
            owner, page = SCREENSHOT_ALIAS[module_id]
            owner_entry = self.shots.get("modules", {}).get(owner, {})
            for p in owner_entry.get("gui_pages", []):
                if p["path"].endswith(page + ".png"):
                    figures.append((p["path"], p["title"]))
        return figures

    def module_params(self, module_id, entry):
        """Parameter table rows for a module, from the live registry."""
        algo_id = entry.get("algo")
        if not algo_id:
            return []
        algo = self.algo_by_id.get(algo_id)
        if not algo:
            return []
        rows = []
        for p in algo.get("params", []):
            default = p.get("default")
            if isinstance(default, str) and default.startswith("<QColor"):
                default = ""
            options = p.get("options") or []
            if options:
                default = str(default)
                try:
                    default = options[int(default)]
                except (ValueError, IndexError):
                    pass
            rows.append({
                "name": p["name"],
                "description": p.get("description", ""),
                "type": p.get("type", ""),
                "default": default,
                "options": options,
                "optional": p.get("optional"),
            })
        return rows

    def captured_params(self, module_id):
        entry = self.shots.get("modules", {}).get(module_id, {})
        return entry.get("params", "")

    def data_notes(self):
        return self.shots.get("data_notes", [])


# ══════════════════════════════════════════════════════════════════════════
#  SHARED FRAGMENTS
# ══════════════════════════════════════════════════════════════════════════
def render_param_table(rows, lang):
    if not rows:
        return ""
    head = (f'<tr><th>Parameter</th><th>{"Açıklama" if lang == "tr" else "Description"}</th>'
            f'<th>Type</th><th>Default</th></tr>')
    body = []
    for r in rows:
        options = ""
        if r["options"]:
            options = (f'<div class="opts">{" · ".join(esc(o) for o in r["options"][:14])}'
                       + (' · …' if len(r["options"]) > 14 else '') + '</div>')
        default = esc(r["default"]) if r["default"] not in (None, "") else "—"
        body.append(
            f'<tr><td class="mono">{esc(r["name"])}</td>'
            f'<td>{esc(r["description"])}{options}</td>'
            f'<td class="mono sm">{esc(r["type"])}</td>'
            f'<td class="mono sm">{default}</td></tr>')
    return (f'<table class="params"><thead>{head}</thead><tbody>'
            + "".join(body) + "</tbody></table>")


def render_figures(figures, lang, wide=False):
    if not figures:
        return ""
    out = []
    for path, caption in figures:
        out.append(
            f'<figure class="shot{" wide" if wide else ""}">'
            f'<a href="{esc(web_img(path))}" target="_blank" rel="noopener">'
            f'<img src="{esc(web_img(path))}" alt="{esc(caption)}" loading="lazy">'
            f'</a>'
            f'<figcaption>{esc(caption)}'
            f'<span class="fig-hint">{"büyütmek için tıklayın" if lang == "tr" else "click to enlarge"}</span>'
            f'</figcaption></figure>')
    return "".join(out)


def render_steps(steps, lang):
    items = "".join(f"<li>{esc(s)}</li>" for s in steps)
    return f'<ol class="steps">{items}</ol>'


def render_trouble(items, lang):
    if not items:
        return ""
    label = "Sorun giderme" if lang == "tr" else "When it goes wrong"
    li = "".join(f"<li>{esc(t)}</li>" for t in items)
    return (f'<div class="trouble"><h4>{label}</h4><ul>{li}</ul></div>')


def render_block(lang, keys, entry, block):
    """Render one localised block (what / question / interpret)."""
    if block not in entry:
        return ""
    text = entry[block]
    if not text:
        return ""
    return f'<p>{esc(text)}</p>'


# ══════════════════════════════════════════════════════════════════════════
#  INTERACTIVE GUIDE (EN)
# ══════════════════════════════════════════════════════════════════════════
INTERACTIVE_CSS = """
:root{
  --ink:#0f172a; --ink2:#334155; --muted:#64748b; --line:#e2e8f0;
  --accent:#7c3aed; --accent2:#a78bfa; --gold:#f59e0b; --paper:#ffffff;
  --bg:#f8fafc; --navy:#0d0f1e;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:80px}
body{margin:0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:var(--ink);
  background:var(--bg);line-height:1.65;font-size:16px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}

/* header */
header.top{background:linear-gradient(135deg,#0d0f1e 0%,#1c1040 60%,#2d1065 100%);
  color:#f1f5f9;padding:3.2rem 2rem 2.6rem;position:relative;overflow:hidden}
header.top::after{content:'';position:absolute;inset:0;
  background-image:linear-gradient(rgba(124,58,237,.07) 1px,transparent 1px),
    linear-gradient(90deg,rgba(124,58,237,.07) 1px,transparent 1px);
  background-size:52px 52px;pointer-events:none}
header.top .wrap{position:relative;z-index:1;max-width:1400px;margin:0 auto}
.eyebrow{display:inline-block;font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;
  font-weight:700;color:var(--accent2);border:1px solid rgba(167,139,250,.35);
  background:rgba(124,58,237,.12);padding:.3rem .8rem;border-radius:100px;margin-bottom:1.1rem}
h1{font-size:clamp(2rem,4.4vw,3.2rem);line-height:1.1;margin:0 0 .8rem;font-weight:800;letter-spacing:-.02em}
header.top p.lead{font-size:1.06rem;color:#cbd5e1;max-width:820px;margin:0 0 1.4rem}
.badges{display:flex;gap:.55rem;flex-wrap:wrap;margin-bottom:1.4rem}
.badge{font-size:.75rem;font-weight:600;padding:.28rem .75rem;border-radius:100px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#e2e8f0}
.badge.gold{background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.3);color:#fcd34d}
.cta{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:.4rem}
.btn{display:inline-flex;align-items:center;gap:.45rem;font-weight:700;font-size:.9rem;
  padding:.6rem 1.15rem;border-radius:8px;border:1px solid transparent}
.btn.p{background:linear-gradient(135deg,var(--accent),#4f46e5);color:#fff}
.btn.s{background:rgba(255,255,255,.08);color:#e2e8f0;border-color:rgba(255,255,255,.16)}
.btn:hover{text-decoration:none;transform:translateY(-1px)}

/* layout */
.wrap{max-width:1400px;margin:0 auto;padding:0 2rem}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr);gap:2.5rem;max-width:1400px;
  margin:0 auto;padding:2.5rem 2rem 4rem}
main{min-width:0;overflow-wrap:break-word}
nav.side{position:sticky;top:1.5rem;align-self:start;max-height:calc(100vh - 3rem);
  overflow-y:auto;padding-right:.4rem}
nav.side h5{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
  margin:1.3rem 0 .45rem;font-weight:700}
nav.side h5:first-child{margin-top:0}
nav.side a{display:block;padding:.32rem .6rem;border-radius:6px;color:var(--ink2);font-size:.86rem;
  border-left:2px solid transparent}
nav.side a:hover{background:#fff;color:var(--accent);text-decoration:none;border-left-color:var(--accent2)}
nav.side a.active{background:#fff;color:var(--accent);font-weight:600;border-left-color:var(--accent)}
nav.side a .tag{font-size:.68rem;color:var(--muted);font-weight:500}

/* sections */
section.mod{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.9rem 2rem;
  margin-bottom:1.6rem;box-shadow:0 1px 3px rgba(15,23,42,.04)}
section.mod h2{margin:.2rem 0 .9rem;font-size:1.5rem;letter-spacing:-.01em;line-height:1.25}
.grouplabel{display:inline-block;font-size:.68rem;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent);background:#f5f3ff;border:1px solid #ddd6fe;
  padding:.18rem .6rem;border-radius:100px}
.q{border-left:3px solid var(--gold);background:#fffbeb;padding:.75rem 1rem;border-radius:0 8px 8px 0;
  margin:0 0 1.1rem;font-style:italic;color:#78350f}
h3.sec{font-size:.78rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  margin:1.6rem 0 .6rem;font-weight:700;border-bottom:1px solid var(--line);padding-bottom:.35rem}
ol.steps{padding-left:1.3rem;margin:.4rem 0}
ol.steps li{margin:.42rem 0}
ol.steps li::marker{font-weight:700;color:var(--accent)}
.read{border-left:3px solid var(--accent);background:#f5f3ff;padding:.85rem 1.1rem;
  border-radius:0 8px 8px 0;margin:1rem 0}
.read strong{color:var(--accent)}
.trouble{border:1px dashed #fca5a5;background:#fef2f2;border-radius:8px;padding:.8rem 1rem;margin:1rem 0}
.trouble h4{margin:0 0 .4rem;font-size:.85rem;color:#b91c1c;letter-spacing:.03em}
.trouble ul{margin:0;padding-left:1.2rem}
.trouble li{margin:.28rem 0;font-size:.93rem}

/* figures */
figure.shot{margin:1.2rem 0}
figure.shot img{width:100%;border:1px solid var(--line);border-radius:10px;background:#fff;
  box-shadow:0 4px 20px rgba(15,23,42,.07);display:block}
figure.shot.wide img{object-fit:contain}
figcaption{font-size:.82rem;color:var(--muted);margin-top:.45rem;display:flex;
  justify-content:space-between;gap:1rem}
.fig-hint{color:var(--accent);white-space:nowrap}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:1rem;margin:1.2rem 0}
.gallery figure.shot{margin:0}
.gallery img{max-height:300px;object-fit:contain;object-position:center top;background:#fff;
  border:1px solid var(--line);border-radius:10px;padding:2px}

/* tables */
table.params{width:100%;border-collapse:collapse;font-size:.85rem;margin:.6rem 0}
table.params th{text-align:left;font-size:.68rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--line);padding:.5rem .6rem}
table.params td{border-bottom:1px solid #f1f5f9;padding:.5rem .6rem;vertical-align:top}
table.params tr:hover td{background:#fafafa}
.mono{font-family:'Cascadia Code','Consolas',monospace}
.sm{font-size:.8rem;color:var(--ink2)}
.opts{font-size:.74rem;color:var(--muted);margin-top:.2rem}
pre.run{background:#0f172a;color:#e2e8f0;padding:.85rem 1rem;border-radius:8px;overflow-x:auto;
  font-size:.78rem;line-height:1.55;margin:.6rem 0}

/* data provenance */
.data-card{background:#0f172a;color:#e2e8f0;border-radius:14px;padding:1.6rem 1.8rem;margin:1.2rem 0}
.data-card h3{color:#fff;margin:.2rem 0 .8rem}
.data-card li{margin:.35rem 0;font-size:.9rem}
.data-card code{background:rgba(255,255,255,.08);padding:.1rem .35rem;border-radius:4px;font-size:.82rem}

/* cheat sheet */
.cheat{width:100%;border-collapse:collapse;font-size:.87rem}
.cheat th{text-align:left;background:#0f172a;color:#fff;padding:.6rem .8rem;font-size:.72rem;
  letter-spacing:.08em;text-transform:uppercase}
.cheat td{padding:.55rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}
.cheat tr:nth-child(even) td{background:#fafafa}

footer{background:#0d0f1e;color:#94a3b8;padding:2.5rem 2rem;text-align:center;font-size:.85rem}
footer a{color:var(--accent2)}
@media(max-width:960px){.layout{grid-template-columns:minmax(0,1fr);padding:1.5rem 1rem}nav.side{position:static;max-height:none}
  header.top{padding:2.2rem 1.2rem}.wrap{padding:0 1.2rem}section.mod{padding:1.3rem 1.1rem}}
@media print{nav.side,.cta{display:none}.layout{grid-template-columns:minmax(0,1fr);padding:0}
  section.mod{break-inside:avoid;border:1px solid #ccc;box-shadow:none}}
"""

INTERACTIVE_JS = """
const links=[...document.querySelectorAll('nav.side a')];
const secs=[...document.querySelectorAll('section.mod')];
const obs=new IntersectionObserver(es=>{
  es.forEach(e=>{if(e.isIntersecting){
    const id=e.target.id;
    links.forEach(l=>l.classList.toggle('active',l.getAttribute('href')==='#'+id));
  }});
},{rootMargin:'-15% 0px -70% 0px',threshold:0});
secs.forEach(s=>obs.observe(s));

const search=document.getElementById('q');
if(search){
  search.addEventListener('input',()=>{
    const q=search.value.toLowerCase().trim();
    document.querySelectorAll('section.mod').forEach(s=>{
      s.style.display=(!q||s.textContent.toLowerCase().includes(q))?'':'none';
    });
    document.querySelectorAll('nav.side h5').forEach(h=>{
      let n=h.nextElementSibling, any=false;
      while(n&&n.tagName!=='H5'){if(n.style.display!=='none')any=true;n=n.nextElementSibling;}
      h.style.display=any?'':'none';
    });
  });
}
"""


def build_interactive(g: Guide) -> str:
    meta = g.meta
    parts = []
    parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>02CartoLab Practical Guide — Step-by-Step Cartography in QGIS</title>
<meta name="description" content="A screenshot-driven practical guide to every 02CartoLab capability, built on real İzmir urban data and rendered by the plugin itself.">
<style>{INTERACTIVE_CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="eyebrow">02CartoLab · Practical Guide</div>
  <h1>Publication cartography, step by step</h1>
  <p class="lead">{esc(meta.get('subtitle_en',''))}</p>
  <div class="badges">
    <span class="badge">QGIS 3.28 → 4.99</span>
    <span class="badge gold">Real data · real renders</span>
    <span class="badge">16 Processing algorithms</span>
    <span class="badge">10 layout archetypes</span>
    <span class="badge">Zero pip dependencies</span>
    <span class="badge">GPL-3.0</span>
  </div>
  <div class="cta">
    <a class="btn p" href="#how-to-read">How to read this guide</a>
    <a class="btn s" href="https://plugins.qgis.org/plugins/zero2cartolab/" target="_blank" rel="noopener">Install from the Hub</a>
    <a class="btn s" href="../CARTOLAB_REFERENCE_MANUAL.html">Reference Manual (theory)</a>
    <a class="btn s" href="https://github.com/YusufEminoglu/zero2cartolab" target="_blank" rel="noopener">Source code</a>
  </div>
</div></header>

<div class="layout">
<nav class="side">
  <input id="q" type="search" placeholder="Filter modules…"
    style="width:100%;padding:.5rem .65rem;border:1px solid var(--line);border-radius:8px;
           font-family:inherit;font-size:.86rem;margin-bottom:.6rem">
""")

    # sidebar navigation
    by_group = {}
    for group, key, entry in g.ordered_modules():
        by_group.setdefault(group, []).append((key, entry))
    for group in GROUP_ORDER:
        if group not in by_group:
            continue
        en_label, _ = GROUP_LABEL.get(group, (group, group))
        parts.append(f"  <h5>{esc(en_label)}</h5>\n")
        for key, entry in by_group[group]:
            en = entry.get("en", {})
            title = en.get("title", key)
            parts.append(f'  <a href="#{slug(key)}">{esc(title)}</a>\n')

    parts.append("""</nav>
<main>
""")

    # how-to-read
    notes = g.data_notes()
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)
    parts.append(f"""
<section class="mod" id="how-to-read">
  <div class="grouplabel">Read this first</div>
  <h2>How to read this guide</h2>
  <p>Every module follows the same shape: the <strong>planning question</strong> the tool answers, what it does,
  the exact clicks or Processing parameters, the real output, how to interpret it, and what breaks.</p>
  <h3 class="sec">Where the screenshots come from</h3>
  <div class="data-card">
    <h3>Nothing here is a mock-up</h3>
    <ul>
      <li>Every map panel is a <strong>QGIS render of a layer the plugin actually produced</strong> during a
      headless run of the real algorithm.</li>
      <li>Every parameter panel is the <strong>literal parameter dictionary</strong> handed to the algorithm.</li>
      <li>Every interface panel is a <strong>screenshot of the real dashboard widget tree</strong>, running
      against the real data.</li>
      <li>Every layout is an <strong>exported print layout</strong>, not a picture of one.</li>
    </ul>
    <h3 style="margin-top:1.1rem">The data behind this guide</h3>
    <ul>{notes_html}</ul>
  </div>
  <h3 class="sec">Reproduce it yourself</h3>
  <p>The capture harness ships with the plugin source. From a QGIS-enabled Python prompt:</p>
  <pre class="run">C:\\OSGeo4W\\bin\\python-qgis-ltr.bat docs\\PRACTICAL_GUIDE\\practical_guide_runner.py --all</pre>
  <p>It resolves the datasets, runs every algorithm, and rewrites <code>manifest/screenshots.json</code> and the
  images under <code>screenshots/</code>. Point it at a different folder with
  <code>--data</code> and the whole guide regenerates against your own city.</p>
</section>
""")

    for group, key, entry in g.ordered_modules():
        en = entry.get("en", {})
        figures = g.module_figures(key)
        rows = g.module_params(key, entry)
        captured = g.captured_params(key)
        algo_id = entry.get("algo")

        parts.append(f'<section class="mod" id="{slug(key)}">\n')
        parts.append(f'  <div class="grouplabel">{esc(group)}</div>\n')
        parts.append(f"  <h2>{esc(en.get('title', key))}</h2>\n")
        if en.get("question"):
            parts.append(f'  <div class="q">{esc(en["question"])}</div>\n')
        if en.get("what"):
            parts.append(f'  <p>{esc(en["what"])}</p>\n')

        if en.get("steps"):
            parts.append('  <h3 class="sec">Step by step</h3>\n')
            parts.append("  " + render_steps(en["steps"], "en") + "\n")

        if figures:
            parts.append('  <h3 class="sec">The result</h3>\n')
            many = len(figures) > 2
            if many:
                parts.append('  <div class="gallery">\n')
                for path, caption in figures:
                    parts.append(
                        f'  <figure class="shot"><a href="{esc(web_img(path))}" target="_blank" rel="noopener">'
                        f'<img src="{esc(web_img(path))}" alt="{esc(caption)}" loading="lazy"></a>'
                        f'<figcaption>{esc(caption)}</figcaption></figure>\n')
                parts.append("  </div>\n")
            else:
                parts.append("  " + render_figures(figures, "en", wide=True) + "\n")

        if en.get("interpret"):
            parts.append('  <div class="read"><strong>Read the output.</strong> '
                         + esc(en["interpret"]) + "</div>\n")

        if rows:
            parts.append('  <h3 class="sec">Parameters</h3>\n')
            parts.append("  " + render_param_table(rows, "en") + "\n")

        if captured:
            parts.append('  <h3 class="sec">Exact run used for the screenshots</h3>\n')
            parts.append(f'  <pre class="run">{esc(captured)}</pre>\n')

        if en.get("trouble"):
            parts.append("  " + render_trouble(en["trouble"], "en") + "\n")

        if algo_id:
            parts.append(f'  <p style="font-size:.82rem;color:var(--muted);margin-top:1.2rem">'
                         f'Processing ID: <code class="mono">{esc(algo_id)}</code></p>\n')
        parts.append("</section>\n")

    # cheat sheet
    rows = []
    for group, key, entry in g.ordered_modules():
        en = entry.get("en", {})
        algo = entry.get("algo")
        rows.append(f'<tr><td><a href="#{slug(key)}">{esc(en.get("title", key))}</a></td>'
                    f'<td>{esc(group)}</td>'
                    f'<td class="mono sm">{esc(algo) if algo else "—"}</td></tr>')
    parts.append(f"""
<section class="mod" id="cheat-sheet">
  <div class="grouplabel">Cheat sheet</div>
  <h2>Every module, one line</h2>
  <table class="cheat">
    <thead><tr><th>Module</th><th>Workspace</th><th>Processing ID</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
</main>
</div>

<footer>
  <p><strong>02CartoLab Practical Guide</strong> · version {esc(meta.get('version',''))} ·
  every screenshot produced by the plugin in a real QGIS runtime on real urban data.</p>
  <p><a href="https://plugins.qgis.org/plugins/zero2cartolab/">QGIS Plugin Hub</a> ·
  <a href="../CARTOLAB_REFERENCE_MANUAL.html">Reference Manual</a> ·
  <a href="https://github.com/YusufEminoglu/zero2cartolab">GitHub</a> ·
  <a href="https://gitlab.com/geophilo1/zero2cartolab">GitLab</a></p>
  <p style="opacity:.65">© 2026 Yusuf Eminoğlu · GEOPHILO · GPL-3.0</p>
</footer>
<script>{INTERACTIVE_JS}</script>
</body></html>""")
    return "".join(parts)


# ══════════════════════════════════════════════════════════════════════════
#  PRINT-READY STATIC GUIDES (TR + EN)
# ══════════════════════════════════════════════════════════════════════════
STATIC_CSS = """
@page{margin:2cm;size:A4}
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;font-size:10pt;line-height:1.55;color:#1a1a1a;
  max-width:100%;margin:0;padding:0}
h1{font-size:21pt;color:#4c1d95;border-bottom:3px solid #7c3aed;padding-bottom:.3em;margin:0 0 .5em;
  page-break-after:avoid}
h2{font-size:15pt;color:#5b21b6;border-bottom:2px solid #ddd6fe;padding-bottom:.2em;margin:1.6em 0 .7em;
  page-break-after:avoid}
h3{font-size:11.5pt;color:#6d28d9;margin:1.3em 0 .5em;page-break-after:avoid}
p{margin:.45em 0}
table{width:100%;border-collapse:collapse;margin:.7em 0;font-size:8.5pt}
th,td{border:1px solid #ddd;padding:3px 5px;text-align:left;vertical-align:top}
th{background:#f5f3ff;font-weight:600}
tr:nth-child(even) td{background:#fafafa}
.mono{font-family:Consolas,monospace;font-size:8pt}
.sm{font-size:8pt;color:#555}
code{font-family:Consolas,monospace;font-size:8.5pt;background:#f5f3ff;padding:.08em .3em;border-radius:3px}
pre{background:#f8fafc;border:1px solid #e2e8f0;padding:.55em;border-radius:4px;overflow-x:auto;
  font-size:8pt;line-height:1.45;margin:.5em 0}
.note{background:#f5f3ff;border-left:4px solid #7c3aed;padding:.55em .9em;margin:.7em 0;
  border-radius:0 4px 4px 0;font-size:9pt}
.warn{background:#fffbeb;border-left:4px solid #f59e0b;padding:.55em .9em;margin:.7em 0;
  border-radius:0 4px 4px 0;font-size:9pt}
.question{background:#fffbeb;border-left:4px solid #f59e0b;padding:.5em .9em;margin:.6em 0;
  font-style:italic;font-size:9pt;color:#78350f}
.grouplabel{display:inline-block;font-size:7.5pt;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#5b21b6;background:#f5f3ff;border:1px solid #ddd6fe;
  padding:.12em .5em;border-radius:99px}
.mod{border:1px solid #e2e8f0;border-radius:6px;padding:.9em 1em;margin:.9em 0;background:#fff;
  page-break-inside:avoid}
.mod h2{border:0;margin:.25em 0 .5em;padding:0;font-size:13pt}
.steps{padding-left:1.3em;margin:.4em 0}
.steps li{margin:.2em 0}
.trouble{border:1px dashed #fca5a5;background:#fef2f2;border-radius:5px;padding:.5em .8em;margin:.6em 0}
.trouble h4{margin:0 0 .25em;font-size:9pt;color:#b91c1c}
.trouble ul{margin:0;padding-left:1.1em;font-size:9pt}
figure{margin:.7em 0;page-break-inside:avoid}
figure img{width:100%;border:1px solid #e2e8f0;border-radius:4px;display:block}
figcaption{font-size:8pt;color:#666;margin-top:.25em}
.gallery{display:grid;grid-template-columns:1fr 1fr;gap:.6em}
.gallery figure img{height:170px;object-fit:contain;object-position:center top;background:#fff}
.toc{columns:2;column-gap:2em;font-size:9pt}
.toc a{text-decoration:none;color:#5b21b6}
.footer{margin-top:2.5em;padding-top:.8em;border-top:1px solid #ddd;font-size:8pt;color:#777;
  text-align:center}
.data{background:#0f172a;color:#e2e8f0;border-radius:6px;padding:.8em 1em;font-size:8.5pt;
  margin:.7em 0}
.data li{margin:.2em 0}
.data code{background:rgba(255,255,255,.12);color:#fff}
"""


def build_static(g: Guide, lang: str) -> str:
    meta = g.meta
    title = meta.get(f"title_{lang}", meta.get("title_en", ""))
    subtitle = meta.get(f"subtitle_{lang}", meta.get("subtitle_en", ""))
    is_tr = lang == "tr"

    labels = {
        "toc": "İçindekiler" if is_tr else "Table of contents",
        "read": "Nasıl okunur" if is_tr else "How to read this guide",
        "steps": "Adım adım" if is_tr else "Step by step",
        "result": "Sonuç" if is_tr else "The result",
        "interpret": "Çıktıyı nasıl okuyun" if is_tr else "Read the output",
        "params": "Parametreler" if is_tr else "Parameters",
        "exact": "Ekran görüntüleri için kullanılan tam çalıştırma" if is_tr else "Exact run used for the screenshots",
        "trouble": "Sorun giderme" if is_tr else "When it goes wrong",
        "cheat": "Özet tablo" if is_tr else "Cheat sheet",
        "module": "Modül" if is_tr else "Module",
        "workspace": "Çalışma alanı" if is_tr else "Workspace",
        "algo": "Processing ID",
        "print": "PDF yapmak için: Tarayıcıda Ctrl+P → “PDF olarak kaydet” → A4, kenar boşlukları: Varsayılan.",
        "data": "Veri kaynağı" if is_tr else "Data provenance",
    }

    out = [f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>02CartoLab — {esc(title)}</title>
<style>{STATIC_CSS}</style>
</head>
<body>
<h1>{esc(title)}</h1>
<p><strong>Version:</strong> {esc(meta.get('version',''))} |
<strong>Companion:</strong> <a href="../CARTOLAB_REFERENCE_MANUAL.html">
{"Referans Kılavuzu" if is_tr else "Reference Manual"}</a> |
<strong>Author:</strong> Geophilo</p>
<div class="note">{esc(subtitle)}</div>
<div class="warn">{esc(labels['print'])}</div>
"""]

    # TOC
    out.append(f'<h2>{esc(labels["toc"])}</h2>\n<div class="toc">')
    for group, key, entry in g.ordered_modules():
        loc = entry.get(lang, entry.get("en", {}))
        out.append(f'<div><a href="#{slug(key)}">{esc(loc.get("title", key))}</a></div>')
    out.append("</div>\n")

    # How to read + data provenance
    notes = g.data_notes()
    if is_tr:
        notes = [
            "Tematik kaynak: mahalle_population_2024.geojson (İzmir mahalle poligonları, 2024 nüfus verisi)",
            "2.5D kaynak: kadifekale_osm_binalar.gpkg (OSM binaları)",
            "Raster kaynak: kadifekale_dem_copernicus30m.tif (Copernicus DEM 30 m)",
            "Akış kaynağı: tire_mahalle_upi_sosyoekonomik.gpkg (toplanma alanları + kritik altyapı)",
            "OD tablosu: 900 gerçek kalkış→kritik varlık çifti (gerçek kapasiteler üzerinde mesafe-azalan çekim modeli)",
            "DEM, ridge motorunun map units üzerinde çalışması için EPSG:4326'dan EPSG:32635'e reprojeksiyonlandı",
        ]
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)
    if is_tr:
        read_text = ("Her modül aynı biçimdedir: aracın yanıtladığı <strong>planlama sorusu</strong>, "
                     "ne yaptığı, tıklamalar ya da Processing parametreleri, gerçek çıktı, nasıl "
                     "yorumlanacağı ve ne zaman bozulur.")
        real_text = ("Ekran görüntülerinin hiçbiri sahte değildir. Her harita paneli, eklentinin gerçekten "
                     "ürettiği bir katmanın QGIS render'ıdır; her parametre paneli algoritmaya verilen "
                     "gerçek parametre sözlüğüdür; her arayüz paneli gerçek dashboard'un ekran görüntüsüdür; "
                     "her düzen dışa aktarılmış gerçek bir baskı düzenidir.")
    else:
        read_text = ("Every module follows the same shape: the <strong>planning question</strong> the tool "
                     "answers, what it does, the exact clicks or Processing parameters, the real output, how "
                     "to interpret it, and what breaks.")
        real_text = ("Nothing here is a mock-up. Every map panel is a QGIS render of a layer the plugin "
                     "actually produced; every parameter panel is the literal parameter dictionary handed to "
                     "the algorithm; every interface panel is a screenshot of the real dashboard widget tree; "
                     "every layout is an exported print layout.")
    out.append(f"""
<h2>{esc(labels['read'])}</h2>
<p>{read_text}</p>
<div class="data">
  <strong>{esc(labels['data'])}</strong>
  <ul>{notes_html}</ul>
</div>
""")

    # Modules
    for group, key, entry in g.ordered_modules():
        loc = entry.get(lang, entry.get("en", {}))
        figures = g.module_figures(key)
        rows = g.module_params(key, entry)
        captured = g.captured_params(key)
        algo_id = entry.get("algo")

        out.append(f'<div class="mod" id="{slug(key)}">\n')
        out.append(f'<span class="grouplabel">{esc(group)}</span>\n')
        out.append(f'<h2>{esc(loc.get("title", key))}</h2>\n')
        if loc.get("question"):
            out.append(f'<div class="question">{esc(loc["question"])}</div>\n')
        if loc.get("what"):
            out.append(f'<p>{esc(loc["what"])}</p>\n')
        if loc.get("steps"):
            out.append(f'<h3>{esc(labels["steps"])}</h3>\n')
            out.append(render_steps(loc["steps"], lang) + "\n")
        if figures:
            out.append(f'<h3>{esc(labels["result"])}</h3>\n')
            if len(figures) > 2:
                out.append('<div class="gallery">')
                for path, caption in figures:
                    out.append(f'<figure><img src="{esc(web_img(path))}" alt="{esc(caption)}">'
                               f'<figcaption>{esc(caption)}</figcaption></figure>')
                out.append("</div>\n")
            else:
                for path, caption in figures:
                    out.append(f'<figure><img src="{esc(web_img(path))}" alt="{esc(caption)}">'
                               f'<figcaption>{esc(caption)}</figcaption></figure>\n')
        if loc.get("interpret"):
            out.append(f'<div class="note"><strong>{esc(labels["interpret"])}.</strong> '
                       f'{esc(loc["interpret"])}</div>\n')
        if rows:
            out.append(f'<h3>{esc(labels["params"])}</h3>\n')
            out.append(render_param_table(rows, lang) + "\n")
        if captured:
            out.append(f'<h3>{esc(labels["exact"])}</h3>\n')
            out.append(f'<pre>{esc(captured)}</pre>\n')
        if loc.get("trouble"):
            out.append(render_trouble(loc["trouble"], lang) + "\n")
        if algo_id:
            out.append(f'<p class="sm">{esc(labels["algo"])}: <code>{esc(algo_id)}</code></p>\n')
        out.append("</div>\n")

    # cheat sheet
    out.append(f'<h2>{esc(labels["cheat"])}</h2>\n<table>\n<thead><tr><th>{esc(labels["module"])}</th>'
               f'<th>{esc(labels["workspace"])}</th><th>{esc(labels["algo"])}</th></tr></thead>\n<tbody>')
    for group, key, entry in g.ordered_modules():
        loc = entry.get(lang, entry.get("en", {}))
        out.append(f'<tr><td><a href="#{slug(key)}">{esc(loc.get("title", key))}</a></td>'
                   f'<td>{esc(group)}</td><td class="mono">{esc(entry.get("algo") or "—")}</td></tr>')
    out.append("</tbody></table>\n")

    out.append(f"""<div class="footer">
02CartoLab Practical Guide · {esc(title)} · version {esc(meta.get('version',''))}<br>
Every screenshot produced by the plugin in a real QGIS runtime on real urban data.<br>
© 2026 Yusuf Eminoğlu · GEOPHILO · GPL-3.0 ·
<a href="https://plugins.qgis.org/plugins/zero2cartolab/">Plugin Hub</a> ·
<a href="https://github.com/YusufEminoglu/zero2cartolab">GitHub</a>
</div>
</body></html>""")
    return "".join(out)


# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    g = Guide()
    if not g.content:
        print("guide_content.json missing or empty", flush=True)
        return 2

    MANUALS.mkdir(parents=True, exist_ok=True)
    inter = MANUALS / "practical_guide.html"
    html = build_interactive(g)
    inter.write_text(html, encoding="utf-8")
    print(f"wrote {inter.name} ({inter.stat().st_size // 1024} KB)", flush=True)

    # The directory URL (/<plugin>/PRACTICAL_GUIDE/) must open the guide
    # instead of a 404, so the folder carries the guide as its index.
    index = MANUALS / "index.html"
    index.write_text(html, encoding="utf-8")
    print(f"wrote {index.name} ({index.stat().st_size // 1024} KB)", flush=True)

    tr = MANUALS / "practical_guide_static.html"
    tr.write_text(build_static(g, "tr"), encoding="utf-8")
    print(f"wrote {tr.name} ({tr.stat().st_size // 1024} KB)", flush=True)

    en = MANUALS / "practical_guide_static_en.html"
    en.write_text(build_static(g, "en"), encoding="utf-8")
    print(f"wrote {en.name} ({en.stat().st_size // 1024} KB)", flush=True)

    print(f"modules: {len(g.ordered_modules())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
