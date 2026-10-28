#!/usr/bin/env python3
"""Fetch + render the Warcraft III icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0) and Font
Awesome Free (CC BY 4.0), as in the Age of Empires II set. The control
groups are game-icons.net units drawn twice, as for Age of Empires II, with a
plus for Ctrl (create) and a ringed plus for Shift (add). SOURCES.md credits
each. The ESC mark is WARCRAFT III set in Cinzel Black (SIL OFL 1.1); the
game's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/warcraft3/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402

ICONS = {
    # Selection and view
    "hero": "gi:lorc/visored-helm",
    "idleworker": "gi:delapouite/miner",
    "townhall": "gi:delapouite/castle",
    "lastevent": "gi:lorc/ringing-bell",
    "subgroup": "gi:lorc/cycle",
    "portrait": "fa:crosshairs",
    # Camera
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "rotateleft": "fa:rotate-left",
    "rotateright": "fa:rotate-right",
    # Menus
    "questlog": "gi:lorc/scroll-unfurled",
    "gamemenu": "fa:bars",
    "allies": "gi:delapouite/shaking-hands",
    "chatlog": "gi:delapouite/notebook",
    "options": "fa:gear",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "help": "fa:circle-question",
    "quit": "fa:door-open",
    "music": "fa:music",
    "sound": "fa:volume-high",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "chatall": "gi:delapouite/megaphone",
    "chatallies": "gi:lorc/conversation",
}

# Control groups: one unit per digit, drawn twice as a group (aoe2.groups()).
GROUP_UNITS = {
    "1": "lorc/spartan",
    "2": "lorc/bowman",
    "3": "delapouite/horse-head",
    "4": "delapouite/dwarf-face",
    "5": "lorc/wolf-head",
    "6": "delapouite/trebuchet",
    "7": "delapouite/griffin-symbol",
    "8": "lorc/wyvern",
    "9": "lorc/dragon-head",
    "0": "delapouite/farmer",
}

# Key area of each icon, from warcraft3.yaml; the default is 40 x 40.
SIZES = {"hero": (34, 40), "idleworker": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "help": (34, 34), "chat": (34, 34)}
HEROES = "123"                                  # F1..F3: the helmet with the hero's number

# The ESC mark is set in Cinzel (SIL OFL 1.1), its Black instance.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf")
MARK_SS = 8                                     # supersampling factor for the ESC mark


def _with_ring_plus(mask, size=13, bar=3):
    """Shift+digit (add to the group): the Ctrl plus inside a 1 px ring."""
    import numpy as np
    H, W = mask.shape
    yy, xx = np.mgrid[0:H, 0:W]
    cy, cx = H - size // 2 - 1, W - size // 2 - 1
    r = size // 2 + 2
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    ring = disc & program_mark.dilate(~disc, 1)
    p = np.zeros((H, W), bool)
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2 + 2:cx + size // 2 - 1] = True
    p[cy - size // 2 + 2:cy + size // 2 - 1, cx - bar // 2:cx + bar // 2 + 1] = True
    p |= ring
    return (mask & ~program_mark.dilate(disc, aoe2.GROUP_SEAM - 1)) | p


def groups(out: Path) -> None:
    """group<N>.png (select), groupnew<N>.png (Ctrl: create) and groupadd<N>.png
    (Shift: add)."""
    for digit in GROUP_UNITS:
        g = aoe2._group_mask(out / f"_unit{digit}.png")
        aoe2._save_cell(g, out / f"group{digit}.png")
        aoe2._save_cell(aoe2._with_plus(g), out / f"groupnew{digit}.png")
        aoe2._save_cell(_with_ring_plus(g), out / f"groupadd{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png, groupadd{digit}.png  <- _unit{digit}.png twice")


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, as in the AoE2 set, drawn at
    exactly its key area so the generator places it 1:1. The icons in INK fill
    a smaller box in the bottom-right corner of that area."""
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
        if stem == "hero":
            for n in HEROES:
                cnc._save_mask(cnc._stamp(canvas, n, height=12, top=17), out / f"hero{n}.png")
    print(f"  {len(ICONS)} key icons drawn flat (+ hero1..{HEROES[-1]})")


def _mark_font(px: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(cnc._font(FONT_URL)), px)
    f.set_variation_by_name("Black")
    return f


def program(out: Path) -> None:
    """program.png: WARCRAFT at the largest size that fits 70 px, over a III
    1.4 times as tall, centred on the whole 72x40 cell. Drawn at MARK_SS times
    the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = program_mark.W, program_mark.H, MARK_SS
    for cap in range(14, 5, -1):
        ref = _mark_font(200).getbbox("H")
        px = round(200 * cap * ss / (ref[3] - ref[1]))
        top, bottom = _mark_font(px), _mark_font(round(px * 1.4))
        tb, bb = top.getbbox("WARCRAFT"), bottom.getbbox("III")
        if tb[2] - tb[0] <= (w - 2) * ss:
            break
    gap = 5 * ss
    height = (tb[3] - tb[1]) + gap + (bb[3] - bb[1])
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    d.text(((w * ss - (tb[2] - tb[0])) // 2 - tb[0], y - tb[1]), "WARCRAFT", font=top, fill=255)
    y += tb[3] - tb[1] + gap
    d.text(((w * ss - (bb[2] - bb[0])) // 2 - bb[0], y - bb[1]), "III", font=bottom, fill=255)
    canvas = np.asarray(im.resize((w, h), Image.BOX)) > 110
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- WARCRAFT III (Cinzel Black, cap {cap} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render(ICONS, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    flat_icons(out)
    groups(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
