#!/usr/bin/env python3
"""Fetch and draw the Total Commander shortcut icons.

Icons are Microsoft Fluent UI System Icons (MIT) and one Material Symbol
(Apache-2.0), both through `icon_fetch`. Where an action is the same as in the
7-Zip File Manager set (view, edit, move, new folder, sort keys), the same
Fluent glyph is used, so both sets draw the same cell. The two drive badges
are drawn here. The ESC mark is a drawn letter tile, because the Total
Commander logo is proprietary shareware art. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/totalcmd/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

FLUENT = {
    # F-key row (same glyphs as sevenzip/ where the action is the same)
    "reread":      "Arrow Sync",
    "view":        "Eye",
    "edit":        "Text Edit Style",
    "copyto":      "Copy Arrow Right",
    "moveto":      "Arrow Forward",
    "newfolder":   "Folder Add",
    "panelmenu":   "Navigation",
    "menubar":     "Window Header Horizontal",
    # Shift + F-keys
    "columns":     "Table Simple",
    "compare":     "Arrow Bidirectional Left Right",
    "viewone":     "Document One Page",
    "newfile":     "Document Add",
    "copyhere":    "Copy Add",
    "rename":      "Rename",
    "mkdirtarget": "Folder Arrow Right",
    "deleteperm":  "Delete Dismiss",
    "contextmenu": "More Vertical",
    # Alt + F-keys
    "altviewer":   "Eye Tracking",
    "lister":      "Document Search",
    "exit":        "Power",
    "pack":        "Archive",
    "movetoarc":   "Archive Multiple",
    "unpack":      "Archive Arrow Back",
    "testarc":     "Shield Checkmark",
    "find":        "Search",
    "findproc":    "Search Square",
    "cmdhistory":  "Window Console",
    "treedialog":  "Folder Search",
    "breadcrumb":  "Location",
    "buttonbar":   "Toolbox",
    "history":     "History",
    "back":        "Arrow Left",
    "forward":     "Arrow Right",
    "props":       "Info",
    "dirsizes":    "Calculator",
    # Ctrl + F-keys: views, sort, filters
    "brief":       "Text Bullet List Square",
    "full":        "Document Table",
    "thumbs":      "Image Multiple",
    "comments":    "Comment Multiple",
    "sortname":    "Text Sort Ascending",
    "sortext":     "Document",
    "sortdate":    "Calendar",
    "sortsize":    "Data Bar Vertical",
    "unsorted":    "Arrow Sort",
    "tree":        "Text Bullet List Tree",
    "print":       "Print",
    "allfiles":    "Document Multiple",
    "programs":    "Apps",
    "userfiles":   "Document Settings",
    # Ctrl + letters and navigation
    "parent":      "Folder Arrow Up",
    "root":        "Home",
    "openarchive": "Folder Zip",
    "showleft":    "Panel Left",
    "showright":   "Panel Right",
    "selectfile":  "Select Object",
    "switchpanel": "Arrow Swap",
    "branch":      "Branch Fork",
    "hotlist":     "Bookmark Multiple",
    "ftpconnect":  "Globe",
    "ftpnew":      "Globe Add",
    "ftpdisconnect": "Plug Disconnected",
    "ftpmode":     "Arrow Repeat All",
    "gotarget":    "Arrow Turn Right",
    "calcspace":   "Calculator",
    "multirename": "ms:edit_note",
    "pathtocmd":   "Text Field",
    "quickview":   "Panel Right Expand",
    "quickviewwin": "Window New",
    "quickfilter": "Filter",
    "lastfilter":  "Filter Sync",
    "newtab":      "Tab Add",
    "tablist":     "Tab Desktop Multiple",
    "exchange":    "Folder Swap",
    "closetab":    "Dismiss",
    "closetabs":   "Dismiss Square Multiple",
    "comment":     "Comment Note",
    "opentab":     "Folder Open",
    "opentabother": "Arrow Export Up",
    "nexttab":     "Arrow Next",
    "prevtab":     "Arrow Previous",
    "shortcuts":   "Link",
}

# Drive badges for Alt+F1 / Alt+F2: a rounded outline with a drive letter
# notation inside. Drawn at 4x the 36x32 key area and reduced, so the outline
# stays 2 px.
BADGES = {
    "driveleft":  "L:",
    "driveright": "R:",
}
W, H, S = 36, 32, 4


def _badge(path: Path, text: str) -> None:
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    stroke = 2 * S
    pad = stroke // 2 + S
    d.rounded_rectangle([pad, 4 * S, W * S - pad, H * S - 4 * S],
                        radius=6 * S, outline=white, width=stroke)
    font = ImageFont.truetype(BOLD, 15 * S)
    d.text(((W * S) / 2, (H * S) / 2), text, font=font, fill=white, anchor="mm")
    img.resize((W, H), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, text in BADGES.items():
        _badge(out / f"{name}.png", text)
    program_marks.ensure(out / "progmark.png", "TC")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
