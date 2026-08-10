#!/usr/bin/env python3
"""Fetch + render the LibreOffice shortcut icons (reproducible source step).

One icon folder serves all three modules — `writer.yaml`, `calc.yaml` and
`impress.yaml` share `icon_dir: icons`, because the LibreOffice modules share a
large common command set (file, clipboard, find, character formatting) and only
diverge in their module-specific tail.

Style route: **Microsoft Fluent UI System Icons (MIT)**. The three ESC
**program marks** are drawn, license-clean substitutes (`../program_marks.py`) —
one per module, distinguished by initial + motif (document / grid / screen).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/libreoffice/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import doc_mark, icon_fetch  # noqa: E402
import material_symbols as ms  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # --- shared across all three modules ---
    "new": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "print": "Print",
    "quit": "Dismiss",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pastespecial": "Clipboard Paste",
    "selectall": "Select All On",
    "find": "Search",
    "replace": "Arrow Swap",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "clearfmt": "Text Clear Formatting",
    "spelling": "Text Grammar Wand",
    "styles": "Text Effects",
    "navigator": "Compass Northwest",
    # --- Writer ---
    "doubleunderline": "Text Underline Double",
    "center": "Text Align Center",
    "left": "Text Align Left",
    "right": "Text Align Right",
    "justify": "Text Align Justify",
    "bodytext": "Text Paragraph",
    "heading1": "Text Header 1",
    "heading2": "Text Header 2",
    "heading3": "Text Header 3",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "unorderedlist": "Text Bullet List",
    "createstyle": "Star Emphasis",
    "updatestyle": "Arrow Sync",
    "lastpos": "Arrow Undo",
    # --- Calc ---
    "editcell": "Table Cell Edit",
    "absref": "Money",
    "recalc": "Arrow Sync",
    "recalcall": "Arrow Repeat All",
    "formatcells": "Table Simple",
    "selectcolumn": "Table Insert Column",
    "selectrow": "Table Insert Row",
    "selectallcells": "Table Simple",
    "insertcells": "Table Add",
    "deletecells": "Table Delete Row",
    "showformulas": "Calculator",
    "groupdata": "Group",
    "fmtdecimal": "Text Number Format",
    "fmtexp": "Text Superscript",
    "fmtdate": "Calendar",
    "fmtcurrency": "Money",
    "fmtpercent": "Circle Half Fill",
    # --- Impress ---
    "slideshow": "Slide Play",
    "duplicateslide": "Slide Multiple",
    "edittext": "Text T",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "combine": "Layer",
    "tofront": "Position Forward",
    "backward": "Position Backward",
}

# Label per module. ⚠️ "IMPRESS" does NOT fit inside the page at Fluent's native
# aspect ratio (interior ~26px, the word needs 25px + clearance) — see doc_mark's
# header. Stretching the page to fit it was tried and rejected.
DOC_MARKS = {"writer": "WRITER", "calc": "CALC", "impress": "IMPR"}


# See webapps/fetch_icons.py: Fluent has no ordered-list glyph, so this one
# comes from Material Symbols (Apache-2.0).
MATERIAL = {"orderedlist": "format_list_numbered"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    for stem, name in MATERIAL.items():
        ms.render(name, out / f"{stem}.png", weight=300)
        print(f"  {stem}.png  <- material-symbols/{name}")
    n += len(MATERIAL)
    # Program marks: Fluent `Document` frame + motif + module name, placed by
    # geometry (see doc_mark). build() asserts nothing touches the page outline.
    for app, label in DOC_MARKS.items():
        dest = out / f"lo_{app}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        r = doc_mark.build(app, [label], page_h=39.6, stretch=1.0, save=dest)
        assert r and r[1] == 0 and r[2] == 0, f"{app}: content touches the page outline: {r}"
        print(f"  {dest.name}  <- fluent Document + '{r[0]}' (0 touching, 0 outside)")
    print(f"Wrote {n} icons (+ {len(DOC_MARKS)} document marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
