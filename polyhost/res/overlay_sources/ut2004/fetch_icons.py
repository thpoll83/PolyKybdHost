#!/usr/bin/env python3
"""Fetch + render the Unreal Tournament 2004 icons (reproducible).

The key icons are flat 1-bit silhouettes from game-icons.net (CC BY 3.0,
credit per author in SOURCES.md), as in the Counter-Strike 2 set. They are
what the keyboard shows when the game's own files are not on the machine;
with them, the weapon keys are redrawn from the game
(polyhost/services/game_assets/unreal2). The ESC mark is UT2004 set in Bebas
Neue (SIL OFL 1.1); Epic's logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/ut2004/fetch_icons.py

The fetched icons are re-rendered on every run. The ESC mark is written only
when its PNG is missing, so a hand edit to the committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Weapon slots 1 to 0 (the weapons' InventoryGroup in XWeapons.u)
    "shieldgun": "gi:lorc/bolt-shield",
    "assaultrifle": "gi:skoll/mp5",
    "biorifle": "gi:lorc/goo-spurt",
    "shockrifle": "gi:lorc/laser-precision",
    "linkgun": "gi:lorc/linked-rings",
    "minigun": "gi:lorc/bullets",
    "flakcannon": "gi:lorc/striking-diamonds",
    "rocketlauncher": "gi:lorc/missile-swarm",
    "lightninggun": "gi:lorc/lightning-tear",
    "superweapon": "gi:lorc/mushroom-cloud",
}

# The weapon keys use a 48 x 40 area, as the pictures read from the game do;
# the icon fills the 40 x 40 box at its right.
WEAPON_AREA = (48, 40)
SIZES = {stem: WEAPON_AREA for stem in ICONS}
INK = {stem: (40, 40) for stem in ICONS}


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, INK.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def program(out: Path) -> None:
    """program.png: UT2004 in Bebas Neue at the largest size that fits
    70 x 38 px, centred on the whole 72x40 cell."""
    path = out / "program.png"
    if not fac._missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font_path = cnc._font(fac.MARK_FONT_URL)
    w, h, ss, text = 72, 40, fac.MARK_SS, "UT2004"
    for px in range(400, 40, -4):
        font = ImageFont.truetype(str(font_path), px)
        b = font.getbbox(text)
        if b[2] - b[0] <= 70 * ss and b[3] - b[1] <= 38 * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (b[2] - b[0])) // 2 - b[0],
                             (h * ss - (b[3] - b[1])) // 2 - b[1]), text,
                            font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > fac.MARK_THRESHOLD, path)
    print(f"  program.png  <- {text} (Bebas Neue, {(b[3] - b[1]) // ss} px high)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    flat_icons(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
