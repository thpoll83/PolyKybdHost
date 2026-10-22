#!/usr/bin/env python3
"""Fetch + render the GitHub Desktop shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the GitHub
logo from Simple Icons (CC0 artwork; nominative use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/githubdesktop/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "fullscreen": "Full Screen Maximize",
    "resetzoom": "ms:restart_alt",
    "narrower": "Panel Left Contract",
    "wider": "Panel Left Expand",
    "devtools": "Window Dev Tools",
    "newrepo": "ms:create_new_folder",
    "addlocal": "Folder Add",
    "clone": "ms:cloud_download",
    "repolist": "ms:library_books",
    "push": "Arrow Upload",
    "pull": "Arrow Download",
    "fetch": "Arrow Sync",
    "removerepo": "Folder Prohibited",
    "viewongithub": "Globe",
    "shell": "Window Console",
    "showfolder": "Folder Open",
    "editor": "Code",
    "openwith": "ms:open_in_new",
    "issue": "ms:adjust",
    "newworktree": "ms:account_tree",
    "changes": "ms:difference",
    "history": "History",
    "branches": "Branch",
    "worktrees": "ms:lan",
    "summary": "Text Edit Style",
    "commit": "ms:commit",
    "stash": "Archive",
    "filter": "Filter",
    "newbranch": "Branch Fork",
    "rename": "Rename",
    "deletebranch": "Delete",
    "discard": "Arrow Undo",
    "stashall": "Archive Arrow Back",
    "update": "Arrow Sync Circle",
    "compare": "ms:compare_arrows",
    "merge": "ms:merge",
    "squash": "ms:compress",
    "rebase": "ms:move_up",
    "compareongithub": "ms:compare",
    "branchongithub": "ms:open_in_browser",
    "previewpr": "Eye",
    "pullrequest": "Branch Request",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "github.png", "github")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
