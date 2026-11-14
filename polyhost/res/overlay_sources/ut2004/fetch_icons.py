#!/usr/bin/env python3
"""Fetch + render the Unreal Tournament 2004 icons (reproducible).

The key icons are flat 1-bit silhouettes from game-icons.net (CC BY 3.0,
credit per author in SOURCES.md) and Material Symbols (Apache-2.0), as in the
Counter-Strike 2 set. They are
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
    "translocator": "gi:lorc/teleport",
    # Weapons and inventory
    "lastweapon": "ms:history",
    "bestweapon": "ms:star",
    "throwweapon": "ms:place_item",
    "nextweapon": "ms:skip_next",
    "invprev": "ms:chevron_left",
    "invnext": "ms:chevron_right",
    # Movement and actions
    "jump": "gi:delapouite/jump-across",
    "use": "ms:touch_app",
    "taunt": "ms:mood",
    "basepath": "ms:route",
    # Communication
    "talk": "ms:chat",
    "teamtalk": "ms:forum",
    "type": "ms:keyboard",
    "voicetalk": "ms:mic",
    "voiceteam": "ms:groups",
    "voicelocal": "ms:near_me",
    "voicepublic": "ms:public",
    "speechmenu": "gi:delapouite/megaphone",
    "vote": "ms:how_to_vote",
    "ingamechat": "ms:chat_bubble",
    # Display and menus
    "scores": "ms:scoreboard",
    "stats": "ms:bar_chart",
    "behindview": "ms:3p",
    "netstats": "ms:network_check",
    "screenshot": "ms:screenshot_monitor",
    "music": "ms:music_note",
    "radar": "ms:radar",
    "console": "ms:terminal",
    "growhud": "ms:zoom_out_map",       # the arrows point outward
    "shrinkhud": "ms:zoom_in_map",      # the arrows point inward
    "pause": "ms:pause",
}

# The weapon keys use a 48 x 40 area, as the pictures read from the game do;
# the icon fills the 40 x 40 box at its right.
WEAPON_AREA = (48, 40)
WEAPONS = ("shieldgun", "assaultrifle", "biorifle", "shockrifle", "linkgun", "minigun",
           "flakcannon", "rocketlauncher", "lightninggun", "superweapon")
SIZES = {stem: WEAPON_AREA for stem in WEAPONS}
# F1 to F6: the F-key legend area AoE2 measured (34 x 40), as in the Warcraft III set.
SIZES.update({stem: (34, 40) for stem in ("scores", "ingamechat", "stats", "behindview", "netstats")})
INK = {stem: (40, 40) for stem in WEAPONS}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK.update({"talk": (34, 34), "teamtalk": (34, 34), "voicepublic": (34, 34), "pause": (30, 30),
            "invprev": (26, 34), "invnext": (26, 34)})


def flat_icons(out: Path) -> None:
    """Every fetched icon as a flat 1-bit silhouette, drawn at exactly its key area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(zeroad._flat(out / f"{stem}.png", size, INK.get(stem, size)),
                       out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def crouch(out: Path) -> None:
    """crouch.png (C, Duck): a figure crouched over a floor line, drawn here
    because the game-icons and Material Symbols figures read as praying.
    Strokes 4.5 px wide, drawn 8 times larger and box-filtered to 40 x 40."""
    path = out / "crouch.png"
    if not fac._missing(path):
        return
    import numpy as np
    from PIL import Image, ImageDraw
    ss, size = 8, 40
    im = Image.new("L", (size * ss, size * ss), 0)
    d = ImageDraw.Draw(im)

    def line(points, width):
        d.line([(x * ss, y * ss) for x, y in points], fill=255, width=round(width * ss), joint="curve")

    d.ellipse([22 * ss, 3 * ss, 31 * ss, 12 * ss], fill=255)          # head
    line([(25, 14), (17, 25)], 4.5)                                   # back
    line([(17, 25), (30, 28), (25, 38)], 4.5)                         # front thigh and shin
    line([(17, 25), (12, 38)], 4.5)                                   # rear leg, knee down
    line([(22, 17), (31, 22)], 3.5)                                   # arm
    line([(5, 38), (37, 38)], 2)                                      # floor
    cnc._save_mask(np.asarray(im.resize((size, size), Image.BOX)) > 110, path)
    print("  crouch.png  <- drawn")


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
    crouch(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
