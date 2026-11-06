#!/usr/bin/env python3
"""Fetch the foobar2000 shortcut icons.

Icons are Microsoft Fluent UI System Icons (MIT) and Material Symbols
(Apache-2.0), both through `icon_fetch`. Where the action is the same as in the
VLC set (open files, save playlist, add a URL, properties), the same glyph is
used. The ESC mark is the foobar2000 logo (the foobar2000.org favicon) reduced
to a 32x32 1-bit trace, dark pixels lit. See SOURCES.md.

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/foobar2000/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

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


# foobar2000.org's favicon is the foobar2000 logo. Google's favicon service serves it.
FOOBAR_ICON_URL = "https://www.google.com/s2/favicons?domain=foobar2000.org&sz=256"
FOOBAR_DARK_LUMA = 128


def _foobar_mark(dest: Path, px: int = 32) -> None:
    """The foobar2000 logo as a px*px 1-bit trace: fitted into the square,
    pixels at luma 128 or darker lit. Drawn at the keycap size so the generator
    copies it 1:1."""
    if dest.exists():
        print(f"  {dest.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request

    from PIL import Image
    req = urllib.request.Request(FOOBAR_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= FOOBAR_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)
    print(f"  {dest.name}  <- foobar2000 logo, 1-bit trace")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    _foobar_mark(out / "foobar2000.png")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
