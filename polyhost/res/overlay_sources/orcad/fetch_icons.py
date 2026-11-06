#!/usr/bin/env python3
"""Fetch + render the Cadence OrCAD X Capture shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. The schematic tools that KiCad's Schematic
Editor has too (wire, bus, bus entry, junction, no-connect, power, net label,
part, text, mirror, rotate, repeat) are byte-identical copies of KiCad's icons.
Run simulation is the same glyph as Altium's F9.

Two icons are drawn here and guarded (a committed PNG is left as it is):

* `ground.png`: the ground symbol (a stem and three bars). Neither icon set
  has one.
* `orcad.png`, the ESC mark. No OrCAD X application icon is published at a
  size that can be traced (orcad.com and cadence.com serve a 16 px favicon),
  so the mark is drawn: a rounded tile with "OX" cut out, drawn as a 32x32
  1-bit image so the generator copies it 1:1. OrCAD is a trademark of Cadence
  Design Systems; the mark does not reproduce their logo. See SOURCES.md.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/orcad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch, program_marks  # noqa: E402

FLUENT = {
    "database": "Database",
    "fisheyedyn": "ms:lens_blur",
    "fisheyeset": "ms:loupe",
    "fisheyereset": "ms:blur_off",
    "descend": "ms:login",
    "testbench": "ms:science",
    "sendpcb": "ms:upload",
    "rectangle": "ms:rectangle",
    "selfilter": "Filter",
    "ungroup": "ms:join_left",
    "groupadd": "ms:add_box",
    "groupremove": "ms:indeterminate_check_box",
    "snaptoggle": "ms:grid_on",
    "panup": "ms:keyboard_double_arrow_up",
    "pandown": "ms:keyboard_double_arrow_down",
    "panleft": "ms:keyboard_double_arrow_left",
    "panright": "ms:keyboard_double_arrow_right",
    "simulate": "ms:play_circle",
    "simresults": "ms:monitoring",
}

# Same action, same glyph as KiCad's Schematic Editor (byte-identical copies).
BORROW = {
    "wire.png": "kicad",
    "bus.png": "kicad",
    "busentry.png": "kicad",
    "junction.png": "kicad",
    "noconnect.png": "kicad",
    "power.png": "kicad",
    "netlabel.png": "kicad",
    "symbol.png": "kicad",
    "text.png": "kicad",
    "lines.png": "kicad",
    "mirrorh.png": "kicad",
    "mirrorv.png": "kicad",
    "rotccw.png": "kicad",
    "repeat.png": "kicad",
    "refresh.png": "kicad",
    "center.png": "kicad",
    "leavesheet.png": "kicad",
    "properties.png": "kicad",
    "expandconn.png": "kicad",
}

SIZE = 96
SS = 4


def _ground(path: Path) -> None:
    """Ground symbol, black on transparent like the fetched glyphs: a vertical
    stem and three bars that get shorter downwards."""
    u = SIZE * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (0, 0, 0, 255)
    w = int(u * 0.07)
    cx = u // 2
    d.rectangle([cx - w // 2, int(u * 0.10), cx + w // 2, int(u * 0.46)], fill=ink)
    for i, half in enumerate((0.36, 0.24, 0.12)):
        y = int(u * (0.46 + i * 0.15))
        d.rectangle([cx - int(u * half), y, cx + int(u * half), y + w], fill=ink)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path)


def _orcad_mark(path: Path, px: int = 32) -> None:
    """Rounded tile with "OX" cut out, reduced to px*px 1-bit (alpha lit)."""
    big = path.with_suffix(".tmp.png")
    program_marks.letter_mark(big, "OX")
    src = Image.open(big).convert("RGBA").getchannel("A")
    big.unlink()
    small = src.resize((px, px), Image.LANCZOS)
    a = small.point(lambda v: 255 if v >= 128 else 0)
    Image.merge("RGBA", (a, a, a, a)).save(path)


def _guarded(path: Path, draw, what: str) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- {what}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    _guarded(out / "ground.png", _ground, "drawn in orcad/fetch_icons.py")
    _guarded(out / "orcad.png", _orcad_mark, "drawn program mark (OX tile)")
    print(f"Wrote {n + 2} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
