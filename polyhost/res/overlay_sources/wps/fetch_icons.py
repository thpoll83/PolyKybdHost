#!/usr/bin/env python3
"""Fetch + render the WPS Office (Writer, Spreadsheets, Presentation) icons.

Most actions are the same as in Microsoft Office, so their icons are copied
byte for byte from the Word, Excel and PowerPoint sets (`icon_fetch.borrow`).
The same picture then renders the same cell, and the overlay icon library
stores it once. The actions only WPS lists get Microsoft Fluent UI System Icons
(MIT). The three ESC program marks are drawn letter tiles
(`program_marks.letter_mark`), because the WPS logo is a proprietary mark that
Simple Icons does not carry. See SOURCES.md.

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

# ESC program marks: {file: (letter, motif)}.
MARKS = {
    "wps_writer.png": ("W", "corner"),
    "wps_sheets.png": ("S", "grid"),
    "wps_presentation.png": ("P", "screen"),
}


def main() -> None:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    for name, (letter, motif) in MARKS.items():
        program_marks.ensure(out / name, letter, motif=motif)


if __name__ == "__main__":
    main()
