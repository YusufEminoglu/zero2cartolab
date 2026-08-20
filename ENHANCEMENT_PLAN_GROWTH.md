# CartoLab Growth Roadmap — 732 → 25,000+ downloads by 1 Jan 2027

> Internal planning doc. Named `ENHANCEMENT_PLAN_*` so `packaging/zip_hub.py`
> auto-excludes it from the Hub zip. Not committed by default — it is strategy,
> not shipped code. Horizon: **~6 months (Jul 2026 → Jan 2027).**

---

## 1. The honest growth model

`plugins.qgis.org` shows one number: **cumulative downloads across all versions.**
It goes up from two independent engines:

1. **New installs** — someone finds CartoLab and installs it. Driven by
   discoverability + reputation + (later) your PR.
2. **Update re-downloads** — when you publish a new version, every user whose
   QGIS auto-updates **re-downloads it, and that counts.** So a base of *N*
   active users releasing twice a month generates ≈ *2N* downloads/month for
   free, and each release re-surfaces you on the Hub's "Recently updated" feed.

So the whole strategy reduces to one sentence:

> **Grow the active base × ship often × make every visitor convert and stay.**

### What 25k in 6 months actually requires

34× in ~24 weeks from a 732 base is a **stretch goal**. Being candid: product
quality alone rarely 34×'s downloads in six months — it usually needs a
distribution spike too (your videos/tutorials/PR). But the product is what
decides whether that spike **sticks or leaks away**. This plan does two things:

- Maximises the **organic** engine that works even with zero PR (Hub SEO,
  release cadence, votes, localization, shareable output).
- Makes CartoLab so broadly useful and frictionless that **every** click your
  PR sends converts to an install, a vote, and a word-of-mouth recommendation.

Product-led + cadence alone, executed hard, realistically lands **8–15k**.
The **25k** ceiling is reachable when your PR multiplier lands on top of a
product that's ready to catch it. This plan gets the product ready.

### Trajectory to steer by (cumulative, not a promise)

| Month | Target cumulative | What's driving it |
|------:|------------------:|-------------------|
| Jul (now) | ~0.8k | baseline |
| Aug | ~2.5k | SEO + onboarding + Sprint 1 release, cadence starts |
| Sep | ~5k | template gallery, palettes searchable, first word-of-mouth |
| Oct | ~9k | Auto Atlas (signature), base compounding on updates |
| Nov | ~15k | localization opens non-English markets + your PR ramps |
| Dec | ~21k | stickiness + featured push + holiday project season |
| **Jan 1** | **25k+** | compounding base × cadence × PR |

The curve is **accelerating**, not linear — the first months build the base
that makes the later months compound. If a month underperforms, the lever to
pull is almost always *discoverability*, not more features.

---

## 2. The three levers (everything below maps to one of these)

**A — Discoverability (get found).** Hub search SEO, release cadence, votes,
localization, "featured" eligibility. *Cheapest, fastest, most neglected.*

**B — Breadth (be useful to more people).** Reposition from "advanced
publication cartography" (a niche) to **"the fastest way to make any good map in
QGIS"** (a universal need) — without dropping the advanced tools. Add the
broadly-searched essentials: quick styling, color palettes, templates, export
presets, atlas, legend/scale/north helpers.

**C — Delight & retention (they stay and tell others).** 5-second first-run
value, zero-config, zero-dependency, rock-solid stability, and **output so good
it markets itself** — every map a user posts in a report or on social is a free
ad with your name on it.

---

## 3. Six-sprint roadmap (each sprint = one Hub release; ship ~monthly)

| Sprint | Month | Theme | Headline deliverables | Lever |
|-------:|-------|-------|-----------------------|:-----:|
| **0** | Jul (now) | Foundation & SEO | Metadata SEO rewrite · in-app vote nudge · first-run onboarding + 5-sec sample map | A, C |
| **1** | Aug | "Any map, good, fast" | Palette Library (ColorBrewer + viridis + colorblind-safe) · Quick Style one-click · Export Presets | A, B |
| **2** | Sep | Template Gallery | Named layout templates (Report Figure, Poster, Social Card, Fact Sheet, Side-by-side) on the Auto Map Sheet engine | B, C |
| **3** | Oct | **Auto Atlas** (signature) | Map series — one page per feature/category → multi-page PDF / image set | B, C |
| **4** | Nov | Stickiness | Style & Template Library (save/load/share) · Map Snapshot (canvas→figure, no designer) · inline preview | C |
| **5** | Dec | Reach & polish | Localization (TR + ES + PT) · colorblind checker everywhere · stability/perf pass · apply for "featured" | A, C |

Guardrail: **cadence beats scope.** A smaller sprint shipped on time beats a big
one that slips — every release is a download event and a Hub resurfacing. Pick a
day (e.g. the 1st) and ship every month, even if a feature waits.

---

## 4. Detailed, functional implementation plan — Sprints 0 & 1

Specs are written to CartoLab's existing architecture: pure logic in `core/`
(qgis-free, unit-tested), algorithms in `processing/`, layout code in `layout/`,
UI in `ui/cartolab_dashboard.py`. Every item keeps the gates green
(209 unit / 33 e2e ×2 / flake8 / bandit 0 M-H) and adds no external dependency.

### SPRINT 0 — Foundation & SEO

#### 0.1 Metadata SEO rewrite (`metadata.txt`)  ← biggest ROI, lowest effort
The in-app Plugin Manager search matches `name`, `tags`, `description`, `about`.
Today's tags miss the terms people actually type. Proposed change (needs your
sign-off — this is user-facing copy):

- **tags** — add the high-search terms: `choropleth, map layout, print layout,
  atlas, map series, legend, north arrow, scale bar, color ramp, colorbrewer,
  colorblind, viridis, heatmap, thematic map, map design, symbology, export`.
- **description** — lead with the universal job-to-be-done, keep the advanced
  terms for the long tail:
  > "Design publication-quality thematic maps and print layouts in QGIS in
  > minutes — choropleths, bivariate maps, cartograms, dot-density, hexbins,
  > proportional symbols; one-click map layouts with legend, scale bar and north
  > arrow; atlas map series; and colorblind-safe color palettes."
- **about** — first sentence must contain "thematic maps", "print layout",
  "choropleth", "color palette" (the searched nouns).

Acceptance: `validate_plugin.py` VALID, no bare `%`, tags ≤ Hub limit, reads
naturally (no keyword stuffing — the Hub review team penalises that).

#### 0.2 First-run onboarding (`ui/onboarding.py` + hook in `main_plugin.py`)
- On first load after install (QSettings flag `planx_cartolab/seen_welcome`),
  show a small welcome dialog: three buttons — **"Create a sample map"**,
  **"Open Dashboard"**, **"Rate CartoLab ⭐"**.
- **"Create a sample map"** builds an in-memory demo polygon layer (a value
  grid — *no bundled data, zero zip weight*), applies Quick Style (0.1 Sprint 1)
  or a graduated renderer, then calls `create_map_sheet(iface, ...)`. User sees
  a finished, beautiful map **in ~5 seconds** — the single strongest retention
  moment.
- Never shows again after dismissal; reachable later from the dashboard header.

Acceptance: GUI smoke test constructs the dialog offscreen; "Create sample map"
produces a layout with a styled map + legend without touching disk.

#### 0.3 In-app vote / rate nudge (`ui/cartolab_dashboard.py` footer)
- A one-line, non-modal footer: "Enjoying CartoLab? ⭐ Rate it on the QGIS Hub"
  → opens `https://plugins.qgis.org/plugins/planx_cartolab/`.
- Votes raise Hub ranking **and** trust (social proof converts installs).
  Shown subtly, dismissible — nagging backfires.

### SPRINT 1 — "Any map, good, fast" (the breadth engine)

#### 1.1 Palette Library (`core/palettes.py`, pure logic + unit tests)
- `PALETTES: dict[str, dict]` — each: `{"kind": "sequential|diverging|
  qualitative", "cb_safe": bool, "colors": [hex,...]}`. Include the
  universally-searched sets: ColorBrewer (YlOrRd, Blues, RdBu, Spectral, Set2…),
  scientific (viridis, magma, plasma, cividis — all colorblind-safe).
- API: `get_palette(name, n)` (sample/interpolate to *n* classes),
  `list_palettes(kind=None, cb_safe_only=False)`, `is_colorblind_safe(name)`.
- Interpolation is pure math (linear in RGB or Lab) — fully unit-testable
  headless. ~20 new unit checks.
- Why it sells: "colorbrewer qgis", "viridis qgis", "colorblind qgis" are
  frequent searches; palettes are needed by *every* thematic map.

#### 1.2 Quick Style algorithm (`processing/alg_quick_style.py` + dashboard button)
- Input: any vector layer + one field. If numeric → graduated renderer
  (quantile or the existing Geometric-Interval engine) with a chosen palette;
  if text → categorized renderer with a qualitative palette. Optional: turn on
  smart labels (reuse `label_points` logic) + a subtle outline.
- Dashboard: a prominent **"Style this layer"** button — pick layer, pick field,
  pick palette, done. Sane defaults so the *default* click already looks good.
- Why it sells: styling is the #1 thing new QGIS users struggle with; this is
  the broadest-appeal feature in the whole plan. Reuses palettes (1.1).

#### 1.3 Export Presets (`layout/export_presets.py` + dashboard section)
- One-click exports built on the existing `export_layout()`:
  "PNG · web (1200 px)", "PNG · print (300 dpi)", "PDF · vector",
  "SVG · editable", "Social card (1200×630)".
- Operates on the selected layout; for users without a layout, offer
  **Map Snapshot** (Sprint 4) later.
- Why it sells: "export map qgis high resolution" is a constant pain; presets
  remove all the dialog friction.

Acceptance for Sprint 1: new `core/palettes.py` unit-tested; Quick Style added
to the provider (algorithm count guard updated 12 → 13, e2e asserts it applies a
renderer); export presets covered by the layout e2e; flake8/bandit clean;
CHANGELOG + metadata bumped; zip validated.

---

## 5. Cadence & measurement discipline

- **Release day:** the 1st of each month. Even a small, polished release counts
  as a download event + Hub resurfacing. Never skip a month.
- **Version invariant:** never reuse a version number that may have been
  uploaded (burns the Hub slot). Bump semver: features → minor, fixes → patch.
- **Track weekly:** `plugins.qgis.org/plugins/planx_cartolab/` shows total
  downloads and votes. Log both every Friday in a simple table. If a month's
  slope flattens → the fix is discoverability (SEO/localization/votes), rarely
  more features.
- **Protect the moat:** zero external dependencies, offscreen-clean, gates green
  every release. One crash-y release costs more reputation than three great ones
  earn.

---

## 6. Risks & guardrails

- **"25k" depends on the base growing.** If PR slips, expect 8–15k and treat
  that as a strong result; keep compounding into 2027.
- **Don't keyword-stuff** metadata — the Hub review team can reject it, and it
  reads as spam to users.
- **Don't dilute quality for feature count.** Breadth yes, bloat no; every
  addition must have sane one-click defaults or it raises the skill floor
  instead of lowering it.
- **Localization is a real download lever**, not a nicety — Brazil, LATAM and
  Europe are QGIS's largest communities. TR/ES/PT first.

---

## 7. Progress log

- **✅ Sprint 0 — v1.5.1 (2026-07-13, pushed; uploaded to Hub):** metadata SEO,
  first-run welcome + 5-second sample map, Rate-on-Hub nudge.
- **✅ Sprint 1 — v1.6.0 (2026-07-13, pushed):** `core/palettes.py` (ColorBrewer
  + colour-blind-safe viridis family), Quick Style (algorithm + dashboard panel
  with live preview), export presets (PNG/PDF/SVG @ 96–600 dpi). 13 algorithms;
  gates green (239 unit, 37 e2e ×2 QGIS).

### Next: Sprint 2 — Layout Template Gallery
Named templates on the Auto Map Sheet engine (Report Figure, Poster A1/A2,
Social Card 1200×630, A4 Fact Sheet, side-by-side comparison) with a thumbnail
picker. Then Sprint 3 = **Auto Atlas** (the signature feature).

### Standing cadence reminder
Ship the 1st of each month. A release is a download event even without new
features; skipping a month is the one thing that breaks the compounding.
