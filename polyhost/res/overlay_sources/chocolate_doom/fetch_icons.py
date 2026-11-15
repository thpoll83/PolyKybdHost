#!/usr/bin/env python3
"""Fetch + render the icons of the Chocolate Doom, Crispy Doom, DSDA-Doom and
Woof! sets (reproducible).

The four specs in this folder share one `icons/` directory. The key icons are
the flat 1-bit silhouettes of the GZDoom set (`../gzdoom/fetch_icons.py` holds
the catalogue and the drawing code); SOURCES.md credits each. No id Software
artwork is used.

ESC marks: Chocolate Doom, DSDA-Doom and Woof! use the port's own icon, cut to
1 bit. Crispy Doom's icon is the "D" of the Doom logo, so its mark is a
wordmark in Black Ops One (SIL OFL 1.1).

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/chocolate_doom/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.gzdoom import fetch_icons as gz  # noqa: E402

STEMS = (
    # Movement
    "forward", "back", "strafeleft", "straferight", "turnleft", "turnright", "reverse",
    "use", "autorun", "mouselook",
    # Weapons
    "fist", "pistol", "shotgun", "chaingun", "rocket", "plasma", "bfg", "chainsaw",
    "supershotgun", "weapontoggle",
    # Automap
    "map", "mapfollow", "mapgrid", "mapmark", "mapclear", "mapmaxzoom", "maprotate",
    "mapoverlay", "maptag",
    # Function keys
    "help", "save", "load", "volume", "detail", "hud", "quicksave", "endgame", "messages",
    "quickload", "quit", "gamma", "spy",
    # Screen, game, levels and demos
    "sizeup", "sizedown", "pause", "chat", "restart", "nextlevel", "prevlevel",
    "demoskip", "demoend",
)
# Key area of each icon, from the specs; the default is 40 x 40. F1 to F9 are
# 34 px wide and F10 to F12 30 px, as in the GZDoom set.
SIZES = {**{s: (34, 40) for s in ("help", "save", "load", "volume", "detail", "hud",
                                  "quicksave", "endgame", "messages", "quickload")},
         **{s: (30, 40) for s in ("quit", "gamma", "spy")}}

RAW = "https://raw.githubusercontent.com/"
# Each port's own icon at the release commit the keys were read from:
# (file, url, crop, grey level of the cut, light the dark pixels).
MARKS = (
    # Chocolate Doom 3.1.1: a chocolate bar with a "D". The dark wrapper is lit.
    ("program.png", RAW + "chocolate-doom/chocolate-doom/"
     "410d96855b5df5410ff591a90efeafa889119224/data/doom.png", None, 140, True),
    # DSDA-Doom v0.30.1: a goose. The light body is lit.
    ("program_dsda.png", RAW + "kraflab/dsda-doom/"
     "8ed581ad5c868b4dba1c39eb21d29e4ddbed9fad/prboom2/ICONS/dsda-doom.png", None, 90, False),
    # Woof! 16.0.0: a "D" beside a dog's head.
    ("program_woof.png", RAW + "fabiangreffrath/woof/"
     "4553f9a739d8979a69907c9dab384678902522fa/data/woof.png", None, 90, False),
)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    gz.build(out, STEMS, SIZES)
    for name, url, crop, cut, dark in MARKS:
        gz.own_icon_mark(out / name, url, crop, cut, dark)
    gz.wordmark(out / "program_crispy.png", ("Crispy", "Doom"))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
