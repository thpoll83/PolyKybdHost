#!/usr/bin/env python3
"""Fetch + render the DeckCraft shortcut icons (reproducible).

* Glyphs shared with the PowerPoint overlay (same action, same picture) are
  copied byte-for-byte from `powerpoint/icons/`; the arrange-order arrows and
  the drawn guides cross come from `illustrator/icons/` (see `icon_fetch.borrow`).
* Everything else: Microsoft Fluent UI System Icons (MIT), Material Symbols
  (Apache-2.0) for the one gap (`ms:` prefix).
* Program icon (ESC): DeckCraft's OWN app icon (MIT OR Apache-2.0, storytold/
  deckcraft `assets/app-icon/hicolor/scalable/apps/ai.storyteller.deckcraft.svg`,
  pinned to the commit below). The orange background tile is dropped and the
  orange bars recoloured to the black ink so the board reads as linework at 1-bit
  (`luma`, t150). Guarded: a committed `deckcraft.png` is never re-rendered.

    PYTHONPATH=. python polyhost/res/overlay_sources/deckcraft/fetch_icons.py
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import cairosvg

from polyhost.res.overlay_sources import icon_fetch

COMMIT = "457406a7a5b62425e915926c8ccb0984e61a198c"
APP_ICON = ("https://raw.githubusercontent.com/storytold/deckcraft/" + COMMIT +
            "/assets/app-icon/hicolor/scalable/apps/ai.storyteller.deckcraft.svg")
BG_TILE = '<rect x="16" y="16" width="480" height="480" rx="111.84" fill="#f26b1d"/>'

BORROW = {
    # from the PowerPoint overlay (same action -> same glyph)
    "new.png": "powerpoint", "open.png": "powerpoint", "save.png": "powerpoint",
    "saveas.png": "powerpoint", "print.png": "powerpoint", "close.png": "powerpoint",
    "newslide.png": "powerpoint", "duplicate.png": "powerpoint",
    "copy.png": "powerpoint", "cut.png": "powerpoint", "paste.png": "powerpoint",
    "undo.png": "powerpoint", "redo.png": "powerpoint", "selectall.png": "powerpoint",
    "bold.png": "powerpoint", "italic.png": "powerpoint", "underline.png": "powerpoint",
    "hyperlink.png": "powerpoint", "group.png": "powerpoint", "ungroup.png": "powerpoint",
    "left.png": "powerpoint", "center.png": "powerpoint", "right.png": "powerpoint",
    "justify.png": "powerpoint", "fontinc.png": "powerpoint", "fontdec.png": "powerpoint",
    "copyformat.png": "powerpoint", "slideshow.png": "powerpoint",
    "fromcurrent.png": "powerpoint", "spelling.png": "powerpoint",
    # from the Illustrator overlay (arrange order + drawn guides cross)
    "tofront.png": "illustrator", "toback.png": "illustrator",
    "forward.png": "illustrator", "backward.png": "illustrator",
    "guides.png": "illustrator",
}

FLUENT = {
    "strikethrough": "Text Strikethrough",
    "superscript": "Text Superscript",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomfit": "Zoom Fit",
    "prefs": "Settings",
    "nextwindow": "Window Multiple",
    "ribbon": "Panel Top Contract",
    "filetab": "Document Briefcase",
    "mediaplay": "Video Play Pause",
    "gridlines": "Grid",
    "changecase": "Text Change Case",
    "edittext": "Rename",
    "delete": "Delete",
    "firstslide": "Arrow Previous",
    "lastslide": "Arrow Next",
    "prevslide": "Chevron Up",
    "nextslide": "Chevron Down",
    "regroup": "Group Return",
    "comment": "Comment Add",
    "animpainter": "Paint Brush Sparkle",
    "animapply": "Sparkle",
    "pastetext": "Clipboard Text Edit",
    "palette": "ms:manage_search",
}


def _draw_program_mark(path: Path) -> None:
    svg = urllib.request.urlopen(
        urllib.request.Request(APP_ICON, headers={"User-Agent": "polykybd"}), timeout=60).read().decode()
    if BG_TILE not in svg:
        raise RuntimeError("upstream app icon changed: background tile not found")
    board = svg.replace(BG_TILE, "").replace("#f26b1d", "#0b0b0c")
    cairosvg.svg2png(bytestring=board.encode(), write_to=str(path),
                     output_width=256, output_height=256)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.borrow(BORROW, out)
    icon_fetch.fluent(FLUENT, out)
    if (out / "deckcraft.png").exists():
        print("  deckcraft.png  <- committed asset (left as-is)")
    else:
        _draw_program_mark(out / "deckcraft.png")
        print(f"  deckcraft.png  <- storytold/deckcraft@{COMMIT[:8]} app icon (board only)")
    print(f"Wrote {len(BORROW) + len(FLUENT) + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
