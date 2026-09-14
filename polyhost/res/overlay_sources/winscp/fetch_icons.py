#!/usr/bin/env python3
"""Fetch + render the WinSCP shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`.

The ESC **program mark is WinSCP'S OWN LOGO**, which is the best possible answer
and is available here for a reason worth stating: **WinSCP is GPL-3.0**, and this
host is GPL-3.0-or-later, so its artwork can simply be redistributed. That is not
true of most of the apps this repo draws marks for -- the Office and Adobe logos
are proprietary and no catalog carries them either, which is why those overlays
settle for a drawn or curated generic. When an app is free software, ASK FOR ITS
OWN ICON FIRST.

⚠️ This replaced the curated generic `mdi:folder-network`, which in turn had
replaced a drawn two-panels-and-an-arrow mark. Both were approximations of an app
whose real mark was redistributable all along.

⚠️ Rendered `mode: bright` from the .ico's **64x64 frame**. The logo is three
overlapping gradient-filled shapes -- an up-left arrow, a padlock and a
down-right arrow -- and what has to survive 1-bit at 40 px is that they stay
apart. `bright` lights the pale fills and leaves the dark outlines unlit, which
does that; `alpha` lights the whole badge as one solid blob (the alpha channel
IS the badge) and every `luma` threshold is a dark smear.

⚠️ The FRAME choice is not "bigger is better", which is what it looks like:
measured at the shipped settings, 64 / 128 / 256 all render to within one lit
pixel of each other (545 / 544 / 544), so 64 is simply the smallest frame that
has converged. 40 and 48 are the ones that differ -- both drop the keyhole, and
the shackle detaches from the lock body at 40 and fuses into it at 48. Render
the sweep rather than reasoning from the source before changing either.

Shortcuts come from WinSCP's OWN documentation (Commander Keyboard Shortcuts),
so this is the documented set. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/winscp/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import program_marks  # noqa: E402
import prompt_glyph  # noqa: E402
import number_badge  # noqa: E402

FLUENT = {
    # transfer -- the app's whole purpose
    "download":  "Arrow Download",
    "upload":    "Arrow Upload",
    "copyfiles": "Copy",
    "movefiles": "Arrow Forward",
    "duplicate": "Document Multiple",
    "sync":      "Cloud Sync",
    "keepuptodate": "Arrow Sync Checkmark",
    "queue":     "Timer",
    "processqueue": "Play",
    # files
    "rename":    "Rename",
    "edit":      "Text Edit Style",
    "editnew":   "Document Add",
    "newfolder": "Folder Add",
    "delete":    "Delete",
    "props":     "Info",
    "link":      "Link",
    "compare":   "Document Split Hint",
    "find":      "Document Search",
    "incsearch": "Search",
    # selection
    "selectall":   "Select All On",
    "deselectall": "Select All Off",
    "restoresel":  "Arrow Counterclockwise",
    "copynames":   "Clipboard Letter",
    "copypaths":   "Clipboard Link",
    "copylocal":   "Panel Left",
    "copyremote":  "Panel Right",
    "paste":       "Clipboard Paste",
    # navigation
    "reread":    "Arrow Sync",
    "parent":    "Folder Arrow Up",
    "root":      "Home",
    "homedir":   "Home",
    "back":      "Arrow Circle Left",
    "forward":   "Arrow Circle Right",
    "bookmark":  "Star",
    "bookmarks": "Bookmark Multiple",
    "pathleft":  "Panel Left",
    "pathright": "Panel Right",
    "tree":      "Organization",
    # tabs & session
    "newtab":     "Tab Add",
    "newsession": "Server",
    "newlocaltab": "Window New",
    "closetab":   "Dismiss Square",
    "nexttab":    "Arrow Right",
    "prevtab":    "Arrow Left",
    "reconnect":  "Plug Connected",
    "tab":        "Tab",
    # tools & view
    "putty":      "Open",
    "prefs":      "Settings",
    "commandline": "Text Grammar Settings",
    "explorer":   "Folder Open",
    "hidden":     "Eye Off",
    "filter":     "Filter",
    "autorefresh": "Arrow Repeat All",
    "syncbrowse": "Arrow Swap",
    "switchpanel": "Arrow Swap",
    "quit":       "Power",
    # sorting (Ctrl+F3..F9)
    "sortname":  "Text Sort Ascending",
    "sortext":   "Filter",
    "sorttime":  "Calendar",
    "sortsize":  "Data Bar Vertical",
    "sortattrs": "Options",
    "sortowner": "Person",
    "sortgroup": "People",
}


WINSCP_ICO = ("https://raw.githubusercontent.com/winscp/winscp/master/"
              "source/resource/Application.ico")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Alt+<N> switches to tab N -- the number IS the information, so it goes
    # inside the Tab glyph (see number_badge).
    n += number_badge.numbered(out / "tab.png", "1234567890", out, "tab")

    # ⚠️ Fluent has NO terminal glyph -- its "Prompt" is the AI-prompt sparkle,
    # which is what shipped here first and read as nothing to do with a shell.
    # `prompt_glyph` draws the `>_` (see that module for why Fluent has none);
    # frameless, since a frame here would read as a second window.
    prompt_glyph.ensure(out / "terminal.png",
                        what="bare `>_` shell prompt")
    n += 1

    program_marks.own_icon(out / "progmark.png", WINSCP_ICO, 64,
                           credit="winscp/winscp Application.ico")
    n += 1
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
