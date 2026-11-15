#!/usr/bin/env python3
"""Fetch + render the Endless Sky icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. The fleet group keys (0 to 9) are a ship with the group number
above it. SOURCES.md credits each icon. The ESC mark is "Endless" over "Sky"
set in Russo One (SIL OFL 1.1); the game's own icon is CC BY-SA 4.0 and is not
used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/endless_sky/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Flying
    "forward": "fa:rocket",
    "turnleft": "fa:rotate-left",
    "turnright": "fa:rotate-right",
    "reverse": "fa:arrow-turn-down",
    "autosteer": "mdi:steering",
    "afterburner": "fa:fire",
    "cloak": "fa:eye-slash",
    "mouseturn": "fa:computer-mouse",
    "stop": "fa:circle-stop",
    # Weapons
    "primary": "gi:lorc/ray-gun",
    "secondary": "gi:lorc/rocket",
    "selectsecondary": "fa:list",
    # Targets and other ships
    "nextship": "mdi:target",
    "nearesthostile": "mdi:skull-scan",
    "nearestasteroid": "fa:meteor",
    "nextescort": "fa:shield-halved",
    "nearestany": "mdi:crosshairs-gps",
    "board": "fa:right-to-bracket",
    "repair": "fa:screwdriver-wrench",
    "hail": "fa:comments",
    "scan": "gi:lorc/radar-sweep",
    # Travel
    "land": "fa:plane-arrival",
    "jump": "gi:lorc/vortex",
    "fleetjump": "gi:lorc/star-swirl",
    # Fleet orders
    "deploy": "fa:jet-fighter-up",
    "forcedeploy": "gi:delapouite/jet-fighter",
    "fight": "gi:lorc/crossed-swords",
    "holdfire": "fa:ban",
    "gather": "fa:arrows-to-circle",
    "formation": "mdi:dots-triangle",
    "holdposition": "fa:anchor",
    "ammo": "gi:lorc/bullets",
    "harvest": "fa:box-open",
    # Panels and the view
    "map": "fa:map",
    "info": "fa:id-card",
    "messagelog": "fa:scroll",
    "help": "fa:circle-question",
    "pause": "fa:pause",
    "fastforward": "fa:forward",
    "performance": "fa:gauge-high",
    "fullscreen": "fa:expand",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
}
# Parts of the group icons, drawn by groups() and removed afterwards.
GROUP_PARTS = {"_ship": "fa:shuttle-space", "_flag": "fa:flag"}
GROUPS = "1234567890"
GROUP_SHIP = (40, 22)       # box of the ship or flag, at the bottom of the key area
GROUP_DIGIT_PX = 14         # height of the group number, in the top-right corner
GROUP_PLUS = 11             # size of the plus of "add group", in the top-left corner
GROUP_PLUS_BAR = 3          # its stroke width

# Key area of each icon, from endless_sky.yaml; the default is 40 x 40. The
# widths are the ones the AoE2 set measured to keep the F-key legends whole.
SIZES = {"help": (34, 40), "performance": (34, 40), "fullscreen": (21, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"map": (34, 34), "info": (36, 34), "messagelog": (34, 34), "help": (32, 32),
       "pause": (30, 32), "holdfire": (34, 34), "stop": (34, 34), "mouseturn": (34, 34),
       "afterburner": (34, 34), "nextescort": (34, 34), "harvest": (36, 34)}

# The ESC mark is set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARK_LINES = ("Endless", "Sky")    # the ESC mark, one line each
MARK_GAP = 2                # px between the two lines
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 90         # grey level (0..255) from which a box-filtered pixel is lit


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


def groups(out: Path) -> None:
    """group<N>.png (select fleet group N): the ship at the bottom of a 40x40
    area with N in the top-right corner. groupadd<N>.png (Shift) adds a plus in
    the top-left corner. groupset<N>.png (Ctrl: store the selected ships as
    group N) has the flag in place of the ship."""
    import numpy as np
    w = h = 40
    plus = np.zeros((GROUP_PLUS, GROUP_PLUS), bool)
    lo = (GROUP_PLUS - GROUP_PLUS_BAR) // 2
    plus[lo:lo + GROUP_PLUS_BAR, :] = True
    plus[:, lo:lo + GROUP_PLUS_BAR] = True
    bases = {}
    for name, part in (("group", "_ship"), ("groupset", "_flag")):
        m = _alpha_mask(out / f"{part}.png", GROUP_SHIP)
        base = np.zeros((h, w), bool)
        base[h - m.shape[0]:, w - m.shape[1]:] = m
        bases[name] = base
    bases["groupadd"] = bases["group"].copy()
    bases["groupadd"][1:1 + GROUP_PLUS, 0:GROUP_PLUS] = plus
    for n in GROUPS:
        g = zeroad._digit(n, GROUP_DIGIT_PX)
        for name, base in bases.items():
            m = base.copy()
            m[0:g.shape[0], w - g.shape[1]:] |= g
            cnc._save_mask(m, out / f"{name}{n}.png")
    print(f"  group, groupadd and groupset {GROUPS[0]}..{GROUPS[-1]}  <- numbered")


def program(out: Path) -> None:
    """program.png: the lines of MARK_LINES, all at the largest one size at
    which each fits 70 px wide and all, with MARK_GAP between them, fit 38 px
    high, centred on the whole 72x40 cell. Drawn at MARK_SS times the size and
    box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    gap = MARK_GAP * ss
    path = str(cnc._font(FONT_URL))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        boxes = [font.getbbox(line) for line in MARK_LINES]
        height = sum(b[3] - b[1] for b in boxes) + gap * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(MARK_LINES, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- {' / '.join(MARK_LINES)} (Russo One, {px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **GROUP_PARTS}, out)
    flat_icons(out)
    groups(out)
    for stem in GROUP_PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
