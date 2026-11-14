#!/usr/bin/env python3
"""Fetch + render the Quake source port icons (reproducible).

One set for Ironwail, vkQuake and QuakeSpasm. The key icons are flat 1-bit
silhouettes from game-icons.net (CC BY 3.0), Font Awesome Free (CC BY 4.0) and
Material Design Icons (Apache-2.0); `../gzdoom/fetch_icons.py` holds the
catalogue and the drawing code, and SOURCES.md credits each icon. The ESC mark
is "Quake" set in New Rocker (SIL OFL 1.1). No id Software artwork or logo is
used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/quake/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.devilutionx import fetch_icons as devx  # noqa: E402
from polyhost.res.overlay_sources.gzdoom import fetch_icons as gz  # noqa: E402

STEMS = (
    # Movement
    "forward", "back", "strafeleft", "straferight", "turnleft", "turnright", "jump",
    "swimup", "swimdown", "lookup", "lookdown", "centerview", "mouselook", "keylook",
    # Weapons: axe, shotgun, double-barrelled shotgun, nailgun, super nailgun
    # (the minigun), grenade launcher, rocket launcher, thunderbolt
    "axe", "shotgun", "supershotgun", "nailgun", "chaingun", "grenade", "rocket",
    "thunderbolt", "nextweapon",
    # Function keys
    "help", "save", "load", "options", "multiplayer", "quicksave", "quickload", "quit",
    "zoom", "screenshot",
    # Screen and game
    "scores", "sizeup", "sizedown", "pause", "chat", "console",
)
# Key area of each icon, from quake.yaml; the default is 40 x 40. F1 to F9 are
# 34 px wide and F10 to F12 30 px, as in the GZDoom set.
SIZES = {**{s: (34, 40) for s in ("help", "save", "load", "options", "multiplayer",
                                  "quicksave", "quickload")},
         **{s: (30, 40) for s in ("quit", "zoom", "screenshot")}}

# The ESC mark is set in New Rocker (SIL OFL 1.1), as the DevilutionX set's.
FONT_URL = devx.FONT_URL
MARK_THRESHOLD = 110        # grey level (0..255) from which a mark pixel is lit


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    gz.build(out, STEMS, SIZES)
    gz.wordmark(out / "program.png", ("Quake",), FONT_URL, MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
