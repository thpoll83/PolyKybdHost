"""Which face a macro keycap draws with, and where its icon comes from.

A macro owns its whole keycap -- it cannot ride a modifier, because QMK carries the
wrapped key in the low byte and a macro keycode is 0x7700+ -- so the cell can be more
than a legend. The firmware's ``render_macro_key()`` offers three styles, and this
module is the host's model of the two that need a font decision:

* ``ICON`` draws a chosen glyph above the caption. The glyph comes from the font packs
  the keyboard actually has, so the candidates are the bundles this host ships.
* ``TEXT`` drops the mark and draws the caption at the largest face that fits, walking
  the same ladder the firmware does: the two ``latinbig`` tiers, then the resident face,
  then ``_Mid_``.

Qt-free on purpose: the editor previews through it, and so does
``tools/macro_label_preview.py --check``, which is what keeps the preview and the
keycap from disagreeing.
"""

from __future__ import annotations

import glob
import os

from polyhost.services import macro_label as ml

MID_FONT_SYMBOL = "NotoSans_Regular_Mid_19px7b"

# The `latinbig` tiers are emitted into supplementary PUA plane 15 rather than at native
# codepoints, because g_all_fonts is scanned front-to-back and the resident latin face
# is always in front -- a second face at the same codepoints could never be reached.
# These MUST match glyph_size_base[] in the firmware's poly_keymap.c.
BIG_BASE = {"M": 0xF0000, "L": 0xF3000}


def load_ui_font(font_dir: str, filename: str, symbol: str):
    """Parse one standalone UI face out of a committed firmware header.

    The three UI faces (_Small_, _Mid_, _Nano_) are deliberately absent from
    ``ALL_FONTS[]`` -- no codepoint can reach them, which is why the firmware draws
    through a single-font array -- so they have to be read from their own header rather
    than through ``load_all_fonts()``.
    """
    from tools.gfx_font import GfxFont, _parse_header

    path = os.path.join(font_dir, filename)
    bitmaps: dict = {}
    glyph_arrays: dict = {}
    fonts: dict = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        _parse_header(fh.read(), bitmaps, glyph_arrays, fonts)
    raw = fonts.get(symbol)
    if raw is None:
        raise RuntimeError(f"{symbol} not found in {path}")
    return GfxFont(name=symbol, bitmap=bitmaps[raw["bmp"]], glyphs=glyph_arrays[raw["gly"]],
                   first=raw["first"], last=raw["last"], yAdvance=raw["yAdvance"])


def default_pack_dir() -> str:
    """Where this repo keeps the font-pack bundles it ships to the keyboard."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "res", "fontpack")


def load_pack_fonts(pack_dir: str | None = None, bundles=None) -> list:
    """Every font in the shipped bundles, in ALL_FONTS priority order.

    Priority matters for exactly the reason it does on the keyboard: two fonts can
    cover one codepoint, and the lower global index is the one that draws.
    """
    from polyhost.services import fontpack_reader as fr

    pack_dir = pack_dir or default_pack_dir()
    fonts = []
    for path in sorted(glob.glob(os.path.join(pack_dir, "*.plyf"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        if bundles is not None and stem not in bundles:
            continue
        try:
            pack = fr.decode_pack_file(path, name_hint=stem)
        except Exception:
            continue     # a bundle we cannot read is one the picker simply omits
        for f in pack.fonts:
            f.bundle = stem
            fonts.append(f)
    fonts.sort(key=lambda f: getattr(f, "global_index", 0))
    return fonts


def find_glyph(fonts, cp: int):
    """The (font, glyph) that would draw `cp`, front-to-back. None if nothing does.

    Mirrors kdisp_gfx_glyph_font: the FIRST font covering the codepoint with a drawable
    glyph wins, and a gap record (all-zero) is skipped rather than treated as a hit --
    that is what makes a shadowed-glyph dedupe invisible to a reader.
    """
    for f in fonts:
        if not (f.first <= cp <= f.last):
            continue
        g = f.glyphs[cp - f.first]
        if g["width"] or g["height"]:
            return f, g
    return None


def bbox(text: str, fonts, base: int = 0):
    """Ink box of `text` drawn through `fonts`, with `base` added to each codepoint.

    `fonts` is a LIST, looked up front-to-back per glyph -- a tier is not one face.
    The `latinbig` bundle emits twelve sub-fonts per tier (one per latin range), so a
    caption with an accent spans two of them, and requiring a single font to cover the
    whole string would reject exactly the captions the tier exists to draw.

    All-or-nothing, mirroring ``glyph_size_remap()``: one missing glyph rejects the
    whole tier, because a partial hit would mix two faces in one caption -- and by the
    baseline-align rule that also means two baselines.

    Returns (xmin, xmax, ymin, ymax) relative to the pen origin, or None.
    """
    x = 0
    box = None
    for ch in text:
        hit = find_glyph(fonts, ord(ch) + base)
        if hit is None:
            return None
        g = hit[1]
        if not (g["width"] and g["height"]):
            x += g["xAdvance"]
            continue
        l, r = x + g["xOffset"], x + g["xOffset"] + g["width"] - 1
        t, b = g["yOffset"], g["yOffset"] + g["height"] - 1
        box = (l, r, t, b) if box is None else (min(box[0], l), max(box[1], r),
                                                min(box[2], t), max(box[3], b))
        x += g["xAdvance"]
    return box


def caption_ladder(pack_fonts, resident_fonts=None, mid_font=None, nano_font=None):
    """The faces ``render_macro_key()`` tries for STYLE_TEXT, biggest first.

    Each entry is (fonts, base, name) -- a LIST of fonts, because a tier is a set of
    sub-fonts covering different ranges rather than one face.

    The two big tiers live in a PACK bundle, so they are simply absent on a keyboard
    with no font pack -- which is why the resident face is ON the list rather than
    assumed to be the floor.
    """
    out = []
    for tier in ("L", "M"):
        base = BIG_BASE[tier]
        tier_fonts = [f for f in pack_fonts if f.first >= base and f.last < base + 0x3000]
        if tier_fonts:
            out.append((tier_fonts, base, f"latinbig {tier}"))
    if resident_fonts:
        out.append((list(resident_fonts), 0, "resident"))
    if mid_font is not None:
        out.append(([mid_font], 0, "mid"))
    if nano_font is not None:
        out.append(([nano_font], 0, "nano"))
    return out


def plan_caption(text: str, ladder, panel_w: int = ml.PANEL_W, panel_h: int = ml.PANEL_H):
    """Pick the first tier on the ladder whose ink fits the panel.

    Returns (fonts, base, box, name) or None. None means even the smallest face
    overflows, which the firmware treats as "nothing to draw here" and falls back to a
    captioned style -- an empty keycap being worse than the small one it replaced.
    """
    if not text:
        return None
    for fonts, base, name in ladder:
        box = bbox(text, fonts, base)
        if box is None:
            continue
        if (box[1] - box[0] + 1) <= panel_w and (box[3] - box[2] + 1) <= panel_h:
            return fonts, base, box, name
    return None


def load_render_fonts(font_dir: str | None = None, pack_dir: str | None = None):
    """The best available model of the keyboard's ``g_all_fonts``.

    Two sources, and the difference matters:

    * the firmware's committed headers, via ``load_all_fonts()`` -- this IS the
      ALL_FONTS priority order, resident faces included, so a lookup through it routes
      a codepoint exactly as the keyboard would. It needs a qmk_firmware checkout
      beside this repo.
    * the ``.plyf`` bundles this host ships, which are always present but carry only
      the PACK half. A resident glyph therefore looks absent, and a codepoint a
      resident font would have won is attributed to the pack copy instead.

    Prefer the first, fall back to the second, and say which came back so a caller can
    be honest about it rather than quietly previewing the wrong face.
    """
    font_dir = font_dir or ml.default_font_dir()
    try:
        from tools.gfx_font import load_all_fonts
        fonts = load_all_fonts(font_dir)
        if fonts:
            return fonts, "headers"
    except Exception:
        # Deliberately swallowed: no qmk_firmware checkout beside this repo is the
        # NORMAL case for an installed host, and the pack fallback below covers it.
        # Anything else that goes wrong reading the headers has the same remedy, so
        # there is nothing to distinguish here -- the caller is told which source it
        # got and can be honest about the difference.
        pass
    return load_pack_fonts(pack_dir), "packs"
