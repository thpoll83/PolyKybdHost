#!/usr/bin/env python3
"""Fetch + render the League of Legends icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Factorio and Age of Empires
II sets: game shapes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and interface shapes from Material Symbols (Apache-2.0). The item
slots and the ally numbers are drawn here. The ESC mark is LEAGUE set in Bebas
Neue (SIL OFL 1.1); Riot's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/lol/fetch_icons.py

The fetched icons are re-rendered on every run. The drawn icons (item slots,
allies, the ESC mark) are written only when their PNG is missing, so a hand
edit to a committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402

ICONS = {
    # Abilities and items
    "levelup": "ms:upgrade",
    "trinket": "gi:lorc/lantern-flame",
    "recall": "ms:home",
    "champonly": "gi:sbed/targeted",
    # Player movement
    "attackmove": "gi:lorc/crossed-swords",
    "hold": "ms:pan_tool",
    "stop": "ms:block",
    # Camera
    "centre": "ms:center_focus_strong",
    "camlock": "ms:lock",
    "self": "ms:person",
    "mouselock": "ms:mouse",
    "screenshot": "ms:screenshot_monitor",
    "fullscreen": "ms:fullscreen",
    "minimapdrag": "ms:map",
    "fps": "ms:speed",
    # Communication
    "ping": "ms:error",
    "visionping": "ms:visibility",
    "joke": "ms:theater_comedy",
    "taunt": "gi:lorc/shouting",
    "dance": "ms:music_note",
    "laugh": "ms:sentiment_very_satisfied",
    "emotetoggle": "ms:toggle_on",
    "mastery": "ms:military_tech",
    "fistbump": "gi:lorc/fist",
    "mybad": "ms:sentiment_dissatisfied",
    "emotewheel": "ms:add_reaction",
    "chat": "ms:chat",
    "allchat": "ms:public",
    "chathistory": "ms:history",
    "mic": "ms:mic",
    # Menus and shop
    "scoreboard": "ms:scoreboard",
    "menu": "ms:menu",
    "stats": "ms:query_stats",
    "basicstats": "ms:bar_chart",
    "shop": "gi:delapouite/shop",
    "shopsearch": "ms:search",
    "shoptabs": "ms:tab",
}

# Key area of each icon, from lol.yaml; the default is 40 x 40.
SIZES = {"self": (34, 40), "screenshot": (30, 40), "mouselock": (34, 40)}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"chat": (34, 34), "allchat": (34, 34), "ping": (34, 34), "stop": (34, 34),
       "laugh": (34, 34), "mybad": (34, 34), "emotewheel": (34, 34),
       "visionping": (40, 30), "self": (30, 34), "mouselock": (26, 34)}

# The inventory is two rows of three slots: keys 1 2 3 are the top row, 5 6 7
# the bottom row (4 is the trinket). `item<k>.png` shows that slot filled.
ITEM_SLOTS = {"1": (0, 0), "2": (0, 1), "3": (0, 2), "5": (1, 0), "6": (1, 1), "7": (1, 2)}


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key
    area. The icons in INK fill a smaller box in the bottom-right corner."""
    import numpy as np
    from PIL import Image
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        box = INK.get(stem, size)
        alpha = Image.open(out / f"{stem}.png").convert("RGBA").getchannel("A")
        alpha = alpha.crop(alpha.getbbox())
        scale = min(box[0] / alpha.width, box[1] / alpha.height)
        alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                             Image.LANCZOS)
        m = np.asarray(alpha) > 150
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def item_slots(out: Path) -> None:
    """item<k>.png (keys 1 2 3 5 6 7), 40x40: the 3x2 inventory as 2 px frames
    of 12x12, 1 px apart, with the slot of that key filled."""
    import numpy as np
    for key, (row, col) in ITEM_SLOTS.items():
        path = out / f"item{key}.png"
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
        print(f"  item{key}.png  <- drawn (row {row + 1}, slot {col + 1})")


def allies(out: Path) -> None:
    """ally<n>.png (F2..F5: select ally 1..4), 34x40: the person glyph with the
    ally number beside it."""
    import numpy as np
    font = None
    for n in "1234":
        path = out / f"ally{n}.png"
        if not fac._missing(path):
            continue
        font = font or fac._bold(16)
        g = fac._glyph_mask("ms:person", (20, 30))
        m = np.zeros((40, 34), bool)
        m[40 - g.shape[0]:, 0:g.shape[1]] = g
        m |= fac._text_mask(n, font, (34, 40), (28, 27))
        cnc._save_mask(m, path)
        print(f"  ally{n}.png  <- ms:person + {n}")


def program(out: Path) -> None:
    """program.png: LEAGUE in Bebas Neue at the largest size that fits
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
        b = font.getbbox("LEAGUE")
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), "LEAGUE",
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  program.png  <- LEAGUE (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    flat_icons(out)
    item_slots(out)
    allies(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
