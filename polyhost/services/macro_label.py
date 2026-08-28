"""Pixel measurement for a macro keycap label.

The firmware truncates a label by MEASURED WIDTH, not by character count -- in the
_Nano_ 10 px face a 'W' is about three times an 'i', so a fixed cut either clips a wide
label off the 72 px panel or wastes half the band on a narrow one. The editor has to
show the same truncation while the user types, which means running the same arithmetic
rather than an approximation of it.

This module is the arithmetic, mirroring ``kdisp_gfx_text_bbox`` for the single-font,
plain-ASCII case that a label always is: the cursor starts at 0, each glyph contributes
``[x + xOffset, x + xOffset + width - 1]``, and ``x`` advances by ``xAdvance``. The
per-font baseline adjustment that the general bbox applies is identically zero here,
because a label is drawn through a single-font array whose ``fonts[0]`` IS the nano face
(the same reason the language flags draw through ``{ &flag_font }``).

Qt-free and import-light on purpose: the daemon, the CLI and the GUI all reach it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The keycap's visible window. Must match SCREEN_WIDTH / SCREEN_HEIGHT in the firmware's
# config.h -- these are the panel, not a layout choice.
PANEL_W = 72
PANEL_H = 40

# Must match POLY_MACRO_LABEL_LEN in keyboards/polykybd/config.h. The pixel fit is the
# real limit; this is the storage stride, and a label longer than it is cut before it
# ever reaches the measurement.
LABEL_MAX_CHARS = 12

NANO_FONT_SYMBOL = "NotoSans_Regular_Nano_10px7b"


@dataclass(frozen=True)
class LabelFit:
    """What a label will actually look like on the keycap."""

    text: str          # the part that fits
    dropped: str       # the part that will not be drawn
    width: int         # pixel width of `text`
    full_width: int    # pixel width of the whole input, so a UI can show overflow

    @property
    def truncated(self) -> bool:
        return bool(self.dropped)


def _glyph(font, cp: int):
    if not (font.first <= cp <= font.last):
        return None
    g = font.glyphs[cp - font.first]
    if g["width"] == 0 and g["height"] == 0 and g["xAdvance"] == 0:
        return None
    return g


def measure(text: str, font) -> int:
    """Pixel width of `text` in `font`, by the firmware's own box arithmetic.

    Zero for the empty string, and for a string with no drawable glyph -- an empty box
    has no width rather than a negative one, which is the case a naive `xmax - xmin`
    gets wrong.
    """
    x = 0
    xmin, xmax = None, None
    for ch in text:
        g = _glyph(font, ord(ch))
        if g is None:
            # The firmware substitutes '!' for a codepoint no font covers. A label can
            # only contain ASCII (poly_macro_label_set drops the rest at the door), so
            # this is unreachable in practice -- mirrored anyway so the two agree even
            # when they are both wrong.
            g = _glyph(font, ord("!"))
            if g is None:
                continue
        if g["width"] > 0 and g["height"] > 0:
            left = x + g["xOffset"]
            right = left + g["width"] - 1
            xmin = left if xmin is None else min(xmin, left)
            xmax = right if xmax is None else max(xmax, right)
        x += g["xAdvance"]
    if xmin is None:
        return 0
    return xmax - xmin + 1


def fit(text: str, font, width: int = PANEL_W) -> LabelFit:
    """Drop trailing characters until the run fits `width`.

    Measuring after each drop rather than estimating from a per-character width is the
    whole point: the face is proportional, so an estimate is wrong in both directions.
    """
    text = text[:LABEL_MAX_CHARS]
    full = measure(text, font)
    kept = text
    while kept and measure(kept, font) > width:
        kept = kept[:-1]
    return LabelFit(text=kept, dropped=text[len(kept):], width=measure(kept, font), full_width=full)


def load_nano_font(font_dir: str):
    """Parse the nano face out of the firmware's committed header.

    Reads the shipped bytes rather than a description of them, so a regenerated font
    changes what the editor shows without anyone having to remember to update a table.

    Parses ``nano_font.h`` DIRECTLY rather than going through ``load_all_fonts()``:
    that returns the ``ALL_FONTS[]`` priority list, and the three standalone UI faces
    (_Small_, _Mid_, _Nano_) are deliberately not in it -- no codepoint can reach them,
    which is exactly why the firmware draws a label through a single-font array.
    """
    from tools.gfx_font import GfxFont, _parse_header  # the header parser

    path = os.path.join(font_dir, "nano_font.h")
    bitmaps: dict = {}
    glyph_arrays: dict = {}
    fonts: dict = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        _parse_header(fh.read(), bitmaps, glyph_arrays, fonts)
    raw = fonts.get(NANO_FONT_SYMBOL)
    if raw is None:
        raise RuntimeError(f"{NANO_FONT_SYMBOL} not found in {path}")
    return GfxFont(
        name=NANO_FONT_SYMBOL,
        bitmap=bitmaps[raw["bmp"]],
        glyphs=glyph_arrays[raw["gly"]],
        first=raw["first"],
        last=raw["last"],
        yAdvance=raw["yAdvance"],
    )


def default_font_dir() -> str:
    """Best guess at the firmware's font directory in a checkout beside this repo."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(os.path.dirname(here), "qmk_firmware",
                        "keyboards", "polykybd", "base", "fonts")
