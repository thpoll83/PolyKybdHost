#!/usr/bin/env python3
"""Shared icon source for game overlays: **game-icons.net** (CC BY 3.0).

The game sets use game-icons.net because the app icon sets (Fluent, Material
Symbols) have no game shapes: no catapult, anvil, barracks or windmill. A
comparison of four sources on the 72x40 keycap (2026-10-22) kept this one.

⚠️ CC BY 3.0 requires credit to each icon's AUTHOR, not only to the site.
Every set that uses this module lists, in its `SOURCES.md`, each file with its
`author/name` and the licence. `render()` prints that line for each icon.

Icons are named `author/name`, as in the site's URLs
(https://game-icons.net/1x1/lorc/anvil.html is `lorc/anvil`).

    from polyhost.res.overlay_sources import game_icons
    game_icons.render({"blacksmith": "lorc/anvil"}, out_dir)
"""
from __future__ import annotations

from pathlib import Path

import cairosvg

from polyhost.res.overlay_sources.icon_fetch import _get

# Black on a transparent ground, so the overlays render it in `alpha` mode.
URL = "https://game-icons.net/icons/000000/transparent/1x1/{}.svg"
RENDER_PX = 128
LICENCE = "CC BY 3.0"


def render(mapping: dict[str, str], out_dir: Path, render_px: int = RENDER_PX) -> int:
    """Render `{filename_stem: "author/name"}` into `out_dir` as RGBA PNGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, name in mapping.items():
        svg = _get(URL.format(name))
        png = cairosvg.svg2png(bytestring=svg, output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- game-icons.net/{name} ({LICENCE}, by {name.split('/')[0]})")
    return len(mapping)
