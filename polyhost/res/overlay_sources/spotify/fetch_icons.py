#!/usr/bin/env python3
"""Fetch + render the Spotify shortcut icons (reproducible).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries). The ESC mark is the
Spotify logo from Simple Icons (CC0 artwork; nominative use, see
`../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/spotify/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

FLUENT = {
    "search": "Search",
    "searchpage": "ms:manage_search",
    "help": "Keyboard",
    "filter": "Filter",
    "shuffle": "Arrow Shuffle",
    "repeat": "Arrow Repeat All",
    "like": "Heart",
    "contextmenu": "More Horizontal",
    "logout": "Sign Out",
    "library": "Library",
    "playlists": "ms:library_music",
    "podcasts": "ms:podcasts",
    "artists": "ms:artist",
    "albums": "ms:album",
    "audiobooks": "ms:auto_stories",
    "home": "Home",
    "nowplaying": "ms:music_note",
    "liked": "ms:heart_check",
    "madeforyou": "Person Heart",
    "newreleases": "ms:new_releases",
    "charts": "ms:trending_up",
    "queue": "ms:queue_music",
    "npsidebar": "Panel Right",
    "libsidebar": "Panel Left",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    brand_marks.ensure(out / "spotify.png", "spotify")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
