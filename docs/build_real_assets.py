#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the landing-page showcase images from *real* 02CartoLab output.

docs/assets/{hero,bivariate,layout,modules}.jpg used to be AI-generated
concept graphics — invented neighbourhood labels, a fabricated attribution and
a gallery frame around the whole thing. They are replaced here with images
that the plugin itself produced on real İzmir data:

    hero.jpg      the Report Figure publication layout (real exported layout)
    bivariate.jpg the bivariate choropleth result panel
    layout.jpg    the Auto Map Sheet output
    modules.jpg   a montage of eight real module results

Run after the capture harness:
    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat practical_guide_runner.py --all
    python docs/build_real_assets.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "PRACTICAL_GUIDE" / "screenshots"
ASSETS = HERE / "assets"

HEADER_H, PANEL_H, PANEL_W = 58, 620, 900
RESULT_BOX = (0, HEADER_H + PANEL_H, PANEL_W, HEADER_H + PANEL_H * 2)
CONTEXT_BOX = (PANEL_W, HEADER_H + PANEL_H, PANEL_W * 2, HEADER_H + PANEL_H * 2)

INK = (15, 23, 42)
MUTED = (100, 116, 139)
PAPER = (255, 255, 255)


def _font(size: int, bold: bool = False):
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf",
                 "arialbd.ttf" if bold else "arial.ttf",
                 "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        for root in (Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")):
            candidate = root / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _crop_result(name: str) -> Image.Image:
    """Crop the RESULT panel out of a 4-panel composite."""
    src = SHOTS / name
    with Image.open(src) as im:
        return im.convert("RGB").crop(RESULT_BOX)


def _fit(im: Image.Image, size, cover=True):
    """Resize to fill `size`, centred (cover) or fitted (contain)."""
    target_w, target_h = size
    if cover:
        ratio = max(target_w / im.width, target_h / im.height)
        new = (max(1, int(im.width * ratio)), max(1, int(im.height * ratio)))
        im = im.resize(new, Image.LANCZOS)
        left = (im.width - target_w) // 2
        top = (im.height - target_h) // 2
        return im.crop((left, top, left + target_w, top + target_h))
    ratio = min(target_w / im.width, target_h / im.height)
    new = (max(1, int(im.width * ratio)), max(1, int(im.height * ratio)))
    return im.resize(new, Image.LANCZOS)


def build_hero() -> None:
    src = SHOTS / "layout_templates" / "report_figure.png"
    if not src.exists():
        return
    with Image.open(src) as im:
        hero = _fit(im.convert("RGB"), (1600, 900))
    hero.save(ASSETS / "hero.jpg", "JPEG", quality=86, optimize=True, progressive=True)
    print("assets/hero.jpg  ← real Report Figure layout export")


def build_bivariate() -> None:
    result = _crop_result("bivariate/bivariate_4panel.png")
    out = _fit(result, (1400, 900))
    out.save(ASSETS / "bivariate.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("assets/bivariate.jpg  ← real bivariate choropleth output")


def build_layout() -> None:
    src = SHOTS / "map_sheet" / "map_sheet.png"
    if not src.exists():
        return
    with Image.open(src) as im:
        sheet = im.convert("RGB")
    canvas = Image.new("RGB", (1400, 1000), PAPER)
    fitted = _fit(sheet, (1340, 940), cover=False)
    canvas.paste(fitted, ((1400 - fitted.width) // 2, (1000 - fitted.height) // 2))
    canvas.save(ASSETS / "layout.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("assets/layout.jpg  ← real Auto Map Sheet export")


def build_modules() -> None:
    tiles = [
        ("quick_style/quick_style_4panel.png", "Quick Style"),
        ("cartogram/cartogram_4panel.png", "Cartogram"),
        ("dot_density/dot_density_4panel.png", "Dot density"),
        ("hexbin/hexbin_4panel.png", "Hexbin"),
        ("value_by_alpha/value_by_alpha_4panel.png", "Value-by-Alpha"),
        ("dorling/dorling_4panel.png", "Dorling cartogram"),
        ("ridge_map/ridge_map_4panel.png", "Ridge map"),
        ("building_25d/building_25d_4panel.png", "2.5D buildings"),
    ]
    cols, rows = 4, 2
    tile_w, tile_h = 420, 300
    pad, header = 14, 34
    canvas = Image.new("RGB", (cols * tile_w + (cols + 1) * pad,
                              rows * (tile_h + header) + (rows + 1) * pad), PAPER)
    draw = ImageDraw.Draw(canvas)
    font = _font(17, bold=True)

    for i, (rel, caption) in enumerate(tiles):
        src = SHOTS / rel
        if not src.exists():
            continue
        col, row = i % cols, i // cols
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + header + pad)
        with Image.open(src) as im:
            panel = _fit(im.convert("RGB").crop(RESULT_BOX), (tile_w, tile_h))
        canvas.paste(panel, (x, y))
        draw.text((x + 2, y + tile_h + 8), caption, fill=INK, font=font)

    canvas.save(ASSETS / "modules.jpg", "JPEG", quality=86, optimize=True, progressive=True)
    print("assets/modules.jpg  ← montage of eight real module outputs")


def refresh_showcase_images() -> None:
    """Replace the legacy docs/img/ renders with the real captures.

    The old files were produced by the e2e harness with synthetic data. The
    filenames are kept so nothing that links to them breaks — only the
    content changes, from mock-up to genuine plugin output.
    """
    img_dir = HERE / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        "real_dashboard.png": "gui_dashboard/dashboard_quick_style.png",
        "01_map_sheet_blueprint.png": "layout_templates/utm_field_sheet.png",
        "01_map_sheet_dark_matter.png": "layout_templates/emergency_brief.png",
        "01_map_sheet_japanese_washi.png": "layout_templates/academic_journal.png",
        "01_map_sheet_sepia_atlas.png": "layout_templates/fact_sheet.png",
        "01_map_sheet_swiss_modern.png": "layout_templates/report_figure.png",
        "01_map_sheet_warm_editorial.png": "layout_templates/planning_board.png",
        "02_template_report_figure_16x9.png": "layout_templates/report_figure.png",
        "03_template_academic_journal_a4.png": "layout_templates/academic_journal.png",
        "04_template_poster_exhibition_a2.png": "layout_templates/poster_exhibition.png",
        "05_template_fact_sheet_a4.png": "layout_templates/fact_sheet.png",
        "06_template_comparative_diptych.png": "layout_templates/side_by_side_diptych.png",
        "07_bivariate_choropleth_layout.png": "bivariate/bivariate_4panel.png",
        "08_value_by_alpha_layout.png": "value_by_alpha/value_by_alpha_4panel.png",
        "09_cartogram_layout.png": "cartogram/cartogram_4panel.png",
        "10_hexbin_layout.png": "hexbin/hexbin_4panel.png",
        "11_bivariate_matrix_standalone.png": "bivariate_matrix/bivariate_matrix.png",
        "12_atlas_map_series_page1.png": "map_sheet/map_sheet.png",
    }
    updated = 0
    for target_name, source_rel in mapping.items():
        source = SHOTS / source_rel
        if not source.exists():
            continue
        shutil.copy2(source, img_dir / target_name)
        updated += 1
    print(f"img/  ← {updated} showcase images refreshed with real plugin output")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_hero()
    build_bivariate()
    build_layout()
    build_modules()
    refresh_showcase_images()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
