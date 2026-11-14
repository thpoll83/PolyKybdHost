#!/usr/bin/env python3
"""Fetch + render the Widelands icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0) and
game-icons.net (CC BY 3.0), drawn with the functions of the Beyond All Reason
set. Drawn here: the landmarks (a pin with the number cut out) and the six game
speed keys (the forward arrows over the step). SOURCES.md credits each. The ESC
mark is the game's own logo (GPL-2.0-or-later), its W and L split by colour.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/widelands/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.beyond_all_reason import fetch_icons as bar  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.icon_fetch import _get  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Map display
    "buildhelp": "fa:trowel-bricks",
    "minimap": "fa:map",
    "census": "fa:tags",
    "statuslabels": "fa:bars-progress",
    "soldierlevels": "fa:medal",
    "buildings": "fa:building",
    "workareas": "fa:bullseye",
    # Statistics and windows
    "statsgeneral": "fa:chart-line",
    "statswares": "fa:chart-column",
    "statsbuildings": "fa:city",
    "stock": "fa:boxes-stacked",
    "statssoldiers": "gi:lorc/crossed-swords",
    "seafaring": "fa:ship",
    "objectives": "fa:list-check",
    "diplomacy": "gi:delapouite/shaking-hands",
    "messages": "fa:envelope",
    "encyclopedia": "fa:book-open",
    "pinnednote": "fa:thumbtack",
    "chat": "gi:delapouite/chat-bubble",
    # Navigation
    "starthq": "fa:house-flag",
    "quicknav": "fa:location-arrow",
    "locationnext": "fa:forward-step",
    "locationprev": "fa:backward-step",
    "zoomout": "fa:magnifying-glass-minus",
    "zoomreset": "fa:magnifying-glass",
    # Game and program
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "exit": "fa:power-off",
    "restart": "fa:rotate-right",
    "soundoptions": "fa:volume-high",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    "music": "fa:music",
    "tooltipmode": "fa:universal-access",
}

# The game speed keys (Page Up, Page Down; Shift and Ctrl change the step):
# {stem: the step drawn below the forward arrows}.
SPEED = "fa:forward"
SPEED_STEPS = {"speedup": "+1×", "speeddown": "−1×",
               "speedupslow": "+¼×", "speeddownslow": "−¼×",
               "speedupfast": "+10×", "speeddownfast": "−10×"}

# The landmarks (1 to 9 go to, Ctrl+1 to 9 set).
PIN = "fa:location-dot"
LANDMARKS = (1, 2, 3, 4, 5, 6, 7, 8, 9)

# Key area of each icon, from widelands.yaml; the default is 40 x 40. The F-key
# areas use the legend widths measured for Age of Empires II.
SIZES = {"encyclopedia": (34, 40), "tooltipmode": (34, 40), "pinnednote": (34, 40),
         "music": (34, 40), "screenshot": (30, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (32, 32), "load": (34, 34), "exit": (32, 32), "chat": (34, 34),
       "messages": (34, 34), "workareas": (34, 34), "zoomout": (32, 32),
       "zoomreset": (32, 32), "screenshot": (30, 30), "music": (30, 30),
       "tooltipmode": (32, 32), "pinnednote": (28, 34), "buildings": (30, 36),
       "soldierlevels": (30, 36), "fullscreen": (32, 32), "stock": (36, 34),
       "soundoptions": (38, 32), "minimap": (38, 32), "census": (36, 34)}

# The ESC mark: the game's logo at the pinned release.
LOGO_URL = ("https://raw.githubusercontent.com/widelands/widelands/v1.3.1/"
            "data/images/logos/wl-ico-128.png")
LOGO_SIZE = 40              # px, the whole key height
LOGO_SEAM = 1               # unlit px between the L and the W behind it
LOGO_THRESHOLD = 110        # grey level (0..255) from which a box-filtered pixel is lit


def speed_icons(out: Path) -> None:
    """One icon per row of SPEED_STEPS: the forward arrows in the top 40 x 22
    of a 40 x 40 area, and the step below them in DejaVu Sans Bold at the
    largest height up to 13 px at which it is at most 40 px wide."""
    import numpy as np
    arrows = bar._placed(out / "_speed.png", (40, 22), (34, 22))
    for stem, text in SPEED_STEPS.items():
        for height in range(13, 6, -1):
            g = zeroad._digit(text, height)
            if g.shape[1] <= 40:
                break
        canvas = np.zeros((40, 40), bool)
        canvas[:22] = arrows
        canvas[40 - g.shape[0]:, 40 - g.shape[1]:] = g
        cnc._save_mask(canvas, out / f"{stem}.png")
    print(f"  {', '.join(f'{s}.png' for s in SPEED_STEPS)}  <- {SPEED} + the step")


def program(out: Path) -> None:
    """program.png: the logo at LOGO_SIZE px, 1 bit. The logo is a green W
    behind a red L; as one silhouette the two letters merge. The letters are
    split by colour and the W is cleared LOGO_SEAM px around the L. A committed
    program.png is kept."""
    import numpy as np
    from PIL import Image
    if (out / "program.png").exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    a = np.asarray(Image.open(io.BytesIO(_get(LOGO_URL))).convert("RGBA")).astype(float)
    opaque = a[..., 3] > 140
    red = opaque & (a[..., 0] > a[..., 1] + 10)
    green = opaque & (a[..., 1] > a[..., 0] + 5)

    def small(m):
        im = Image.fromarray((m * 255).astype(np.uint8)).resize((LOGO_SIZE, LOGO_SIZE), Image.BOX)
        return np.asarray(im) > LOGO_THRESHOLD

    w, l = small(green), small(red)
    cnc._save_mask((w & ~program_mark.dilate(l, LOGO_SEAM)) | l, out / "program.png")
    print(f"  program.png  <- {LOGO_URL}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    parts = {"_pin": PIN, "_speed": SPEED}
    cnc.render({**ICONS, **parts}, out)
    bar.flat(ICONS, SIZES, INK, out)
    speed_icons(out)
    bar.numbered_pins(out / "_pin.png", LANDMARKS, "landmark", "landmarkset", out)
    for stem in parts:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
