#!/usr/bin/env python3
"""Fetch + render the Rocket League icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The ESC
mark sets the wordmark ROCKET / LEAGUE in Archivo Black (SIL OFL 1.1), two
heavy lines as the logo has; Psyonix's logo art is not used.

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


def program(path: Path) -> None:
    """program.png: ROCKET over LEAGUE in Archivo Black. Left as it is when the PNG exists."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    im, d, P = game_set.mark_canvas()
    archivo = game_set.google_font(game_set.ARCHIVO_BLACK)
    game_set.fit_text(d, "ROCKET", (1, 2, 71, 19), archivo)
    game_set.fit_text(d, "LEAGUE", (1, 21, 71, 38), archivo)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- ROCKET LEAGUE wordmark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    program(out / "program.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
