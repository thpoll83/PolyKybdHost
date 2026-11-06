#!/usr/bin/env python3
"""Fetch + render the Counter-Strike 2 icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the League of Legends and
Factorio sets: game shapes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and interface shapes from Material Symbols (Apache-2.0). The two
radio wheel keys get their number drawn here. The ESC mark is CS2 set in Bebas
Neue (SIL OFL 1.1); Valve's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/cs2/fetch_icons.py

The fetched icons are re-rendered on every run. The drawn icons (the radio
wheels, the ESC mark) are written only when their PNG is missing, so a hand
edit to a committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Weapon slots
    "primary": "gi:skoll/ak47",
    "secondary": "gi:john-colburn/pistol-gun",
    "knife": "gi:lorc/bowie-knife",
    "grenade": "gi:lorc/grenade",
    "bomb": "gi:delapouite/dynamite",
    "hegrenade": "gi:lorc/mine-explosion",
    "flashbang": "gi:lorc/flash-grenade",
    "smoke": "gi:lorc/smoking-orb",
    "decoy": "ms:volume_up",
    "molotov": "gi:lorc/fire-bomb",
    "healthshot": "gi:lorc/syringe",
    "lastweapon": "ms:history",
    # Actions
    "jump": "gi:delapouite/jump-across",
    "use": "ms:touch_app",
    "reload": "ms:autorenew",
    "inspect": "ms:visibility",
    "drop": "ms:place_item",
    "switchhands": "ms:swap_horiz",
    # Buying
    "buymenu": "gi:delapouite/shopping-cart",
    "autobuy": "ms:shopping_cart_checkout",
    "rebuy": "ms:replay",
    "sellback": "ms:sell",
    # Communication
    "radio": "gi:delapouite/walkie-talkie",   # only drawn with its number, in radios()
    "radiomenu": "ms:campaign",
    "spray": "gi:lorc/spray",
    "teamchat": "ms:chat",
    "allchat": "ms:public",
    # Menus
    "scoreboard": "ms:scoreboard",
    "loadout": "gi:delapouite/backpack",
    "teammenu": "ms:groups",
    "console": "ms:terminal",
    "screenshot": "ms:screenshot_monitor",
    "quit": "ms:logout",
}

# Key area of each icon, from cs2.yaml; the default is 40 x 40.
SIZES = {"autobuy": (34, 40), "rebuy": (34, 40), "screenshot": (34, 40), "quit": (30, 40)}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"teamchat": (34, 34), "allchat": (34, 34), "grenade": (34, 40), "bomb": (40, 34),
       "hegrenade": (36, 36), "molotov": (34, 40), "loadout": (30, 40),
       "scoreboard": (40, 34), "decoy": (36, 36)}

# The radio wheel keys: C opens wheel 1, V wheel 2.
RADIO_WHEELS = ("1", "2")
RADIO_BOX = (26, 40)      # the walkie-talkie, at the right of the 40 x 40 area
RADIO_DIGIT_PX = 15       # digit height, drawn in the top-left of the area


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key
    area. The icons in INK fill a smaller box in the bottom-right corner."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, INK.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def radios(out: Path) -> None:
    """radio<n>.png (C, V: radio wheel 1 and 2), 40x40: the walkie-talkie at
    the right with the wheel number in the top-left corner. The plain
    walkie-talkie is deleted afterwards, since no key draws it."""
    src = out / "radio.png"
    for n in RADIO_WHEELS:
        path = out / f"radio{n}.png"
        if not fac._missing(path):
            continue
        m = zeroad._flat(src, (40, 40), RADIO_BOX)
        d = zeroad._digit(n, RADIO_DIGIT_PX)
        m[0:d.shape[0], 0:d.shape[1]] |= d
        cnc._save_mask(m, path)
        print(f"  radio{n}.png  <- walkie-talkie + {n}")
    src.unlink()


def program(out: Path) -> None:
    """program.png: CS2 in Bebas Neue at the largest size that fits
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
        b = font.getbbox("CS2")
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), "CS2",
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  program.png  <- CS2 (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    flat_icons(out)
    radios(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
