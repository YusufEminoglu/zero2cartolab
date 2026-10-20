#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimise the captured screenshots for the web.

The capture harness writes full-resolution PNGs so nothing is lost from the
source. This step produces web-sized copies (screenshots/web/) that the
Practical Guide embeds, so the published page stays light without asking the
reader to zoom a 1800 px composite.

Usage:
    python optimize_images.py [--max-width 1800] [--quality 82]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "screenshots"
DST = HERE / "screenshots" / "web"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-width", type=int, default=1800)
    ap.add_argument("--quality", type=int, default=82)
    args = ap.parse_args()

    total_before = 0
    total_after = 0
    count = 0

    for src in sorted(SRC.rglob("*.png")):
        if "web" in src.parts:
            continue
        rel = src.relative_to(SRC)
        dst = DST / rel.with_suffix(".jpg")
        dst.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > args.max_width:
                ratio = args.max_width / im.width
                im = im.resize((args.max_width, max(1, int(im.height * ratio))),
                               Image.LANCZOS)
            im.save(dst, "JPEG", quality=args.quality, optimize=True, progressive=True)

        before = src.stat().st_size
        after = dst.stat().st_size
        total_before += before
        total_after += after
        count += 1
        print(f"  {rel.as_posix():<58} {before // 1024:>5} KB → {after // 1024:>4} KB", flush=True)

    print(f"\n{count} images: {total_before // 1024} KB → {total_after // 1024} KB "
          f"({100 * total_after / max(total_before, 1):.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
