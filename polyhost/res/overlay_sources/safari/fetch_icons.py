#!/usr/bin/env python3
"""Fetch + render the Safari shortcut icons (reproducible).

Actions Safari shares with the other browsers reuse the Firefox set's cells,
copied unchanged, so a key looks the same in every browser. The Safari-only
actions are Microsoft Fluent UI System Icons (MIT) or Material Symbols
(Apache-2.0, `ms:` entries). ESC is left to the generic program mark.

    pip install cairosvg
    .venv/bin/python polyhost/res/overlay_sources/safari/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

BORROWED = {f: "firefox" for f in (
    "addressbar.png", "back.png", "closetab.png", "forward.png", "home.png",
    "nexttab.png", "prevtab.png", "reader.png", "reopentab.png", "settings.png",
    "lasttab.png", "tab1.png", "tab2.png", "tab3.png", "tab4.png", "tab5.png",
    "tab6.png", "tab7.png", "tab8.png", "bmsidebar.png",
)}

FLUENT = {
    "taboverview": "ms:grid_view",
    "readinglist": "Reading List",
    "addreading": "Reading List Add",
    "switchwindow": "Window Multiple",
    "pagetop": "Arrow Upload",
    "pagebottom": "Arrow Download",
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
