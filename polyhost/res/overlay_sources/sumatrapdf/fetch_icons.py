#!/usr/bin/env python3
"""Fetch + render the SumatraPDF shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). `tab1.png`..`tab9.png` are
borrowed unchanged from `../winscp/icons` (Fluent `Tab` + digit). ESC is left to
the generic program mark (the OS icon of SumatraPDF.exe).

    pip install cairosvg
    python polyhost/res/overlay_sources/sumatrapdf/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

BORROWED = {f"tab{d}.png": "winscp" for d in "123456789"}

FLUENT = {
    # --- file ---
    "newwindow": "Window New",
    "close": "Document Dismiss",
    "saveas": "Save Edit",
    "saveannots": "Save Copy",
    "rename": "Rename",
    "properties": "Info",
    "quit": "Power",
    "openinwindow": "ms:open_in_new",
    # --- navigation ---
    "gotopage": "ms:move_down",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "favorite": "Star Add",
    "prevpage": "Arrow Circle Up",
    "nextpage": "Arrow Circle Down",
    "prevfile": "ms:skip_previous",
    "nextfile": "ms:skip_next",
    "findnext": "ms:manage_search",
    "findprev": "ms:search_off",
    "nexttab": "ms:tab",
    "prevtab": "ms:tab_move",
    "recenttab": "ms:history",
    # --- view ---
    "singlepage": "Document",
    "facing": "ms:auto_stories",
    "bookview": "Book Open",
    "rotateleft": "Arrow Rotate Counterclockwise",
    "rotateright": "Arrow Rotate Clockwise",
    "presentation": "ms:co_present",
    "fullscreen": "Full Screen Maximize",
    "bookmarks": "Bookmark Multiple",
    "toc": "ms:toc",
    "toolbar": "ms:toolbar",
    "menubar": "ms:menu",
    "caret": "ms:text_select_start",
    # --- zoom ---
    "fitpage": "ms:fit_screen",
    "actualsize": "ms:1x_mobiledata",
    "fitwidth": "ms:fit_page_width",
    "fitcontent": "ms:center_focus_strong",
    "customzoom": "ms:zoom_in_map",
    # --- single keys ---
    "scrolldown": "ms:keyboard_arrow_down",
    "scrollup": "ms:keyboard_arrow_up",
    "scrollleft": "ms:keyboard_arrow_left",
    "scrollright": "ms:keyboard_arrow_right",
    "reload": "ms:refresh",
    "flippage": "ms:menu_book",
    "cyclezoom": "ms:zoom_in",
    "continuous": "ms:view_day",
    "pageinfo": "ms:description",
    "invert": "ms:invert_colors",
    "cursorpos": "ms:my_location",
    "highlight": "Highlight",
    "underline": "ms:format_underlined",
    # --- other ---
    "palette": "ms:terminal",
    "help": "ms:help",
}


def main() -> int:
    here = Path(__file__).resolve().parent
    out = here / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for name, app in BORROWED.items():
        shutil.copyfile(here.parent / app / "icons" / name, out / name)
        print(f"  {name}  <- ../{app}/icons/{name}")
    icon_fetch.fluent(FLUENT, out)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
