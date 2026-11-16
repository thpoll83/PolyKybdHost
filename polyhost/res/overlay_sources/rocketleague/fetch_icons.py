#!/usr/bin/env python3
"""Fetch + render the Rocket League icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark is RL in Bebas Neue (SIL OFL 1.1); Psyonix's logo art is not used.

    PYTHONPATH=. python polyhost/res/overlay_sources/rocketleague/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_set  # noqa: E402

ICONS = {
    # Car
    "rollleft": "ms:rotate_90_degrees_ccw",
    "rollright": "ms:rotate_90_degrees_cw",
    "ballcam": "gi:delapouite/soccer-ball",
    "item": "ms:offline_bolt",
    "reset": "ms:replay",
    # Communication
    "src_quickchat": "ms:sms",          # only drawn with its number
    "allchat": "ms:public",
    "teamchat": "ms:chat",
    "partychat": "gi:delapouite/three-friends",
    "pushtotalk": "ms:mic",
    # Menus
    "scoreboard": "ms:scoreboard",
    "nexttrack": "ms:skip_next",
    "graphs": "ms:monitoring",
}

SIZES = {"graphs": (34, 40)}
INK = {"teamchat": (34, 34), "allchat": (34, 34), "scoreboard": (40, 34),
       "nexttrack": (32, 32)}
NUMBERED = {f"quickchat{n}": ("src_quickchat", str(n), (28, 28)) for n in range(1, 5)}


def main() -> int:
    return game_set.build(Path(__file__).resolve().parent / "icons", ICONS, sizes=SIZES, ink=INK,
                          numbered=NUMBERED, mark="RL")


if __name__ == "__main__":
    raise SystemExit(main())
