#!/usr/bin/env python3
"""Fetch + render the Dota 2 icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the League of Legends set: game
shapes from game-icons.net (CC BY 3.0, credit per author in SOURCES.md) and
interface shapes from Material Symbols (Apache-2.0). The item slots and the
numbered control groups are drawn here. The ESC mark is DOTA 2 set in Bebas
Neue (SIL OFL 1.1); Valve's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/dota2/fetch_icons.py

The fetched icons are re-rendered on every run. The drawn icons (item slots,
control groups, the ESC mark) are written only when their PNG is missing, so a
hand edit to a committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Unit actions
    "hero": "ms:person",
    "attack": "gi:lorc/crossed-swords",
    "hold": "ms:pan_tool",
    "stop": "ms:block",
    "move": "gi:delapouite/walk",
    "learn": "ms:upgrade",
    "talents": "ms:account_tree",
    "glyph": "gi:lorc/stone-tower",
    "scan": "gi:lorc/radar-sweep",
    "nextunit": "ms:skip_next",
    # Shop and courier
    "courier": "gi:delapouite/horse-head",
    "deliver": "ms:local_shipping",
    "shop": "gi:delapouite/shop",
    "quickbuy": "ms:shopping_cart",
    "sticky": "ms:push_pin",
    # Interface
    "scoreboard": "ms:scoreboard",
    "pause": "ms:pause",
    "screenshot": "ms:screenshot_monitor",
    "console": "ms:terminal",
    "showcase": "ms:zoom_in",
    # Chat
    "teamchat": "ms:chat",
    "allchat": "ms:public",
    "voice": "ms:mic",
    "chatwheel": "ms:forum",
    # Control groups: only drawn with their number, in groups()
    "group": "ms:groups",
    "groupadd": "ms:group_add",
}

# Key area of each icon, from dota2.yaml; the default is 40 x 40. F1 to F9 use
# the areas AoE2 measured for F-key legends.
SIZES = {stem: (34, 40) for stem in ("hero", "courier", "deliver", "shop", "quickbuy",
                                     "screenshot", "sticky", "pause")}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"hero": (30, 34), "stop": (34, 34), "pause": (30, 34), "teamchat": (34, 34),
       "allchat": (34, 34), "chatwheel": (34, 34), "scoreboard": (40, 34),
       "deliver": (34, 30)}

# The inventory is two rows of three slots: Z X C the top row, V B N the bottom
# row. `item_<key>.png` shows that slot filled.
ITEM_SLOTS = {"z": (0, 0), "x": (0, 1), "c": (0, 2), "v": (1, 0), "b": (1, 1), "n": (1, 2)}

# Control groups 1..9: the group glyph at the bottom, the number in the top-left.
GROUPS = "123456789"
GROUP_BOX = (40, 24)      # the group glyph, at the bottom of the 40 x 40 area
GROUP_DIGIT_PX = 14       # digit height
GROUP_SEAM = 2            # unlit rows between the digit and the glyph


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key
    area. The icons in INK fill a smaller box in the bottom-right corner."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, INK.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def item_slots(out: Path) -> None:
    """item_<key>.png (Z X C V B N), 40x40: the 3x2 inventory as 2 px frames of
    12x12, 1 px apart, with the slot of that key filled (as in the League of
    Legends set)."""
    import numpy as np
    for key, (row, col) in ITEM_SLOTS.items():
        path = out / f"item_{key}.png"
        if not fac._missing(path):
            continue
        m = np.zeros((40, 40), bool)
        for r in range(2):
            for c in range(3):
                x, y = 2 + c * 13, 13 + r * 14
                m[y:y + 12, x:x + 12] = True
                if (r, c) != (row, col):
                    m[y + 2:y + 10, x + 2:x + 10] = False
        cnc._save_mask(m, path)
        print(f"  item_{key}.png  <- drawn (row {row + 1}, slot {col + 1})")


def groups(out: Path) -> None:
    """group<n>.png (1..9: select group n) and groupadd<n>.png (Ctrl+1..9:
    assign group n), 40x40: the group glyph at the bottom with the number
    above it on the left. The plain glyphs are deleted afterwards, since no key
    draws them."""
    import numpy as np
    for stem in ("group", "groupadd"):
        src = out / f"{stem}.png"
        for n in GROUPS:
            path = out / f"{stem}{n}.png"
            if not fac._missing(path):
                continue
            g = zeroad._flat(src, (40, 40), GROUP_BOX)
            d = zeroad._digit(n, GROUP_DIGIT_PX)
            top = int(np.nonzero(g.any(axis=1))[0][0])
            y = max(0, top - GROUP_SEAM - d.shape[0])
            g[y:y + d.shape[0], 0:d.shape[1]] |= d
            cnc._save_mask(g, path)
            print(f"  {stem}{n}.png  <- {ICONS[stem]} + {n}")
        src.unlink()


def program(out: Path) -> None:
    """program.png: DOTA 2 in Bebas Neue at the largest size that fits
    70 x 38 px, centred on the whole 72x40 cell."""
    path = out / "program.png"
    if not fac._missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(fac.MARK_FONT_URL)
    w, h, ss = 72, 40, fac.MARK_SS
    for px in range(400, 40, -4):
        font = ImageFont.truetype(str(font_path), px)
        b = font.getbbox("DOTA 2")
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), "DOTA 2",
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  program.png  <- DOTA 2 (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    flat_icons(out)
    item_slots(out)
    groups(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
