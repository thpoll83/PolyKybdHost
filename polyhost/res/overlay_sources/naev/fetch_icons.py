#!/usr/bin/env python3
"""Fetch + render the Naev icons (reproducible).

The key icons are flat silhouettes from game-icons.net (CC BY 3.0), Font
Awesome Free (CC BY 4.0) and Material Design Icons (Apache-2.0), as in the
Endless Sky set. The weapon set keys (0 to 9) are a ray gun with the set number
above it. SOURCES.md credits each icon. The ESC mark is "NAEV" set in Quantico
Bold (SIL OFL 1.1); the game's own logo is CC BY-SA 4.0 and is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/naev/fetch_icons.py
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
    "accel": "fa:rocket",
    "turnleft": "fa:rotate-left",
    "turnright": "fa:rotate-right",
    "reverse": "fa:arrow-turn-down",
    "face": "fa:location-arrow",
    "stealth": "fa:user-secret",
    "mousefly": "fa:computer-mouse",
    "cooldown": "fa:snowflake",
    # Weapons
    "primary": "gi:lorc/ray-gun",
    "secondary": "gi:lorc/rocket",
    # Targets
    "targetnearest": "mdi:target",
    "targethostile": "mdi:skull-scan",
    "targetclear": "mdi:crosshairs-off",
    "targetnext": "fa:forward-step",
    "targetprev": "fa:backward-step",
    # Escorts
    "escortattack": "gi:lorc/crossed-swords",
    "escorthold": "fa:anchor",
    "escortreturn": "fa:house",
    "escortclear": "fa:eraser",
    # Navigation
    "targetspob": "gi:lorc/ringed-planet",
    "approach": "fa:plane-arrival",
    "targetjump": "gi:delapouite/star-gate",
    "jump": "gi:lorc/vortex",
    "autonav": "fa:route",
    "starmap": "fa:map",
    "overlaymap": "fa:map-location-dot",
    # Communication
    "hail": "fa:comments",
    "autohail": "fa:phone-volume",
    "scan": "gi:lorc/radar-sweep",
    "logup": "fa:angles-up",
    "logdown": "fa:angles-down",
    # Game
    "info": "fa:circle-info",
    "pause": "fa:pause",
    "speed": "fa:forward",
    "screenshot": "fa:camera",
    "console": "fa:terminal",
}
# Part of the weapon set icons, drawn by weapon_sets() and removed afterwards.
SET_PARTS = {"_gun": "gi:lorc/ray-gun"}
SETS = "1234567890"
SET_GUN = (40, 24)          # box of the ray gun, at the bottom of the key area
SET_DIGIT_PX = 14           # height of the set number, in the top-right corner

# Key area of each icon, from naev.yaml; the default is 40 x 40. The widths are
# the ones the AoE2 set measured to keep the F-key legends whole.
SIZES = {"console": (34, 40), "screenshot": (21, 40)}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"starmap": (34, 34), "overlaymap": (34, 34), "info": (32, 32), "pause": (30, 32),
       "mousefly": (34, 34), "escortreturn": (36, 34), "escortclear": (36, 34),
       "stealth": (34, 36), "face": (34, 34), "targetnext": (30, 30), "targetprev": (30, 30)}

# The ESC mark is set in Quantico Bold (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/quantico/Quantico-Bold.ttf")
MARK_TEXT = "NAEV"
MARK_SS = 8                 # supersampling factor for the ESC mark
MARK_THRESHOLD = 90         # grey level (0..255) from which a box-filtered pixel is lit


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in INK fill a smaller box in the
    bottom-right corner of that area."""
    import numpy as np
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        m = endless_sky._alpha_mask(out / f"{stem}.png", INK.get(stem, size))
        canvas = np.zeros((size[1], size[0]), bool)
        canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {len(ICONS)} key icons drawn flat")


def weapon_sets(out: Path) -> None:
    """weapset<N>.png: the ray gun at the bottom of a 40x40 area with N in the
    top-right corner."""
    import numpy as np
    w = h = 40
    gun = endless_sky._alpha_mask(out / "_gun.png", SET_GUN)
    base = np.zeros((h, w), bool)
    base[h - gun.shape[0]:, w - gun.shape[1]:] = gun
    for n in SETS:
        g = zeroad._digit(n, SET_DIGIT_PX)
        m = base.copy()
        m[0:g.shape[0], w - g.shape[1]:] |= g
        cnc._save_mask(m, out / f"weapset{n}.png")
    print(f"  weapset{SETS[0]}..{SETS[-1]}.png  <- numbered")


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
    print(f"  program.png  <- {MARK_TEXT} (Quantico Bold, {px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **SET_PARTS}, out)
    flat_icons(out)
    weapon_sets(out)
    for stem in SET_PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
