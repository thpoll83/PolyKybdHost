#!/usr/bin/env python3
"""Fetch + render the WPS Office (Writer, Spreadsheets, Presentation) icons.

Most actions are the same as in Microsoft Office, so their icons are copied
byte for byte from the Word, Excel and PowerPoint sets (`icon_fetch.borrow`).
The same picture then renders the same cell, and the overlay icon library
stores it once. The actions only WPS lists get Microsoft Fluent UI System Icons
(MIT). The three ESC program marks are drawn here in the shape of the WPS app
icons: a filled rounded square with a "W", a 2x2 grid or a "P" cut out. The
WPS artwork itself is a proprietary mark that Simple Icons does not carry, so it
is not copied. See SOURCES.md.

    pip install cairosvg
    python polyhost/res/overlay_sources/wps/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PIL import Image, ImageFont  # noqa: E402

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

# Icons that WPS shares with the Microsoft Office sets: {file: source app}.
BORROW = {
    # Word
    "new.png": "word", "open.png": "word", "save.png": "word", "saveas.png": "word",
    "print.png": "word", "copy.png": "word", "cut.png": "word", "paste.png": "word",
    "undo.png": "word", "redo.png": "word", "selectall.png": "word",
    "bold.png": "word", "italic.png": "word", "underline.png": "word",
    "font.png": "word", "hyperlink.png": "word", "fontdec.png": "word",
    "fontinc.png": "word", "subscript.png": "word", "left.png": "word",
    "center.png": "word", "right.png": "word", "justify.png": "word",
    "find.png": "word", "replace.png": "word", "goto.png": "word",
    "spelling.png": "word",
    # Excel
    "formatcells.png": "excel", "close.png": "excel", "flashfill.png": "excel",
    "filldown.png": "excel", "fillright.png": "excel", "filter.png": "excel",
    "autosum.png": "excel", "edit.png": "excel", "calc.png": "excel",
    # PowerPoint
    "newslide.png": "powerpoint", "group.png": "powerpoint",
    "ungroup.png": "powerpoint", "slideshow.png": "powerpoint",
    "fromcurrent.png": "powerpoint",
}

# Actions with no icon in the Microsoft sets.
FLUENT = {
    "trackchanges": "Document Edit",
    "wordcount": "Text Word Count",
    "translate": "Translate",
    "superscript": "Text Superscript",
    "distributed": "Text Align Distributed",
    "pagebreak": "Document Page Break",
    "updatefield": "Arrow Sync",
    "macro": "Script",
    "vbaeditor": "Code",
    "taskpane": "Panel Right",
    "chart": "Data Bar Vertical Add",
    "date": "Calendar Today",
    "time": "Clock",
    "insertcells": "Table Add",
    "repeat": "Arrow Repeat All",
    "deleteslide": "Delete",
}

# ESC program marks: {file: letter, or "grid" for the 2x2 grid}.
MARKS = {
    "wps_writer.png": "W",
    "wps_sheets.png": "grid",
    "wps_presentation.png": "P",
}

# The marks are drawn at the size the keycap shows them (the binding's
# `program_icon_region` is 37x32, so a square mark is 32x32 keycap pixels).
# `_fit_stamp` then copies them 1:1, which keeps the dither patterns exact.
PX = 32
SS = 32                 # supersample factor for the anti-aliased shapes
GLYPH_SHIFT = (-2, -2)  # keycap pixels: the glyph sits up and left, as in WPS
BAND = 3                # keycap pixels: width of the shaded bottom and side bands
BAND_SIDE = "left"      # which side gets the sparse band


def _shape(glyph: str) -> Image.Image:
    """The tile with `glyph` cut out, as a bool-able 'L' image of PX x PX."""
    from PIL import Image, ImageDraw

    u = PX * SS
    pad = SS                                    # one keycap pixel
    img = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=int(u * 0.18), fill=255)
    dx, dy = GLYPH_SHIFT[0] * SS, GLYPH_SHIFT[1] * SS
    if glyph == "grid":
        g0, g1 = int(u * 0.25), u - int(u * 0.25)
        w = int(u * 0.06)
        m = (g0 + g1) // 2
        d.rectangle([g0 + dx, g0 + dy, g1 + dx, g1 + dy], fill=0)
        for x0, y0, x1, y1 in ((g0 + w, g0 + w, m - w // 2, m - w // 2),
                               (m + w // 2, g0 + w, g1 - w, m - w // 2),
                               (g0 + w, m + w // 2, m - w // 2, g1 - w),
                               (m + w // 2, m + w // 2, g1 - w, g1 - w)):
            d.rectangle([x0 + dx, y0 + dy, x1 + dx, y1 + dy], fill=255)
    else:
        f = ImageFont.truetype(program_marks.BOLD, int(u * 0.52))
        box = d.textbbox((0, 0), glyph, font=f)
        cx = (u - (box[2] - box[0])) // 2 - box[0]
        cy = (u - (box[3] - box[1])) // 2 - box[1]
        d.text((cx + dx, cy + dy), glyph, font=f, fill=0)
    return img.resize((PX, PX), Image.LANCZOS).point(lambda v: 255 if v > 127 else 0)


def draw_mark(path: Path, glyph: str) -> None:
    """Rounded tile with `glyph` cut out and two dithered bands, as in WPS.

    The bottom BAND rows are a checkerboard (every second pixel lit). The
    BAND columns on BAND_SIDE are sparser: one pixel lit in each 2x2 block.
    White on transparent, so the binding uses `program_icon_mode: alpha`.
    """
    from PIL import Image

    lit = _shape(glyph).load()
    tile = _shape("").load()   # the tile alone, to find its edges
    xs = [x for x in range(PX) if any(tile[x, y] for y in range(PX))]
    ys = [y for y in range(PX) if any(tile[x, y] for x in range(PX))]
    side = range(xs[0], xs[0] + BAND) if BAND_SIDE == "left" else range(xs[-1] - BAND + 1, xs[-1] + 1)
    bottom = range(ys[-1] - BAND + 1, ys[-1] + 1)
    out = Image.new("RGBA", (PX, PX), program_marks.CLEAR)
    px = out.load()
    for y in range(PX):
        for x in range(PX):
            if not lit[x, y]:
                continue
            if x in side:
                on = x % 2 == xs[0] % 2 and y % 2 == ys[-1] % 2
            elif y in bottom:
                on = (x + y) % 2 == 0
            else:
                on = True
            if on:
                px[x, y] = program_marks.WHITE
    out.save(path)


def mark(path: Path, glyph: str) -> None:
    """Draw one program mark unless the file is already committed."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw_mark(path, glyph)
        print(f"  {path.name}  <- drawn program mark ({glyph!r})")


def main() -> None:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    for name, glyph in MARKS.items():
        mark(out / name, glyph)


if __name__ == "__main__":
    main()
