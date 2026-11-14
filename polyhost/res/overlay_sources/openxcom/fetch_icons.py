#!/usr/bin/env python3
"""Fetch + render the OpenXcom icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. The digits are a filled disc with the number cut out (centre on
visible enemy 1 to 10), and the two hands carry L and R. Quick save and quick load add a bolt. SOURCES.md
credits each. The ESC mark is the game's own icon (GPL-3.0-or-later), reduced
to 1 bit.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/openxcom/fetch_icons.py

program.png is kept when it already exists, so a hand edit survives a re-run.
Delete it to draw it again.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.devilutionx import fetch_icons as dx  # noqa: E402
from polyhost.res.overlay_sources.mindustry import fetch_icons as mindustry  # noqa: E402
from polyhost.res.overlay_sources.openmw import fetch_icons as openmw  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

ICONS = {
    # Battlescape: view and units
    "levelup": "mdi:stairs-up",
    "leveldown": "mdi:stairs-down",
    "centerunit": "fa:location-crosshairs",
    "prevunit": "mdi:account-arrow-left",
    "nextunit": "mdi:account-arrow-right",
    "deselect": "mdi:account-off",
    "minimap": "fa:map",
    "lighting": "fa:lightbulb",
    # Battlescape: the selected soldier
    "inventory": "gi:lorc/knapsack",
    "stats": "fa:id-card",
    "kneel": "fa:person-praying",
    "reload": "gi:delapouite/machine-gun-magazine",
    # Battlescape: time units and the turn
    "reservenone": "fa:ban",
    "reservesnap": "mdi:bullet",
    "reserveaimed": "fa:crosshairs",
    "reserveauto": "mdi:ammunition",
    "zerotus": "fa:battery-empty",
    "endturn": "fa:hourglass-end",
    "abort": "mdi:exit-run",
    # Inventory screen
    "savetemplate": "fa:file-export",
    "applytemplate": "fa:file-import",
    "clearinventory": "fa:trash-can",
    "autoequip": "fa:shirt",
    # Geoscape
    "bases": "fa:warehouse",
    "graphs": "fa:chart-line",
    "ufopaedia": "fa:book",
    "funding": "fa:sack-dollar",
    # Every screen
    "fps": "fa:gauge-high",
    "screenshot": "fa:camera",
}
# Parts of the composed icons.
PARTS = {"_floppy": "fa:floppy-disk", "_folder": "fa:folder-open", "_bolt": "fa:bolt",
         "_disc": "fa:circle", "_lefthand": "mdi:hand-back-left",
         "_righthand": "mdi:hand-back-right", "_kneel": "fa:person-praying", "_time": "fa:hourglass-half"}

# Key area of each icon, from openxcom.yaml; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"reservenone": (34, 40), "reservesnap": (34, 40), "reserveauto": (30, 40),
         "fps": (34, 40), "prevunit": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area.
INK = {"reservenone": (30, 30), "reserveaimed": (34, 34), "centerunit": (34, 34),
       "screenshot": (30, 30), "fps": (32, 28), "stats": (38, 30), "minimap": (38, 32),
       "zerotus": (40, 24), "lighting": (26, 36), "endturn": (26, 34),
       "savetemplate": (34, 34), "applytemplate": (34, 34), "clearinventory": (30, 34),
       "autoequip": (38, 32), "bases": (38, 30), "ufopaedia": (30, 34),
       "funding": (32, 34), "graphs": (36, 32), "reservesnap": (30, 36)}

ENEMIES = range(1, 11)    # the keys 1 to 9 and 0 (enemy 10)

# The ESC mark: the game's icon (an alien head over an X), 128 x 128.
MARK_URL = ("https://raw.githubusercontent.com/OpenXcom/OpenXcom/"
            "4a4bae5fa2e5a09282928e84943fc84b093e34ff/res/linux/icons/openxcom_128x128.png")
MARK_SIZE = 40
MARK_LUMA = 90            # opaque pixels lighter than this are lit (the eyes are darker)


def enemy_icons(out: Path) -> None:
    """enemy<N>.png: a filled disc with the digit of its key cut out (centre on
    visible enemy N; the 0 key is enemy 10)."""
    disc = dx._fit("_disc", out, (40, 40), (36, 36))
    for n in ENEMIES:
        cnc._save_mask(mindustry.numbered(disc, str(n % 10), 7), out / f"enemy{n}.png")
    print(f"  enemy1..{ENEMIES[-1]}.png  <- numbered disc")


def hand_icons(out: Path) -> None:
    """lefthand.png (Q) and righthand.png (E): the back of a left or a right
    hand, with L or R lit in the top-left corner of the 40 x 40 area."""
    for stem, letter in (("lefthand", "L"), ("righthand", "R")):
        c = dx._fit(f"_{stem}", out, (40, 40), (26, 40))
        g = zeroad._digit(letter, 15)
        c[:g.shape[0], :g.shape[1]] = g
        cnc._save_mask(c, out / f"{stem}.png")
    print("  lefthand.png, righthand.png  <- hand + L or R")


def reserve_kneel(out: Path) -> None:
    """reservekneel.png (J): the kneeling figure with a small hourglass in the
    bottom-right corner, 2 px clear of the figure."""
    import numpy as np
    c = np.zeros((40, 40), bool)
    c[:, :30] = dx._fit("_kneel", out, (30, 40), (30, 40))
    t = dx._fit("_time", out, (40, 40), (12, 17))
    cnc._save_mask((c & ~program_mark.dilate(t, 2)) | t, out / "reservekneel.png")
    print("  reservekneel.png  <- fa:person-praying + fa:hourglass-half")


def program(out: Path) -> None:
    """program.png: the game's icon, box-filtered to MARK_SIZE px. An opaque
    pixel lighter than MARK_LUMA is lit, so the alien's eyes stay dark."""
    import numpy as np
    from PIL import Image
    path = out / "program.png"
    if path.exists():
        print("  program.png  <- committed asset (left as-is)")
        return
    im = Image.open(io.BytesIO(cnc._get(MARK_URL))).convert("RGBA")
    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
    bg.alpha_composite(im)
    grey = bg.convert("L").resize((MARK_SIZE, MARK_SIZE), Image.BOX)
    cnc._save_mask(np.asarray(grey) > MARK_LUMA, path)
    print("  program.png  <- res/linux/icons/openxcom_128x128.png (OpenXcom, GPL-3.0-or-later)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    mindustry.flat_icons(out, ICONS, SIZES, INK)
    enemy_icons(out)
    hand_icons(out)
    reserve_kneel(out)
    openmw.bolt_icons(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
