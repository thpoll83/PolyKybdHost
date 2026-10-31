#!/usr/bin/env python3
"""Fetch + render the fheroes2 icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0) and Font
Awesome Free (CC BY 4.0), as in the Warcraft III set. F2 (quick save) is the
Font Awesome floppy disk with a bolt beside it. SOURCES.md credits each. The
ESC mark is the name "fheroes2" set in Pirata One (SIL OFL 1.1); the game's own
icon and logo art are not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/fheroes2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Adventure map: heroes and towns
    "endturn": "fa:hourglass-end",
    "nexthero": "gi:lorc/visored-helm",
    "nexttown": "gi:delapouite/castle",
    "movehero": "fa:person-walking-arrow-right",
    "sleephero": "fa:bed",
    "castspell": "fa:wand-magic-sparkles",
    "dig": "gi:lorc/spade",
    "defaultaction": "fa:circle-play",
    "openfocus": "fa:up-right-from-square",
    # Adventure map: views and dialogs
    "viewworld": "fa:map",
    "kingdom": "fa:crown",
    "puzzle": "fa:puzzle-piece",
    "scenarioinfo": "fa:circle-info",
    "adventureoptions": "fa:compass",
    "systemoptions": "fa:gear",
    "fileoptions": "fa:file-lines",
    "newgame": "fa:file-circle-plus",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "quit": "fa:power-off",
    # Battle
    "retreat": "fa:person-running",
    # Town and army dialogs
    "well": "fa:bucket",
    "build": "fa:hammer",
    "upgrade": "fa:circle-up",
    "swaparmies": "fa:right-left",
    # Global
    "fullscreen": "fa:expand",
    "textmode": "fa:font",
}
# Parts of quicksave.png (F2), drawn by quicksave().
QUICKSAVE_PARTS = {"_floppy": "fa:floppy-disk", "_bolt": "fa:bolt"}

# Key area of each icon, from fheroes2.yaml; the default is 40 x 40. F2 and F4
# use the widths AoE2 measured to keep their legends whole.
SIZES = {"quicksave": (34, 40), "fullscreen": (30, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "fileoptions": (32, 34),
       "puzzle": (34, 34), "scenarioinfo": (32, 32), "adventureoptions": (32, 32),
       "defaultaction": (32, 32), "upgrade": (32, 32), "kingdom": (36, 34)}

# The ESC mark is set in Pirata One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/pirataone/PirataOne-Regular.ttf")
MARK_TEXT = "fheroes2"
MARK_SS = 8                 # supersampling factor for the ESC mark
# Grey level (0..255) from which a box-filtered ESC mark pixel is lit. At 120
# the thin joins of the "r" and "s" break; at 80 they hold.
MARK_THRESHOLD = 80


def _alpha_mask(path: Path, box: tuple[int, int]):
    """The icon's alpha cropped to its ink, scaled to fit `box` (w, h), 1-bit."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    return np.asarray(alpha) > 150


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    import numpy as np
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = _alpha_mask(out / f"{stem}.png", INK.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def quicksave(out: Path) -> None:
    """quicksave.png (F2): the floppy disk in the bottom-right corner, with a
    bolt above its left edge, cut out of the disk by a 2 px gap."""
    import numpy as np
    from polyhost.res.overlay_sources.aoe2 import program_mark
    w, h = SIZES["quicksave"]
    disk = _alpha_mask(out / "_floppy.png", (26, 26))
    bolt = _alpha_mask(out / "_bolt.png", (14, 20))
    canvas = np.zeros((h, w), bool)
    canvas[h - disk.shape[0]:, w - disk.shape[1]:] = disk
    b = np.zeros((h, w), bool)
    b[0:bolt.shape[0], 0:bolt.shape[1]] = bolt
    canvas = (canvas & ~program_mark.dilate(b, 2)) | b
    cnc._save_mask(canvas, out / "quicksave.png")
    print("  quicksave.png  <- fa:floppy-disk + fa:bolt")


def program(out: Path) -> None:
    """program.png: "fheroes2" at the largest size that fits 70x38 px, centred
    on the whole 72x40 cell. Drawn at MARK_SS times the size and box-filtered
    down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    path = str(cnc._font(FONT_URL))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        box = font.getbbox(MARK_TEXT)
        if box[2] - box[0] <= (w - 2) * ss and box[3] - box[1] <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0],
                             (h * ss - (box[3] - box[1])) // 2 - box[1]),
                            MARK_TEXT, font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- {MARK_TEXT} (Pirata One, {px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **QUICKSAVE_PARTS}, out)
    flat_icons(out)
    quicksave(out)
    for stem in QUICKSAVE_PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
