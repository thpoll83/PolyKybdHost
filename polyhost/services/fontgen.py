"""Build GFX font glyphs from a TTF/OTF on the host — fontconvert's render path
in pure Python (freetype-py + the NumPy dither port), no compiled binary.

This is the *extend* half of the font-pack tooling: given a font file + the same
options the C `fontconvert` exposes, produce a `fontpack_reader.PackFont` (glyphs +
1-bit bitmaps) that can be previewed in the inspector and spliced into a bundle for
a flash-trial.  It mirrors fontconvert.c / font_render.c so output matches the C
tool (deterministic-dither paths) bit-for-bit when the FreeType version matches:

  * DPI 141, TrueType interpreter v35 (mono) / v40 (colour) — the hinting knob that
    makes mono output byte-identical;
  * strike selection for bitmap (colour-emoji) faces, FT_Set_Char_Size otherwise;
  * variable-font `wght` pin (-w);
  * per-glyph metrics xAdvance=advance>>6, xOffset=bitmap_left, yOffset=1-bitmap_top,
    rescaled when -r/-W shrinks a colour strike;
  * the pixel pipeline (mono passthrough / gray / BGRA dither + -N/-I/-E/-O) via
    fontgen_dither.

freetype-py / uharfbuzz / numpy are imported lazily so the rest of the host (and
the read-only inspector) keep working without them.  Range mode is implemented
here; HarfBuzz sequence/composite mode (flags, ZWJ emoji) is the next step.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, field

from polyhost.services import fontpack_reader as fpr
from polyhost.services import fontgen_dither as fd

DPI = 141
_TT_V35 = 35
_TT_V40 = 40


@dataclass
class RenderOptions:
    """Mirror of fontconvert's FontSettings (the generation-relevant subset)."""
    size: int = 12            # -s
    height: int = 0           # -r  (render-size limit + yAdvance source)
    yadvance: int = 0         # -Y  (override emitted yAdvance; 0 = use -r/native)
    xshift: int = 0           # -X
    max_width: int = 0        # -W
    weight: int = -1          # -w  (>=0 pins wght; -1 = unset)
    offset: int = 0           # -o/-n applied to emitted first/last
    bits: int = 16            # -b  (16 or 32)
    render_mode: int = 0      # -g
    dither_mode: int = fd.DITHER_FLOYD_STEINBERG  # -D
    normalize: bool = False   # -N
    invert: bool = False      # -I
    edge_preserve: bool = False  # -E
    saturation_boost: float = 0.0  # -B
    sharpness: float = 0.0    # -U
    gamma_val: float = 1.0    # -G
    contrast: float = 1.0     # -c
    exposure: float = 0.0     # -e
    outline: int = 0          # -O

    def _dither_opts(self) -> fd.DitherOpts:
        return fd.DitherOpts(
            render_mode=self.render_mode, dither_mode=self.dither_mode,
            normalize=self.normalize, sharpness=self.sharpness, gamma_val=self.gamma_val,
            contrast=self.contrast, exposure=self.exposure,
            saturation_boost=self.saturation_boost, outline=self.outline,
            invert=self.invert, edge_preserve=self.edge_preserve,
            max_width=self.max_width, height=self.height)


def _set_tt_interpreter(version: int):
    """Pin the TrueType interpreter version on the global FreeType library (the
    knob fontconvert sets so mono hinting — hence pixels — matches)."""
    import freetype
    import freetype.raw as raw
    ver = ctypes.c_uint(version)
    raw.FT_Property_Set(freetype.get_handle(), b"truetype", b"interpreter-version",
                        ctypes.byref(ver))


def _setup_face_size(face, opts: RenderOptions):
    """Port of font_render.c setup_face_size."""
    import freetype
    if face.num_fixed_sizes > 0:
        target_px = (opts.size * DPI + 36) // 72
        best, best_diff = 0, 1 << 30
        for i in range(face.num_fixed_sizes):
            sz = face.available_sizes[i]
            diff = abs((sz.y_ppem >> 6) - target_px)
            if diff < best_diff:
                best_diff, best = diff, i
        face.select_size(best)
        return True
    face.set_char_size(opts.size << 6, 0, DPI, 0)
    return False


def _apply_weight(face, weight: int):
    """Port of fontconvert.c -w: pin the wght axis on a variable font."""
    if weight < 0 or not face.has_multiple_masters:
        return
    try:
        info = face.get_variation_info()
    except Exception:
        return
    coords = []
    found = False
    for ax in info.axes:
        d = ax.default
        if getattr(ax, "tag", None) in (b"wght", "wght"):
            w = weight << 16                      # 16.16 fixed
            d = max(ax.minimum, min(ax.maximum, w))
            found = True
        coords.append(d)
    if found:
        try:
            face.set_var_design_coords(coords)
        except Exception:
            pass


def _scale_metric(v: int, num: int, den: int) -> int:
    if den == 0 or num == den:
        return v
    r = v * num / den
    return int(r + (0.5 if r >= 0 else -0.5))


def render_range(font_path: str, first: int, last: int, opts: RenderOptions | None = None,
                 name: str = "") -> fpr.PackFont:
    """Render a codepoint range [first, last] to a PackFont (fontconvert range mode).

    Missing glyphs become zero-size entries (matching the C tool), so the returned
    glyph list has exactly last-first+1 records, indexable as the firmware does.
    """
    import freetype
    opts = opts or RenderOptions()
    _set_tt_interpreter(_TT_V40 if opts.render_mode == 1 else _TT_V35)
    face = freetype.Face(font_path)
    _apply_weight(face, opts.weight)
    is_strike = _setup_face_size(face, opts)

    load_flags = (freetype.FT_LOAD_RENDER |
                  (freetype.FT_LOAD_TARGET_NORMAL | freetype.FT_LOAD_COLOR
                   if opts.render_mode == 1 else freetype.FT_LOAD_TARGET_MONO))
    dopts = opts._dither_opts()

    glyphs: list[dict] = []
    bitmap = bytearray()
    for cp in range(first, last + 1):
        gid = face.get_char_index(cp)
        if gid == 0:
            # No glyph for this codepoint.  fontconvert `continue`s without writing
            # the table slot, which prints as all-zeros (fresh malloc → zeroed page);
            # emit an all-zero record (bitmapOffset 0) to match.  width/height 0 means
            # the firmware never dereferences the offset, so 0 is also semantically
            # correct, not just C-bug-compatible.  (A gid!=0 glyph with an empty
            # bitmap — e.g. space — keeps its real metrics below, as the C tool does.)
            glyphs.append(_empty_glyph(0))
            continue
        face.load_glyph(gid, load_flags)
        slot = face.glyph
        bm = slot.bitmap
        xadv = slot.advance.x >> 6
        xoff = slot.bitmap_left
        yoff = 1 - slot.bitmap_top
        if bm.rows == 0 or bm.width == 0:
            glyphs.append(dict(bitmapOffset=len(bitmap), width=0, height=0,
                               xAdvance=xadv, xOffset=xoff, yOffset=yoff))
            continue
        packed, out_w, out_h = fd.render_bitmap_to_bits(
            bm.pixel_mode, bm.width, bm.rows, bm.pitch, bytes(bm.buffer), dopts)
        if (out_w, out_h) != (bm.width, bm.rows):     # colour strike was shrunk
            xadv = _scale_metric(xadv, out_w, bm.width)
            xoff = _scale_metric(slot.bitmap_left, out_w, bm.width)
            yoff = _scale_metric(1 - slot.bitmap_top, out_h, bm.rows)
        if out_w:
            xoff += opts.xshift
        glyphs.append(dict(bitmapOffset=len(bitmap), width=out_w, height=out_h,
                           xAdvance=xadv, xOffset=xoff, yOffset=yoff))
        bitmap += packed

    yadv = _emit_yadvance(face, opts, glyphs)
    return fpr.PackFont(name=name or _font_stem(font_path), bitmap=bytes(bitmap),
                        glyphs=glyphs, first=first + opts.offset,
                        last=last + opts.offset, yAdvance=yadv)


def _empty_glyph(off: int) -> dict:
    return dict(bitmapOffset=off, width=0, height=0, xAdvance=0, xOffset=0, yOffset=0)


def _emit_yadvance(face, opts: RenderOptions, glyphs: list) -> int:
    if opts.yadvance != 0:
        return opts.yadvance
    if opts.height != 0:
        return opts.height
    h = face.size.height >> 6
    if h == 0 and glyphs:
        return glyphs[0]["height"]
    return h


def _font_stem(path: str) -> str:
    import os
    return os.path.splitext(os.path.basename(path))[0]
