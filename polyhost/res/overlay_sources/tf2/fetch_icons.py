#!/usr/bin/env python3
"""Fetch + render the Team Fortress 2 icons (reproducible).

Flat 1-bit silhouettes from game-icons.net (CC BY 3.0, credit per author in
SOURCES.md) and Material Symbols (Apache-2.0), drawn by `game_set.py`. The
voice menu and PDA keys get their number drawn in. The ESC mark sets the
wordmark TEAM / FORTRESS 2 in Anton (SIL OFL 1.1), with a round emblem after
TEAM as the logo has between its words; Valve's logo art is not used.

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


def program(path: Path) -> None:
    """program.png: TEAM over FORTRESS 2 in Anton, and the emblem."""
    im, d, P = game_set.mark_canvas()
    import math
    ss = game_set.MARK_SS
    anton = game_set.google_font(game_set.ANTON)
    game_set.fit_text(d, "TEAM", (1, 1, 46, 17), anton)
    game_set.fit_text(d, "FORTRESS 2", (1, 21, 71, 39), anton)
    # The emblem: a disc with a ring cut out, notched at the four points.
    cx, cy, r = 57, 9, 8

    def disc(k, fill):
        d.ellipse([(cx - r * k) * ss, (cy - r * k) * ss, (cx + r * k) * ss, (cy + r * k) * ss], fill=fill)
    disc(1, 255)
    disc(0.55, 0)
    disc(0.3, 255)
    for deg in (0, 90, 180, 270):
        t = math.radians(deg)
        d.line(P((cx + math.cos(t) * r * 0.35, cy + math.sin(t) * r * 0.35),
                 (cx + math.cos(t) * (r + 0.5), cy + math.sin(t) * (r + 0.5))), fill=0, width=int(1.2 * ss))
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- TEAM FORTRESS 2 wordmark")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    game_set.build(out, ICONS, sizes=SIZES, ink=INK, numbered=NUMBERED, mark=None)
    program(out / "program.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
