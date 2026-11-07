#!/usr/bin/env python3
"""Fetch + render the LabVIEW shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Icons for the same action as a MATLAB key
are byte copies of the MATLAB set's (BORROW). The ESC mark is a 32x32 1-bit
trace of NI's site icon (see SOURCES.md); it is traced only when the PNG is
missing, so a committed or hand-edited mark is never redrawn.

    pip install cairosvg
    python polyhost/res/overlay_sources/labview/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.typingtests.fetch_icons import (  # noqa: E402
    _guarded, _load, trace_mark)

FLUENT = {
    "forward": "ms:flip_to_front",
    "backward": "ms:flip_to_back",
    "tofront": "ms:vertical_align_top",
    "toback": "ms:vertical_align_bottom",
    "realign": "ms:align_horizontal_left",
    "redistribute": "ms:horizontal_distribute",
    "cleanup": "ms:cleaning_services",
    "actualsize": "Ratio One To One",
    "searchresults": "ms:manage_search",
    "nextwindow": "ms:switch_right",
    "prevwindow": "ms:switch_left",
    "errorlist": "ms:error",
    "showinproject": "ms:account_tree",
    "allwindows": "Window Multiple",
    "classbrowser": "ms:category",
    "nigel": "Sparkle",
    "panelswap": "ms:swap_horiz",
    "quickdrop": "ms:bolt",
    "grid": "ms:grid_4x4",
    "tile": "ms:vertical_split",
    "viprops": "ms:info",
    "history": "ms:history",
    "debugwin": "ms:bug_report",
    "quickopen": "ms:file_open",
    "saveall": "Save Multiple",
    "quit": "ms:logout",
    "contexthelp": "ms:help_center",
    "lockhelp": "ms:lock",
    "help": "ms:help",
    "runmode": "ms:toggle_on",
    "brokenwires": "ms:link_off",
    "fontup": "ms:text_increase",
    "fontdown": "ms:text_decrease",
    "fontstyle": "ms:text_format",
}

# Same action as a MATLAB Editor key: byte copies of the MATLAB icons.
BORROW = {f"{n}.png": "matlab" for n in (
    "findnext", "findprev", "maximize", "stepin", "stepover", "stepout",
    "run", "stop")}
BORROW_AS = {"newvi.png": ("matlab", "newscript.png"),
             "fullview.png": ("matlab", "resetzoom.png")}

# NI's site icon (the NI mark), from Google's favicon service, 180 px. The
# LabVIEW application icon itself could not be fetched (see SOURCES.md).
MARK_URL = "https://www.google.com/s2/favicons?domain=ni.com&sz=256"
MARK_LUMA = 180
MARK_DARK_LIT = True


def _crop_to_ink(icon, luma: int):
    """The icon cut to the box of its pixels at `luma` or darker: the favicon
    puts the mark on a light grey square that would shrink it to 60 %."""
    from PIL import Image
    flat = Image.new("RGBA", icon.size, "white")
    flat.alpha_composite(icon)
    box = flat.convert("L").point(lambda v: 255 if v <= luma else 0).getbbox()
    return icon.crop(box)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    here = Path(__file__).resolve().parent.parent
    for name, (app, src) in sorted(BORROW_AS.items()):
        dest = out / name
        if dest.exists():
            print(f"  {name}  <- committed asset (left as-is)")
        else:
            dest.write_bytes((here / app / "icons" / src).read_bytes())
            print(f"  {name}  <- copied from {app}/icons/{src}")
    _guarded(out / "labview.png",
             lambda p: trace_mark(_crop_to_ink(_load(MARK_URL), MARK_LUMA), p, MARK_LUMA, MARK_DARK_LIT))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
