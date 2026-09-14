#!/usr/bin/env python3
"""Fetch the Sticky Notes shortcut icons (reproducible source step).

All glyphs are Microsoft Fluent UI System Icons (MIT) — the house style across
every PolyKybd app overlay, and license-clean against the GPL-3.0-or-later host.

⚠️ Where an action also exists on the `notepad` / `notepadpp` overlays, the SAME
Fluent glyph is used on purpose, so the three text editors read alike: bold,
italic, underline, strikethrough, undo, redo, copy, cut, paste, select-all and
find are all shared.

⚠️ NO program mark is baked here. Sticky Notes runs inside `ONENOTE.EXE`, so the
mark cannot come from the app name either -- it is named by the mapping entry's
`icon:` key (see `ICON_APP` in handler/common.py), which is what stops a Sticky
Notes window drawing the OneNote logo.

    pip install cairosvg
    python polyhost/res/overlay_sources/stickynotes/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# filename -> Fluent folder name. Every one probed against
# raw.githubusercontent.com before being listed: there is no "Note Multiple",
# no "Sticky Note", no "Arrow Export Ltr".
FLUENT = {
    # --- the note itself -------------------------------------------------
    "newnote":    "Note Add",
    "closenote":  "Document Dismiss",
    "delnote":    "Delete",
    "noteslist":  "Apps List",
    # ⚠️ Cycling FORWARD and BACKWARD share one glyph family rather than one
    # glyph: "Arrow Repeat All" reads as a cycle, and the direction is carried
    # by the modifier on the keycap (Ctrl+Tab vs Ctrl+Shift+Tab), which the
    # firmware draws on separate layers anyway.
    "cyclefwd":   "Arrow Repeat All",
    "cycleback":  "Arrow Repeat All",
    # --- editing (shared with the notepad/notepadpp overlays) -------------
    "selectall":  "Select All On",
    "copy":       "Copy",
    "cut":        "Cut",
    "paste":      "Clipboard Paste",
    "undo":       "Arrow Undo",
    "redo":       "Arrow Redo",
    "find":       "Search",
    # --- caret motion ----------------------------------------------------
    "wordleft":   "Arrow Left",
    "wordright":  "Arrow Right",
    "notetop":    "Arrow Up",
    "notebottom": "Arrow Down",
    "delwordback": "Backspace",
    # --- formatting (shared) ---------------------------------------------
    "bold":       "Text Bold",
    "italic":     "Text Italic",
    "underline":  "Text Underline",
    "strike":     "Text Strikethrough",
    "bullets":    "Text Bullet List",
}


def _forward_delete(out: Path) -> None:
    """⌦ — the Backspace glyph mirrored, for "delete the NEXT word".

    ⚠️ Not a trash can, which is what the first cut drew. `Ctrl+D` (delete the
    whole note) is a trash can, so `Ctrl+Delete` (delete one word forward) drew
    the IDENTICAL picture -- two very different destructive actions, one glyph,
    on the same overlay. Caught by looking at the rendered sheet, not by reading
    the table.

    ⌫ and ⌦ are the real key symbols for this pair and Fluent ships only the
    first, so the second is the first flipped. Deterministic, so a re-run
    reproduces it byte for byte; the glyph is drawn white-on-transparent, and a
    mirror moves alpha exactly like colour.
    """
    src = out / "delwordback.png"
    img = Image.open(src).convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT)
    img.save(out / "delword.png")
    print("  delword.png  <- delwordback.png mirrored (forward delete)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    count = icon_fetch.fluent(FLUENT, out)
    _forward_delete(out)
    print(f"Wrote {count + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
