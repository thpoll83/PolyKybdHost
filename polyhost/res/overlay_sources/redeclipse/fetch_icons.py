#!/usr/bin/env python3
"""Fetch + render the Red Eclipse icons (reproducible).

The key icons are flat 1-bit silhouettes, as in the Xonotic set: game shapes
from game-icons.net (CC BY 3.0, credit per author in SOURCES.md) and interface
shapes from Material Symbols (Apache-2.0). The ESC mark is the game's name set
in Bebas Neue (SIL OFL 1.1); the game's logo art is CC BY-SA 4.0 and is not
used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/redeclipse/fetch_icons.py

The fetched icons are re-rendered on every run. The ESC mark is written only
when its PNG is missing, so a hand edit to the committed PNG is kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.factorio import fetch_icons as fac  # noqa: E402
from polyhost.res.overlay_sources.xonotic import fetch_icons as xon  # noqa: E402

ICONS = {
    # Movement
    "forward": "ms:arrow_upward",
    "back": "ms:arrow_downward",
    "left": "ms:arrow_back",
    "right": "ms:arrow_forward",
    "jump": "gi:delapouite/jump-across",
    "special": "gi:lorc/sprint",
    # Weapons 1 to 9, 0, - and =
    "claw": "gi:lorc/claw-slashes",
    "pistol": "gi:john-colburn/pistol-gun",
    "sword": "gi:lorc/broadsword",
    "shotgun": "gi:delapouite/sawed-off-shotgun",
    "smg": "gi:delapouite/uzi",
    "flamer": "gi:carl-olsen/flame",
    "plasma": "gi:lorc/plasma-bolt",
    "zapper": "gi:sbed/electric",
    "rifle": "gi:skoll/lee-enfield",
    "grenade": "gi:lorc/grenade",
    "mine": "gi:lorc/land-mine",
    "rocket": "gi:lorc/rocket",
    # Weapon actions
    "weaponup": "ms:keyboard_double_arrow_up",
    "weapondown": "ms:keyboard_double_arrow_down",
    "reload": "ms:autorenew",
    "drop": "ms:place_item",
    "use": "ms:touch_app",
    "affinity": "gi:lorc/flying-flag",
    "suicide": "ms:skull",
    # Communication
    "chat": "ms:public",
    "teamchat": "ms:chat",
    "command": "ms:terminal",
    # Match
    "scoreboard": "ms:scoreboard",
    "bindmap": "ms:keyboard",
    "pause": "ms:pause",
    "addbot": "ms:person_add",
    "delbot": "ms:person_remove",
    "spectate": "ms:visibility",
    "play": "ms:sports_esports",
    # Function keys
    "help": "ms:help",
    "edit": "ms:edit",
    "maps": "ms:map",
    "votes": "ms:how_to_vote",
    "servers": "ms:dns",
    "profile": "ms:account_circle",
    "team": "ms:groups",
    "console": "ms:article",
    "thirdperson": "ms:cameraswitch",
    "screenshot": "ms:screenshot_monitor",
}

# Key area of each icon, from redeclipse.yaml; the default is 40 x 40.
SIZES = {"help": xon.F_KEY, "edit": xon.F_KEY, "maps": xon.F_KEY, "votes": xon.F_KEY,
         "servers": xon.F_KEY, "profile_f": xon.F_KEY, "team_f": xon.F_KEY,
         "console": xon.F_KEY, "thirdperson": xon.F_KEY, "screenshot": xon.F_KEY_WIDE}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"forward": (30, 30), "back": (30, 30), "left": (30, 30), "right": (30, 30),
       "weaponup": (30, 30), "weapondown": (30, 30),
       "chat": (34, 34), "teamchat": (34, 34), "scoreboard": (40, 34), "pause": (30, 30),
       "suicide": (32, 34), "grenade": (34, 40), "mine": (36, 36), "flamer": (36, 36),
       "help": (32, 32), "profile": (34, 34), "servers": (32, 32), "votes": (32, 32),
       "edit": (30, 30), "console": (32, 32), "maps": (32, 32)}

# Actions on two keys with different areas: the F-key copy of the icon.
F_COPIES = {"profile_f": ("profile", (32, 32)), "team_f": ("team", xon.F_KEY)}

MARK_LINES = ("RED", "ECLIPSE")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    fac.render(ICONS, out)
    for stem, (src, box) in F_COPIES.items():
        xon.resized(out / f"{src}.png", out / f"{stem}.png", SIZES[stem], box)
    xon.flat_icons(ICONS, SIZES, INK, out)
    xon.text_mark(MARK_LINES, fac.MARK_FONT_URL, out / "program.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
