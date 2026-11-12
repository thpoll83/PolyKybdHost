#!/usr/bin/env python3
"""Fetch + render the Mozilla Firefox shortcut icons (reproducible source step).

Three sources, in this order of preference:

1. **Borrowed from `chrome/icons/`, byte for byte.** Every action Firefox shares
   with Chromium (new tab, close tab, reload, find, zoom, tab 1..8, back, ...)
   draws the SAME cell as the Chrome set: same file, same placement keys in
   `bindings.yaml`, so the overlay cache stores it once board-wide and a user
   switching browsers sees the same picture for the same action. Firefox's
   "New private window" is Chrome's "New incognito window" and reuses that art.
2. **Derived from a borrowed icon** (mirrored), for the "other direction" of a
   borrowed action Chrome has no art for: Find previous. Guarded like any drawn
   asset, so a committed file is never overwritten.
3. **Microsoft Fluent UI System Icons (MIT)** -- the house style -- for the
   Firefox-only actions, and **Material Symbols (Apache-2.0)** via `ms:` where
   Fluent has no fitting glyph.

No ESC program mark is drawn: like `chrome_template`, ESC is left to the generic
program mark (the OS's own Firefox icon, else Simple Icons `firefox`). The
Firefox logo is a Mozilla trademark and is not redistributed here. See SOURCES.md.

Run from the repo root with the project venv:

    .venv/bin/python polyhost/res/overlay_sources/firefox/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# Identical actions: the Chrome set's reclaimed cells, copied unchanged.
BORROWED = {f: "chrome" for f in (
    "addressbar.png", "back.png", "bookmark.png", "closetab.png", "closetab_f4.png",
    "devtools.png", "downloads.png", "find.png", "findnext.png", "findnext_f3.png",
    "forward.png", "fullscreen.png", "history.png", "incognito.png", "lasttab.png",
    "newtab.png", "newwindow.png", "nexttab.png", "prevtab.png", "reload.png",
    "reload_f5.png", "reopentab.png",
    "tab1.png", "tab2.png", "tab3.png", "tab4.png", "tab5.png", "tab6.png",
    "tab7.png", "tab8.png", "zoomin.png", "zoomout.png", "zoomreset.png",
)}

# Firefox-only actions. Fluent folder names unless prefixed `ms:`.
FLUENT = {
    "websearch": "Globe Search",
    "pagesource": "Code",
    "pageinfo": "Info",
    "bmsidebar": "Bookmark Multiple",
    "bmtoolbar": "Star Line Horizontal 3",
    "bmalltabs": "Star Add",
    "library": "Library",
    "libhistory": "ms:manage_history",
    "addons": "Puzzle Piece",
    "hardreload": "Arrow Clockwise Dashes",
    "screenshot": "Screenshot",
    "closewindow": "Dismiss Square",
    "reopenwindow": "ms:reopen_window",
    "clearhistory": "History Dismiss",
    "textdirection": "Text Direction Horizontal Right",
    "mute": "Speaker Mute",
    "home": "Home",
    "caret": "ms:text_select_start",
    "reader": "Reading Mode Mobile",
    "pip": "Picture In Picture",
    "quit": "Power",
    "settings": "Settings",
    "minimize": "Subtract Square",
    "hide": "ms:visibility_off",
    "hideothers": "ms:hide_source",
    "stop": "Dismiss Circle",
    "findselection": "ms:find_in_page",
    "aichat": "Sparkle",
    "sidebar": "Panel Left",
    "tabssidebar": "Tab Desktop Multiple",
    "movetabright": "ms:tab_move",
    # DevTools panels
    "webconsole": "ms:terminal",
    "browserconsole": "Window Console",
    "inspector": "Cursor Hover",
    "network": "ms:lan",
    "debugger": "Bug",
    "responsive": "Phone Laptop",
    "styleeditor": "Paint Brush",
    "performance": "Top Speed",
    "storage": "Database",
    "accessibility": "Accessibility",
    "browsertoolbox": "Wrench Screwdriver",
}


def _mirror_in_place(src: Path, dest: Path) -> None:
    """Mirror the ink of a 72x40 cell left-right, keeping its bounding box where
    it was (so a bottom-right glyph stays bottom-right)."""
    im = Image.open(src).convert("RGBA")
    box = im.getchannel("A").getbbox() or (0, 0, im.width, im.height)
    flipped = im.crop(box).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(flipped, box[:2])
    out.save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.borrow(BORROWED, out)
    n += icon_fetch.fluent(FLUENT, out)

    # Derived (guarded): the left-pointing twins of borrowed / fetched glyphs.
    derived = {
        "findprev.png": out / "findnext.png",
        "findprev_f3.png": out / "findnext_f3.png",
        "movetableft.png": out / "movetabright.png",
    }
    for name, src in derived.items():
        dest = out / name
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            _mirror_in_place(src, dest)
            print(f"  {name}  <- mirrored {src.name}")
        n += 1
    print(f"{n} icons in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
