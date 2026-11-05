#!/usr/bin/env python3
"""Fetch the foobar2000 shortcut icons.

Icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. Where the action is the same as in the
VLC set (open files, save playlist, add a URL, properties), the same glyph is
used. The ESC mark is the foobar2000 logo from Simple Icons (CC0 artwork;
nominative use, see `../brand_marks.py`). See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/foobar2000/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "search":         "Search",
    "newplaylist":    "ms:playlist_add",
    "removeplaylist": "ms:playlist_remove",
    "openfile":       "Document",
    "saveplaylist":   "Save",
    "addlocation":    "Globe",
    "preferences":    "Settings",
    "properties":     "Info",
    "ontop":          "Pin",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "foobar2000.png", "foobar2000")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
