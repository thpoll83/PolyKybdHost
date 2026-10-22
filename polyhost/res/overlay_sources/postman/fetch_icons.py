#!/usr/bin/env python3
"""Fetch + render the Postman shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). `tab1..tab8.png` are Fluent
`Tab` with a digit, from `../number_badge.py`. The ESC mark is the Postman logo
from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/postman/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402
import number_badge  # noqa: E402

FLUENT = {
    "newtab": "Tab Add",
    "closetab": "Dismiss",
    "forceclosetab": "Dismiss Square",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "lasttab": "ms:last_page",
    "reopentab": "ms:tab_recent",
    "url": "Link",
    "saveas": "Save Edit",
    "send": "Send",
    "senddownload": "ms:cloud_download",
    "torequest": "ms:vertical_align_top",
    "toresponse": "ms:vertical_align_bottom",
    "sidebar": "Panel Left",
    "rightsidebar": "Panel Right",
    "swapsidebars": "ms:swap_horiz",
    "rename": "Rename",
    "group": "Folder Add",
    "moveup": "Arrow Up",
    "movedown": "Arrow Down",
    "duplicate": "Copy Add",
    "findreplace": "ms:find_replace",
    "import": "ms:input",
    "shortcuts": "Keyboard",
    "newwindow": "Window New",
    "runner": "ms:play_circle",
    "twopane": "ms:vertical_split",
    "universalsearch": "ms:travel_explore",
    "clearconsole": "ms:clear_all",
    "console": "Window Console",
    "workbench": "ms:handyman",
    "resetlayout": "ms:restart_alt",
    "resetzoom": "ms:fit_screen",
    "closewindow": "Dismiss Circle",
    "back": "Arrow Left",
    "forward": "Arrow Right",
    "switchpane": "ms:flip_to_front",
    "devtools": "Window Dev Tools",
    "_tabbase": "Tab",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_tabbase.png", "12345678", out, "tab")
    brand_marks.ensure(out / "postman.png", "postman")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
