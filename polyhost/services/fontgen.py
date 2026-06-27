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

⚠️ Colour-emoji (NotoColorEmoji) glyphs are PNG-compressed CBDT bitmaps, so they
need a **PNG-enabled FreeType**.  freetype-py ships a *bundled* libfreetype built
WITHOUT PNG → colour glyphs raise FreeType "unimplemented feature".  Mono/gray
fonts work regardless; for colour emoji either install a freetype-py whose bundled
lib has PNG, or make it load a system libfreetype with PNG (remove/symlink the
bundled .so so freetype.raw falls back to ctypes.util.find_library('freetype')).

freetype-py / uharfbuzz / numpy are imported lazily so the rest of the host (and
the read-only inspector) keep working without them.  Both modes are implemented:
range mode (`render_range`) and HarfBuzz sequence mode (`render_sequence`, the
flag / ZWJ-emoji path) — the latter byte-exact vs the C tool, including GSUB
ligature shaping.  Composite (-C) is bitmap-exact (its multi-base xAdvance can
differ by ≤1px; the base+mark use it targets is exact).
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
    offset: int = 0           # -o/-n applied to emitted first/last (range mode)
    seq_first: int = 0        # -F  base codepoint for sequence mode
    composite: bool = False   # -C  composite each group into one glyph (mono)
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


def _load_glyph_rendered(face, gid: int, color: bool):
    """Load + render one glyph, mirroring extract_range_ft: load WITHOUT
    FT_LOAD_RENDER (which would try to re-render — and fail with 'unimplemented' —
    an embedded colour bitmap), then FT_Render_Glyph only for outline glyphs.
    Returns face.glyph."""
    import freetype
    flags = (freetype.FT_LOAD_TARGET_NORMAL | freetype.FT_LOAD_COLOR
             if color else freetype.FT_LOAD_TARGET_MONO)
    face.load_glyph(gid, flags)
    slot = face.glyph
    if slot.format != freetype.FT_GLYPH_FORMAT_BITMAP:
        mode = freetype.FT_RENDER_MODE_NORMAL if color else freetype.FT_RENDER_MODE_MONO
        try:
            slot.render(mode)
        except TypeError:
            freetype.FT_Render_Glyph(slot._FT_GlyphSlot, mode)
    return slot


def _emit_loaded_glyph(slot, bitmap_offset: int, dopts, xshift: int):
    """A glyph already loaded+rendered into `slot` → (GFXglyph dict, packed bytes).

    Shared by range and sequence modes — mirrors the per-glyph body of
    extract_range_ft / shape_render_group: metrics from the slot, render via the
    dither pipeline, rescale metrics if a colour strike was shrunk, and apply -X
    to non-empty glyphs (the C does this at emit time; identical outcome)."""
    bm = slot.bitmap
    xadv = slot.advance.x >> 6
    xoff = slot.bitmap_left
    yoff = 1 - slot.bitmap_top
    if bm.rows == 0 or bm.width == 0:
        return dict(bitmapOffset=bitmap_offset, width=0, height=0,
                    xAdvance=xadv, xOffset=xoff, yOffset=yoff), b""
    packed, out_w, out_h = fd.render_bitmap_to_bits(
        bm.pixel_mode, bm.width, bm.rows, bm.pitch, bytes(bm.buffer), dopts)
    if (out_w, out_h) != (bm.width, bm.rows):
        xadv = _scale_metric(xadv, out_w, bm.width)
        xoff = _scale_metric(slot.bitmap_left, out_w, bm.width)
        yoff = _scale_metric(1 - slot.bitmap_top, out_h, bm.rows)
    if out_w:
        xoff += xshift
    return dict(bitmapOffset=bitmap_offset, width=out_w, height=out_h,
                xAdvance=xadv, xOffset=xoff, yOffset=yoff), packed


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
    _setup_face_size(face, opts)

    color = opts.render_mode == 1
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
        slot = _load_glyph_rendered(face, gid, color)
        rec, packed = _emit_loaded_glyph(slot, len(bitmap), dopts, opts.xshift)
        glyphs.append(rec)
        bitmap += packed

    yadv = _emit_yadvance(face, opts, glyphs)
    return fpr.PackFont(name=name or _font_stem(font_path), bitmap=bytes(bitmap),
                        glyphs=glyphs, first=first + opts.offset,
                        last=last + opts.offset, yAdvance=yadv)


def _parse_groups(seq_str: str):
    """'1F1E9 1F1EA, 1F1EB 1F1F7' → [[0x1F1E9,0x1F1EA],[0x1F1EB,0x1F1F7]] (hex,
    comma = independent glyph group, space/tab = codepoints within a group)."""
    groups = []
    for part in seq_str.split(","):
        cps = []
        for tok in part.replace("\t", " ").split():
            try:
                cps.append(int(tok, 16))
            except ValueError:
                pass
        if cps:
            groups.append(cps)
    return groups


def _shape(hb, hb_font, cps):
    """Shape one codepoint group → (glyph_infos, glyph_positions), mirroring the C
    (content UNICODE, cluster=i, LTR, guess_segment_properties, hb_shape)."""
    buf = hb.Buffer()
    buf.add_codepoints(cps)
    buf.direction = "ltr"
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, None)
    return buf.glyph_infos, buf.glyph_positions


def render_sequence(font_path: str, sequence: str, opts: RenderOptions | None = None,
                    name: str = "") -> fpr.PackFont:
    """HarfBuzz sequence mode (fontconvert -S): shape each comma-group and emit a
    glyph per shaped result (or one composited glyph per group with -C / composite).

    Emits at codepoints [seq_first, seq_first + count - 1] (the -F base), so flags
    and ZWJ emoji get a stable Private-Use range instead of synthetic 0..N-1.
    """
    import freetype
    import uharfbuzz as hb
    opts = opts or RenderOptions()
    _set_tt_interpreter(_TT_V40 if opts.render_mode == 1 else _TT_V35)
    face = freetype.Face(font_path)
    _apply_weight(face, opts.weight)
    _setup_face_size(face, opts)

    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
    # Scale so GPOS positions come out in 26.6 px (composite mode places marks by
    # them); harmless for the non-composite path, which only uses glyph ids.
    hb_font.scale = (int(face.size.x_ppem * 64), int(face.size.y_ppem * 64))

    groups = _parse_groups(sequence)
    if opts.composite:
        glyphs, bitmap = _render_composite(face, hb, hb_font, opts, groups)
    else:
        glyphs, bitmap = _render_shaped(face, hb, hb_font, opts, groups)

    if not glyphs:
        raise ValueError(f"no glyphs rendered from sequence {sequence!r}")
    first = opts.seq_first
    last = first + len(glyphs) - 1
    if opts.bits != 32 and last > 0xFFFF:
        raise ValueError(f"sequence last codepoint 0x{last:X} exceeds 0xFFFF in "
                         "16-bit mode — pass bits=32 or a smaller seq_first")
    yadv = _emit_yadvance(face, opts, glyphs)
    return fpr.PackFont(name=name or _font_stem(font_path), bitmap=bytes(bitmap),
                        glyphs=glyphs, first=first, last=last, yAdvance=yadv)


def _render_shaped(face, hb, hb_font, opts: RenderOptions, groups):
    """Non-composite -S: one GFXglyph per shaped glyph id (font_render.c
    shape_render_group).  Used by language flags and ZWJ emoji."""
    color = opts.render_mode == 1
    dopts = opts._dither_opts()
    glyphs, bitmap = [], bytearray()
    for cps in groups:
        infos, _pos = _shape(hb, hb_font, cps)
        for info in infos:
            slot = _load_glyph_rendered(face, info.codepoint, color)
            rec, packed = _emit_loaded_glyph(slot, len(bitmap), dopts, opts.xshift)
            glyphs.append(rec)
            bitmap += packed
    return glyphs, bitmap


def _render_composite(face, hb, hb_font, opts: RenderOptions, groups):
    """Composite -S -C: OR all glyphs of a group into one bitmap at their GPOS
    positions, one GFXglyph per group, MONO only (font_render.c
    composite_render_group).  Best-effort port — unverified vs the C tool (needs a
    cluster font like Devanagari); the flag/emoji path above is the tested one."""
    glyphs, bitmap = [], bytearray()
    for cps in groups:
        infos, pos = _shape(hb, hb_font, cps)
        placed = []   # (bits_2d as set of (x,y), w, h, devL, devT)
        penx = peny = 0.0
        for info, p in zip(infos, pos):
            _load_glyph_rendered(face, info.codepoint, False)   # mono, into face.glyph
            bm = face.glyph.bitmap
            w, h = bm.width, bm.rows
            gx = penx + p.x_offset / 64.0
            gy = peny - p.y_offset / 64.0
            devL = round(gx) + face.glyph.bitmap_left
            devT = round(gy) - face.glyph.bitmap_top
            # Advance from FreeType (hinted), offsets from GPOS — as hb_ft does.
            # This makes the composite *bitmap* byte-exact vs the C tool.  Caveat:
            # the C's hb_ft reports a slightly different per-glyph advance source,
            # so the emitted xAdvance of a multi-*base*-glyph group can differ by
            # ≤1px; the real -C use (one base + zero-advance combining marks) is
            # exact.  -C is not used by the flag/emoji path (that's non-composite).
            penx += face.glyph.advance.x / 64.0
            peny -= face.glyph.advance.y / 64.0
            if w > 0 and h > 0:
                buf = bytes(bm.buffer)
                lit = {(x, y) for y in range(h) for x in range(w)
                       if buf[y * bm.pitch + (x >> 3)] & (0x80 >> (x & 7))}
                placed.append((lit, w, h, devL, devT))
        total_adv = round(penx)
        if not placed:
            glyphs.append(dict(bitmapOffset=len(bitmap), width=0, height=0,
                               xAdvance=total_adv, xOffset=0, yOffset=0))
            continue
        minL = min(d for _, _, _, d, _ in placed)
        minT = min(t for _, _, _, _, t in placed)
        maxR = max(d + w for _, w, _, d, _ in placed)
        maxB = max(t + h for _, _, h, _, t in placed)
        CW, CH = maxR - minL, maxB - minT
        bits = fd._Bits(CW * CH)
        for lit, w, h, devL, devT in placed:
            ox, oy = devL - minL, devT - minT
            for (x, y) in lit:
                bits.set((oy + y) * CW + (ox + x))
        glyphs.append(dict(bitmapOffset=len(bitmap), width=CW, height=CH,
                           xAdvance=total_adv,
                           xOffset=minL + (opts.xshift if CW else 0),
                           yOffset=1 + minT))
        bitmap += bytes(bits.buf)
    return glyphs, bitmap


def _empty_glyph(off: int) -> dict:
    return dict(bitmapOffset=off, width=0, height=0, xAdvance=0, xOffset=0, yOffset=0)


def _emit_yadvance(face, opts: RenderOptions, glyphs: list) -> int:
    # Mirrors the GFXfont footer in fontconvert.c (range & sequence share it):
    #   -Y → as-is; -r → s.height; metrics.height==0 → table[0].height;
    #   else (uint8_t)(metrics.height >> 6).
    if opts.yadvance != 0:
        return opts.yadvance
    if opts.height != 0:
        return opts.height
    h = face.size.height >> 6
    if h == 0:
        return glyphs[0]["height"] if glyphs else 0
    return h & 0xFF


def _font_stem(path: str) -> str:
    import os
    return os.path.splitext(os.path.basename(path))[0]
