#!/usr/bin/env python3
"""Fetch + render the Wargus icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and game-icons.net (CC BY 3.0), drawn the same way as the Warcraft III set.
The control groups show one Warcraft II unit each from game-icons.net: a plus
for Ctrl (create the group), a plus in a ring for Ctrl+Shift (add the selection
to the group) and a plus in a selection box for Shift (add the group to the
selection). SOURCES.md credits each. The ESC mark is WAR over GUS set in
Germania One (SIL OFL 1.1); no art from the game is used.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/wargus/fetch_icons.py
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
    # Menus (Wargus scripts/commands.lua)
    "help": "fa:circle-question",
    "options": "fa:gear",
    "speedmenu": "fa:gauge-high",
    "soundmenu": "fa:sliders",
    "preferences": "fa:user-gear",
    "diplomacy": "fa:handshake-simple",
    "gamemenu": "fa:bars",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "quit": "fa:door-open",
    "exit": "fa:power-off",
    "restart": "fa:rotate-left",
    # Map view (Stratagus src/ui/interface.cpp)
    # The three stored positions and the two viewport keys share these shapes;
    # positions() adds the digit or the arrow that tells them apart.
    "_savepos": "fa:thumbtack",
    "lastevent": "fa:bell",
    "center": "fa:crosshairs",
    "track": "fa:video",
    "_viewport": "fa:table-columns",
    "terrain": "fa:mountain-sun",
    # Game and window
    "faster": "fa:forward",
    "slower": "fa:backward",
    "pause": "fa:pause",
    "fullscreen": "fa:expand",
    "grabmouse": "fa:computer-mouse",
    "music": "fa:music",
    "sound": "fa:volume-high",
    "messages": "fa:comment-slash",
    "screenshot": "fa:camera",
    "chat": "fa:comment",
}
# Select idle worker: a digging worker with "Zz" (idle_worker()).
IDLE_WORKER = "fa:person-digging"

# Control groups: one Warcraft II unit per digit, drawn once at full height.
GROUP_UNITS = {
    "1": "cathelineau/swordman",       # footman
    "2": "delapouite/archer",          # archer
    "3": "delapouite/ogre",            # ogre
    "4": "heavenly-dog/catapult",      # catapult
    "5": "lorc/pointy-hat",            # mage
    "6": "delapouite/dynamite",        # demolition squad
    "7": "skoll/zeppelin",             # goblin zeppelin
    "8": "lorc/galleon",               # ships
    "9": "delapouite/spiked-dragon-head",  # dragon
    "0": "lorc/wood-axe",              # peasant
}

# Key area of each icon, from wargus.yaml; the default is 40 x 40.
SIZES = {"help": (34, 40), "options": (34, 40), "speedmenu": (34, 40),
         "soundmenu": (34, 40), "preferences": (34, 40), "_savepos": (34, 40)}
# The map (F2 to F4 and Ctrl+B): game-icons.net, rendered once as _map.png.
MAP_ICON = "delapouite/rolled-cloth"
# Map positions 1 to 3: the digit cut out of the map's sheet (F2 to F4) and out
# of the pin's head (Shift+F2 to Shift+F4), all 34 x 40, one digit height per
# set, with POS_MARGIN lit pixels kept around the digit.
POS_SIZE = (34, 40)
POS_MARGIN = 2
POS_DIGIT_MAX = {"recallpos": 14, "savepos": 16}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"save": (34, 34), "load": (34, 34), "help": (30, 30), "chat": (34, 34),
       "music": (30, 30), "screenshot": (30, 30), "faster": (32, 32), "slower": (32, 32),
       "pause": (30, 30), "lastevent": (34, 34)}

# The ESC mark is set in Germania One (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/germaniaone/GermaniaOne-Regular.ttf")
MARK_SS = 8              # supersampling factor for the ESC mark and the idle-worker "Zz"
MARK_THRESHOLD = 90      # grey level (0..255) from which a box-filtered pixel is lit
MARK_GAP = 3             # px between WAR and GUS


def _with_box_plus(mask, size=15, bar=3):
    """Shift+digit (add the group to the selection): a plus inside the four
    corners of a selection box, in the lower-right corner of the cell."""
    import numpy as np
    H, W = mask.shape
    y0, x0 = H - size - 1, W - size - 1
    p = np.zeros((H, W), bool)
    arm = 5
    for y, x, dy, dx in ((y0, x0, 1, 1), (y0, x0 + size - 1, 1, -1),
                         (y0 + size - 1, x0, -1, 1), (y0 + size - 1, x0 + size - 1, -1, -1)):
        for i in range(arm):
            p[y, x + dx * i] = True
            p[y + dy * i, x] = True
    cy, cx = y0 + size // 2, x0 + size // 2
    half = size // 2 - 3
    p[cy - bar // 2:cy + bar // 2 + 1, cx - half:cx + half + 1] = True
    p[cy - half:cy + half + 1, cx - bar // 2:cx + bar // 2 + 1] = True
    box = np.zeros((H, W), bool)
    box[y0:y0 + size, x0:x0 + size] = True
    return (mask & ~program_mark.dilate(box, aoe2.GROUP_SEAM)) | p


def groups(out: Path) -> None:
    """group<N>.png (select), groupnew<N>.png (Ctrl: create),
    groupjoin<N>.png (Shift: add the group to the selection) and
    groupadd<N>.png (Ctrl+Shift: add the selection to the group)."""
    for digit in GROUP_UNITS:
        g = wc3._single(out / f"_unit{digit}.png")
        aoe2._save_cell(g, out / f"group{digit}.png")
        aoe2._save_cell(aoe2._with_plus(g), out / f"groupnew{digit}.png")
        aoe2._save_cell(_with_box_plus(g), out / f"groupjoin{digit}.png")
        aoe2._save_cell(wc3._with_ring_plus(g), out / f"groupadd{digit}.png")
        print(f"  group{digit}, groupnew{digit}, groupjoin{digit}, groupadd{digit}  <- _unit{digit}.png")


def _fit(path: Path, size, box=None):
    """The shape in `path` as a flat 1-bit silhouette `size` (w, h), filling
    `box` (default: all of it) in the bottom-right corner."""
    import numpy as np
    from PIL import Image
    box = box or size
    alpha = Image.open(path).convert("RGBA").getchannel("A")
    alpha = alpha.crop(alpha.getbbox())
    scale = min(box[0] / alpha.width, box[1] / alpha.height)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))),
                         Image.LANCZOS)
    m = np.asarray(alpha) > 150
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[size[1] - m.shape[0]:, size[0] - m.shape[1]:] = m
    return canvas


def flat_icons(out: Path) -> None:
    """Every key icon as a flat 1-bit silhouette, drawn at exactly its key
    area so the generator places it 1:1. The icons in INK fill a smaller box
    in the bottom-right corner of that area. bigmap.png is the map of F2 to F4."""
    for stem in ICONS:
        size = SIZES.get(stem, (40, 40))
        cnc._save_mask(_fit(out / f"{stem}.png", size, INK.get(stem, size)), out / f"{stem}.png")
    cnc._save_mask(_fit(out / "_map.png", (40, 40)), out / "bigmap.png")
    print(f"  {len(ICONS) + 1} key icons drawn flat")


def idle_worker(out: Path) -> None:
    """idleworker.png: the worker in the lower left, a large Z and a small z
    above it on the right, 40x40."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    size, ss = 40, MARK_SS
    a = Image.open(out / "_worker.png").convert("RGBA").getchannel("A")
    a = a.crop(a.getbbox())
    k = min(34 * ss / a.width, 28 * ss / a.height)
    a = a.resize((round(a.width * k), round(a.height * k)), Image.LANCZOS)
    im = Image.new("L", (size * ss, size * ss), 0)
    im.paste(255, (0, size * ss - a.height), a)
    d = ImageDraw.Draw(im)
    font = cnc._font(cnc.DIGIT_FONT_URL)
    for text, px, x, y in (("Z", 17, 25, 0), ("z", 11, 18, 4)):
        f = ImageFont.truetype(str(font), px * ss)
        b = f.getbbox(text)
        d.text((x * ss - b[0], y * ss - b[1]), text, font=f, fill=255)
    cnc._save_mask(np.asarray(im.resize((size, size), Image.BOX)) > 110, out / "idleworker.png")
    print(f"  idleworker.png  <- {IDLE_WORKER} + Zz (DejaVu Sans Bold)")


def program(out: Path) -> None:
    """program.png: WAR over GUS, each line as large as fits half the cell,
    centred on the whole 72x40 cell. Drawn at MARK_SS times the size and
    box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = program_mark.W, program_mark.H, MARK_SS
    path = str(cnc._font(FONT_URL))
    line_h = (h - 2 - MARK_GAP) // 2
    for px in range(60 * ss, 4 * ss, -ss // 2):
        font = ImageFont.truetype(path, px)
        boxes = [font.getbbox(t) for t in ("WAR", "GUS")]
        if all(b[2] - b[0] <= (w - 2) * ss and b[3] - b[1] <= line_h * ss for b in boxes):
            break
    height = sum(b[3] - b[1] for b in boxes) + MARK_GAP * ss
    y = (h * ss - height) // 2
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    for text, b in zip(("WAR", "GUS"), boxes):
        d.text(((w * ss - (b[2] - b[0])) // 2 - b[0], y - b[1]), text, font=font, fill=255)
        y += b[3] - b[1] + MARK_GAP * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- WAR / GUS (Germania One, {px / ss:.1f} px)")


def _digit(text: str, height: int):
    """`text` in DejaVu Sans Bold, at most `height` px tall, as a cropped mask."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ss = MARK_SS
    path = str(cnc._font(cnc.DIGIT_FONT_URL))
    for px in range(60, 4, -1):
        f = ImageFont.truetype(path, px * ss)
        left, top, right, bottom = f.getbbox(text)
        im = Image.new("L", (right - left + 2 * ss, bottom - top + 2 * ss), 0)
        ImageDraw.Draw(im).text((ss - left, ss - top), text, font=f, fill=255)
        m = np.asarray(im.resize((im.width // ss, im.height // ss), Image.BOX)) > 110
        ys, xs = np.nonzero(m)
        m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        if m.shape[0] <= height:
            return m
    raise SystemExit(f"no size of {text!r} is {height} px or less")


def _load(path: Path):
    import numpy as np
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGBA").getchannel("A")) > 127


def _erode(m, n: int):
    """The pixels of `m` that are at least `n` px inside it; outside the canvas counts as unlit."""
    import numpy as np
    p = np.pad(m, n)
    return ~program_mark.dilate(~p, n)[n:-n, n:-n]


def positions(out: Path) -> None:
    """recallpos1..3.png (F2 to F4): the map with the position's digit cut
    out of its sheet, as near the middle and the top as fits. savepos1..3.png
    (Shift+F2 to Shift+F4): the pushpin with the digit cut out of the middle of
    its head. Each set uses one digit height, the tallest that leaves
    POS_MARGIN lit pixels around every digit.
    viewportprev.png (Ctrl+V) and viewportnext.png (Alt+V): the two-pane window
    with a left arrow in the left pane or a right arrow in the right pane."""
    import numpy as np

    def on_sheet(shape, g):
        """(row, column) for `g` inside the map, nearest the middle, then the top."""
        inner = _erode(shape, POS_MARGIN)
        gh, gw = g.shape
        spots = [(abs(x + gw / 2 - shape.shape[1] / 2), y, x)
                 for y in range(shape.shape[0] - gh + 1) for x in range(shape.shape[1] - gw + 1)
                 if inner[y:y + gh, x:x + gw].all()]
        return min(spots)[1:] if spots else None

    def in_head(shape, g):
        """(row, column) for `g` centred on the pin's head (the rows above the needle)."""
        rows = shape.any(1)
        top = int(np.argmax(rows))
        end = top
        while end + 1 < len(rows) and rows[end + 1]:
            end += 1
        ys, xs = np.nonzero(shape[:end + 1])
        gh, gw = g.shape
        y = int(round((ys.min() + ys.max() + 1) / 2 - gh / 2))
        x = int(round((xs.min() + xs.max() + 1) / 2 - gw / 2))
        return (y, x) if _erode(shape, POS_MARGIN)[y:y + gh, x:x + gw].all() else None

    for name, shape, place in (("recallpos", _fit(out / "_map.png", POS_SIZE), on_sheet),
                               ("savepos", _load(out / "_savepos.png"), in_head)):
        for height in range(POS_DIGIT_MAX[name], 4, -1):
            glyphs = [_digit(str(n), height) for n in (1, 2, 3)]
            spots = [place(shape, g) for g in glyphs]
            if all(spots):
                break
        else:
            raise SystemExit(f"{name}: no digit fits inside the shape")
        for n, (g, (y, x)) in enumerate(zip(glyphs, spots), 1):
            m = shape.copy()
            m[y:y + g.shape[0], x:x + g.shape[1]] &= ~g
            cnc._save_mask(m, out / f"{name}{n}.png")
        print(f"  {name}1..3.png  <- digits 1 to 3 cut out ({height} px)")
    window = _load(out / "_viewport.png")
    for name, left in (("viewportprev", True), ("viewportnext", False)):
        m = window.copy()
        # the pane: the unlit pixels of this half in the rows where the frame's
        # outer column is lit (that leaves out the rounded corners)
        half = slice(0, window.shape[1] // 2) if left else slice(window.shape[1] // 2, window.shape[1])
        pane = ~window[:, half] & window[:, :1]
        py, px = np.nonzero(pane)
        cy = (py.min() + py.max()) // 2
        cx = (px.min() + px.max()) // 2 + half.start
        size = 9
        mid = size // 2
        for i in range(mid + 1):                 # the head, a triangle
            m[cy - i:cy + i + 1, cx - mid + i if left else cx + mid - i] = True
        for x in (range(cx, cx + mid + 1) if left else range(cx - mid, cx + 1)):
            m[cy - 1:cy + 2, x] = True            # the shaft, 3 px
        cnc._save_mask(m, out / f"{name}.png")
    print("  viewportprev.png, viewportnext.png  <- _viewport.png + an arrow in one pane")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, "_worker": IDLE_WORKER}, out)
    game_icons.render({**{f"_unit{d}": n for d, n in GROUP_UNITS.items()}, "_map": MAP_ICON}, out, render_px=256)
    flat_icons(out)
    idle_worker(out)
    positions(out)
    groups(out)
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
