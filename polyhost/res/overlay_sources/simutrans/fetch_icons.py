#!/usr/bin/env python3
"""Fetch + render the Simutrans icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0),
Material Design Icons (Apache-2.0) and game-icons.net (CC BY 3.0), with the
same sources as the OpenTTD and OpenRCT2 sets for the same actions. A few are
composed here from those shapes: raise and lower land (drawn, as in the OpenTTD
set), the railway track turned upright, the station list (a train under a
roof, from the OpenTTD set), found a city (the city with a plus), hide trees
and hide buildings (the shape struck through), the block reservation tool (the
signal struck through) and the two underground slice keys (the layers with an
arrow). SOURCES.md credits each. The ESC mark is "Simu" over "trans" set in
Russo One (SIL OFL 1.1); the game's own logo is not used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/simutrans/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.openttd import fetch_icons as ottd  # noqa: E402

# Drawn flat at their key area (SIZES, default 40 x 40).
ICONS = {
    # Tools (plain letters)
    "query": "fa:arrow-pointer",
    "remove": "mdi:bulldozer",
    "showblocks": "mdi:traffic-light",
    "transformer": "fa:plug-circle-bolt",
    "headquarters": "fa:building",
    "buildroad": "fa:road",
    "electrify": "fa:bolt",
    "powerline": "mdi:transmission-tower",
    "marker": "fa:signs-post",
    "buyhouse": "fa:house-circle-check",
    "lastused": "fa:clock-rotate-left",
    # Game
    "pause": "fa:pause",
    "faster": "fa:forward",
    "slower": "fa:backward",
    "fastforward": "fa:forward-fast",
    "screenshot": "fa:camera",
    "undo": "fa:arrow-rotate-left",
    "switchplayer": "fa:people-arrows",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "quit": "fa:power-off",
    "options": "fa:gear",
    "help": "fa:circle-question",
    # View
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "rotatemap": "fa:rotate-right",
    "underground": "mdi:tunnel",
    "sliced": "fa:layer-group",
    "grid": "mdi:grid",
    "names": "fa:tag",
    "coverage": "mdi:map-marker-radius",
    "owner": "fa:flag",
    "tooltips": "mdi:tooltip-text",
    "singleways": "fa:highlighter",
    "jump": "fa:location-crosshairs",
    # Windows
    "closetop": "fa:rectangle-xmark",
    "closeall": "mdi:close-box-multiple",
    "minimap": "fa:map",
    "lines": "fa:route",
    "finances": "fa:sack-dollar",
    "players": "fa:users",
    "messages": "fa:envelope",
    "gameinfo": "fa:circle-info",
    "scenarioinfo": "fa:list-check",
    "waybuilder": "mdi:map-marker-path",
    # Lists
    "convoys": "fa:train",
    "towns": "fa:city",
    "goods": "fa:boxes-stacked",
    "factories": "fa:industry",
    "attractions": "fa:landmark",
    "depots": "fa:warehouse",
    "vehicles": "fa:truck",
    "labels": "fa:tags",
}

# Shapes that only feed the composed icons below.
PARTS = {
    "_railway": "gi:delapouite/railway",
    "_station_train": "fa:train-subway",
    "_city": "fa:city",
    "_tree": "fa:tree",
    "_house": "fa:house",
    "_signal": "mdi:traffic-light",
    "_layers": "fa:layer-group",
}

# Key area of each icon, from simutrans.yaml; the default is 40 x 40. F1 keeps
# its legend whole at 34 px, F6 and F7 at 30 px (the widths of the OpenTTD set).
SIZES = {"help_f1": (34, 40), "scenarioinfo": (30, 40), "waybuilder": (30, 40)}
# Icons used on a second key with a narrower area: stem -> (source stem, area, ink box).
NARROW = {"help_f1": ("help", (34, 40), (30, 30))}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "options": (32, 32), "help": (32, 32),
       "gameinfo": (32, 32), "pause": (26, 30), "faster": (34, 26), "slower": (34, 26),
       "fastforward": (34, 26), "zoomin": (30, 30), "zoomout": (30, 30),
       "screenshot": (32, 30), "closetop": (34, 30), "quit": (32, 32),
       "messages": (34, 34), "minimap": (34, 34), "headquarters": (30, 36),
       "query": (26, 36), "names": (34, 34), "owner": (32, 34), "electrify": (28, 36),
       "jump": (34, 34), "lastused": (34, 34), "undo": (32, 32), "rotatemap": (32, 32),
       "scenarioinfo": (30, 30), "waybuilder": (30, 30), "sliced": (34, 34)}

# The ESC mark is set in Russo One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/russoone/RussoOne-Regular.ttf")
MARK_LINES = ("Simu", "trans")   # the ESC mark, one line each
MARK_GAP = 2                # px between the lines of an ESC mark
MARK_SS = 8                 # supersampling factor for an ESC mark
MARK_THRESHOLD = 110        # grey level (0..255) from which a box-filtered ESC mark pixel is lit


def flat_icons(out: Path, icons=None, sizes=None, ink=None, narrow=None) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key area
    so the generator places it 1:1. The icons in `ink` fill a smaller box in
    the bottom-right corner of that area. The icons in `narrow` are drawn a
    second time for a key with a narrower area. The defaults are this set's
    tables; the other builder sets pass their own."""
    icons = ICONS if icons is None else icons
    sizes = SIZES if sizes is None else sizes
    ink = INK if ink is None else ink
    narrow = NARROW if narrow is None else narrow
    for stem, (src, size, box) in narrow.items():
        cnc._save_mask(ottd._corner(ottd._fit(out / f"{src}.png", box), size), out / f"{stem}.png")
    for stem in icons:
        size = sizes.get(stem, (40, 40))
        m = ottd._fit(out / f"{stem}.png", ink.get(stem, size))
        cnc._save_mask(ottd._corner(m, size), out / f"{stem}.png")
    print(f"  {len(icons) + len(narrow)} key icons drawn flat")


def terrain(out: Path) -> None:
    """raise.png (U): ground with a hill and an up arrow over it. lower.png (D):
    ground with a pit and a down arrow into it. The shapes of the OpenTTD set."""
    hill = [(0, 40), (0, 32), (9, 32), (15, 23), (25, 23), (31, 32), (40, 32), (40, 40)]
    pit = [(0, 40), (0, 25), (9, 25), (15, 33), (25, 33), (31, 25), (40, 25), (40, 40)]
    cnc._save_mask(ottd._draw([hill, ottd._arrow(20, 1, 19, up=True)]), out / "raise.png")
    cnc._save_mask(ottd._draw([pit, ottd._arrow(20, 1, 21, up=False)]), out / "lower.png")
    print("  raise.png, lower.png drawn")


def upright_rail(out: Path, stem: str = "buildrail", size=(40, 40)) -> None:
    """<stem>.png: the railway track turned upright, as the OpenTTD set draws
    Build railway."""
    from PIL import Image
    a = Image.open(out / "_railway.png").convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    r = a.rotate(90, resample=Image.BICUBIC, expand=True)
    tmp = out / "_railway_rot.png"
    Image.merge("RGBA", (r, r, r, r)).save(tmp)
    cnc._save_mask(ottd._corner(ottd._fit(tmp, size), size), out / f"{stem}.png")
    tmp.unlink()
    print(f"  {stem}.png  <- gi:delapouite/railway turned 90 degrees")


def composed(out: Path) -> None:
    """The icons made from two shapes."""
    import numpy as np
    # Shift+C: the town list's city with a plus.
    city = ottd._corner(ottd._fit(out / "_city.png", (34, 36)), (40, 40))
    shifted = np.zeros_like(city)
    shifted[:36, :36] = city[4:, 4:]
    cnc._save_mask(aoe2._with_plus(shifted), out / "foundcity.png")
    # Shift+5 and Shift+': the object struck through, as the OpenTTD set draws
    # its invisibility keys.
    for stem, part in (("hidetrees", "_tree"), ("hidehouses", "_house")):
        m = ottd._corner(ottd._fit(out / f"{part}.png", (36, 34)), (40, 40))
        cnc._save_mask(ottd._struck(m), out / f"{stem}.png")
    # B: the signal struck through (remove a block reservation).
    m = ottd._corner(ottd._fit(out / "_signal.png", (40, 40)), (40, 40))
    cnc._save_mask(ottd._struck(m), out / "clearblock.png")
    # Shift+= and -: the layers of the sliced view with an arrow up or down.
    layers = ottd._corner(ottd._fit(out / "_layers.png", (26, 26)), (40, 40))
    for stem, up in (("sliceup", True), ("slicedown", False)):
        arrow = ottd._draw([ottd._arrow(7, 2, 38, up=up, shaft=4, head=14, head_h=9)])
        cnc._save_mask(layers | arrow, out / f"{stem}.png")
    print("  foundcity.png, hidetrees.png, hidehouses.png, clearblock.png, "
          "sliceup.png, slicedown.png composed")


def text_mark(out: Path, lines, font_url: str, threshold: int = MARK_THRESHOLD,
              gap: int = MARK_GAP) -> None:
    """program.png: `lines`, one below the other, all at the largest one size
    at which each fits 70 px wide and all of them, `gap` px apart, fit 38 px
    high, centred on the whole 72x40 cell. Drawn at MARK_SS times the size and
    box-filtered down (the method of the fheroes2 set)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    g = gap * ss
    path = str(cnc._font(font_url))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + g * (len(boxes) - 1)
        if all(b[2] - b[0] <= (w - 2) * ss for b in boxes) and height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * ss - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + g
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, out / "program.png")
    print(f"  program.png  <- {' / '.join(lines)} ({font_url.rsplit('/', 1)[1]}, {px / ss:.1f} px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    flat_icons(out)
    terrain(out)
    upright_rail(out)
    ottd.station(out)
    composed(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    text_mark(out, MARK_LINES, FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
