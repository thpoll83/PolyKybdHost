#!/usr/bin/env python3
"""Fetch + render the Hedgewars icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0, one icon). The weapon slots (F1
to F10), the timer keys (1 to 5) and the bounciness keys (Shift+1 to 5) have
their number drawn in. SOURCES.md credits each. The ESC mark is "Hedge" over
"wars" set in Lilita One (SIL OFL 1.1); the game's own art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/hedgewars/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.fheroes2.fetch_icons import _alpha_mask  # noqa: E402
from polyhost.res.overlay_sources.supertuxkart import fetch_icons as stk  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Movement
    "longjump": "gi:delapouite/jump-across",
    "highjump": "fa:angles-up",
    "switch": "fa:people-arrows",
    "switchback": "mdi:account-arrow-left",
    # Weapons
    "attack": "fa:bomb",
    "changetimer": "mdi:timer-plus",
    "changebounce": "mdi:basketball",
    # Camera
    "findhog": "mdi:account-search",
    # Chat
    "chat": "fa:comment",
    "clanchat": "fa:comments",
    "chathistory": "mdi:message-text-clock",
    # Game
    "pause": "fa:pause",
    "confirm": "fa:check",
    "closeengine": "fa:power-off",
    "voldown": "fa:volume-low",
    "volup": "fa:volume-high",
    "mute": "fa:volume-xmark",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    "mapimage": "fa:mountain-sun",
    "speedup": "fa:forward",
    "record": "fa:video",
    # Heads-up display
    "mission": "mdi:clipboard-text",
    "objectinfo": "fa:circle-info",
    "teambars": "fa:bars-progress",
    "hogtags": "mdi:tag-text",
    "tagtypes": "mdi:tag-multiple",
}
# Parts of the composed icons; removed after the run.
PARTS = {
    "_crosshair": "fa:crosshairs",
    "_up": "mdi:arrow-up-bold",
    "_down": "mdi:arrow-down-bold",
    "_walker": "fa:person-walking",
    "_ammo": "mdi:ammunition",
    "_stopwatch": "fa:stopwatch",
    "_ball": "mdi:basketball",
}

# Key area of each icon, from hedgewars.yaml; the default is 40 x 40.
SIZES: dict[str, tuple[int, int]] = {}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"pause": (28, 30), "chat": (36, 34), "screenshot": (36, 32), "record": (36, 30),
       "objectinfo": (34, 34), "attack": (36, 36), "closeengine": (34, 34),
       "confirm": (34, 34), "changebounce": (34, 34)}

SLOT_AREA = (30, 40)        # F1 to F10: one width for all ten
SLOTS = range(1, 11)
SLOT_DIGIT_PX = 13          # height of the slot number, lit in the top-left corner
TIMERS = range(1, 6)
TIMER_DIGIT_PX = 16         # height of the timer number, cut out of the stopwatch face
BOUNCE_DIGIT_PX = 14        # height of the bounciness number, lit in the top-left corner

# The ESC mark is set in Lilita One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/lilitaone/LilitaOne-Regular.ttf")
MARK_LINES = ("Hedge", "wars")
MARK_THRESHOLD = 110


def _corner(base, glyph, size=(40, 40)):
    """`base` in the bottom-right corner of a `size` (w, h) canvas and `glyph`
    lit in the top-left corner, cut out of `base` by a 2 px gap."""
    import numpy as np
    w, h = size
    canvas = np.zeros((h, w), bool)
    canvas[h - base.shape[0]:, w - base.shape[1]:] = base
    g = np.zeros((h, w), bool)
    g[0:glyph.shape[0], 0:glyph.shape[1]] = glyph
    return (canvas & ~program_mark.dilate(g, 2)) | g


def composed(out: Path) -> None:
    """aimup.png and aimdown.png: the crosshair with an arrow in the top-left
    corner. walkleft.png and walkright.png: the walker, mirrored for left."""
    import numpy as np
    cross = _alpha_mask(out / "_crosshair.png", (30, 30))
    for name, arrow in (("aimup", "_up"), ("aimdown", "_down")):
        cnc._save_mask(_corner(cross, _alpha_mask(out / f"{arrow}.png", (16, 18))),
                       out / f"{name}.png")
    walker = _alpha_mask(out / "_walker.png", (40, 40))
    canvas = np.zeros((40, 40), bool)
    canvas[40 - walker.shape[0]:, 40 - walker.shape[1]:] = walker
    cnc._save_mask(canvas, out / "walkright.png")
    canvas = np.zeros((40, 40), bool)
    canvas[40 - walker.shape[0]:, 40 - walker.shape[1]:] = walker[:, ::-1]
    cnc._save_mask(canvas, out / "walkleft.png")
    print("  aimup, aimdown, walkleft, walkright  <- composed")


def numbered(out: Path) -> None:
    """slot<N>.png (F1 to F10): the cartridges with N lit in the top-left
    corner. timer<N>.png (1 to 5): the stopwatch, its face filled, with N cut
    out of the face. bounce<N>.png (Shift+1 to 5): the ball with N lit in the
    top-left corner."""
    import numpy as np
    ammo = _alpha_mask(out / "_ammo.png", (SLOT_AREA[0], 24))
    for n in SLOTS:
        cnc._save_mask(_corner(ammo, zeroad._digit(str(n), SLOT_DIGIT_PX), SLOT_AREA),
                       out / f"slot{n}.png")
    watch = zeroad._fill_holes(np.pad(_alpha_mask(out / "_stopwatch.png", (38, 38)), 1))
    canvas = np.zeros((40, 40), bool)
    canvas[40 - watch.shape[0]:, 40 - watch.shape[1]:] = watch
    # The digit is centred on the face: the rows within 8 px of the widest row.
    rows = np.nonzero(canvas.sum(axis=1) >= canvas.sum(axis=1).max() - 8)[0]
    cols = np.nonzero(canvas[rows[0]:rows[-1] + 1].any(axis=0))[0]
    cy, cx = (rows[0] + rows[-1] + 1) // 2, (cols[0] + cols[-1] + 1) // 2
    for n in TIMERS:
        g = zeroad._digit(str(n), TIMER_DIGIT_PX)
        m = canvas.copy()
        y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
        m[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(m, out / f"timer{n}.png")
    ball = _alpha_mask(out / "_ball.png", (28, 28))
    for n in TIMERS:
        cnc._save_mask(_corner(ball, zeroad._digit(str(n), BOUNCE_DIGIT_PX)),
                       out / f"bounce{n}.png")
    print("  slot1..10, timer1..5, bounce1..5  <- numbered")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    stk.flat_icons(out, ICONS, SIZES, INK)
    composed(out)
    numbered(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    stk.text_mark(out / "program.png", MARK_LINES, FONT_URL, MARK_THRESHOLD, gap=1)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
