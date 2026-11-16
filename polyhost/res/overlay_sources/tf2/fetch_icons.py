#!/usr/bin/env python3
"""Fetch + render the Team Fortress 2 icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The
three voice menu keys get their menu number drawn in. The ESC mark is TF2 in
Bebas Neue (SIL OFL 1.1); Valve's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/tf2/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Movement
    "forward": "ms:arrow_upward",
    "left": "ms:arrow_back",
    "back": "ms:arrow_downward",
    "right": "ms:arrow_forward",
    # Weapon slots
    "primary": "gi:lorc/rocket",
    "secondary": "gi:john-colburn/pistol-gun",
    "melee": "gi:sbed/wrench",
    "src_pda": "ms:tablet_android",          # only drawn with its number
    "lastweapon": "ms:history",
    # Actions
    "jump": "gi:delapouite/jump-across",
    "reload": "ms:autorenew",
    "inspect": "ms:visibility",
    "taunt": "ms:celebration",
    "actionitem": "ms:redeem",
    "dropitem": "gi:delapouite/briefcase",
    "disguise": "gi:lorc/domino-mask",
    "disguiseteam": "ms:swap_horiz",
    # Communication
    "src_voice": "gi:delapouite/walkie-talkie",   # only drawn with its number
    "medic": "ms:medical_services",
    "spray": "gi:lorc/spray",
    "allchat": "ms:public",
    "teamchat": "ms:chat",
    "partychat": "gi:delapouite/three-friends",
    "voice": "ms:mic",
    # Menus
    "scoreboard": "ms:scoreboard",
    "changeteam": "ms:flag",
    "changeclass": "ms:switch_account",
    "loadout": "ms:checkroom",
    "backpack": "ms:backpack",
    "mapinfo": "ms:map",
    "accept": "ms:check",
    "decline": "ms:close",
    "console": "ms:terminal",
    "roundinfo": "ms:info",
    "contracts": "ms:assignment",
    "screenshot": "ms:screenshot_monitor",
    "savereplay": "ms:video_file",
    "report": "ms:report",
    "quit": "ms:logout",
    "pause": "ms:pause",
}

SIZES = {"roundinfo": (34, 40), "contracts": (34, 40), "screenshot": (34, 40),
         "savereplay": (34, 40), "report": (34, 40), "quit": (30, 40)}
INK = {"teamchat": (34, 34), "allchat": (34, 34), "scoreboard": (40, 34), "medic": (36, 36),
       "primary": (36, 36), "forward": (30, 34), "back": (30, 34), "left": (34, 30), "right": (34, 30),
       "backpack": (34, 40),
       "accept": (34, 34), "decline": (30, 30), "pause": (30, 30), "dropitem": (36, 32)}
NUMBERED = {"pda1": ("src_pda", "1"), "pda2": ("src_pda", "2"),
            "voice1": ("src_voice", "1"), "voice2": ("src_voice", "2"), "voice3": ("src_voice", "3")}


def main() -> int:
    return game_set.build(Path(__file__).resolve().parent / "icons", ICONS, sizes=SIZES, ink=INK,
                          numbered=NUMBERED, mark="TF2")


if __name__ == "__main__":
    raise SystemExit(main())
