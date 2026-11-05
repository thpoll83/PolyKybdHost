#!/usr/bin/env python3
"""Fetch + render the GitKraken Desktop shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The git actions that GitHub
Desktop also has (commit, fetch, new branch, clone, ...) are copied from
`../githubdesktop/icons`, so both apps draw the same picture for the same action.
`tab1..tab9.png` are Fluent `Tab` with a digit and `fav1..fav9.png` Fluent
`Bookmark` with a digit, from `../number_badge.py`. The ESC mark is the GitKraken
logo from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/gitkraken/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402
import number_badge  # noqa: E402

FLUENT = {
    "shortcuts": "Keyboard",
    "stage": "Add Square",
    "unstage": "Subtract Square",
    "stageall": "Add Square Multiple",
    "unstageall": "Subtract Square Multiple",
    "stagecommit": "ms:done_all",
    "firstcommit": "ms:vertical_align_top",
    "lastcommit": "ms:vertical_align_bottom",
    "palette": "ms:keyboard_command_key",
    "searchcommits": "ms:manage_search",
    "openpalette": "Folder Search",
    "blame": "Document Search",
    "terminal": "Window Console",
    "terminalpanel": "ms:terminal",
    "filemanager": "Folder Open",
    "difftool": "ms:difference",
    "closetab": "Dismiss",
    "leftpanel": "Panel Left",
    "detailpanel": "Panel Right",
    "newtab": "Tab Add",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "reopentab": "ms:tab_recent",
    "tabslist": "ms:view_list",
    "init": "ms:create_new_folder",
    "openrepo": "ms:folder_open",
    "repomanagement": "ms:library_books",
    "_tabbase": "Tab",
    "_favbase": "Bookmark",
}

# Same action as in GitHub Desktop: copy that set's drawing byte for byte.
BORROW = {name: "githubdesktop" for name in (
    "commit.png", "fetch.png", "newbranch.png", "clone.png", "summary.png",
    "filter.png", "fullscreen.png", "resetzoom.png", "editor.png", "devtools.png",
)}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    number_badge.numbered(out / "_tabbase.png", "123456789", out, "tab")
    number_badge.numbered(out / "_favbase.png", "123456789", out, "fav",
                          size=44 / 96, centre=(0.50, 0.42))
    brand_marks.ensure(out / "gitkraken.png", "gitkraken")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
