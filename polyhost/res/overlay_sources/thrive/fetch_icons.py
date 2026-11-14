#!/usr/bin/env python3
"""Fetch + render the Thrive icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0), Material
Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0, one icon). F5 and F9
(quick save, quick load) are the floppy disk and the open folder with a bolt
beside them. SOURCES.md credits each. The ESC mark is "Thrive" set in Righteous
(SIL OFL 1.1); the game's own logo art is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/thrive/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.fheroes2.fetch_icons import _alpha_mask  # noqa: E402
from polyhost.res.overlay_sources.hedgewars.fetch_icons import _corner  # noqa: E402
from polyhost.res.overlay_sources.supertuxkart import fetch_icons as stk  # noqa: E402

ICONS = {
    # Movement
    "forward": "mdi:arrow-up-bold",
    "backwards": "mdi:arrow-down-bold",
    "left": "mdi:arrow-left-bold",
    "right": "mdi:arrow-right-bold",
    "autoforward": "fa:angles-up",
    # Abilities
    "toxin": "fa:skull-crossbones",
    "slime": "gi:delapouite/slime",
    "engulf": "mdi:pac-man",
    "eject": "mdi:eject",
    "packcommands": "fa:bullhorn",
    "mucocyst": "fa:shield-halved",
    "siderophore": "mdi:magnet",
    "binding": "fa:link",
    "unbindall": "fa:link-slash",
    "unbinding": "mdi:link-variant-minus",
    "germinate": "fa:seedling",
    "reproduce": "mdi:circle-multiple",
    # Game
    "fastmode": "fa:forward-fast",
    "pause": "fa:pause",
    "help": "fa:circle-question",
    "hidehud": "mdi:eye-off",
    "fps": "mdi:counter",
    "metrics": "fa:chart-line",
    "debugpanel": "fa:bug",
    "console": "mdi:console",
    "fullscreen": "fa:expand",
    "screenshot": "fa:camera",
    # Editor
    "undo": "fa:rotate-left",
    "redo": "fa:rotate-right",
    "delete": "fa:trash",
}
# Parts of quicksave.png (F5) and quickload.png (F9); removed after the run.
PARTS = {"_floppy": "fa:floppy-disk", "_folder": "fa:folder-open", "_bolt": "fa:bolt"}

# Key area of each icon, from thrive.yaml; the default is 40 x 40.
FKEY = (34, 40)
SIZES = {"help": FKEY, "hidehud": FKEY, "fps": FKEY, "metrics": FKEY, "debugpanel": FKEY}
# Solid icons that read heavier than the outline ones: drawn in a smaller box.
INK = {"pause": (28, 30), "help": (32, 32), "screenshot": (36, 32), "delete": (32, 34),
       "mucocyst": (34, 36), "eject": (34, 34), "engulf": (36, 36), "toxin": (36, 36),
       "debugpanel": (32, 32), "fps": (32, 32)}

# The ESC mark is set in Righteous (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/righteous/Righteous-Regular.ttf")
MARK_LINES = ("Thrive",)
MARK_THRESHOLD = 110


def quick(out: Path) -> None:
    """quicksave.png (F5) and quickload.png (F9): the disk or the folder in the
    bottom-right corner with a bolt in the top-left corner, cut out by a 2 px
    gap."""
    bolt = _alpha_mask(out / "_bolt.png", (14, 20))
    for name, part, size in (("quicksave", "_floppy", FKEY), ("quickload", "_folder", (40, 40))):
        base = _alpha_mask(out / f"{part}.png", (size[0] - 8, 26))
        cnc._save_mask(_corner(base, bolt, size), out / f"{name}.png")
    print("  quicksave.png, quickload.png  <- composed")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    stk.flat_icons(out, ICONS, SIZES, INK)
    quick(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    stk.text_mark(out / "program.png", MARK_LINES, FONT_URL, MARK_THRESHOLD)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
