#!/usr/bin/env python3
"""Fetch + render the Sourcetree shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The git actions that GitHub
Desktop also has (commit, push, pull, fetch, branch, merge, stash, ...) are
copied from `../githubdesktop/icons`, so both apps draw the same picture for
the same action. The ESC mark is the Sourcetree logo from Simple Icons (CC0
artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    PYTHONPATH=. python polyhost/res/overlay_sources/sourcetree/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "openrepo": "ms:folder_open",
    "closetab": "Dismiss",
    "newtab": "Tab Add",
    "refresh": "Arrow Clockwise",
    "refreshremote": "Cloud Sync",
    "searchview": "ms:manage_search",
    "reposettings": "ms:folder_managed",
    "commitall": "ms:done_all",
    "commitselected": "ms:playlist_add_check",
    "discardselected": "Arrow Reset",
    "checkout": "ms:alt_route",
    "tag": "Tag",
    "openfile": "Open",
    "externaldiff": "ms:compare",
    "add": "Add Square",
    "unstage": "Subtract Square",
    "remove": "Document Dismiss",
    "addremove": "Add Square Multiple",
    "logselected": "Document Bullet List Clock",
    "blame": "Person Search",
    "flownext": "ms:account_tree",
    "sidebar": "Panel Left",
    "repodetails": "Info",
    "commandhistory": "ms:receipt_long",
    "remotehosted": "Cloud",
    "bulletlist": "Text Bullet List",
    "numberedlist": "ms:format_list_numbered",
    "codeblock": "Code Block",
    "header": "Text Header 1",
    "hrule": "Line Horizontal 1",
    "link": "Link",
}

# Same action as in GitHub Desktop: copy that set's drawing byte for byte.
BORROW = {name: "githubdesktop" for name in (
    "clone.png", "commit.png", "push.png", "pull.png", "fetch.png", "newbranch.png",
    "merge.png", "stash.png", "discard.png", "changes.png", "history.png",
    "shell.png", "pullrequest.png", "viewongithub.png", "repolist.png",
    "filter.png", "fullscreen.png", "update.png",
)}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.borrow(BORROW, out)
    brand_marks.ensure(out / "sourcetree.png", "sourcetree")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
