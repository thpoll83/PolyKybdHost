#!/usr/bin/env python3
"""Fetch + render the 0 A.D. icons (reproducible).

The key icons are flat 1-bit silhouettes from game-icons.net (CC BY 3.0) and
Font Awesome Free (CC BY 4.0), as in the Warcraft III and Age of Empires II
sets. The control groups are game-icons.net units, drawn once at full height,
with a plus for Ctrl (create) and a ringed plus for Shift (add), as in the
Warcraft III set. SOURCES.md credits each. The ESC mark is 0 A.D. set in
Cinzel Black (SIL OFL 1.1); the game's own art (CC BY-SA 3.0) is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/zeroad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import game_icons  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.warcraft3 import fetch_icons as wc3  # noqa: E402

ICONS = {
    # Game and dialogs
    "pause": "fa:pause",
    "summary": "fa:chart-column",
    "gamemenu": "fa:bars",
    "diplomacy": "gi:delapouite/shaking-hands",
    "barter": "fa:scale-balanced",
    "matchsettings": "fa:sliders",
    "tutorial": "fa:book-open",
    "lobby": "fa:earth-europe",
    "structree": "fa:sitemap",
    "civinfo": "gi:delapouite/greek-temple",
    "quicksave": "fa:floppy-disk",
    "quickload": "fa:folder-open",
    "screenshot": "fa:camera",
    "bigscreenshot": "fa:image",
    "mousegrab": "fa:computer-mouse",
    "console": "fa:terminal",
    "fullscreen": "fa:expand",
    # Overlays
    "fps": "fa:gauge-high",
    "realtime": "fa:clock",
    "elapsed": "fa:stopwatch",
    "hidegui": "fa:eye-slash",
    "devcommands": "fa:code",
    "diplocolors": "fa:palette",
    "attackrange": "fa:bullseye",
    "aurarange": "gi:lorc/aura",
    "healrange": "fa:kit-medical",
    "guarded": "fa:shield-heart",
    "guarding": "fa:user-shield",
    # Camera
    "resetcam": "fa:compass",
    "lastattack": "fa:triangle-exclamation",
    "birdseye": "fa:map",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "lookup": "fa:angles-up",
    "lookdown": "fa:angles-down",
    "scrollup": "fa:arrow-up",
    "scrolldown": "fa:arrow-down",
    "scrollleft": "fa:arrow-left",
    "scrollright": "fa:arrow-right",
    "jump": "fa:location-dot",
    # Selection
    "idlebuilder": "fa:helmet-safety",
    "idleworker": "gi:delapouite/farmer",
    "idlewarrior": "gi:lorc/crossed-swords",
    "idleunit": "fa:person-circle-question",
    "idleonly": "fa:hourglass-half",
    "woundedonly": "fa:user-injured",
    "civilonly": "fa:wheat-awn",
    # Orders
    "kill": "fa:skull",
    "stop": "fa:hand",
    "backtowork": "fa:person-digging",
    "unload": "fa:arrow-right-from-bracket",
    "guard": "fa:shield-halved",
    "patrol": "fa:route",
    "repair": "fa:hammer",
    "flare": "gi:delapouite/torch",
    "attack": "gi:lorc/broadsword",
    "attackunits": "gi:lorc/target-arrows",
    "buildccw": "fa:arrow-rotate-left",
    "buildcw": "fa:arrow-rotate-right",
    # Chat
    "chat": "gi:delapouite/chat-bubble",
    "teamchat": "gi:lorc/conversation",
    "privatechat": "fa:envelope",
}

# Bases of the speed keys (Ctrl+Shift increases, Ctrl+Alt decreases), drawn by
# speed_icons() with a plus or a minus.
SPEED_BASES = {
    "scroll": "fa:arrows-up-down-left-right",
    "rotate": "fa:rotate",
    "zoom": "fa:magnifying-glass",
}

# Control groups: one unit per digit, drawn once at full height.
GROUP_UNITS = {
    "1": "delapouite/spartan-helmet",
    "2": "lorc/bowman",
    "3": "delapouite/horse-head",
    "4": "delapouite/elephant",
    "5": "lorc/spartan",
    "6": "delapouite/trebuchet",
    "7": "delapouite/siege-tower",
    "8": "delapouite/trireme",
    "9": "delapouite/centurion-helmet",
    "0": "delapouite/roman-toga",
}

# Key area of each icon, from zeroad.yaml; the default is 40 x 40. The F-key
# areas use the legend widths measured for Age of Empires II.
SIZES = {"screenshot": (34, 40), "bigscreenshot": (34, 40), "mousegrab": (34, 40),
         "quicksave": (34, 40), "quickload": (34, 40), "jump": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"quicksave": (30, 30), "quickload": (30, 30), "chat": (34, 34),
       "zoomin": (30, 30), "zoomout": (30, 30), "screenshot": (28, 28),
       "bigscreenshot": (28, 28), "pause": (26, 30), "gamemenu": (30, 30),
       "kill": (32, 32), "stop": (32, 34), "console": (32, 32),
       "scrollup": (26, 32), "scrolldown": (26, 32), "scrollleft": (32, 26),
       "scrollright": (32, 26), "lookup": (28, 30), "lookdown": (28, 30),
       "fullscreen": (30, 30), "hidegui": (36, 30), "devcommands": (36, 30),
       "structree": (36, 30)}
# Insert and Delete in Warcraft III, Q and E here: a person with an arrow
# round their feet, drawn by warcraft3/fetch_icons.py's rotate_icons().
ROTATE_PERSON = "fa:street-view"

# The ESC mark is set in Cinzel (SIL OFL 1.1), its Black instance.
FONT_URL = wc3.FONT_URL
MARK_SS = 8                                     # supersampling factor for the ESC mark
MARK_THRESHOLD = 90                             # grey level (0..255) from which a pixel is lit


def _flat(src: Path, size, box):
    """The alpha of `src` as a 1-bit mask filling `box`, placed in the
    bottom-right corner of a `size` canvas."""
    import numpy as np
    from PIL import Image
    alpha = Image.open(src).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    m = np.asarray(alpha) > 150
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_flat(out / f"{stem}.png", size, INK.get(stem, size)), out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def _with_minus(mask, size=13, bar=3):
    """A minus sign in the lower-right corner, GROUP_SEAM px clear around it."""
    import numpy as np
    H, W = mask.shape
    p = np.zeros((H, W), bool)
    cy, cx = H - size // 2 - 1, W - size // 2 - 1
    p[cy - bar // 2:cy + bar // 2 + 1, cx - size // 2:cx + size // 2 + 1] = True
    return (mask & ~program_mark.dilate(p, aoe2.GROUP_SEAM)) | p


def jump_set(out: Path) -> None:
    """jumpset.png (Ctrl+F5 to F8: set a camera position): the jump pin with
    the Ctrl plus."""
    pin = _flat(out / "_jump.png", (34, 40), (24, 32))
    cnc._save_mask(aoe2._with_plus(pin), out / "jumpset.png")
    print("  jumpset.png  <- fa:location-dot + a plus")


def speed_icons(out: Path) -> None:
    """<base>fast.png and <base>slow.png: the base icon in the top-left 30 x 30
    of the cell area with a plus (faster) or a minus (slower) in the corner."""
    import numpy as np
    for base in SPEED_BASES:
        m = _flat(out / f"_{base}.png", (40, 40), (30, 30))
        shifted = np.zeros_like(m)
        shifted[:34, :34] = m[6:, 6:]                # the base moved to the top-left
        cnc._save_mask(aoe2._with_plus(shifted), out / f"{base}fast.png")
        cnc._save_mask(_with_minus(shifted), out / f"{base}slow.png")
        print(f"  {base}fast.png, {base}slow.png  <- {SPEED_BASES[base]} + a plus / a minus")


def groups(out: Path) -> None:
    """group<N>.png (select), groupnew<N>.png (Ctrl: create) and groupadd<N>.png
    (Shift: add)."""
    for digit in GROUP_UNITS:
        g = wc3._single(out / f"_unit{digit}.png")
        aoe2._save_cell(g, out / f"group{digit}.png")
        aoe2._save_cell(aoe2._with_plus(g), out / f"groupnew{digit}.png")
        aoe2._save_cell(wc3._with_ring_plus(g), out / f"groupadd{digit}.png")
        print(f"  group{digit}.png, groupnew{digit}.png, groupadd{digit}.png  <- _unit{digit}.png")


def program(out: Path) -> None:
    """program.png: 0 A.D. at the largest size that fits 70 x 38 px, centred on
    the whole 72x40 cell. Drawn at MARK_SS times the size and box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h, ss = program_mark.W, program_mark.H, MARK_SS
    text = "0 A.D."
    for px in range(60 * ss, 8 * ss, -ss):
        font = wc3._mark_font(px)
        box = font.getbbox(text)
        if box[2] - box[0] <= (w - 2) * ss and box[3] - box[1] <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).text(((w * ss - (box[2] - box[0])) // 2 - box[0],
                             (h * ss - (box[3] - box[1])) // 2 - box[1]),
                            text, font=font, fill=255)
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- 0 A.D. (Cinzel Black, {px // ss} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    parts = {"_person": ROTATE_PERSON, "_jump": ICONS["jump"],
             **{f"_{b}": s for b, s in SPEED_BASES.items()}}
    cnc.render({**ICONS, **parts}, out)
    game_icons.render({f"_unit{d}": n for d, n in GROUP_UNITS.items()}, out, render_px=256)
    flat_icons(out)
    jump_set(out)
    speed_icons(out)
    groups(out)
    wc3.rotate_icons(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
