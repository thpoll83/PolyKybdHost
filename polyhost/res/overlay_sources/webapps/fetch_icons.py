#!/usr/bin/env python3
"""Fetch + render icons for the browser-hosted app overlays.

One icon folder serves five sets — `github.yaml`, `gitlab.yaml`,
`confluence.yaml`, `googledocs.yaml` and `notion.yaml`. They are grouped
because they share a large command vocabulary (search, edit, comment, submit,
and the markdown/rich-text formatting run of bold/italic/link/lists/headings);
duplicating ~30 identical PNGs five times would be pure noise in the tree.

Style route: **Microsoft Fluent UI System Icons (MIT)**. The five ESC
**program marks** are drawn, license-clean substitutes (`../program_marks.py`) —
the GitHub, GitLab, Atlassian, Google and Notion logos are all trademarks we
may not redistribute.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/webapps/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import material_symbols as ms  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # --- shared: navigation & chrome ---
    "search": "Search",
    "commandpalette": "Apps List Detail",
    "shortcuts": "Keyboard",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "newpage": "Document Add",
    "open": "Folder Open",
    "save": "Save",
    "print": "Print",
    "duplicate": "Square Multiple",
    "darkmode": "Weather Moon",
    "settings": "Settings",
    "sidebar": "Panel Left",
    "rightsidebar": "Panel Right",
    "newtab": "Tab Desktop",
    "closetab": "Dismiss",
    "graph": "Branch Fork",
    # --- shared: editing ---
    "edit": "Document Edit",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "pasteplain": "Clipboard Paste",
    "selectall": "Select All On",
    "find": "Search",
    "findreplace": "Arrow Swap",
    "findfiles": "Document Search",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "strikethrough": "Text Strikethrough",
    "code": "Code",
    "codeblock": "Code Block",
    "link": "Link",
    "quote": "Text Quote",
    "clearfmt": "Text Clear Formatting",
    "superscript": "Text Superscript",
    "subscript": "Text Subscript",
    "fontinc": "Text Font",
    "fontdec": "Text Font Size",
    "indent": "Text Indent Increase",
    "outdent": "Text Indent Decrease",
    "heading1": "Text Header 1",
    "heading2": "Text Header 2",
    "heading3": "Text Header 3",
    "normaltext": "Text Paragraph",
    "bulletlist": "Text Bullet List",
    "todo": "Checkbox Checked",
    "togglelist": "Chevron Right",
    "table": "Table Simple",
    "wordcount": "Text Word Count",
    "alignleft": "Text Align Left",
    "aligncenter": "Text Align Center",
    "alignright": "Text Align Right",
    "alignjustify": "Text Align Justify",
    "comment": "Comment",
    "addcomment": "Chat Add",
    "submit": "Send",
    "preview": "Eye",
    "publish": "Rocket",
    # --- GitHub / GitLab specific ---
    "filefinder": "Document Search",
    "branch": "Branch",
    "blame": "History",
    "canonical": "Link",
    "webide": "Code",
    "createissue": "Add Circle",
    "openitem": "Open",
    "reviewer": "Person Add",
    "assignee": "Person",
    "label": "Tag",
    "milestone": "Flag",
    "nextfile": "Chevron Right",
    "prevfile": "Chevron Left",
    "nextthread": "Arrow Down",
    "prevthread": "Arrow Up",
    "filebrowser": "Folder Open",
    "diffcomments": "Comment Multiple",
    "annotations": "Note",
}

MARKS = {
    "gh.png": ("G", "brackets"),
    "gl.png": ("GL", "brackets"),
    "cf.png": ("C", "corner"),
    "gd.png": ("D", "corner"),
    "nt.png": ("N", "corner"),
}


# Fluent ships NO ordered-list glyph (every "Text Number List *" name 404s), and
# its nearest match, "Text Number Format", draws "ABC 123" -- that reads as
# alphanumeric formatting, not a numbered list. This is exactly the gap Material
# Symbols (Apache-2.0, GPL-3.0-compatible) is kept around to fill.
MATERIAL = {"numberlist": "format_list_numbered"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    for stem, name in MATERIAL.items():
        ms.render(name, out / f"{stem}.png", weight=300)
        print(f"  {stem}.png  <- material-symbols/{name}")
    n += len(MATERIAL)
    for fname, (letter, motif) in MARKS.items():
        program_marks.ensure(out / fname, letter, motif=motif)
    print(f"Wrote {n} icons (+ {len(MARKS)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
