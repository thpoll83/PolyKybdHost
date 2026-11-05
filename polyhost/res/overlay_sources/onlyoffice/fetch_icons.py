#!/usr/bin/env python3
"""Fetch + render the ONLYOFFICE Desktop Editors icons (Document, Spreadsheet,
Presentation).

Actions that the Microsoft Office, WPS Office and LibreOffice sets already draw
are copied from those sets byte for byte (`icon_fetch.borrow`), so the same
action renders the same cell and the overlay icon library stores it once. The
other actions get Microsoft Fluent UI System Icons (MIT) or Material Symbols
(Apache-2.0). Inserted characters (the copyright sign, the euro sign, the
number formats) are drawn here as text. The ESC program mark is the ONLYOFFICE
logo from Simple Icons (CC0-1.0 artwork, nominative use; see SOURCES.md).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/onlyoffice/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

# Icons another office set already draws: {file: source folder}.
BORROW = {
    # Word
    "open.png": "word", "save.png": "word", "saveas.png": "word",
    "print.png": "word", "close.png": "word", "copy.png": "word",
    "cut.png": "word", "paste.png": "word", "undo.png": "word",
    "redo.png": "word", "selectall.png": "word", "bold.png": "word",
    "italic.png": "word", "underline.png": "word", "find.png": "word",
    "replace.png": "word", "hyperlink.png": "word", "subscript.png": "word",
    "fontdec.png": "word", "fontinc.png": "word", "left.png": "word",
    "center.png": "word", "right.png": "word", "justify.png": "word",
    "bullets.png": "word", "clearfmt.png": "word", "indent.png": "word",
    "copyformat.png": "word",
    # Excel
    "strike.png": "excel", "edit.png": "excel", "filter.png": "excel",
    "table.png": "excel", "delcells.png": "excel",
    "calc.png": "excel", "absref.png": "excel", "formatcells.png": "excel",
    # PowerPoint
    "newslide.png": "powerpoint", "duplicate.png": "powerpoint",
    "group.png": "powerpoint", "ungroup.png": "powerpoint",
    "slideshow.png": "powerpoint",
    # WPS Office
    "superscript.png": "wps", "pagebreak.png": "wps", "updatefield.png": "wps",
    "insertcells.png": "wps", "date.png": "wps", "time.png": "wps",
    # LibreOffice
    "heading1.png": "libreoffice", "heading2.png": "libreoffice",
    "heading3.png": "libreoffice",
}

# Actions no other set draws: {file stem: Fluent folder or "ms:<material>"}.
FLUENT = {
    "comments": "Comment Multiple",
    "addcomment": "Comment Add",
    "filepanel": "Navigation",
    "help": "Question Circle",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomreset": "Ratio One To One",
    "nexttab": "Arrow Next",
    "prevtab": "Arrow Previous",
    "pasteplain": "Clipboard Letter",
    "applystyle": "Paint Brush Arrow Down",
    "outdent": "Text Indent Decrease",
    "pagenumber": "Document Page Number",
    "nonprinting": "ms:format_paragraph",
    "columnbreak": "Text Column Two",
    "endnote": "Document Endnote",
    "footnote": "Text Footnote",
    "equation": "Math Formula",
    "function": "ms:function",
    "fillrange": "Paint Bucket",
    "cellnewline": "Text Wrap",
    "dropdown": "Chevron Circle Down",
    "pivot": "Table Lightning",
    "pivotall": "Arrow Sync Circle",
    "summaryrow": "Table Bottom Row",
    "recalcsheet": "Arrow Sync",
    "slideup": "Arrow Up",
    "slidedown": "Arrow Down",
    "slidefirst": "Chevron Double Up",
    "slidelast": "Chevron Double Down",
}

# Inserted characters and number formats, drawn as text: {file: text}.
TEXT = {
    "copyright.png": "©",
    "euro.png": "€",
    "registered.png": "®",
    "trademark.png": "™",
    "ellipsis.png": "…",
    "endash.png": "–",
    "emdash.png": "—",
    "nbhyphen.png": "nb-",
    "nbspace.png": "␣",
    "unicode.png": "U+",
    "fmtgeneral.png": "Gen",
    "fmtcurrency.png": "$",
    "fmtpercent.png": "%",
    "fmtexp.png": "E+",
    "fmtdate.png": "d/m",
    "fmttime.png": "h:m",
    "fmtnumber.png": "0.0",
    "sigma.png": "Σ",
    "showformulas.png": "=A1",
}

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TEXT_PX = 96          # canvas size; the generator scales it into the region
TEXT_FILL = 0.80      # the text's larger side fills this share of the canvas


def draw_text(path: Path, text: str) -> None:
    """`text` centred on a 96x96 transparent canvas, white, as large as fits."""
    ss = 4
    u = TEXT_PX * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = u
    while size > 8:
        font = ImageFont.truetype(FONT, size)
        x0, y0, x1, y1 = d.textbbox((0, 0), text, font=font)
        if max(x1 - x0, y1 - y0) <= u * TEXT_FILL:
            break
        size -= 4
    d.text(((u - (x1 - x0)) // 2 - x0, (u - (y1 - y0)) // 2 - y0), text,
           font=font, fill=(255, 255, 255, 255))
    img.resize((TEXT_PX, TEXT_PX), Image.LANCZOS).save(path)


def main() -> None:
    out = HERE / "icons"
    out.mkdir(exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    for name, text in TEXT.items():
        if (out / name).exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            draw_text(out / name, text)
            print(f"  {name}  <- drawn text {text!r}")
    brand_marks.ensure(out / "onlyoffice.png", "onlyoffice")


if __name__ == "__main__":
    main()
