#!/usr/bin/env python3
"""Fetch + render the GNOME Files (Nautilus) shortcut icons (reproducible).

Style route: Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, the house
style of every other overlay. Concepts (Copy, Paste, Undo, ...) are drawn by the
shared renderer, so they need no file here.

The ESC program mark is NAUTILUS'S OWN symbolic icon
(`org.gnome.Nautilus-symbolic.svg`, the filing-cabinet drawer GNOME shows in the
top bar). Nautilus is GPL-3.0-or-later and this host is GPL-3.0-or-later, so it
ships as is. The symbolic variant is drawn for one colour at 16 px, which is
what a 1-bit keycap needs; the full-colour `org.gnome.Nautilus.svg`
(CC-BY-SA 4.0) is gradient-shaded and smears at 40 px. Guarded: a committed
`nautilus.png` is left as-is, so a hand edit survives a re-run.

Shortcuts come from Nautilus 46 itself (the version Ubuntu 24.04 ships): the
shortcuts window `src/resources/gtk/help-overlay.ui` plus the accelerator tables
in `nautilus-application.c`, `nautilus-window.c` and `nautilus-files-view.c`.
See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/nautilus/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

FLUENT = {
    "newwindow":    "Window New",
    "newtab":       "Tab Add",
    "close":        "Dismiss",
    "quit":         "Sign Out",
    "search":       "Search",
    "searchall":    "Globe Search",
    "location":     "Location",
    "bookmark":     "Bookmark Add",
    "hidden":       "Eye",
    "selectmatch":  "Filter",
    "invertsel":    "Select All Off",
    "link":         "Link",
    "linkhere":     "Link Square",
    "properties":   "Info",
    "open":         "Open",
    "opentab":      "Tab Desktop Arrow Clockwise",
    "openwindow":   "Window Arrow Up",
    "openlocation": "Folder Arrow Right",
    "listview":     "ms:view_list",
    "gridview":     "ms:grid_view",
    "zoomin":       "Zoom In",
    "zoomout":      "Zoom Out",
    "zoomreset":    "Ratio One To One",
    "preferences":  "Settings",
    "prevtab":      "Arrow Previous",
    "nexttab":      "Arrow Next",
    "movetableft":  "Chevron Double Left",
    "movetabright": "Chevron Double Right",
    "restoretab":   "History",
    "newfolder":    "Folder Add",
    "rename":       "Rename",
    "trash":        "Delete",
    "deleteperm":   "Delete Dismiss",
    "back":         "Arrow Left",
    "forward":      "Arrow Right",
    "up":           "Arrow Up",
    "down":         "Arrow Down",
    "home":         "Home",
    "sidebar":      "Panel Left",
    "menu":         "Navigation",
    "help":         "Question Circle",
    "shortcuts":    "Keyboard",
    "root":         "Hard Drive",
}

MARK_URL = ("https://raw.githubusercontent.com/GNOME/nautilus/gnome-46/"
            "data/icons/hicolor/symbolic/apps/org.gnome.Nautilus-symbolic.svg")


def main() -> None:
    out = Path(__file__).resolve().parent / "icons"
    icon_fetch.fluent(FLUENT, out)
    mark = out / "nautilus.png"
    if mark.exists():
        print("  nautilus.png  <- committed asset (left as-is)")
    else:
        svg = icon_fetch._get(MARK_URL)
        mark.write_bytes(cairosvg.svg2png(bytestring=svg, output_width=96, output_height=96))
        print("  nautilus.png  <- GNOME/nautilus gnome-46 org.gnome.Nautilus-symbolic.svg")


if __name__ == "__main__":
    main()
