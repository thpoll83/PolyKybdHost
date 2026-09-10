#!/usr/bin/env python3
"""Fetch + render the WinSCP shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** via `icon_fetch`. The
ESC **program mark** is DRAWN here: two panels with an arrow between them, which
is what WinSCP is. A letter tile was rejected -- "W" collides with Word/WordPad
and "SCP" does not fit the tile at a readable size.

Shortcuts come from WinSCP's OWN documentation (Commander Keyboard Shortcuts),
so this is the documented set. See SOURCES.md.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/winscp/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
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


def _draw_panels_mark(path: Path) -> None:
    """Program mark: two panels with a transfer arrow between them.

    Drawn rather than lettered: WinSCP's own icon is its project artwork, and the
    shared letter tile has no good letter here -- "W" is already Word/WordPad and
    "SCP" will not fit the tile at a readable size. Two panels and an arrow is
    what the app IS, and it reads at 37x32 px. White on transparent, so the
    binding renders it with `mode: alpha`.
    """
    ss = 4
    u = 256 * ss
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    w = int(u * 0.05)
    top, bot = u * 0.16, u * 0.84
    pw = u * 0.30                      # panel width
    d.rounded_rectangle([u * 0.06, top, u * 0.06 + pw, bot], radius=int(u * 0.05),
                        outline=white, width=w)
    d.rounded_rectangle([u * 0.94 - pw, top, u * 0.94, bot], radius=int(u * 0.05),
                        outline=white, width=w)
    # transfer arrow, left -> right, through the gap
    y = u * 0.50
    d.line([(u * 0.40, y), (u * 0.60, y)], fill=white, width=int(u * 0.055))
    d.polygon([(u * 0.62, y), (u * 0.50, y - u * 0.075), (u * 0.50, y + u * 0.075)],
              fill=white)
    img.resize((256, 256), Image.LANCZOS).save(path)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Alt+<N> switches to tab N -- the number IS the information, so it goes
    # inside the Tab glyph (see number_badge).
    n += number_badge.numbered(out / "tab.png", "1234567890", out, "tab")

    # ⚠️ Fluent has NO terminal glyph -- its "Prompt" is the AI-prompt sparkle,
    # which is what shipped here first and read as nothing to do with a shell.
    # `prompt_glyph` draws the `>_` (shared with the Windows Terminal overlay);
    # frameless, since a frame here would read as a second window.
    prompt_glyph.ensure(out / "terminal.png", frame=False,
                        what="bare `>_` shell prompt")
    n += 1

    # ⚠️ Guarded so a re-run never clobbers a hand-tuned mark.
    if (out / "winscp.png").exists():
        print("  winscp.png  <- committed program mark (left as-is)")
    else:
        _draw_panels_mark(out / "winscp.png")
        print("  winscp.png  <- custom (drawn: two panels + transfer arrow)")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
