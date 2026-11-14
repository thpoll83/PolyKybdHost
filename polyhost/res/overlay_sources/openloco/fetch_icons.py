#!/usr/bin/env python3
"""Fetch + render the OpenLoco icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0),
Material Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0), with the
same sources as the OpenRCT2 and OpenTTD sets for the same actions. A few are
composed here from those shapes: the see-through toggles (the shape as an
outline), the height marks (a ruler beside the shape), the direction arrows
(an arrow over the track), Build new vehicles (the vehicle list's train with a
plus), Build tracks (the track turned upright) and the station list (a train
under a roof, from the OpenTTD set). SOURCES.md credits each. The ESC mark is
"Open" over "Loco" set in Archivo Black (SIL OFL 1.1). The game's own logo
(MIT) does not read at 40 px and 1 bit, so it is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/openloco/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.openttd import fetch_icons as ottd  # noqa: E402
from polyhost.res.overlay_sources.simutrans import fetch_icons as simu  # noqa: E402

# Drawn flat at their key area (SIZES, default 40 x 40).
ICONS = {
    # Construction
    "land": "fa:mountain",
    "water": "fa:water",
    "trees": "fa:seedling",
    "bulldoze": "mdi:bulldozer",
    "buildroads": "fa:road",
    "airports": "fa:plane-departure",
    "ports": "fa:anchor",
    "rotateobject": "mdi:rotate-3d-variant",
    # Lists and windows
    "vehicles": "fa:train",
    "towns": "fa:city",
    "industries": "fa:industry",
    "companies": "fa:building",
    "company": "fa:id-card",
    "map": "fa:map",
    "finances": "fa:sack-dollar",
    "announcements": "fa:envelope",
    "lastannouncement": "fa:newspaper",
    "chat": "fa:comment",
    "debug": "fa:bug",
    # View
    "underground": "mdi:tunnel",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "rotateview": "fa:rotate-right",
    # Game
    "pause": "fa:pause",
    "closetop": "fa:rectangle-xmark",
    "closeall": "mdi:close-box-multiple",
    "screenshot": "fa:camera",
}

# Shapes that only feed the composed icons below.
PARTS = {
    "_railway": "gi:delapouite/railway",
    "_station_train": "fa:train-subway",
    "_train": "fa:train",
    "_track": "gi:delapouite/rail-road",
    "_road": "fa:road",
    "_tree": "fa:tree",
    "_house": "fa:house",
    "_bridge": "fa:bridge",
    "_fence": "mdi:fence",
    "_land": "fa:mountain",
    "_arrow": "fa:right-long",
}

# Key area of each icon, from openloco.yaml; the default is 40 x 40. F1 keeps
# its legend whole at 34 px (the width of the OpenRCT2 set).
SIZES = {"chat": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"chat": (30, 30), "announcements": (34, 34), "zoomin": (30, 30), "zoomout": (30, 30),
       "screenshot": (30, 30), "pause": (26, 30), "closetop": (34, 30), "map": (34, 34),
       "rotateview": (32, 32), "company": (36, 30), "lastannouncement": (34, 30),
       "companies": (30, 36), "debug": (34, 34)}

# See-through toggles: the shape as an outline OUTLINE px wide (3 to 6), or
# with every second pixel lit where its parts are too thin for an outline (2, 7).
HOLLOW = {"seeroads": "_road", "seetrees": "_tree", "seebuildings": "_house",
          "seebridges": "_bridge"}
DOTTED = {"seetracks": "_track", "seescenery": "_fence"}
OUTLINE = 2
# Height marks (8, 9): a ruler on the left, the shape on the right.
HEIGHTS = {"heightland": "_land", "heighttrack": "_track"}

# The ESC mark is set in Archivo Black (SIL OFL 1.1).
FONT_URL = ottd.FONT_URL
MARK_LINES = ("Open", "Loco")                   # the ESC mark, one line each


def flat(out: Path, part: str, box=(40, 40), size=(40, 40)):
    """The shape `part` fitted into `box`, in the bottom-right corner of `size`."""
    return ottd._corner(ottd._fit(out / f"{part}.png", box), size)


def new_vehicles(out: Path) -> None:
    """newvehicles.png (N): the train of the vehicle list (V) with a plus, as
    the OpenRCT2 set draws Build new ride."""
    cnc._save_mask(aoe2._with_plus(flat(out, "_train"), size=11), out / "newvehicles.png")
    print("  newvehicles.png  <- _train.png + a plus")


def hollow(out: Path) -> None:
    """The see-through toggles: the shape reduced to its outline, or to every
    second pixel (as the OpenRCT2 set draws its supports)."""
    for stem, part in HOLLOW.items():
        m = flat(out, part)
        cnc._save_mask(m & ~ottd.erode(m, OUTLINE), out / f"{stem}.png")
        print(f"  {stem}.png  <- {part}.png as an outline")
    import numpy as np
    yy, xx = np.mgrid[0:40, 0:40]
    for stem, part in DOTTED.items():
        cnc._save_mask(flat(out, part) & ((xx + yy) % 2 == 0), out / f"{stem}.png")
        print(f"  {stem}.png  <- {part}.png, every second pixel")


def heights(out: Path) -> None:
    """The height-mark toggles, as in the OpenRCT2 set: a ruler at the left of
    the area (a 2 px bar, the full height, with a tick every 4 px, long and
    short in turn), the shape in a 28 x 28 box at the bottom right."""
    import numpy as np
    ruler = np.zeros((40, 9), bool)
    ruler[:, :2] = True
    for i, y in enumerate(range(1, 40, 4)):
        ruler[y:y + 2, 2:9 if i % 2 == 0 else 6] = True
    for stem, part in HEIGHTS.items():
        m = flat(out, part, (28, 28))
        m[:, :ruler.shape[1]] |= ruler
        cnc._save_mask(m, out / f"{stem}.png")
        print(f"  {stem}.png  <- a ruler + {part}.png")


def direction_arrows(out: Path) -> None:
    """dirarrows.png (0): the track in a 28 x 26 box at the bottom right, an
    arrow to the right above it."""
    m = flat(out, "_track", (28, 26))
    arrow = ottd._fit(out / "_arrow.png", (28, 11))
    m[0:arrow.shape[0], 40 - arrow.shape[1]:] |= arrow
    cnc._save_mask(m, out / "dirarrows.png")
    print("  dirarrows.png  <- _track.png + fa:right-long")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    simu.flat_icons(out, ICONS, SIZES, INK, {})
    simu.upright_rail(out, "buildtracks")
    ottd.station(out)
    new_vehicles(out)
    hollow(out)
    heights(out)
    direction_arrows(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    simu.text_mark(out, MARK_LINES, FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
