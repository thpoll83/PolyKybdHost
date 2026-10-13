#!/usr/bin/env python3
"""Fetch + render the GridCraft shortcut icons (reproducible).

GridCraft (github.com/storytold/gridcraft, MIT OR Apache-2.0) is an egui
spreadsheet that imitates Excel. Glyphs are Microsoft Fluent UI System Icons
(MIT, the house style) via `icon_fetch.fluent`, with Material Symbols
(Apache-2.0, `ms:`) for the few gaps. Where the action matches the Excel
overlay, the SAME Fluent glyph is used (see ../excel/fetch_icons.py), so the
two apps draw identical cells.

Derived icons: the hide/unhide COLUMNS glyphs are the rows glyphs
(Arrow Minimize/Maximize Vertical) rotated 90 degrees; Fluent has no
horizontal cut. The three "select to ..." glyphs are Material `select` (dotted
box) with the matching go-to arrow composited inside.

The program mark (ESC) is GridCraft's OWN app icon (assets/app-icon/gridcraft.ico,
64px frame, MIT OR Apache-2.0), guarded so a re-run never clobbers it.

    cd <repo> && PYTHONPATH=. python polyhost/res/overlay_sources/gridcraft/fetch_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from polyhost.res.overlay_sources import icon_fetch, program_marks

GRIDCRAFT_SHA = "84acf6293b1dc1fc09837524e035d674eb4d6741"
APP_ICON = (f"https://raw.githubusercontent.com/storytold/gridcraft/{GRIDCRAFT_SHA}"
            "/assets/app-icon/gridcraft.ico")

ICONS = {
    # file
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "saveas": "Save Edit",
    "close": "Document Dismiss",
    "print": "Print",
    # edit
    "copy": "Copy",
    "cut": "Cut",
    "paste": "Clipboard Paste",
    "pastespecial": "ms:content_paste_go",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "selectall": "Select All On",
    "find": "Search",
    "replace": "Arrow Swap",
    "goto": "Target",
    "filldown": "Arrow Down",
    "fillright": "Arrow Right",
    "flashfill": "Flash",
    "clear": "Eraser",
    "editcell": "Edit",
    "absref": "Lock Closed",
    # format
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "strike": "Text Strikethrough",
    "hyperlink": "Link",
    "formatcells": "Table Settings",
    "font": "Text Font",
    "fontinc": "Font Increase",
    "fontdec": "Font Decrease",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "fmtgeneral": "Text Number Format",
    "fmtnumber": "Number Symbol",
    "fmttime": "Clock",
    "fmtdate": "Calendar",
    "fmtcurrency": "Money",
    "fmtsci": "Text Superscript",
    "borderoutside": "Border Outside",
    "bordernone": "Border None",
    "borderleft": "Border Left",
    "borderright": "Border Right",
    "bordertop": "Border Top",
    "borderbottom": "Border Bottom",
    # cells / rows / columns
    "tableadd": "Table Add",
    "delcells": "Table Delete Row",
    "insertcells": "Table Insert Row",
    "hiderows": "Arrow Minimize Vertical",
    "unhiderows": "Arrow Maximize Vertical",
    "region": "ms:select",
    "insertdate": "Calendar Add",
    "inserttime": "Clock Arrow Download",
    "formulaabove": "Arrow Hook Down Left",
    "valueabove": "ms:vertical_align_bottom",
    # data / formulas
    "filter": "Filter",
    "sort": "Arrow Sort",
    "group": "Group List",
    "ungroup": "Group Dismiss",
    "statistics": "Data Histogram",
    "autosum": "Math Formula",
    "showformulas": "Eye",
    "insertfunction": "ms:function",
    "calc": "Calculator",
    "calcsheet": "Calculator Multiple",
    "definename": "Tag",
    "namemanager": "Tag Multiple",
    "createnames": "ms:new_label",
    "errorcheck": "Warning",
    "spelling": "Text Proofing Tools",
    "macros": "Code",
    # comments
    "comment": "Comment Add",
    "note": "Note Add",
    # sheets / navigation / view
    "insertsheet": "Tab Add",
    "insertchart": "Data Bar Vertical Add",
    "nextsheet": "Document Arrow Right",
    "prevsheet": "Document Arrow Left",
    "screenright": "Chevron Double Right",
    "screenleft": "Chevron Double Left",
    "gostart": "Arrow Up Left",
    "goend": "Arrow Down Right",
    "rowstart": "Arrow Previous",
    "selectbox": "ms:select",       # base of the three select-to composites
    "dropdown": "ms:arrow_drop_down_circle",
    "contextmenu": "More Horizontal",
    "ribbon": "Panel Top Contract",
    "keytips": "Keyboard",
}

# Derived: the column variants are the row glyphs turned 90 degrees.
ROTATED = {"hidecols": "hiderows", "unhidecols": "unhiderows"}

# Derived: "select to ..." = the dotted selection box with the matching go-to
# arrow inside it, so it reads as the selecting twin of the plain go-to key.
COMPOSITES = {"extendstart": "gostart", "extendend": "goend", "extendrow": "rowstart"}
ARROW_PX = 56


def _composite(out: Path, dst: str, arrow: str) -> None:
    base = Image.open(out / "selectbox.png").convert("RGBA")
    arr = Image.open(out / f"{arrow}.png").convert("RGBA").resize((ARROW_PX, ARROW_PX), Image.LANCZOS)
    off = (base.width - ARROW_PX) // 2
    base.alpha_composite(arr, (off, off))
    base.save(out / f"{dst}.png")
    print(f"  {dst}.png  <- selectbox.png + {arrow}.png ({ARROW_PX}px)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(ICONS, out)
    for dst, src in ROTATED.items():
        Image.open(out / f"{src}.png").convert("RGBA").rotate(90, expand=True).save(out / f"{dst}.png")
        print(f"  {dst}.png  <- {src}.png rotated 90")
    for dst, arrow in COMPOSITES.items():
        _composite(out, dst, arrow)
    program_marks.own_icon(out / "gridcraft.png", APP_ICON, frame=64,
                           credit="storytold/gridcraft assets/app-icon/gridcraft.ico (MIT OR Apache-2.0)")
    print(f"Wrote {n + len(ROTATED) + len(COMPOSITES) + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
