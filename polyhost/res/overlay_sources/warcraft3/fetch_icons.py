#!/usr/bin/env python3
"""Fetch + render the Warcraft III icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0) and Font
Awesome Free (CC BY 4.0), as in the Age of Empires II set. The control
groups are game-icons.net units, drawn once at full height, with a plus for
Ctrl (create) and a ringed plus for Shift (add). SOURCES.md credits
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
    # F1 to F3: three different heroes, so the keys differ by more than the legend
    "hero1": "gi:lorc/visored-helm",
    "hero2": "gi:delapouite/wizard-face",
    "hero3": "gi:lorc/crowned-skull",
    "idleworker": "gi:delapouite/miner",
    "townhall": "gi:delapouite/castle",
    "lastevent": "gi:lorc/ringing-bell",
    "subgroup": "gi:lorc/cycle",
    "portrait": "fa:crosshairs",
    # Camera
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
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
    "screenshot": "fa:camera",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "chatall": "gi:delapouite/megaphone",
    "chatallies": "gi:lorc/conversation",
}

# Control groups: one unit per digit, drawn once at full height.
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
SIZES = {"hero1": (34, 40), "hero2": (34, 40), "hero3": (34, 40), "idleworker": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "help": (34, 34), "chat": (34, 34),
       "zoomin": (30, 30), "zoomout": (30, 30), "music": (30, 30), "screenshot": (30, 30)}
# Insert and Delete (rotate the camera): a person with an arrow around their
# feet, drawn by rotate_icons() from this Font Awesome icon.
ROTATE_PERSON = "fa:street-view"

# The ESC mark is set in Cinzel (SIL OFL 1.1), its Black instance.
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzel/Cinzel%5Bwght%5D.ttf")
MARK_SS = 8                                     # supersampling factor for the ESC mark
# Grey level (0..255) from which a box-filtered ESC mark pixel is lit, per line.
# At 110 the thin serifs of WARCRAFT broke off into loose pixels; at 60 none do.
# The III keeps 110: at 60 its serifs join and it reads as "[II]".
MARK_THRESHOLD = {"WARCRAFT": 60, "III": 110}


def _with_ring_plus(mask, size=13, bar=3):
    """Shift+digit (add to the group): the Ctrl plus inside a 1 px ring."""
    import numpy as np
    H, W = mask.shape
    yy, xx = np.mgrid[0:H, 0:W]
    r = size // 2 + 2
    cy, cx = H - r - 1, W - r - 1                  # the whole ring inside the cell
    disc = (yy - cy) ** 2 + (xx - cx) ** 2 <= r * r
    ring = disc & program_mark.dilate(~disc, 1)
    p = np.zeros((H, W), bool)
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2 + 2:cx + size // 2 - 1] = True
    p[cy - size // 2 + 2:cy + size // 2 - 1, cx - bar // 2:cx + bar // 2 + 1] = True
    p |= ring
    return (mask & ~program_mark.dilate(disc, aoe2.GROUP_SEAM - 1)) | p


def _single(src: Path):
    """The unit at the largest height up to GROUP_H whose width leaves 4 px of
    the group cell free on the left."""
    for h in range(aoe2.GROUP_H, 10, -1):
        m = aoe2._unit_mask(src, h)
        if m.shape[1] <= aoe2.GROUP_W - 4:
            return m
    return m


def groups(out: Path) -> None:
    """group<N>.png (select), groupnew<N>.png (Ctrl: create) and groupadd<N>.png
    (Shift: add)."""
    for digit in GROUP_UNITS:
        g = _single(out / f"_unit{digit}.png")
        aoe2._save_cell(g, out / f"group{digit}.png")
        aoe2._save_cell(aoe2._with_plus(g), out / f"groupnew{digit}.png")
        aoe2._save_cell(_with_ring_plus(g), out / f"groupadd{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png, groupadd{digit}.png  <- _unit{digit}.png")


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
    print(f"  {len(ICONS)} key icons drawn flat")


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
    y = (h * ss - height) // 2
    canvas = np.zeros((h, w), bool)
    for text, font, box in (("WARCRAFT", top, tb), ("III", bottom, bb)):
        im = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                                text, font=font, fill=255)
        canvas |= np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD[text]
        y += box[3] - box[1] + gap
    cnc._save_mask(canvas, out / "program.png")
    print(f"  program.png  <- WARCRAFT III (Cinzel Black, cap {cap} px)")


def rotate_icons(out: Path) -> None:
    """rotateleft.png and rotateright.png (Insert, Delete): the person stands at
    the top; below them an arc of an ellipse runs round their feet with the
    arrowhead at the left end (Insert) or the right end (Delete). Drawn at
    MARK_SS times the size and box-filtered down, 40x40."""
    import math

    import numpy as np
    from PIL import Image, ImageDraw
    ss, size = MARK_SS, 40
    a = Image.open(out / "_person.png").convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    k = min(18 * ss / a.width, 26 * ss / a.height)
    person = a.resize((round(a.width * k), round(a.height * k)), Image.LANCZOS)
    box, width = (2 * ss, 24 * ss, 38 * ss, 39 * ss), 3 * ss
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    rx, ry = (box[2] - box[0]) / 2 - width / 2, (box[3] - box[1]) / 2 - width / 2
    for stem, head in (("rotateleft", 160), ("rotateright", 20)):
        im = Image.new("L", (size * ss, size * ss), 0)
        im.paste(255, ((size * ss - person.width) // 2 + 2 * ss, ss), person)
        d = ImageDraw.Draw(im)
        d.arc(box, 20, 160, fill=255, width=width)
        t = math.radians(head)
        px, py = cx + rx * math.cos(t), cy + ry * math.sin(t)
        sign = 1 if head == 160 else -1             # the direction of travel at the head
        tx, ty = -rx * math.sin(t) * sign, ry * math.cos(t) * sign
        n = math.hypot(tx, ty)
        tx, ty = tx / n, ty / n
        length, half = width * 2.6, width * 2.0
        d.polygon([(px + tx * length * 0.8, py + ty * length * 0.8),
                   (px - ty * half, py + tx * half), (px + ty * half, py - tx * half)], fill=255)
        cnc._save_mask(np.asarray(im.resize((size, size), Image.BOX)) > 110, out / f"{stem}.png")
    print(f"  rotateleft.png, rotateright.png  <- {ROTATE_PERSON} + an arrow round the feet")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, "_person": ROTATE_PERSON}, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    flat_icons(out)
    groups(out)
    rotate_icons(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
