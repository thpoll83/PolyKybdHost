#!/usr/bin/env python3
"""Fetch + render the Shattered Pixel Dungeon icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
Material Design Icons (Apache-2.0); the movement arrows are drawn by the
helpers of the Dungeon Crawl Stone Soup set. The quickslot keys (1 to 6) are a
slot frame with the slot number, the bag keys (F1 to F5) a bag with the bag
number cut out. SOURCES.md credits each. The ESC mark is the game's name set
in VT323 (SIL OFL 1.1); the game's own icon, the chest, is not readable at
1 bit (SOURCES.md).

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/shattered_pixel_dungeon/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.dcss import fetch_icons as dcss  # noqa: E402
from polyhost.res.overlay_sources.devilutionx import fetch_icons as devx  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    "wait": "fa:hourglass-half",
    "inventory": "mdi:bag-personal",
    "examine": "fa:magnifying-glass",
    "rest": "fa:bed",
    "attack": "mdi:sword-cross",
    "cycle": "fa:arrows-rotate",
    "action": "fa:hand-pointer",
    "loot": "mdi:tray-arrow-up",
    "resume": "fa:forward",
    "heroinfo": "fa:id-card",
    "journal": "fa:book",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "back": "fa:reply",
    "bag": "mdi:bag-personal",      # the base of bag1.png .. bag5.png
}
for _d in ("n", "e", "s", "w"):
    ICONS[f"move_{_d}"] = f"draw:move:{_d}"

# Key area of each icon, from shattered_pixel_dungeon.yaml; the default is 40 x 40.
BAG_SIZE = (34, 40)                 # the F keys
SIZES = {"bag": BAG_SIZE}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"journal": (34, 34), "back": (36, 34), "resume": (36, 30)}

QUICKSLOTS = range(1, 7)
SLOT = 34                   # outer size of the quickslot frame
SLOT_LINE = 3               # its line width
SLOT_DIGIT_PX = 18          # height of the slot number
BAGS = range(1, 6)
BAG_DIGIT_PX = 18           # height of the bag number
BAG_DIGIT_DROP = 3          # the digit's centre is this far below the bag's centre

# The ESC mark is set in VT323 (SIL OFL 1.1), a terminal font.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/vt323/VT323-Regular.ttf")
MARK_LINES = ("Shattered", "Pixel", "Dungeon")
MARK_THRESHOLD = 110        # grey level (0..255) from which a pixel is lit
MARK_GAP = 1                # px between the lines


def quickslots(out: Path) -> None:
    """slot1.png .. slot6.png: a square frame with the slot number inside."""
    import numpy as np
    for n in QUICKSLOTS:
        m = np.zeros((40, 40), bool)
        y0, x0 = (40 - SLOT) // 2, 40 - SLOT
        m[y0:y0 + SLOT, x0:x0 + SLOT] = True
        m[y0 + SLOT_LINE:y0 + SLOT - SLOT_LINE, x0 + SLOT_LINE:x0 + SLOT - SLOT_LINE] = False
        for y, x in ((y0, x0), (y0, x0 + SLOT - 1), (y0 + SLOT - 1, x0), (y0 + SLOT - 1, x0 + SLOT - 1)):
            m[y, x] = False         # rounded corners
        g = zeroad._digit(str(n), SLOT_DIGIT_PX)
        gy, gx = y0 + (SLOT - g.shape[0]) // 2, x0 + (SLOT - g.shape[1]) // 2
        m[gy:gy + g.shape[0], gx:gx + g.shape[1]] |= g
        cnc._save_mask(m, out / f"slot{n}.png")
    print(f"  slot1..{QUICKSLOTS[-1]}.png  <- drawn")


def bags(out: Path) -> None:
    """bag1.png .. bag5.png: the backpack as one filled shape with its number
    cut out, so the digit reads dark on lit. The plain bag.png is removed, as
    nothing draws it."""
    import numpy as np
    bag = zeroad._fill_holes(devx._load_mask(out / "bag.png"))
    ys, xs = np.nonzero(bag)
    cy = (ys.min() + ys.max() + 1) // 2 + BAG_DIGIT_DROP
    cx = (xs.min() + xs.max() + 1) // 2
    for n in BAGS:
        g = zeroad._digit(str(n), BAG_DIGIT_PX)
        m = bag.copy()
        y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
        m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(m, out / f"bag{n}.png")
    (out / "bag.png").unlink()
    print(f"  bag1..{BAGS[-1]}.png  <- mdi:bag-personal, numbered")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    dcss.build(ICONS, out, SIZES, INK)
    quickslots(out)
    bags(out)
    dcss.wordmark(MARK_LINES, FONT_URL, out / "program.png", MARK_THRESHOLD, MARK_GAP)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
