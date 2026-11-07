#!/usr/bin/env python3
"""Fetch + render the PTC Mathcad Prime shortcut icons (reproducible).

Command icons are Material Symbols (Apache-2.0, `ms:` entries) and Microsoft
Fluent UI System Icons (MIT) through `icon_fetch.fluent`. The operator icons
(root, integral, sum, derivative, logic, programming keywords, ...) are text
in DejaVu Sans Bold (free licence, see SOURCES.md), drawn 1 bit at the keycap
size (36x32) with anti-aliasing off, so the generator copies them 1:1. A few
are drawn with lines (matrix, program, contour plot, Excel component).

The ESC mark is a 32x32 1-bit trace of PTC's site icon (see SOURCES.md).
Drawn and traced icons are made only when the PNG is missing, so a committed
or hand-edited icon is never redrawn.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/mathcad/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
from polyhost.res.overlay_sources.labview.fetch_icons import _crop_to_ink  # noqa: E402
from polyhost.res.overlay_sources.typingtests.fetch_icons import (  # noqa: E402
    _guarded, _load, trace_mark)

FLUENT = {
    "area": "ms:expand",
    "chart": "ms:bar_chart",
    "include": "ms:post_add",
    "object": "ms:widgets",
    "table": "Table",
    "textblock": "ms:subject",
    "textbox": "ms:text_fields",
    "recalcpage": "ms:refresh",
    "calcsheet": "ms:calculate",
    "separateh": "ms:horizontal_distribute",
    "separatev": "ms:vertical_distribute",
    "pagebreak": "ms:insert_page_break",
    "labels": "ms:label",
    "gotopage": "ms:find_in_page",
    "tooperator": "ms:swap_horiz",
    "breaktoggle": "ms:wrap_text",
    "scaling": "ms:straighten",
    "matrixcol": "ms:view_column",
    "matrixrow": "ms:table_rows",
    "insertcol": "Table Insert Column",
    "xyplot": "ms:show_chart",
    "plot3d": "ms:view_in_ar",
    "polarplot": "ms:track_changes",
    "link": "ms:link",
}

W, H = 36, 32
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# name -> (text, font px). One line of text, centred on its ink.
TEXT = {
    "sqrt": ("√x", 24),          # square root and nth root
    "integral": ("∫", 30),
    "sum": ("Σ", 28),
    "product": ("∏", 28),
    "gradient": ("∇", 26),
    "prime": ("f′", 26),
    "infinity": ("∞", 28),
    "greek": ("α", 28),
    "ge": ("≥", 26),
    "le": ("≤", 26),
    "element": ("∈", 26),
    "xor": ("⊕", 26),
    "and": ("∧", 26),
    "or": ("∨", 26),
    "not": ("¬", 26),
    "globaldef": ("≡", 26),
    "definition": (":=", 24),
    "localdef": ("←", 26),
    "equalto": ("=", 28),
    "cross": ("×", 26),
    "norm": ("‖x‖", 20),
    "transpose": ("Mᵀ", 22),
    "abs": ("|x|", 22),
    "power": ("xⁿ", 24),
    "polar": ("∠", 26),
    "limit": ("lim", 16),
    "symbolic": ("→", 26),
    "linconv": ("f∗g", 15),
    "circconv": ("⊛", 28),
    "functions": ("f(x)", 14),
    "mathregion": ("x+y", 15),
    "solveblock": ("x=?", 15),
    "inlinediv": ("x/y", 15),
    "breakadd": ("+↵", 18),
    "breaksub": ("−↵", 18),
    "breakmul": ("×↵", 18),
    "breakdiv": ("/↵", 18),
    "kw_if": ("if", 22),
    "kw_else": ("else", 13),
    "kw_for": ("for", 16),
    "kw_while": ("while", 10),
    "kw_break": ("break", 10),
    "kw_return": ("return", 10),
    "kw_try": ("try", 16),
}

# name -> (top line, bottom line, font px): two lines.
TWO_LINE = {
    "kw_elseif": ("else", "if", 11),
    "kw_alsoif": ("also", "if", 11),
    "kw_continue": ("con", "tinue", 11),
}


def _canvas():
    im = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"  # no anti-aliasing: the glyph is 1 bit as drawn
    return im, d


def _font(px: int):
    return ImageFont.truetype(FONT, px)


def _centred(im: Image.Image) -> Image.Image:
    box = im.getbbox()
    ink = im.crop(box)
    out = Image.new("1", (W, H), 0)
    out.paste(ink, ((W - ink.width) // 2, (H - ink.height) // 2))
    return out


def _save(im: Image.Image, path: Path) -> None:
    """White on transparent, so the binding renders it in alpha mode."""
    a = _centred(im).convert("L")
    Image.merge("RGBA", (a, a, a, a)).save(path)


def draw_text(path: Path, text: str, px: int) -> None:
    im, d = _canvas()
    d.text((W // 2, H // 2), text, font=_font(px), fill=1, anchor="mm")
    _save(im, path)


def draw_two_line(path: Path, top: str, bottom: str, px: int) -> None:
    im, d = _canvas()
    d.text((W // 2, 1), top, font=_font(px), fill=1, anchor="mt")
    d.text((W // 2, H - 1), bottom, font=_font(px), fill=1, anchor="mb")
    _save(im, path)


def draw_fraction(path: Path, top: str, bottom: str, px: int = 14) -> None:
    im, d = _canvas()
    d.text((W // 2, 8), top, font=_font(px), fill=1, anchor="mm")
    d.rectangle((4, 15, W - 5, 16), fill=1)
    d.text((W // 2, 24), bottom, font=_font(px), fill=1, anchor="mm")
    _save(im, path)


def draw_conjugate(path: Path) -> None:
    """z with a bar over it."""
    im, d = _canvas()
    d.text((W // 2, 19), "z", font=_font(24), fill=1, anchor="mm")
    d.rectangle((10, 2, W - 11, 4), fill=1)
    _save(im, path)


def draw_vectorize(path: Path) -> None:
    """M with a right arrow over it."""
    im, d = _canvas()
    d.text((W // 2, 20), "M", font=_font(20), fill=1, anchor="mm")
    d.rectangle((6, 4, W - 10, 5), fill=1)
    d.polygon([(W - 11, 0), (W - 5, 4.5), (W - 11, 9)], fill=1)
    _save(im, path)


def draw_matrix(path: Path) -> None:
    """Square brackets around a 2x2 grid of filled squares."""
    im, d = _canvas()
    d.rectangle((4, 2, 6, 29), fill=1)
    d.rectangle((4, 2, 10, 4), fill=1)
    d.rectangle((4, 27, 10, 29), fill=1)
    d.rectangle((29, 2, 31, 29), fill=1)
    d.rectangle((25, 2, 31, 4), fill=1)
    d.rectangle((25, 27, 31, 29), fill=1)
    for x in (11, 19):
        for y in (8, 17):
            d.rectangle((x, y, x + 5, y + 6), fill=1)
    _save(im, path)


def draw_program(path: Path) -> None:
    """Mathcad's program operator: a vertical bar with lines of code."""
    im, d = _canvas()
    d.rectangle((6, 2, 8, 29), fill=1)
    for y, x1 in ((4, 30), (11, 24), (18, 30), (25, 22)):
        d.rectangle((13, y, x1, y + 2), fill=1)
    _save(im, path)


def draw_contour(path: Path) -> None:
    """Three nested contour lines."""
    im, d = _canvas()
    d.ellipse((1, 2, 34, 29), outline=1, width=2)
    d.ellipse((7, 7, 28, 24), outline=1, width=2)
    d.ellipse((13, 12, 22, 19), fill=1)
    _save(im, path)


def draw_excel(path: Path) -> None:
    """A sheet with an X: a spreadsheet component, not the Excel logo."""
    im, d = _canvas()
    d.rectangle((2, 2, 33, 29), outline=1, width=2)
    d.line((9, 8, 26, 23), fill=1, width=4)
    d.line((26, 8, 9, 23), fill=1, width=4)
    _save(im, path)


DRAWN = {
    "derivative": lambda p: draw_fraction(p, "d", "dx"),
    "partial": lambda p: draw_fraction(p, "∂", "∂x"),
    "conjugate": draw_conjugate,
    "vectorize": draw_vectorize,
    "matrix": draw_matrix,
    "program": draw_program,
    "contourplot": draw_contour,
    "excel": draw_excel,
}

# PTC's site icon (the PTC mark); mathcad.com redirects to ptc.com and has the
# same icon. Google's favicon service, 256 px.
MARK_URL = "https://www.google.com/s2/favicons?domain=ptc.com&sz=256"
MARK_LUMA = 200
MARK_DARK_LIT = True


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    for name, (text, px) in TEXT.items():
        _guarded(out / f"{name}.png", lambda p, t=text, s=px: draw_text(p, t, s))
    for name, (top, bottom, px) in TWO_LINE.items():
        _guarded(out / f"{name}.png",
                 lambda p, a=top, b=bottom, s=px: draw_two_line(p, a, b, s))
    for name, fn in DRAWN.items():
        _guarded(out / f"{name}.png", fn)
    _guarded(out / "mathcad.png", lambda p: trace_mark(
        _crop_to_ink(_load(MARK_URL), MARK_LUMA), p, MARK_LUMA, MARK_DARK_LIT))
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
