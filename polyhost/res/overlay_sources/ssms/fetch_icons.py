#!/usr/bin/env python3
"""Fetch + render the SQL Server Management Studio shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Google Material Symbols
(Apache-2.0) for an `ms:` name. Where SSMS has the same command as Visual Studio
(SSMS is built on the Visual Studio shell), the glyph is the one
`../visualstudio/fetch_icons.py` uses, so the two sets draw those keys the same.

The ESC mark is drawn here (`draw_mark()`): Microsoft's SSMS icon is
proprietary, so the set ships a substitute, a database cylinder.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/ssms/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    # --- query ---
    "execute": "Play",
    "parse": "Checkmark Square",
    "estimatedplan": "Flowchart",
    "actualplan": "Flowchart Circle",
    "resultsgrid": "Table",
    "resultstext": "Text Align Left",
    "resultsfile": "Document Arrow Down",
    "resultspane": "Panel Bottom",          # as dbeaver "results"
    "togglepane": "ms:swap_vert",           # as dbeaver "switchpanel"
    "templateparams": "Braces Variable",
    "copywithheaders": "Table Copy",
    "querydesigner": "Table Edit",
    "refreshcache": "Arrow Sync",
    "sphelp": "Info",
    "spwho": "People",
    "splock": "Lock Closed",
    "newquery": "Window New",
    "nexterror": "Error Circle",
    # --- tool windows ---
    "objectexplorer": "Server",
    "objectdetails": "Apps List Detail",
    "registeredservers": "Server Multiple",
    "templateexplorer": "ms:library_books",
    "copilot": "Sparkle",
    "toolbox": "Toolbox",
    "browser": "Globe",
    "activitymonitor": "Pulse",
    "profiler": "ms:monitoring",
    "documentation": "Book Open",
    # --- shared with ../visualstudio (same Fluent / Material glyph) ---
    "newproject": "Folder Add",
    "openproject": "Folder Arrow Right",
    "addnewitem": "ms:library_add",
    "solutionexplorer": "ms:account_tree",
    "properties": "Wrench",
    "output": "Window Text",
    "nextdocument": "Tabs",
    "saveall": "Save Multiple",
    "navback": "Arrow Left",
    "navforward": "Arrow Right",
    "replaceinfiles": "Folder Swap",
    "clipboardring": "Clipboard Multiple",
    "lineopenabove": "ms:add_row_above",
    "lineopenbelow": "ms:add_row_below",
    "movelinedown": "ms:move_down",
    "rename": "Rename",
    # --- editing ---
    "uppercase": "ms:uppercase",
    "lowercase": "ms:lowercase",
    "selectword": "ms:match_word",
    "clearall": "Eraser",
}

MARK = "ssms.png"


def draw_mark(path: Path) -> None:
    """A database cylinder: an open lid over three filled bands.

    White on transparent at 256x256, drawn at 4x and downscaled, so the
    binding renders it with `program_icon_mode: alpha`.
    """
    ss = 4
    u = 256 * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white, clear = (255, 255, 255, 255), (0, 0, 0, 0)
    x0, x1 = int(u * 0.14), int(u * 0.86)
    ry = int(u * 0.11)                      # half-height of the end ellipses
    top, bottom = int(u * 0.08), int(u * 0.92)
    gap = int(u * 0.055)                    # vertical size of a band gap
    # body and bottom curve
    d.rectangle([x0, top + ry, x1, bottom - ry], fill=white)
    d.ellipse([x0, bottom - 2 * ry, x1, bottom], fill=white)
    # two curved gaps between the bands: knock out a crescent of height `gap`
    for f in (0.42, 0.66):
        y = int(u * f)                      # lower edge of the gap at the centre
        d.ellipse([x0, y - 2 * ry, x1, y], fill=clear)
        d.rectangle([x0, y - ry - gap, x1, y - ry], fill=clear)
        d.ellipse([x0, y - 2 * ry - gap, x1, y - gap], fill=white)
    # the lid: a ring, so the top reads as an ellipse and not a flat edge
    d.ellipse([x0, top, x1, top + 2 * ry], fill=white)
    w = int(u * 0.05)
    d.ellipse([x0 + w, top + w, x1 - w, top + 2 * ry - w], fill=clear)
    img.resize((256, 256), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    # Hand-editable: never clobber a committed mark.
    if (out / MARK).exists():
        print(f"  {MARK}  <- committed asset (left as-is)")
    else:
        draw_mark(out / MARK)
        print(f"  {MARK}  <- drawn program mark (database cylinder)")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
