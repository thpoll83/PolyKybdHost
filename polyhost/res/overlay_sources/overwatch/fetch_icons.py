#!/usr/bin/env python3
"""Fetch + render the Overwatch 2 icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark is OW in Bebas Neue (SIL OFL 1.1); Blizzard's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/overwatch/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Abilities and weapons (the same command for every hero; what it does
    # depends on the hero)
    "ultimate": "gi:lorc/burning-meteor",
    "ability2": "gi:lorc/magic-palm",
    "reload": "ms:autorenew",
    "melee": "gi:lorc/punch",
    "interact": "ms:touch_app",
    "weapon": "gi:john-colburn/pistol-gun",
    "jump": "gi:delapouite/jump-across",
    # Communication
    "ping": "gi:delapouite/position-marker",
    "comms": "gi:delapouite/walkie-talkie",
    "healing": "ms:medical_services",
    "ultstatus": "ms:percent",
    "spray": "gi:lorc/spray",
    "pushtotalk": "ms:mic",
    "mute": "ms:mic_off",
    "chat": "ms:chat",
    # Menus
    "scoreboard": "ms:scoreboard",
    "heroselect": "ms:switch_account",
    "endorse": "gi:delapouite/thumb-up",
    "social": "gi:delapouite/three-friends",
    "highlight": "gi:delapouite/film-projector",
    "screenshot": "ms:screenshot_monitor",
}

SIZES = {"highlight": (34, 40)}
INK = {"chat": (34, 34), "scoreboard": (40, 34), "healing": (36, 36),
       "ultstatus": (34, 34), "weapon": (40, 32)}


def main() -> int:
    return game_set.build(Path(__file__).resolve().parent / "icons", ICONS, sizes=SIZES, ink=INK,
                          mark="OW")


if __name__ == "__main__":
    raise SystemExit(main())
