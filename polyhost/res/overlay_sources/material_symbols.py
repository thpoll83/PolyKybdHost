#!/usr/bin/env python3
"""Shared icon source: **Google Material Symbols** (reproducible fetch helper).

Material Symbols are **Apache-2.0** licensed. PolyKybdHost is now
**GPL-3.0-or-later** (relicensed 2026-06), and GPLv3 *is* Apache-2.0-compatible —
so this set is license-clean to bundle as rendered 1-bit overlay assets. (Under
the project's previous GPL-2.0 it would NOT have been: the FSF treats Apache-2.0
as GPLv2-incompatible. This is the icon set the relicense unblocked.)

It sits alongside the other peer sources used by the per-app `fetch_icons.py`:
  * Microsoft Fluent UI System Icons   - MIT
  * KDE Breeze                          - LGPLv3
  * Google Material Symbols (this file) - Apache-2.0

Status: **backup / comparison source only.** Fluent (MIT) is the house style for
every app overlay; a full Photoshop+Illustrator A/B (2026-06) kept Fluent. Reach
for Material to fill a gap Fluent lacks, or to cherry-pick one of the glyphs it
draws better (`tune`, `filter_b_and_w`, `invert_colors`, `line_weight`,
`library_add`, `format_shapes`, `join_inner`, `grid`). Render at **weight 250-300**
for keycap legibility: `wght200` is too thin to survive the 1-bit/40 px downscale
and the bare default (~400) is a touch heavy.

Usage from an app's `fetch_icons.py`::

    from polyhost.res.overlay_sources import material_symbols as ms
    ms.render("content_cut", out_dir / "cut.png", weight=300)  # outlined, 96px
    ms.render("visibility", out_dir / "eye.png", fill=True)    # filled variant

Browse / pick names at https://fonts.google.com/icons (the icon's name in
snake_case is its asset name, e.g. "content_cut", "filter_alt", "priority_high").
Record `source: material-symbols/<name> (Apache-2.0)` per binding, same as the
Fluent/Breeze entries.

    pip install cairosvg
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import cairosvg

# Per-icon SVGs live in the google/material-design-icons repo under symbols/web/.
RAW = ("https://raw.githubusercontent.com/google/material-design-icons/master/"
       "symbols/web/{name}/materialsymbols{style}/{file}")
STYLES = ("outlined", "rounded", "sharp")
RENDER_PX = 96


def asset_path(name: str, style: str = "outlined", fill: bool = False,
               weight: int | None = None) -> str:
    """Repo-relative path of a Material Symbol SVG. The bare
    ``<name>_24px.svg`` is the default instance; ``fill``/``weight`` select the
    corresponding axis variant the repo ships."""
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}, got {style!r}")
    mid = ""
    if weight is not None:
        mid += f"wght{weight}"
    if fill:
        mid += "fill1"
    fname = f"{name}_{mid}_24px.svg" if mid else f"{name}_24px.svg"
    return RAW.format(name=name, style=style, file=fname)


def fetch_svg(name: str, style: str = "outlined", fill: bool = False,
              weight: int | None = None) -> bytes:
    url = asset_path(name, style, fill, weight)
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def render(name: str, out_path: Path, style: str = "outlined", fill: bool = False,
           weight: int | None = None, px: int = RENDER_PX) -> Path:
    """Fetch a Material Symbol and write it as a ``px`` x ``px`` RGBA PNG — the
    same format the generator's ``luma`` mode consumes for Fluent glyphs."""
    out_path = Path(out_path)
    png = cairosvg.svg2png(bytestring=fetch_svg(name, style, fill, weight),
                           output_width=px, output_height=px)
    out_path.write_bytes(png)
    return out_path


if __name__ == "__main__":  # tiny smoke test
    import sys
    tgt = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/material_sample.png")
    render(sys.argv[1] if len(sys.argv) > 1 else "search", tgt)
    print(f"wrote {tgt}")
