#!/usr/bin/env python3
"""Fetch + render the SuperTuxKart icons (reproducible).

The key icons are flat silhouettes from Material Design Icons (Apache-2.0) and
Font Awesome Free (CC BY 4.0). SOURCES.md credits each. The ESC mark is "Super"
over "TuxKart" set in Racing Sans One (SIL OFL 1.1); the game's own logo art is
not used.

`flat_icons()` and `text_mark()` are also used by the Hedgewars, FlightGear and
Thrive sets.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/supertuxkart/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.fheroes2.fetch_icons import _alpha_mask  # noqa: E402

ICONS = {
    # Driving
    "accelerate": "mdi:speedometer",
    "brake": "mdi:car-brake-alert",
    "steerleft": "mdi:arrow-left-top-bold",
    "steerright": "mdi:arrow-right-top-bold",
    "nitro": "mdi:rocket-launch",
    "skid": "mdi:car-traction-control",
    "fire": "fa:gift",
    "lookback": "mdi:eye-arrow-left",
    "rescue": "fa:life-ring",
    # Every screen
    "screenshot": "fa:camera",
    "recordvideo": "fa:video",
    "savereplay": "fa:film",
    "savehistory": "fa:clock-rotate-left",
    "fps": "mdi:counter",
    "kartpowerups": "mdi:go-kart",
    "soccerplayers": "mdi:soccer",
}

# Key area of each icon, from supertuxkart.yaml; the default is 40 x 40.
SIZES: dict[str, tuple[int, int]] = {}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"fire": (34, 34), "screenshot": (36, 32), "recordvideo": (36, 30),
       "savereplay": (34, 34), "rescue": (36, 36)}

# The ESC mark is set in Racing Sans One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/racingsansone/RacingSansOne-Regular.ttf")
MARK_LINES = ("Super", "TuxKart")   # the ESC mark, one line each
# Grey level (0..255) from which a box-filtered ESC mark pixel is lit.
MARK_THRESHOLD = 100


def flat_icons(out: Path, icons, sizes=None, ink=None) -> None:
    """Every icon of `icons` (file stems) as a flat 1-bit silhouette, drawn at
    exactly its key area (`sizes`, default 40 x 40) so the generator places it
    1:1. An icon in `ink` fills a smaller box in the bottom-right corner of
    that area."""
    import numpy as np
    sizes, ink = sizes or {}, ink or {}
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        m = _alpha_mask(out / f"{stem}.png", ink.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def text_mark(path: Path, lines, font_url: str, threshold: int, gap: int = 2, ss: int = 8) -> None:
    """The ESC mark: `lines`, one below the other with `gap` px between them,
    at the largest one size at which each fits 70 px wide and all fit 38 px
    high, centred on the whole 72x40 cell. Drawn at `ss` times the size and
    box-filtered down; a pixel is lit from grey `threshold` of 255."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h = 72, 40
    font_path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(font_path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * ss * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, path)
    print(f"  {path.name}  <- {' / '.join(lines)} ({px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render(ICONS, out)
    flat_icons(out, ICONS, SIZES, INK)
    text_mark(out / "program.png", MARK_LINES, FONT_URL, MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
