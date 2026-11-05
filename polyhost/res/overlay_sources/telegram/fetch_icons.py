#!/usr/bin/env python3
"""Fetch + render the Telegram Desktop shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). `folder1..folder6.png` and
`chat1..chat8.png` are Fluent `Folder` and `Chat Empty` with a digit, from
`../number_badge.py`. The ESC mark is the Telegram logo from Simple Icons (CC0
artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/telegram/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402
import number_badge  # noqa: E402

FLUENT = {
    # --- window ---
    "closewindow": "Dismiss",
    "closeothers": "Dismiss Square Multiple",
    "reopenwindow": "Window New",
    "lock": "Lock Closed",
    "minimize": "ms:minimize",
    "quit": "Power",
    # --- chat list ---
    "search": "Search",
    "nextchat": "Arrow Circle Down",
    "prevchat": "Arrow Circle Up",
    "firstchat": "ms:vertical_align_top",
    "lastchat": "ms:vertical_align_bottom",
    "nextfolder": "Folder Arrow Right",
    "prevfolder": "Folder Arrow Left",
    "lastfolder": "ms:last_page",
    "saved": "Bookmark",
    "archive": "Archive",
    "contacts": "People",
    "chatmenu": "More Vertical",
    "chatpreview": "Eye",
    "voice": "Mic",
    # --- message formatting ---
    "bold": "Text Bold",
    "italic": "Text Italic",
    "underline": "Text Underline",
    "strike": "Text Strikethrough",
    "mono": "Code",
    "quote": "Text Quote",
    "spoiler": "Eye Off",
    "clearformat": "Text Clear Formatting",
    "link": "Link",
    # --- bases for the numbered composites ---
    "_folderbase": "Folder",
    "_chatbase": "Chat Empty",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    number_badge.numbered(out / "_folderbase.png", "123456", out, "folder")
    number_badge.numbered(out / "_chatbase.png", "12345678", out, "chat",
                          size=48 / 96, centre=(0.52, 0.48))
    brand_marks.ensure(out / "telegram.png", "telegram")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
