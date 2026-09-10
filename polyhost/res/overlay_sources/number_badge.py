#!/usr/bin/env python3
"""Shared **numbered glyph** composites: a base glyph with a digit inside it.

Several apps bind a whole row of digits to "the Nth of something" — Windows
Terminal's `Ctrl+Alt+1..8` switch-to-tab, WinSCP's `Alt+1..0` switch-to-tab —
and the number IS the information. A bare container glyph does not carry it:
Fluent's `Tab` is an empty rounded box, which at 40 px on a keycap reads as
nothing at all. (Established by rendering the overlay, not by reading the glyph
name.)

Peer of the other shared mark sources (`program_marks`, `rect_mark`,
`doc_mark`, `geo_marks`, `editor_glyphs`).

⚠️ Three rules the Word line-spacing set learned the hard way, and the reason
this is one implementation rather than a copy per app:

* **Static font size.** Auto-fitting per value renders the same digit at
  different sizes across the family, which reads as sloppy rather than as a set.
* **Fixed centre.** Every digit is placed identically, so the family differs
  only in the digit.
* **Liberation Sans.** Real Arial is not installed here; Liberation is
  metric-compatible.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def numbered(base: Path, digits: str, out_dir: Path, stem: str,
             size: float = 52 / 96, centre: tuple[float, float] = (0.50, 0.56)) -> int:
    """Write `<stem><d>.png` for each character of `digits`, over `base`.

    `size` and `centre` are fractions of the base image, so the same call works
    whatever resolution the base glyph was rendered at. The default 52/96 is the
    size the Windows Terminal set was tuned and rendered at; it is expressed as
    that fraction rather than rounded so the committed art stays byte-identical. `centre` defaults a
    little below the geometric middle because a container glyph's interior
    usually is.
    """
    img0 = Image.open(base).convert("RGBA")
    px = img0.width
    font = ImageFont.truetype(BOLD, int(px * size))
    for d in digits:
        img = img0.copy()
        ImageDraw.Draw(img).text((px * centre[0], px * centre[1]), d,
                                 fill=(0, 0, 0, 255), font=font, anchor="mm")
        img.save(out_dir / f"{stem}{d}.png")
    print(f"  {stem}{digits[0]}..{stem}{digits[-1]}.png  <- composite ({base.stem} + digit)")
    return len(digits)
