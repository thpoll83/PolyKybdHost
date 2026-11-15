#!/usr/bin/env python3
"""Fetch + render the icons of the two Caesar III engines, Julius and Augustus
(reproducible).

Both sets use one icons/ folder: Augustus has every default hotkey of Julius
and four more. The key icons are flat 1-bit silhouettes from Font Awesome Free
(CC BY 4.0), Material Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0).
Composed here: the map bookmarks (a numbered pin, with a plus for "set", drawn
by the 0 A.D. set), the three window sizes (a window with its width above it)
and the minimap screenshot (the camera with a map above it). SOURCES.md credits
each. The ESC marks are a laurel wreath (game-icons.net) over the engine's name
set in Cinzel Decorative (SIL OFL 1.1); the engines' own icons are not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/caesar3/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.openttd import fetch_icons as ottd  # noqa: E402
from polyhost.res.overlay_sources.simutrans import fetch_icons as simu  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

# Drawn flat at their key area (SIZES, default 40 x 40).
ICONS = {
    # Game
    "pause": "fa:pause",
    "slower": "fa:backward",
    "faster": "fa:forward",
    "load": "fa:folder-open",
    "save": "fa:floppy-disk",
    # City view
    "overlay": "fa:layer-group",
    "legion": "gi:delapouite/centurion-helmet",
    "rotateleft": "fa:rotate-left",
    "rotateright": "fa:rotate-right",
    # Advisors (1 to 0, - and =)
    "labor": "fa:person-digging",
    "military": "gi:lorc/crossed-swords",
    "imperial": "gi:lorc/laurel-crown",
    "ratings": "fa:ranking-star",
    "trade": "fa:scale-balanced",
    "population": "fa:users",
    "health": "fa:staff-snake",
    "education": "fa:scroll",
    "entertainment": "fa:masks-theater",
    "religion": "gi:delapouite/greek-temple",
    "financial": "fa:coins",
    "chief": "gi:delapouite/caesar",
    # Overlays
    "water": "fa:droplet",
    "fire": "fa:fire",
    "damage": "fa:house-crack",
    "crime": "fa:handcuffs",
    "problems": "fa:triangle-exclamation",
    # Window
    "centerwindow": "fa:arrows-to-dot",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    "cityscreenshot": "fa:panorama",
    # Augustus only
    "rotatebuilding": "mdi:rotate-3d-variant",
    "clone": "fa:clone",
    "mothball": "fa:store-slash",
}

# Shapes that only feed the composed icons below. _jump is the name the 0 A.D.
# set's jump_pins() reads.
PARTS = {
    "_jump": zeroad.JUMP_PIN,
    "_window": "fa:window-maximize",
    "_camera": "fa:camera",
    "_map": "fa:map",
    "_wreath": "gi:lorc/laurels",          # above the name in the ESC marks
}

# Key area of each icon, from julius.yaml and augustus.yaml; the default is
# 40 x 40. F1 to F9 use 34 px, the width of the 0 A.D. set's F-key icons.
SIZES = {"centerwindow": (34, 40)}
# Icons used on a second key with a narrower area: stem -> (source stem, area, ink box).
NARROW = {"fullscreen_f6": ("fullscreen", (34, 40), (30, 30))}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"pause": (26, 30), "slower": (34, 26), "faster": (34, 26), "save": (34, 34),
       "load": (34, 34), "centerwindow": (30, 30), "fullscreen": (32, 32),
       "screenshot": (32, 30), "cityscreenshot": (36, 30), "rotateleft": (32, 32),
       "rotateright": (32, 32), "water": (28, 36), "problems": (36, 34),
       "overlay": (36, 36), "clone": (32, 32), "education": (34, 34)}

# F7, F8, F9: the window width each key sets.
WINDOW_SIZES = {"resize640": "640", "resize800": "800", "resize1024": "1024"}

# The ESC marks are set in Cinzel Decorative Black (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzeldecorative/CinzelDecorative-Black.ttf")
MARKS = {"program_julius": "Julius", "program_augustus": "Augustus"}
MARK_GAP = 2                # unlit rows between the wreath and the name
MARK_SS = 8                 # supersampling factor for the name
MARK_THRESHOLD = 90         # grey level (0..255) from which a box-filtered name pixel is lit


def window_sizes(out: Path) -> None:
    """resize640.png, resize800.png, resize1024.png (F7, F8, F9): a window at
    the bottom right of the 34 x 40 area, its width in px above it."""
    import numpy as np
    window = ottd._corner(ottd._fit(out / "_window.png", (30, 24)), (34, 40))
    for stem, text in WINDOW_SIZES.items():
        badge = ottd._badge_text(text)
        h, w = badge.shape
        m = window.copy()
        canvas = np.zeros_like(m)
        canvas[2:2 + h, 34 - w:] = badge
        cnc._save_mask(m | canvas, out / f"{stem}.png")
    print("  resize640.png, resize800.png, resize1024.png  <- fa:window-maximize + the width")


def minimap_screenshot(out: Path) -> None:
    """minimapscreenshot.png (Shift+F12, Augustus): the camera with a map above
    it, laid out like the OpenTTD set's zoomed screenshots."""
    m = ottd._corner(ottd._fit(out / "_camera.png", (28, 21)), (40, 40))
    badge = ottd._fit(out / "_map.png", (24, 17))
    h, w = badge.shape
    x = 40 - 14 - w // 2                      # centred over the camera
    m[0:h, x:x + w] |= badge
    cnc._save_mask(m, out / "minimapscreenshot.png")
    print("  minimapscreenshot.png  <- fa:camera + fa:map")


def _name(text: str):
    """`text` in the mark's font at the largest size that fits 70 px wide, as
    a cropped 1-bit mask."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ss, path = MARK_SS, str(cnc._font(FONT_URL))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        left, top, right, bottom = font.getbbox(text)
        if right - left <= 70 * ss:
            break
    im = Image.new("L", ((right - left) // ss * ss + 2 * ss, (bottom - top) // ss * ss + 2 * ss), 0)
    ImageDraw.Draw(im).text((ss - left, ss - top), text, font=font, fill=255)
    m = np.asarray(im.resize((im.width // ss, im.height // ss), Image.BOX)) > MARK_THRESHOLD
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def program(out: Path, stem: str, text: str) -> None:
    """<stem>.png: the engine's name along the bottom of the 72x40 cell, a
    laurel wreath centred in the rows above it."""
    import numpy as np
    w, h = 72, 40
    name = _name(text)
    nh, nw = name.shape
    wreath = ottd._fit(out / "_wreath.png", (w, h - nh - MARK_GAP))
    wh, ww = wreath.shape
    canvas = np.zeros((h, w), bool)
    canvas[0:wh, (w - ww) // 2:(w - ww) // 2 + ww] = wreath
    canvas[h - nh:, (w - nw) // 2:(w - nw) // 2 + nw] = name
    cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {stem}.png  <- gi:lorc/laurels + {text} (Cinzel Decorative Black)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    simu.flat_icons(out, ICONS, SIZES, INK, NARROW)
    zeroad.jump_pins(out)
    window_sizes(out)
    minimap_screenshot(out)
    for stem, text in MARKS.items():
        program(out, stem, text)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
