#!/usr/bin/env python3
"""Fetch + render the Oolite icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and Material Design Icons (Apache-2.0), as in the
Endless Sky set. Keys that step forwards or backwards through a list show the
list's icon with an arrow above it. SOURCES.md credits each icon. The ESC mark
is "Oolite" set in Righteous (SIL OFL 1.1).

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/oolite/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.endless_sky import fetch_icons as endless_sky  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Flying
    "rollleft": "fa:rotate-left",
    "rollright": "fa:rotate-right",
    "pitchforward": "fa:angles-down",
    "pitchback": "fa:angles-up",
    "yawleft": "fa:arrow-left",
    "yawright": "fa:arrow-right",
    "speedup": "mdi:speedometer",
    "speeddown": "mdi:speedometer-slow",
    "injectfuel": "fa:fire",
    "jumpdrive": "fa:forward-fast",
    "hyperspace": "gi:lorc/vortex",
    "galactic": "gi:lorc/star-swirl",
    "autopilot": "fa:robot",
    "fastdock": "fa:plane-arrival",
    "clearance": "mdi:airport",
    "mouseroll": "fa:computer-mouse",
    # Weapons and equipment
    "lasers": "gi:lorc/ray-gun",
    "weaponsonline": "fa:toggle-on",
    "missile": "gi:lorc/rocket",
    "nextmissile": "fa:repeat",
    "targetmissile": "fa:location-crosshairs",
    "unarmmissile": "mdi:crosshairs-off",
    "targetincoming": "fa:triangle-exclamation",
    "ident": "fa:tag",
    "ecm": "fa:tower-broadcast",
    "activate": "fa:power-off",
    "equipmode": "fa:sliders",
    "dumpcargo": "fa:arrow-up-from-bracket",
    "rotatecargo": "fa:boxes-stacked",
    # Views
    "viewforward": "mdi:arrow-up-bold-box-outline",
    "viewaft": "mdi:arrow-down-bold-box-outline",
    "viewport": "mdi:arrow-left-bold-box-outline",
    "viewstarboard": "mdi:arrow-right-bold-box-outline",
    "customview": "fa:video",
    "fovwider": "mdi:angle-obtuse",
    "fovnarrower": "mdi:angle-acute",
    "scannerzoom": "fa:magnifying-glass-plus",
    "scannerunzoom": "fa:magnifying-glass-minus",
    "hud": "mdi:monitor-dashboard",
    "bloom": "fa:sun",
    # Screens
    "launch": "fa:plane-departure",
    "options": "fa:gear",
    "equipship": "fa:wrench",
    "interfaces": "fa:list",
    "status": "fa:clipboard-list",
    "charts": "fa:map",
    "systemdata": "gi:lorc/ringed-planet",
    "market": "fa:scale-balanced",
    "commslog": "fa:comments",
    # Game
    "pause": "fa:pause",
    "snapshot": "fa:camera",
    "fps": "fa:gauge-high",
}
# The same icon at the narrower area of an F key: {file stem: icon stem}.
F_COPIES = {"fstatus": "status", "fcharts": "charts", "fsystemdata": "systemdata",
            "fmarket": "market"}

# Icons drawn with an arrow above them by stepped(): {file stem: (part, arrow)}.
STEPPED = {
    "targetnext": ("_target", "_right"), "targetprev": ("_target", "_left"),
    "compassnext": ("_compass", "_right"), "compassprev": ("_compass", "_left"),
    "mfdcyclenext": ("_display", "_right"), "mfdcycleprev": ("_display", "_left"),
    "mfdswitchnext": ("_columns", "_right"), "mfdswitchprev": ("_columns", "_left"),
    "primenext": ("_plug", "_right"), "primeprev": ("_plug", "_left"),
    "navnext": ("_route", "_right"), "navprev": ("_route", "_left"),
    "mouseyaw": ("_mouse", "_leftright"),
}
# Fast equipment activation: the bolt with the slot letter, drawn by lettered().
LETTERED = {"fasta": "A", "fastb": "B"}
PARTS = {"_target": "mdi:target", "_compass": "fa:compass", "_display": "fa:display",
         "_columns": "fa:table-columns", "_plug": "fa:plug", "_route": "fa:route",
         "_mouse": "fa:computer-mouse", "_bolt": "fa:bolt",
         "_right": "fa:right-long", "_left": "fa:left-long", "_leftright": "fa:left-right"}
STEP_ICON = (40, 26)        # box of the list's icon, at the bottom of the key area
STEP_ARROW = (18, 12)       # box of the arrow, in the top-right corner
LETTER_PX = 14              # height of the slot letter, in the top-right corner
LETTER_BOLT = (26, 32)      # box of the bolt, at the bottom left of the key area

# Key area of each icon, from oolite.yaml; the default is 40 x 40. The widths
# are the ones the AoE2 set measured to keep the F-key legends whole.
SIZES = {"launch": (34, 40), "options": (34, 40), "equipship": (34, 40), "interfaces": (30, 40),
         "fstatus": (34, 40), "fcharts": (34, 40), "fsystemdata": (34, 40), "fmarket": (34, 40),
         "bloom": (34, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"charts": (34, 34), "status": (34, 36), "pause": (30, 32), "mouseroll": (34, 34),
       "injectfuel": (34, 34), "ident": (34, 34), "targetincoming": (36, 34),
       "customview": (36, 34), "weaponsonline": (38, 30), "yawleft": (32, 32),
       "yawright": (32, 32), "fcharts": (30, 30), "fstatus": (30, 34), "options": (32, 32),
       "interfaces": (28, 28), "equipship": (32, 32), "jumpdrive": (36, 30)}

# The ESC mark is set in Righteous (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/righteous/Righteous-Regular.ttf")
MARK_TEXT = "Oolite"
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 90         # grey level (0..255) from which a box-filtered pixel is lit


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area. The F_COPIES are drawn from the same
    source at their own area."""
    import numpy as np
    drawn = {}
    for stem, source in [*F_COPIES.items(), *((s, s) for s in ICONS)]:
        size = SIZES.get(stem, (40, 40))
        m = endless_sky._alpha_mask(out / f"{source}.png", INK.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        drawn[stem] = canvas
    for stem, canvas in drawn.items():
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(drawn)} key icons drawn flat")


def stepped(out: Path) -> None:
    """The STEPPED icons: the part at the bottom of a 40x40 area with the arrow
    in the top-right corner."""
    import numpy as np
    w = h = 40
    for stem, (part, arrow) in STEPPED.items():
        m = endless_sky._alpha_mask(out / f"{part}.png", STEP_ICON)
        a = endless_sky._alpha_mask(out / f"{arrow}.png", STEP_ARROW)
        canvas = np.zeros((h, w), bool)
        canvas[h - m.shape[0]:, w - m.shape[1]:] = m
        canvas[0:a.shape[0], w - a.shape[1]:] = a
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(STEPPED)} icons with an arrow")


def lettered(out: Path) -> None:
    """fasta.png and fastb.png: the bolt at the bottom left of a 40x40 area
    with the slot letter in the top-right corner."""
    import numpy as np
    w = h = 40
    bolt = endless_sky._alpha_mask(out / "_bolt.png", LETTER_BOLT)
    for stem, letter in LETTERED.items():
        g = zeroad._digit(letter, LETTER_PX)
        canvas = np.zeros((h, w), bool)
        canvas[h - bolt.shape[0]:, 0:bolt.shape[1]] = bolt
        canvas[0:g.shape[0], w - g.shape[1]:] = g
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {', '.join(f'{s}.png' for s in LETTERED)}  <- bolt with a letter")


def program(out: Path) -> None:
    """program.png: MARK_TEXT at the largest size at which it fits 70 px wide
    and 38 px high, centred on the whole 72x40 cell. Drawn at MARK_SS times the
    size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    path = str(cnc._font(FONT_URL))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        box = font.getbbox(MARK_TEXT)
        if box[2] - box[0] <= (w - 2) * ss and box[3] - box[1] <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0],
                             (h * ss - (box[3] - box[1])) // 2 - box[1]),
                            MARK_TEXT, font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- {MARK_TEXT} (Righteous, {px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    stepped(out)
    lettered(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
