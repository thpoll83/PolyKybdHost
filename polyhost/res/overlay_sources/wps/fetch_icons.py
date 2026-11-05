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


def grid_mark(path: Path) -> None:
    """Rounded tile with a 2x2 grid cut out: a square frame and a cross.

    White on transparent, like `program_marks.letter_mark`, so the binding uses
    `program_icon_mode: alpha`.
    """
    from PIL import Image, ImageDraw

    u = program_marks.SIZE * program_marks.SS
    pad = int(u * 0.055)
    img = Image.new("RGBA", (u, u), program_marks.CLEAR)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=int(u * 0.18),
                        fill=program_marks.WHITE)
    g0, g1 = int(u * 0.25), u - int(u * 0.25)   # grid square
    w = int(u * 0.06)                           # line width
    clear = program_marks.CLEAR
    d.rectangle([g0, g0, g1, g1], fill=clear)
    m = (g0 + g1) // 2
    cells = [(g0 + w, g0 + w, m - w // 2, m - w // 2),
             (m + w // 2, g0 + w, g1 - w, m - w // 2),
             (g0 + w, m + w // 2, m - w // 2, g1 - w),
             (m + w // 2, m + w // 2, g1 - w, g1 - w)]
    for box in cells:
        d.rectangle(box, fill=program_marks.WHITE)
    img.resize((program_marks.SIZE, program_marks.SIZE), Image.LANCZOS).save(path)


def mark(path: Path, glyph: str) -> None:
    """Draw one program mark unless the file is already committed."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    elif glyph == "grid":
        grid_mark(path)
        print(f"  {path.name}  <- drawn program mark (2x2 grid)")
    else:
        program_marks.letter_mark(path, glyph)
        print(f"  {path.name}  <- drawn program mark ('{glyph}')")


def main() -> None:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    for name, glyph in MARKS.items():
        mark(out / name, glyph)


if __name__ == "__main__":
    main()
