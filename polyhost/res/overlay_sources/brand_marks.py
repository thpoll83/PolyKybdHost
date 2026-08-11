#!/usr/bin/env python3
"""Shared source for **real brand logos**, via Simple Icons (artwork CC0-1.0).

Most app logos are proprietary and get a drawn substitute (`program_marks.py`)
or a labelled document frame (`doc_mark.py`). A few are different: the brand
publishes a plain monochrome mark that reads perfectly as a 1-bit silhouette,
and Simple Icons redistributes that artwork under **CC0-1.0**.

Two permissions, and they are not the same thing:

* **Copyright** — the SVG files in `simple-icons/simple-icons` are CC0, so we
  may ship a rendered copy in this GPL-3.0-or-later repo.
* **Trademark** — CC0 on the artwork grants NO trademark rights. The basis for
  using these is **nominative use**: the mark identifies the very application
  the overlay set is for, unmodified and with no endorsement implied. That is
  the same basis as the LibreOffice marks. Do NOT reach for this module to
  decorate something the mark does not actually denote.

So the rule for picking a source is:

    the app's own mark, monochrome + CC0 -> brand_marks (this file)
    the app is a document/page           -> doc_mark  (framed + labelled)
    anything else                        -> program_marks (drawn letter tile)

Output is **white-on-transparent**, so bindings render it with
`program_icon_mode: alpha` (the alpha *is* the shape). Simple Icons paints a
single black path, so the alpha channel already carries the silhouette and no
recolouring of the SVG is needed.

    from polyhost.res.overlay_sources import brand_marks
    brand_marks.ensure(out / "gh.png", "github")

Like the other mark helpers, `ensure()` is a **guard**: a committed file is left
alone so a hand-tuned mark survives a re-run.

    pip install cairosvg
"""
from __future__ import annotations

import io
import time
import urllib.error
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image

SI = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/{}.svg"
RENDER_PX = 256


def _get(url: str, attempts: int = 5) -> bytes:
    """Fetch with backoff — raw.githubusercontent 403s/resets intermittently
    under the session network policy, and one failure is not 'unavailable'."""
    for i in range(attempts):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "polykybd"}),
                timeout=30).read()
        except (urllib.error.URLError, OSError):
            if i == attempts - 1:
                raise
            time.sleep(2 ** i)
    raise AssertionError("unreachable")


def render(slug: str, dest: Path, px: int = RENDER_PX) -> None:
    """Render the Simple Icons mark `slug` to `dest` as white-on-transparent."""
    png = cairosvg.svg2png(bytestring=_get(SI.format(slug)),
                           output_width=px, output_height=px)
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").split()[3]
    white = Image.new("L", alpha.size, 255)
    Image.merge("RGBA", (white, white, white, alpha)).save(dest)


def ensure(dest: Path, slug: str, px: int = RENDER_PX) -> None:
    """Render `slug` unless `dest` is already committed (never clobber a tune)."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    render(slug, dest, px)
    print(f"  {dest.name}  <- simple-icons/{slug} (CC0)")
