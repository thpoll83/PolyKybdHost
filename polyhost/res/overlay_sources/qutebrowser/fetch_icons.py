#!/usr/bin/env python3
"""Fetch + render the qutebrowser shortcut icons (reproducible source step).

Three sources:

1. **Borrowed byte for byte** from `chrome/icons/` and `firefox/icons/` for
   every action the other browsers also have (new tab, close tab, reload, back,
   find, zoom, tab 1..8, ...). The bindings place them exactly as those sets
   do, so the overlay cache stores each cell once board-wide and a user who
   switches browsers sees the same picture for the same action.
2. **Microsoft Fluent UI System Icons (MIT)**, the house style, for the
   qutebrowser-only actions, and **Material Symbols (Apache-2.0)** via `ms:`
   where Fluent has no fitting glyph.
3. **The ESC mark**: the qutebrowser logo (`qutebrowser/icons/qutebrowser-256x256.png`
   at tag v3.7.0, GPL-3.0-or-later like the rest of the repository) reduced to
   a 32x32 1-bit trace with the LIGHT pixels lit, so the globe reads as a disc
   with the "qb" cut out of it. Drawn at keycap size so the generator copies it
   1:1, and guarded: a committed `qutebrowser.png` is never redrawn.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/qutebrowser/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# Actions qutebrowser shares with Chromium / Firefox: the same cells, copied.
BORROWED = {f: "chrome" for f in (
    "addressbar.png", "back.png", "bookmark.png", "closetab.png", "find.png",
    "findnext.png", "forward.png", "fullscreen.png", "incognito.png", "lasttab.png",
    "newtab.png", "newwindow.png", "nexttab.png", "prevtab.png", "reload.png",
    "reload_f5.png", "reopentab.png",
    "tab1.png", "tab2.png", "tab3.png", "tab4.png", "tab5.png", "tab6.png",
    "tab7.png", "tab8.png", "zoomin.png", "zoomout.png", "zoomreset.png",
)}
BORROWED.update({f: "firefox" for f in (
    "caret.png", "closewindow.png", "findprev.png", "hardreload.png", "home.png",
    "mute.png", "quit.png", "reopenwindow.png", "stop.png",
)})

# qutebrowser-only actions. Fluent folder names unless prefixed `ms:`.
FLUENT = {
    # opening pages
    "opentab": "Tab Add",
    "openbg": "ms:tab_unselected",
    "pasteopen": "ms:content_paste_go",
    "pasteopentab": "Clipboard Link",
    "tabselect": "ms:tab",
    "lasttabswap": "Arrow Swap",
    "pin": "Pin",
    # hints
    "hint": "ms:ads_click",
    "hinttab": "ms:open_in_new",
    "hintmenu": "Link",
    "follow": "Arrow Enter",
    "followtab": "Open",
    # scrolling and page navigation
    "scrollleft": "Arrow Left",
    "scrolldown": "Arrow Down",
    "scrollup": "Arrow Up",
    "scrollright": "Arrow Right",
    "scrollbottom": "ms:vertical_align_bottom",
    "pagedown": "ms:keyboard_double_arrow_down",
    "pageup": "ms:keyboard_double_arrow_up",
    "halfdown": "ms:keyboard_arrow_down",
    "halfup": "ms:keyboard_arrow_up",
    "prevpage": "ms:navigate_before",
    "nextpage": "ms:navigate_next",
    "prevpagetab": "ms:keyboard_double_arrow_left",
    "nextpagetab": "ms:keyboard_double_arrow_right",
    "increment": "ms:exposure_plus_1",
    "decrement": "ms:exposure_neg_1",
    # modes and commands
    "command": "ms:terminal",
    "searchback": "ms:manage_search",
    "insert": "ms:edit",
    "passthrough": "ms:keyboard",
    "linesel": "ms:subject",
    "setmark": "Location Add",
    "jumpmark": "ms:my_location",
    "repeat": "ms:repeat",
    "macrorecord": "Record",
    "macrorun": "Play Circle",
    # quickmarks, yank, downloads, print
    "qmsave": "ms:bookmark_add",
    "qmload": "ms:bookmarks",
    "qmloadtab": "ms:collections_bookmark",
    "yank": "ms:content_copy",
    "dlcancel": "ms:file_download_off",
    "print": "Print",
}

# The qutebrowser logo at the newest release tag. GPL-3.0-or-later (the
# repository's LICENSE; the README credits the icon to Jad / yelo).
QUTEBROWSER_ICON_URL = ("https://raw.githubusercontent.com/qutebrowser/qutebrowser/"
                        "v3.7.0/qutebrowser/icons/qutebrowser-256x256.png")
QUTEBROWSER_LIGHT_LUMA = 128


def _qutebrowser_mark(dest: Path, px: int = 32) -> None:
    """The qutebrowser logo as a px*px 1-bit trace: composited over black,
    contain-fitted into the square with LANCZOS, pixels brighter than luma 128
    lit. The light globe is lit and the dark "qb" stays dark; the other
    polarity (dark pixels lit) keeps only the "qb" and loses the globe."""
    req = urllib.request.Request(QUTEBROWSER_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    black = Image.new("RGBA", icon.size, "black")
    black.alpha_composite(icon)
    src = black.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 0)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v > QUTEBROWSER_LIGHT_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.borrow(BORROWED, out)
    n += icon_fetch.fluent(FLUENT, out)
    mark = out / "qutebrowser.png"
    if mark.exists():
        print(f"  {mark.name}  <- committed asset (left as-is)")
    else:
        _qutebrowser_mark(mark)
        print(f"  {mark.name}  <- qutebrowser logo, 32x32 1-bit trace")
    n += 1
    print(f"{n} icons in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
