#!/usr/bin/env python3
"""Fetch + render the Sublime Text shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)**, plus the shared
custom-drawn editor glyphs (`../editor_glyphs.py`) for multiple cursors and
line ops.

This folder serves BOTH Sublime sets: the Windows/Linux `bindings.yaml` here and
the macOS `../sublime_mac/bindings.yaml`, which points its `icon_dir` back at
this directory. Same app, same actions, same artwork -- only the chords differ,
so duplicating ~40 PNGs would be pure noise. The ESC **program mark** is a drawn substitute
(`../program_marks.py`) — Sublime HQ's logo is proprietary.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/sublime/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import editor_glyphs  # noqa: E402
import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

FLUENT = {
    # navigation -- Sublime's "Goto Anything" family
    "gotoanything": "Document Search",
    "commandpalette": "Apps List Detail",
    "gotosymbol": "Code",
    "gotoline": "Text Number Format",
    "gotoword": "Text Word Count",
    # find / replace
    "find": "Search",
    "replace": "Arrow Swap",
    "findinfiles": "Folder Open",
    "selectalloccur": "Select All On",
    # editing
    "indent": "Text Indent Increase",
    "unindent": "Text Indent Decrease",
    "comment": "Comment",
    "blockcomment": "Comment Multiple",
    "duplicate": "Row Triple",
    "joinlines": "Text Wrap Off",
    "cutline": "Cut",
    "swapup": "Arrow Sort Up",
    "swapdown": "Arrow Sort Down",
    "matchbracket": "Braces",
    "selectbrackets": "Braces",
    "autocomplete": "Text Grammar Wand",
    "insertafter": "Arrow Enter",
    "insertbefore": "Arrow Enter",
    "pasteindent": "Clipboard Paste",
    "softundo": "Arrow Undo",
    "redo": "Arrow Redo",
    # view / tabs / build
    "build": "Play",
    "closetab": "Dismiss",
    "reopentab": "Tab Desktop",
    "sidebar": "Panel Left",
    "fold": "Text Collapse",
    "unfold": "Text Expand",
    "bookmark": "Bookmark",
    "wraptag": "Code",
    # macOS-only actions (see ../sublime_mac/bindings.yaml -- it shares this folder)
    "cycletableft": "Chevron Left",
    "cycletabright": "Chevron Right",
    "gotosymbolproject": "Folder Search",
    "syntaxinfo": "Info",
}

DRAWN = ["multicursor", "cursorabove", "cursorbelow", "deleteline", "selectline"]


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += editor_glyphs.draw_all(out, DRAWN)
    program_marks.ensure(out / "sublime.png", "S", motif="brackets")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
