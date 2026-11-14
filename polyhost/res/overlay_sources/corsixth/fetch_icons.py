#!/usr/bin/env python3
"""Fetch + render the CorsixTH icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0)
and Material Design Icons (Apache-2.0), with the same sources as the OpenTTD
and OpenRCT2 sets for the same actions. Composed here: the five game speeds
(five rising bars, as many lit as the speed), the map positions (a numbered
pin, with a plus for "store", as the 0 A.D. set draws its camera positions),
the zoom variants, the two transparent-wall keys and quick save and quick load
(a bolt beside the icon, as in the fheroes2 set). SOURCES.md credits each. The
ESC mark is the green figure of CorsixTH's own logo (MIT) as a silhouette,
with "Corsix" over "TH" in Archivo Black (SIL OFL 1.1) beside it.

    pip install cairosvg numpy pillow
    python polyhost/res/overlay_sources/corsixth/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import fetch_icons as aoe2  # noqa: E402
from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.openttd import fetch_icons as ottd  # noqa: E402
from polyhost.res.overlay_sources.simutrans import fetch_icons as simu  # noqa: E402
from polyhost.res.overlay_sources.zeroad import fetch_icons as zeroad  # noqa: E402

# Drawn flat at their key area (SIZES, default 40 x 40).
ICONS = {
    # Dialogs and the program
    "confirm": "fa:circle-check",
    "closewindow": "fa:rectangle-xmark",
    "fullscreen": "fa:expand",
    "exit": "fa:power-off",
    "restart": "fa:arrows-rotate",
    "releasemouse": "fa:computer-mouse",
    "screenshot": "fa:camera",
    "console": "fa:terminal",
    "debugscript": "fa:bug",
    "dumplog": "fa:file-lines",
    "dumpstrings": "fa:language",
    "cheats": "fa:wand-magic-sparkles",
    # Game
    "pause": "fa:pause",
    "speedup": "fa:forward-fast",
    "load": "fa:folder-open",
    "save": "fa:floppy-disk",
    "restartlevel": "fa:rotate-left",
    "quitlevel": "fa:door-open",
    # View
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    # Fullscreen windows (F1 to F10)
    "bankmanager": "fa:building-columns",
    "bankstats": "fa:file-invoice-dollar",
    "staff": "fa:users-gear",
    "townmap": "fa:map",
    "casebook": "fa:book-medical",
    "research": "fa:flask",
    "status": "fa:list-check",
    "charts": "fa:chart-line",
    "policy": "fa:clipboard-list",
    "machines": "fa:screwdriver-wrench",
    # Bottom panel
    "buildroom": "fa:trowel-bricks",
    "furnish": "fa:couch",
    "editroom": "fa:pen-ruler",
    "hire": "fa:user-plus",
    "firstmessage": "fa:envelope-open-text",
    "info": "fa:circle-info",
    "jukebox": "fa:record-vinyl",
    # Hospital
    "rotateobject": "mdi:rotate-3d-variant",
    "sell": "fa:hand-holding-dollar",
    "gohome": "fa:house-user",
    "adviser": "fa:user-tie",
    "adviserhistory": "fa:clock-rotate-left",
    # Sound
    "announcements": "fa:bullhorn",
    "sounds": "fa:volume-high",
    "music": "fa:music",
}

# Shapes that only feed the composed icons below. _jump is the pin of the
# 0 A.D. set's camera positions.
PARTS = {
    "_jump": zeroad.JUMP_PIN,
    "_floppy": "fa:floppy-disk",
    "_folder": "fa:folder-open",
    "_bolt": "fa:bolt",
    "_glass": "fa:magnifying-glass",
    "_zoomin": "fa:magnifying-glass-plus",
    "_zoomout": "fa:magnifying-glass-minus",
    "_wall": "mdi:wall",
    "_lock": "fa:lock",
    "_forward": "fa:forward",
}

# Key area of each icon, from corsixth.yaml; the default is 40 x 40. F1 to F3
# and F8 keep their legend whole at 34 px, F4 to F7 at 30 px (the widths of the
# OpenTTD set).
SIZES = {"bankmanager": (34, 40), "bankstats": (34, 40), "staff": (34, 40),
         "status": (30, 40), "charts": (34, 40), "exit": (30, 40)}
# Icons used on a second key with a narrower area: stem -> (source stem, area, ink box).
NARROW = {"townmap_f4": ("townmap", (30, 40), (30, 30)),
          "casebook_f5": ("casebook", (30, 40), (30, 34)),
          "research_f6": ("research", (30, 40), (30, 34))}
# Solid icons that read heavier than the rest: drawn in a smaller box.
INK = {"confirm": (32, 32), "closewindow": (34, 30), "fullscreen": (32, 32), "exit": (30, 30),
       "screenshot": (32, 30), "console": (34, 30), "pause": (26, 30), "speedup": (34, 26),
       "load": (34, 34), "save": (34, 34), "restartlevel": (32, 32), "restart": (32, 32),
       "zoomin": (30, 30), "zoomout": (30, 30), "townmap": (34, 34), "info": (32, 32),
       "bankstats": (28, 36), "casebook": (30, 36), "policy": (30, 36), "dumplog": (28, 36),
       "jukebox": (34, 34), "adviserhistory": (34, 34), "releasemouse": (26, 36),
       "bankmanager": (34, 34), "debugscript": (34, 34), "status": (30, 30)}

# 1 to 5: the game speeds, slowest to fastest.
SPEEDS = (1, 2, 3, 4, 5)
SPEED_BAR, SPEED_GAP, SPEED_STEP = 6, 2, 7     # bar width, gap, height step per bar (px)
# Ctrl+digit recalls and Alt+digit stores a map position.
POSITIONS = "1234567890"
PIN_BOX = (24, 32)                              # the pin's size, as in the 0 A.D. set

# The ESC mark: the green figure of CorsixTH's logo at tag v0.70.2 (MIT, like
# the game), and the name in Archivo Black (SIL OFL 1.1).
LOGO_URL = ("https://raw.githubusercontent.com/CorsixTH/CorsixTH/"
            "7e84444cb0406bb04466dd5880303cd40d21d63c/CorsixTH/Original_Logo.svg")
LOGO_SHA256 = "f19be3b07168e08eb51b6205f796dfdc3d009c48548364aab29accf707908ae9"
FONT_URL = ottd.FONT_URL
MARK_LINES = ("Corsix", "TH")
MARK_GAP = 3                # unlit columns between the name and the figure
MARK_SS = 8                 # supersampling factor for the name
MARK_THRESHOLD = 110        # grey level (0..255) from which a box-filtered name pixel is lit


def flat(out: Path, part: str, box=(40, 40), size=(40, 40)):
    """The shape `part` fitted into `box`, in the bottom-right corner of `size`."""
    return ottd._corner(ottd._fit(out / f"{part}.png", box), size)


def speeds(out: Path) -> None:
    """speed<N>.png (1 to 5): five bars rising to the right, the first N lit
    and the others as a 1 px outline, with the fast-forward arrows at the top
    left."""
    import numpy as np
    arrows = ottd._fit(out / "_forward.png", (18, 12))
    for n in SPEEDS:
        m = np.zeros((40, 40), bool)
        for i in range(len(SPEEDS)):
            x = i * (SPEED_BAR + SPEED_GAP)
            top = 40 - (i + 1) * SPEED_STEP - 4
            bar = np.zeros_like(m)
            bar[top:, x:x + SPEED_BAR] = True
            m |= bar if i < n else bar & ~ottd.erode(bar, 1)
        m[0:arrows.shape[0], 0:arrows.shape[1]] |= arrows
        cnc._save_mask(m, out / f"speed{n}.png")
    print("  speed1.png .. speed5.png  <- five bars + fa:forward")


def positions(out: Path) -> None:
    """recall<N>.png (Ctrl+N) and store<N>.png (Alt+N): the location pin with N
    cut out of its head, and for "store" the pin moved up and left with a
    plus. The layout of the 0 A.D. set's jump_pins(), in a 40 x 40 area."""
    import numpy as np
    for n in POSITIONS:
        pin = zeroad._fill_holes(flat(out, "_jump", PIN_BOX))
        ys, xs = np.nonzero(pin)
        g = zeroad._digit(n, zeroad.JUMP_DIGIT_PX)
        cy = ys.min() + zeroad.JUMP_HEAD_CENTRE
        cx = (xs.min() + xs.max() + 1) // 2
        y0, x0 = cy - g.shape[0] // 2, cx - g.shape[1] // 2
        pin[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] &= ~g
        cnc._save_mask(pin, out / f"recall{n}.png")
        k = zeroad.JUMPSET_SHIFT
        moved = np.zeros_like(pin)
        moved[:-k, :-k] = pin[k:, k:]
        cnc._save_mask(aoe2._with_plus(moved), out / f"store{n}.png")
    print("  recall1..0.png, store1..0.png  <- fa:location-dot with a digit (+ a plus)")


def zooms(out: Path) -> None:
    """zoominmore.png, zoomoutmore.png (Shift+= and Shift+-): the zoom glass
    at 30 px with a second plus or minus at the top left. resetzoom.png (0):
    the plain glass with 1:1 above it, as the OpenTTD set marks its
    default-zoom screenshot."""
    import numpy as np
    for stem, part, sign in (("zoominmore", "_zoomin", ottd._badge_plus()),
                             ("zoomoutmore", "_zoomout", ottd._badge_plus()[4:7, :])):
        m = flat(out, part, (30, 30))
        m[2:2 + sign.shape[0], 0:sign.shape[1]] |= sign
        cnc._save_mask(m, out / f"{stem}.png")
    m = flat(out, "_glass", (26, 26))
    badge = ottd._badge_text("1:1")
    h, w = badge.shape
    canvas = np.zeros_like(m)
    canvas[1:1 + h, 40 - w:] = badge
    cnc._save_mask(m | canvas, out / "resetzoom.png")
    print("  zoominmore.png, zoomoutmore.png, resetzoom.png composed")


def walls(out: Path) -> None:
    """transparent.png (X, while held): the wall with every second pixel lit
    inside, as the OpenTTD set draws its transparency keys.
    toggletransparent.png (Shift+X): the same wall at 28 px with a lock at
    the top left, because the key keeps the walls transparent."""
    wall = flat(out, "_wall")
    cnc._save_mask(ottd._transparent(wall), out / "transparent.png")
    small = ottd._transparent(flat(out, "_wall", (28, 28)))
    lock = ottd._fit(out / "_lock.png", (12, 14))
    box = program_mark.dilate(_canvas(lock), 2)
    cnc._save_mask((small & ~box) | _canvas(lock), out / "toggletransparent.png")
    print("  transparent.png, toggletransparent.png  <- mdi:wall (+ fa:lock)")


def _canvas(m, size=(40, 40)):
    """`m` in the top-left corner of a `size` (w, h) canvas."""
    import numpy as np
    canvas = np.zeros((size[1], size[0]), bool)
    canvas[0:m.shape[0], 0:m.shape[1]] = m
    return canvas


def quick(out: Path) -> None:
    """quicksave.png, quickload.png (Alt+Shift+S, Alt+Shift+L): the disk or
    the folder at 28 px in the bottom-right corner, with a bolt above its left
    edge, cut out of it by a 2 px gap (the fheroes2 set's quick save)."""
    bolt = _canvas(ottd._fit(out / "_bolt.png", (14, 20)))
    for stem, part in (("quicksave", "_floppy"), ("quickload", "_folder")):
        m = flat(out, part, (28, 28))
        cnc._save_mask((m & ~program_mark.dilate(bolt, 2)) | bolt, out / f"{stem}.png")
    print("  quicksave.png, quickload.png  <- fa:floppy-disk / fa:folder-open + fa:bolt")


def _figure():
    """The green figure of the logo as a cropped 1-bit mask 40 px high."""
    import hashlib
    import io

    import cairosvg
    import numpy as np
    from PIL import Image
    from polyhost.res.overlay_sources.icon_fetch import _get
    svg = _get(LOGO_URL)
    if hashlib.sha256(svg).hexdigest() != LOGO_SHA256:
        raise SystemExit("the download is not the CorsixTH logo of v0.70.2")
    png = cairosvg.svg2png(bytestring=svg, output_width=256)
    im = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"), float) / 255
    green = (im[..., 1] > im[..., 0] * 1.5) & (im[..., 1] > im[..., 2] * 1.5) & (im[..., 1] > 0.25)
    ys, xs = np.nonzero(green)
    a = Image.fromarray((green * 255).astype(np.uint8)).crop(
        (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return np.asarray(a.resize((round(a.width * 40 / a.height), 40), Image.BOX)) > 127


def _name(width: int):
    """MARK_LINES, one below the other at one size, the largest at which each
    fits `width` px, as a cropped 1-bit mask."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    ss, path = MARK_SS, str(cnc._font(FONT_URL))
    for px in range(400, 40, -4):
        font = ImageFont.truetype(path, px)
        boxes = [font.getbbox(line) for line in MARK_LINES]
        height = sum(b[3] - b[1] for b in boxes) + 2 * ss * (len(boxes) - 1)
        if all(b[2] - b[0] <= width * ss for b in boxes) and height <= 38 * ss:
            break
    im = Image.new("L", (width * ss, 40 * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (40 * ss - height) // 2
    for line, box in zip(MARK_LINES, boxes):
        draw.text((-box[0], y - box[1]), line, font=font, fill=255)
        y += box[3] - box[1] + 2 * ss
    return np.asarray(im.resize((width, 40), Image.BOX)) > MARK_THRESHOLD


def program(out: Path) -> None:
    """program.png: the logo's figure at the right edge of the 72x40 cell, the
    name in two lines in the columns left of it."""
    if (out / "program.png").exists():
        # Taken from the program's own art: the committed PNG is the source, and
        # an owner's edit of it must survive a re-run. Delete the file to redraw it.
        print("  program.png  <- committed asset (left as-is)")
        return
    import numpy as np
    w, h = 72, 40
    figure = _figure()
    fw = figure.shape[1]
    canvas = np.zeros((h, w), bool)
    canvas[:, w - fw:] = figure
    canvas[:, 0:w - fw - MARK_GAP] = _name(w - fw - MARK_GAP)
    cnc._save_mask(canvas, out / "program.png")
    print("  program.png  <- CorsixTH logo figure + Corsix / TH (Archivo Black)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS}, out)
    simu.flat_icons(out, ICONS, SIZES, INK, NARROW)
    speeds(out)
    positions(out)
    zooms(out)
    walls(out)
    quick(out)
    for stem in PARTS:
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
