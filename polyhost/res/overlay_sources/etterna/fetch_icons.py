#!/usr/bin/env python3
"""Fetch + render the Etterna icons (reproducible).

The key icons are flat 1-bit silhouettes, drawn by the helpers of the
StepMania set: Material Symbols (Apache-2.0), Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0); SOURCES.md credits each. The keys that Etterna
shares with StepMania use the same icons. The ESC mark is Etterna's own logo
(MIT, from the Etterna repository).

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/etterna/fetch_icons.py

The fetched icons are drawn again on every run. The ESC mark is the game's
logo file, so it is written only when its PNG is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.stepmania import fetch_icons as sm  # noqa: E402

# The StepMania icons of the keys that do the same in Etterna.
SHARED = ("start", "select", "operator", "reload", "reloadmetrics", "reloadscripts",
          "reloadoverlays", "debug", "fast", "mute", "revertsync", "autosync", "assist",
          "metronome", "autoplay", "screenshot", "screenshotraw", "fullscreen", "quit",
          "reloadsong")

ICONS = {
    **{stem: sm.ICONS[stem] for stem in SHARED},
    # The four columns of the default game type (dance, 4 keys)
    "colleft": "fa:circle-left",
    "coldown": "fa:circle-down",
    "colup": "fa:circle-up",
    "colright": "fa:circle-right",
    # During a song
    "restart": "ms:replay",
    # Song list
    "translit": "ms:translate",
    "favorite": "ms:star",
    "mirror": "ms:flip",
    "goal": "ms:flag",
    "newsongs": "ms:create_new_folder",
    "practice": "ms:fitness_center",
    "saveprofile": "ms:save",
    "newplaylist": "ms:playlist_add",
    "addtoplaylist": "ms:queue_music",
    "reloadpack": "ms:folder_open",
}
BADGE_PARTS = {stem: sm.BADGE_PARTS[stem] for stem in ("_offset", "_global")}
BADGED = {stem: sm.BADGED[stem] for stem in ("offsetdown", "offsetup", "globaldown", "globalup")}

# Key area of each icon, from etterna.yaml; the default is 40 x 40.
SIZES = {**{stem: size for stem, size in sm.SIZES.items() if stem in ICONS or stem in BADGED},
         "translit": sm.F_KEY}
# Solid or wide icons that read heavier than the rest: drawn in a smaller box at
# the bottom right of their key area.
INK = {**{stem: box for stem, box in sm.INK.items() if stem in ICONS},
       "colleft": (32, 32), "coldown": (32, 32), "colup": (32, 32), "colright": (32, 32),
       "restart": (32, 32), "translit": (32, 32), "favorite": (36, 36), "mirror": (34, 34),
       "goal": (30, 34), "newsongs": (36, 36), "practice": (36, 36), "saveprofile": (32, 32),
       "newplaylist": (36, 36), "addtoplaylist": (36, 36), "reloadpack": (36, 36)}

# The ESC mark: Etterna's logo, Docs/images/etterna-logo-dark.svg at release 0.75.1.
LOGO_URL = ("https://raw.githubusercontent.com/etternagame/etterna/"
            "v0.75.1/Docs/images/etterna-logo-dark.svg")
LOGO_H = 38                 # the logo's height on the 72x40 cell, in px
LOGO_SS = 8                 # the SVG is rendered LOGO_SS times larger and box-filtered
LOGO_THRESHOLD = 128        # grey level (0..255) from which a box-filtered pixel is lit


def program(out: Path) -> None:
    """program.png: Etterna's logo (the letter E and the corner cut off it),
    both shapes lit, LOGO_H px high in the centre of the 72x40 cell."""
    path = out / "program.png"
    if path.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    import io
    import cairosvg
    import numpy as np
    from PIL import Image
    png = cairosvg.svg2png(bytestring=icon_fetch._get(LOGO_URL),
                           output_width=1024, output_height=1024)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    big = alpha.resize((round(alpha.width * LOGO_H * LOGO_SS / alpha.height), LOGO_H * LOGO_SS),
                       Image.LANCZOS)
    w = round(big.width / LOGO_SS)
    logo = np.asarray(big.resize((w, LOGO_H), Image.BOX)) > LOGO_THRESHOLD
    canvas = np.zeros((40, 72), bool)
    y0, x0 = (40 - LOGO_H) // 2, (72 - w) // 2
    canvas[y0:y0 + LOGO_H, x0:x0 + w] = logo
    cnc._save_mask(canvas, path)
    print("  program.png  <- etterna-logo-dark.svg")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    sm.build(ICONS, BADGE_PARTS, BADGED, SIZES, INK, out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
