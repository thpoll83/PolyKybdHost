#!/usr/bin/env python3
"""Fetch + render the OpenMW icons (reproducible).

The key icons are flat silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0), as in the
fheroes2 set. The quick keys are a square frame with the number; the cycle
keys are the weapon or the spell beside a triangle; quick save and quick load add a
bolt. SOURCES.md credits each. The ESC mark is "Open" over "MW" set in Cinzel
Decorative (SIL OFL 1.1); the project's logo is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/openmw/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.aoe2 import program_mark  # noqa: E402
from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.devilutionx import fetch_icons as dx  # noqa: E402
from polyhost.res.overlay_sources.mindustry import fetch_icons as mindustry  # noqa: E402
from polyhost.res.overlay_sources.veloren import fetch_icons as veloren  # noqa: E402

ICONS = {
    # Movement
    "forward": "fa:arrow-up",
    "left": "fa:arrow-left",
    "back": "fa:arrow-down",
    "right": "fa:arrow-right",
    "run": "fa:person-running",
    "alwaysrun": "mdi:run-fast",
    "sneak": "fa:user-ninja",
    "automove": "fa:person-walking-arrow-right",
    "jump": "gi:delapouite/jump-across",
    # Actions
    "activate": "fa:hand-pointer",
    "weapon": "gi:lorc/broadsword",
    "spell": "fa:hand-sparkles",
    "rest": "fa:bed",
    # Windows and view
    "journal": "fa:book-open",
    "quickmenu": "fa:table-cells",
    "console": "fa:terminal",
    "pov": "fa:street-view",
    "hidehud": "fa:eye-slash",
    "postprocess": "fa:sliders",
    "debug": "fa:bug",
    "screenshot": "fa:camera",
}
# Parts of the composed icons.
PARTS = {"_floppy": "fa:floppy-disk", "_folder": "fa:folder-open", "_bolt": "fa:bolt",
         "_prev": "fa:caret-left", "_next": "fa:caret-right"}

# Key area of each icon, from openmw.yaml; the default is 40 x 40. The narrow
# ones keep the key's own legend whole (widths measured for AoE2, see
# ../aoe2/SOURCES.md, Placement).
SIZES = {"quickmenu": (34, 40), "postprocess": (34, 40), "run": (34, 40),
         "sneak": (34, 40), "alwaysrun": (34, 40)}
# Solid icons that read heavier than the rest: drawn in a smaller box at the
# bottom right of their key area.
INK = {"forward": (30, 36), "back": (30, 36), "left": (36, 30), "right": (36, 30),
       "screenshot": (30, 30), "debug": (34, 34), "quickmenu": (30, 30),
       "postprocess": (30, 30), "journal": (38, 30), "rest": (38, 28),
       "console": (36, 30), "hidehud": (38, 30), "activate": (30, 36)}

SLOTS = range(1, 11)      # quick keys 1 to 9 and 0 (quick key 10)
BOLT_SIZE = (34, 40)      # key area of quicksave.png and quickload.png (F5, F9)

# The ESC mark is set in Cinzel Decorative (SIL OFL 1.1).
FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
            "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/cinzeldecorative/CinzelDecorative-Bold.ttf")
MARK_LINES = ("Open", "MW")
MARK_GAP = 2           # px between the two lines
MARK_SS = 8            # supersampling factor
MARK_THRESHOLD = 80    # grey level (0..255) from which a box-filtered pixel is lit


def quick_keys(out: Path) -> None:
    """quick1.png .. quick10.png: the Veloren set's frame with the number."""
    for n in SLOTS:
        cnc._save_mask(veloren.frame_digit(str(n)), out / f"quick{n}.png")
    print(f"  quick1..{SLOTS[-1]}.png  <- frame + number")


def cycle_icons(out: Path) -> None:
    """prevweapon, nextweapon, prevspell, nextspell (40 x 40): the weapon or the
    spell with a solid triangle beside it that points left (previous, on the
    left) or right (next, on the right)."""
    import numpy as np
    for item in ("weapon", "spell"):
        body = dx._fit(f"_{item}", out, (28, 40), (28, 36))
        for stem, arrow, left in ((f"prev{item}", "_prev", True), (f"next{item}", "_next", False)):
            tri = dx._fit(arrow, out, (10, 40), (10, 18))
            c = np.zeros((40, 40), bool)
            if left:
                c[:, :10], c[:, 12:] = tri, body
            else:
                c[:, :28], c[:, 30:] = body, tri
            cnc._save_mask(c, out / f"{stem}.png")
    print("  prevweapon, nextweapon, prevspell, nextspell  <- item beside a triangle")


def bolt_icons(out: Path) -> None:
    """quicksave.png (F5) and quickload.png (F9): the disk or the folder in the
    bottom-right corner with a bolt above its left edge, cut out by a 2 px gap
    (as fheroes2's quick save)."""
    import numpy as np
    w, h = BOLT_SIZE
    bolt = dx._fit("_bolt", out, (14, 20), (14, 20))
    for stem, part, box in (("quicksave", "_floppy", (26, 26)), ("quickload", "_folder", (28, 24))):
        c = dx._fit(part, out, (w, h), box)
        b = np.zeros((h, w), bool)
        b[:bolt.shape[0], :bolt.shape[1]] = bolt
        cnc._save_mask((c & ~program_mark.dilate(b, 2)) | b, out / f"{stem}.png")
    print("  quicksave.png, quickload.png  <- disk or folder + fa:bolt")


def program(out: Path) -> None:
    """program.png: "Open" over "MW", each line at the largest size at which it
    fits 70 px wide, and both, MARK_GAP apart, fit 38 px high; centred on the
    whole 72 x 40 cell. Drawn at MARK_SS times the size and
    box-filtered down."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    w, h, ss = 72, 40, MARK_SS
    path = str(cnc._font(FONT_URL))
    for scale in range(100, 20, -2):
        fonts, boxes = [], []
        for line in MARK_LINES:
            for px in range(round(3 * scale), 10, -2):
                f = ImageFont.truetype(path, px)
                b = f.getbbox(line)
                if b[2] - b[0] <= (w - 2) * ss:
                    break
            fonts.append(f)
            boxes.append(b)
        height = sum(b[3] - b[1] for b in boxes) + MARK_GAP * ss
        if height <= (h - 2) * ss:
            break
    im = Image.new("L", (w * ss, h * ss), 0)
    draw = ImageDraw.Draw(im)
    y = (h * ss - height) // 2
    for line, f, b in zip(MARK_LINES, fonts, boxes):
        draw.text(((w * ss - (b[2] - b[0])) // 2 - b[0], y - b[1]), line, font=f, fill=255)
        y += b[3] - b[1] + MARK_GAP * ss
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > MARK_THRESHOLD, out / "program.png")
    print(f"  program.png  <- {' / '.join(MARK_LINES)} (Cinzel Decorative Bold)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    cnc.render({**ICONS, **PARTS, "_weapon": ICONS["weapon"], "_spell": ICONS["spell"]}, out)
    mindustry.flat_icons(out, ICONS, SIZES, INK)
    quick_keys(out)
    cycle_icons(out)
    bolt_icons(out)
    for stem in (*PARTS, "_weapon", "_spell"):
        (out / f"{stem}.png").unlink()
    program(out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
