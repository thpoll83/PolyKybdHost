#!/usr/bin/env python3
"""Fetch + render the osu! (lazer) icons (reproducible).

The key icons are flat 1-bit silhouettes, drawn by the helpers of the
StepMania set: Material Symbols (Apache-2.0) and Font Awesome Free (CC BY
4.0); SOURCES.md credits each. Z and X show K1 and K2 in a ring, drawn here.
The ESC mark is the game's name set in Varela Round (SIL OFL 1.1); the game's
logo is a trademark and its art is CC BY-NC 4.0, so neither is used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/osu/fetch_icons.py

Every icon and the ESC mark are drawn again on each run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.stepmania import fetch_icons as sm  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

# The ESC mark is set in Varela Round (SIL OFL 1.1).
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/varelaround/VarelaRound-Regular.ttf")
MARK_LINES = ("osu!",)

ICONS = {
    # During a song
    "smoke": "fa:smog",
    "leaderboard": "ms:leaderboard",
    "hud": "ms:visibility",
    "retry": "ms:replay",
    "quickexit": "ms:logout",
    "skip": "ms:fast_forward",
    "mousebuttons": "ms:mouse",
    # Replay
    "stepback": "ms:navigate_before",
    "stepfwd": "ms:navigate_next",
    "replaysettings": "ms:video_settings",
    # Song select
    "mods": "ms:tune",
    "random": "ms:shuffle",
    "prevrandom": "ms:history",
    "options": "ms:menu",
    "deselect": "ms:playlist_remove",
    "grouptoggle": "ms:unfold_more",
    "deletebeatmap": "ms:delete",
    # Music and volume
    "nexttrack": "ms:skip_next",
    "nowplaying": "ms:music_note",
    "mute": "ms:volume_off",
    "volup": "ms:volume_up",
    "voldown": "ms:volume_down",
    # Overlays
    "chat": "ms:chat",
    "social": "ms:groups",
    "toolbar": "ms:toolbar",
    "beatmaplisting": "ms:library_music",
    "settings": "ms:settings",
    "notifications": "ms:notifications",
    "profile": "ms:account_circle",
    "home": "ms:home",
    # Skins and input
    "skineditor": "ms:brush",
    "randomskin": "ms:casino",
    "resetinput": "ms:keyboard",
    # Window and frame rate
    "fullscreen": "ms:fullscreen",
    "screenshot": "ms:photo_camera",
    "framelimit": "ms:timer",
    "framestats": "ms:monitoring",
}
# Icons that get a sign: {file: (source file, sign)}. The source files are
# fetched, used and deleted.
BADGE_PARTS = {"_offset": "ms:schedule", "_speed": "ms:speed", "_scroll": "ms:swap_vert",
               "_meter": "ms:equalizer", "_skin": "ms:palette", "_group": "ms:folder"}
BADGED = {
    "offsetdown": ("_offset", "-"), "offsetup": ("_offset", "+"),
    "modspeeddown": ("_speed", "-"), "modspeedup": ("_speed", "+"),
    "scrollup": ("_scroll", "+"),
    "meterprev": ("_meter", "<"), "meternext": ("_meter", ">"),
    "skinprev": ("_skin", "<"), "skinnext": ("_skin", ">"),
    "groupprev": ("_group", "<"), "groupnext": ("_group", ">"),
}
# Alt+Enter and F11 both toggle full screen; F11 has the narrower F-key area.
SAME = {"fullscreen_f": ("fullscreen", (28, 28))}

# Key area of each icon, from osu.yaml; the default is 40 x 40.
SIZES = {"mods": sm.F_KEY, "random": sm.F_KEY, "prevrandom": sm.F_KEY, "options": sm.F_KEY,
         "scrollup": sm.F_KEY, "nexttrack": sm.F_KEY, "nowplaying": sm.F_KEY, "chat": sm.F_KEY,
         "social": sm.F_KEY, "mute": sm.F_KEY, "framelimit": sm.F_KEY,
         "mousebuttons": sm.F_KEY_WIDE, "fullscreen_f": sm.F_KEY_WIDE,
         "screenshot": sm.F_KEY_WIDE, "framestats": sm.F_KEY_WIDE}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {"smoke": (36, 34), "leaderboard": (34, 34), "hud": (38, 30), "retry": (32, 32),
       "quickexit": (32, 32), "skip": (34, 34), "mousebuttons": (26, 34),
       "stepback": (30, 30), "stepfwd": (30, 30), "replaysettings": (36, 36),
       "mods": (30, 30), "random": (30, 30), "prevrandom": (32, 32), "options": (30, 30),
       "deselect": (36, 36), "grouptoggle": (30, 34), "deletebeatmap": (30, 34),
       "nexttrack": (30, 30), "nowplaying": (28, 32), "mute": (32, 32),
       "volup": (36, 36), "voldown": (36, 36), "chat": (32, 32), "social": (34, 34),
       "toolbar": (34, 34), "beatmaplisting": (34, 34), "settings": (34, 34),
       "notifications": (32, 34), "profile": (34, 34), "home": (34, 34),
       "skineditor": (32, 32), "randomskin": (32, 32), "resetinput": (36, 30),
       "fullscreen": (32, 32), "screenshot": (30, 30), "framelimit": (30, 32),
       "framestats": (30, 30)}

KEY_RING = 36               # Z and X: the diameter of the ring, in px
KEY_TEXT = 12               # and the height of "K1" / "K2" inside it


def key_ring(text: str, path: Path) -> None:
    """A 40x40 icon: a 2 px ring KEY_RING across at the bottom right, with
    `text` (DejaVu Sans Bold, KEY_TEXT px high) in its centre. The game's key
    counter names the two buttons K1 and K2."""
    import numpy as np
    n = KEY_RING
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    d = np.hypot(yy - c, xx - c)
    ring = (d <= c + 0.2) & (d >= c - 2)
    g = zeroad._digit(text, KEY_TEXT)
    y0, x0 = (n - g.shape[0]) // 2, (n - g.shape[1]) // 2
    ring[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] |= g
    canvas = np.zeros((40, 40), bool)
    canvas[40 - n:, 40 - n:] = ring
    cnc._save_mask(canvas, path)
    print(f"  {path.name}  <- ring with {text}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    sm.build(ICONS, BADGE_PARTS, BADGED, SIZES, INK, out, same=SAME)
    key_ring("K1", out / "k1.png")
    key_ring("K2", out / "k2.png")
    sm.text_mark(MARK_LINES, MARK_FONT_URL, out / "program.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
