#!/usr/bin/env python3
"""Fetch + render the PdfCraft shortcut icons (reproducible source step).

PdfCraft (github.com/storytold/pdfcraft, MIT OR Apache-2.0) is an Acrobat-like
PDF workbench in Rust/egui. Its keymap is the app's OWN command registry
(`crates/engine/src/commands.rs`) plus the document view's keys
(`crates/ui-egui/src/canvas.rs::shortcuts`, `lib.rs::tool_keys`), not Acrobat's;
see SOURCES.md for every chord and its file:line.

Style: Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, the house
style. Glyphs that also exist in the Word overlay (the reference document app)
are COPIED from `word/icons/` so the same action draws the same cell.

The ESC program mark is PdfCraft's OWN icon (the engraved lion on green,
`assets/app-icon/pdfcraft.ico`, MIT OR Apache-2.0, 64 px frame). Guarded, so a
re-run never clobbers a committed `progmark.png`.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/pdfcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
PDFCRAFT_SHA = "b5467d93a0ffaa5e5e6658bccdf8655a3ba689c9"
PDFCRAFT_ICO = ("https://raw.githubusercontent.com/storytold/pdfcraft/"
                f"{PDFCRAFT_SHA}/assets/app-icon/pdfcraft.ico")

# Same action as the Word overlay -> same art (byte-identical copy).
FROM_WORD = {
    "open.png": "word",
    "save.png": "word",
    "saveas.png": "word",
    "close.png": "word",
    "print.png": "word",
    "undo.png": "word",
    "redo.png": "word",
    "find.png": "word",
    "copy.png": "word",
    "selectall.png": "word",
}

FLUENT = {
    "closeall":     "Dismiss Square Multiple",
    "properties":   "Info",
    "advsearch":    "Document Search",
    "palette":      "Apps List Detail",       # as aichat/obsidian/sublime/webapps
    "fitvisible":   "Arrow Fit",
    "fitpage":      "Page Fit",
    "fitwidth":     "Arrow Autofit Width",
    "actualsize":   "Ratio One To One",
    "zoomin":       "Zoom In",
    "zoomout":      "Zoom Out",
    "rotatecw":     "Arrow Rotate Clockwise",
    "rotateccw":    "Arrow Rotate Counterclockwise",
    "prevview":     "Arrow Hook Up Left",
    "nextview":     "Arrow Hook Up Right",
    "fullscreen":   "Full Screen Maximize",
    "readmode":     "Book Open",
    "gotopage":     "Document Page Number",
    "settings":     "Settings",
    "jsconsole":    "Window Console",
    "bookmarkadd":  "Bookmark Add",
    "select":       "Cursor",
    "hand":         "Hand Right",
    "delete":       "Delete",
    "firstpage":    "Previous",
    "lastpage":     "Next",
    "prevpage":     "Chevron Left",
    "nextpage":     "Chevron Right",
    "finish":       "Checkmark",
    "apply":        "Checkmark Circle",
    "_arrowup":     "Arrow Up",           # input to the composed findprev.png
}


def _compose_findprev(out: Path) -> None:
    """Find previous: the Search glyph with an up arrow beside it (no stock
    glyph says 'search backwards'; Chevron Left is already Previous page).
    Built from the Fluent PNGs above, so it inherits their MIT licence.
    Guarded: a committed findprev.png is left as-is."""
    dest = out / "findprev.png"
    if dest.exists():
        print("  findprev.png  <- committed asset (left as-is)")
        return
    from PIL import Image
    search = Image.open(out / "find.png").convert("RGBA")
    arrow = Image.open(out / "_arrowup.png").convert("RGBA").resize((64, 64), Image.LANCZOS)
    canvas = Image.new("RGBA", (140, 96), (0, 0, 0, 0))
    canvas.alpha_composite(search, (0, 0))
    canvas.alpha_composite(arrow, (76, 16))
    canvas.save(dest)
    print("  findprev.png  <- composed (word find.png + ms-fluent/Arrow Up)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(FROM_WORD, out)
    _compose_findprev(out)
    program_marks.own_icon(out / "progmark.png", PDFCRAFT_ICO, 64,
                           credit="storytold/pdfcraft assets/app-icon/pdfcraft.ico")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
