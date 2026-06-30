"""Render decoded font-pack glyphs to images — the visual half of the inspector.

Takes the `PackFont` objects from `fontpack_reader` and rasterises them exactly
the way the keycap OLED does: 1-bit, MSB-first, ``bit = yy*width + xx`` into the
glyph's own ``width x height`` box (the packing gotcha from the firmware's
``base/disp_array.c`` — continuous-bit-packed, byte-padded per *glyph*, never per
scanline).  This mirrors ``tools/gfx_font.GfxGlyphRenderer._blit`` but draws each
glyph at native size in its own cell instead of compositing into the 72x40 keycap
window — the right view for browsing/extending a bundle's glyph inventory.

PIL only; no Qt.  The Qt inspector window builds on these (a QImage is one
``ImageQt(img)`` away), and the same functions back the headless CLI contact-sheet
export, so the rendering path is identical whether you view it in a window or on
disk.
"""
from __future__ import annotations

from itertools import islice

from PIL import Image, ImageDraw, ImageFont

# Visible OLED window + the firmware's keycap text origin (base/disp_array.{h,c},
# mirrored in tools/gfx_font.py).  BASE_YADV is IconsFont's yAdvance — fonts[0] in
# the firmware's g_all_fonts, the reference every glyph is baseline-aligned to:
# y += font.yAdvance - fonts[0].yAdvance.  IconsFont is resident (never in a pack),
# so we carry its constant here rather than needing the resident set loaded.
OLED_W, OLED_H = 72, 40
BASELINE = 23
BASE_YADV = 40


def _px(v: float, scale: float) -> int:
    """Pixel size for a base dimension at a (possibly fractional) zoom."""
    return max(1, int(round(v * scale)))


def _glyph_for(font, cp: int):
    """Bounds-checked glyph lookup — a cp below font.first would otherwise index
    negatively and silently render the wrong glyph."""
    if cp < font.first or cp > font.last:
        raise ValueError(f"codepoint U+{cp:04X} outside font range "
                         f"U+{font.first:04X}..U+{font.last:04X}")
    return font.glyphs[cp - font.first]


def glyph_to_image(font, cp: int, scale: int = 1, fg: int = 255, bg: int = 0):
    """Rasterise one glyph at native size (optionally nearest-scaled).

    Returns an ('L', (w*scale, h*scale)) image, or a 1x1 `bg` image for a
    zero-area glyph (e.g. space).  `font` is any object with .first/.glyphs/.bitmap.
    """
    g = _glyph_for(font, cp)
    w, h = g["width"], g["height"]
    if w <= 0 or h <= 0:
        return Image.new("L", (1, 1), bg)
    img = Image.new("L", (w, h), bg)
    px = img.load()
    bmp = font.bitmap
    n = len(bmp)
    bo, bit, cur = g["bitmapOffset"], 0, 0
    for yy in range(h):
        for xx in range(w):
            if (bit & 7) == 0:
                # Guard against a truncated/corrupt pack — an inspector must
                # render what it can rather than crash on bad device data.
                cur = bmp[bo] if 0 <= bo < n else 0
                bo += 1
            if cur & 0x80:
                px[xx, yy] = fg
            cur = (cur << 1) & 0xFF
            bit += 1
    if scale != 1:
        img = img.resize((_px(w, scale), _px(h, scale)), Image.NEAREST)
    return img


def keycap_image(font, cp: int, base_yadv: int = BASE_YADV, scale: float = 1,
                 fg: int = 255, bg: int = 0):
    """Composite one glyph into the 72x40 keycap window as the firmware draws it.

    Reproduces ``kdisp_write_gfx_char``: horizontally centred on the glyph's
    visible width, vertically placed at ``BASELINE + (font.yAdvance - base_yadv)
    + yOffset`` — so a tall pack font (e.g. a flag, yAdvance 54) sits shifted down
    exactly like on hardware, and anything past the 72x40 edge is clipped (the
    firmware's SET_PIXEL_CLIPPED backstop), not wrapped.
    """
    g = _glyph_for(font, cp)
    w, h = g["width"], g["height"]
    img = Image.new("L", (OLED_W, OLED_H), bg)
    px = img.load()
    y_base = BASELINE + (font.yAdvance - base_yadv)
    x_left = (OLED_W - w) // 2          # centre the visible box; xOffset cancels
    bmp, n = font.bitmap, len(font.bitmap)
    bo, bit, cur = g["bitmapOffset"], 0, 0
    for yy in range(h):
        for xx in range(w):
            if (bit & 7) == 0:
                cur = bmp[bo] if 0 <= bo < n else 0
                bo += 1
            if cur & 0x80:
                vx = x_left + xx
                vy = y_base + g["yOffset"] + yy
                if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
                    px[vx, vy] = fg
            cur = (cur << 1) & 0xFF
            bit += 1
    if scale != 1:
        img = img.resize((_px(OLED_W, scale), _px(OLED_H, scale)), Image.NEAREST)
    return img


def glyph_cell(font, cp: int, cell_w: int, cell_h: int, scale: int = 2,
               mode: str = "glyph", base_yadv: int = BASE_YADV, label: bool = True):
    """Render one labelled cell for the flow view: the glyph (or 72x40 keycap)
    centred in a `cell_w x cell_h` box plus its codepoint label.  An *empty* entry
    (width 0 — a codepoint with no glyph in the source font, common in the bundles'
    contiguous ranges) is drawn as a dim dashed placeholder so it's clearly
    distinguishable from a black glyph."""
    g = _glyph_for(font, cp)
    lab_h = 11 if label else 0
    img = Image.new("L", (cell_w, cell_h + lab_h), 0)
    draw = ImageDraw.Draw(img)
    fnt = ImageFont.load_default()
    is_empty = g["width"] == 0 or g["height"] == 0
    if is_empty:
        # dashed grey box + placeholder so an empty entry never looks like a glyph
        for x in range(1, cell_w - 1, 4):
            draw.point((x, 1), fill=70)
            draw.point((x, cell_h - 2), fill=70)
        for y in range(1, cell_h - 1, 4):
            draw.point((1, y), fill=70)
            draw.point((cell_w - 2, y), fill=70)
        draw.text((cell_w // 2 - 3, cell_h // 2 - 6), "ø", fill=90, font=fnt)
        if label:
            draw.text((2, cell_h + 1), f"{cp:04X}", fill=80, font=fnt)
        return img
    cimg = (keycap_image(font, cp, base_yadv=base_yadv, scale=scale)
            if mode == "keycap" else glyph_to_image(font, cp, scale=scale))
    img.paste(cimg, (max(0, (cell_w - cimg.width) // 2),
                     max(0, (cell_h - cimg.height) // 2)))
    if label:
        draw.text((2, cell_h + 1), f"{cp:04X}", fill=130, font=fnt)
    return img


def _raster_to_l(r):
    """A fontgen ColorRaster (mono / 8-bit gray / premultiplied BGRA) → an ('L')
    Pillow image — the smooth, undithered pixels FreeType produced."""
    pm = r.pixel_mode
    if pm == 7:                                     # FT_PIXEL_MODE_BGRA
        import numpy as np
        from polyhost.services import fontgen_dither as fd
        g = fd.bgra_to_gray(r.buf, r.pitch, r.width, r.rows)    # float a·lum in [0,1]
        arr = np.clip(g * 255.0, 0, 255).astype("uint8")
        return Image.fromarray(arr, "L")
    if pm == 2:                                     # FT_PIXEL_MODE_GRAY
        import numpy as np
        arr = np.frombuffer(r.buf, dtype=np.uint8)[:r.rows * r.pitch].reshape(r.rows, r.pitch)
        return Image.fromarray(arr[:, :r.width].copy(), "L")
    img = Image.new("L", (r.width, r.rows), 0)      # FT_PIXEL_MODE_MONO (or other)
    px = img.load()
    buf, n = r.buf, len(r.buf)
    for y in range(r.rows):
        row = y * r.pitch
        for x in range(r.width):
            bi = row + (x >> 3)
            if bi < n and (buf[bi] & (0x80 >> (x & 7))):
                px[x, y] = 255
    return img


def reference_glyph_image(font_path: str, cp: int, opts, fit_h: int | None = None):
    """Render codepoint `cp` straight from the source font — smooth and undithered —
    so the preview can show 'what the font actually draws' beside the dithered
    keycap.  Always antialiased (or colour for an emoji font), independent of the
    dialog's grayscale toggle, since this is the reference, not the keycap output.
    Scaled to `fit_h` px tall (aspect preserved) when given.  None if the font has
    no glyph there (or the build deps are unavailable)."""
    try:
        from dataclasses import replace
        from polyhost.services import fontgen as fg
        import freetype
    except Exception:                               # noqa: BLE001
        return None
    ropts = replace(opts, render_mode=1)            # force smooth/colour render
    fg._set_tt_interpreter(fg._TT_V40)
    face = freetype.Face(font_path)
    fg._apply_weight(face, ropts.weight)
    fg._setup_face_size(face, ropts)
    gid = face.get_char_index(cp)
    if gid == 0:
        return None
    # Only bitmap-strike (CBDT) fonts need the fontTools colour reader; an outline
    # font (num_fixed_sizes 0, incl. COLR/CPAL) renders through FreeType directly —
    # skip opening fontTools for it (avoids a leaked file handle per glyph).
    cfont = fg._open_color_font(font_path, ropts) if face.num_fixed_sizes > 0 else None
    r = fg._raster_for_gid(face, gid, True, cfont)
    if r.width == 0 or r.rows == 0:
        return None
    img = _raster_to_l(r)
    if fit_h and img.height and img.height != fit_h:
        neww = max(1, round(img.width * fit_h / img.height))
        img = img.resize((neww, fit_h), Image.LANCZOS)
    return img


def reference_sequence_image(font_path: str, group: str, opts, fit_h: int | None = None):
    """Smooth reference for a *sequence-mode* glyph (a flag / ZWJ emoji / matra):
    HarfBuzz-shape the codepoint `group` (e.g. ``"1F1FA 1F1F8"``) and composite the
    shaped glyph(s) straight from the font — undithered, colour/antialiased — so the
    preview can show the source glyph beside the dithered keycap even though the
    glyph's pack codepoint is a synthetic PUA slot the font has no glyph for.  None
    if nothing renders (or the build deps are unavailable)."""
    try:
        from dataclasses import replace
        from polyhost.services import fontgen as fg
        import freetype
        import uharfbuzz as hb
        import numpy as np
    except Exception:                               # noqa: BLE001
        return None
    cps = [int(t, 16) for t in str(group).replace(",", " ").split() if t.strip()]
    if not cps:
        return None
    ropts = replace(opts, render_mode=1)
    fg._set_tt_interpreter(fg._TT_V40)
    face = freetype.Face(font_path)
    fg._apply_weight(face, ropts.weight)
    fg._setup_face_size(face, ropts)
    cfont = fg._open_color_font(font_path, ropts, face)
    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(font_path)))
    hb_font.scale = (int(face.size.x_ppem * 64), int(face.size.y_ppem * 64))
    infos, pos = fg._shape(hb, hb_font, cps)
    placed, penx, peny = [], 0.0, 0.0
    for info, p in zip(infos, pos):
        r = fg._raster_for_gid(face, info.codepoint, True, cfont)
        if r.width and r.rows:
            arr = np.asarray(_raster_to_l(r))
            devL = round(penx + p.x_offset / 64.0) + r.left
            devT = round(peny - p.y_offset / 64.0) - r.top
            placed.append((arr, devL, devT))
        penx += p.x_advance / 64.0
        peny -= p.y_advance / 64.0
    if not placed:
        return None
    minL = min(d for _, d, _ in placed)
    minT = min(t for _, _, t in placed)
    maxR = max(d + a.shape[1] for a, d, _ in placed)
    maxB = max(t + a.shape[0] for a, _, t in placed)
    canvas = np.zeros((max(1, maxB - minT), max(1, maxR - minL)), dtype=np.uint8)
    for a, d, t in placed:
        y0, x0 = t - minT, d - minL
        sub = canvas[y0:y0 + a.shape[0], x0:x0 + a.shape[1]]
        np.maximum(sub, a, out=sub)                 # lighten-composite the group
    img = Image.fromarray(canvas, "L")
    if fit_h and img.height and img.height != fit_h:
        neww = max(1, round(img.width * fit_h / img.height))
        img = img.resize((neww, fit_h), Image.LANCZOS)
    return img


def preview_sheet(pack, source_path: str = None, opts=None, cols: int = 12,
                  scale: int = 3, pad: int = 6, title: str = "",
                  base_yadv: int = BASE_YADV, sequence: str = None):
    """The build/extend dialog's preview: every glyph of `pack` as a 72x40 keycap,
    with the *source-font* glyph (smooth, undithered) drawn beside it for comparison
    when `source_path`/`opts` are supplied.  Degrades to keycap-only (no reference)
    for a sequence-mode pack or a codepoint the source can't render."""
    glyphs = list(_iter_glyphs(pack))
    if not glyphs:
        return Image.new("L", (200, 40), 0)
    kc_w, kc_h = _px(OLED_W, scale), _px(OLED_H, scale)
    fnt = ImageFont.load_default()

    want_ref = bool(source_path) and opts is not None
    # Sequence-mode builds (flags/matras) have synthetic PUA codepoints the source
    # font has no glyph for, so the reference is shaped from the sequence groups
    # instead of looked up by codepoint (1:1 when the group/glyph counts match; else
    # the whole sequence backs the first cell).
    groups = [g.strip() for g in str(sequence).split(",") if g.strip()] if sequence else None
    refs, ref_w = [], 0
    for i, (font, cp) in enumerate(glyphs):
        ri = None
        if want_ref and groups is not None:
            grp = groups[i] if len(groups) == len(glyphs) else (sequence if i == 0 else None)
            ri = reference_sequence_image(source_path, grp, opts, fit_h=kc_h) if grp else None
        elif want_ref:
            ri = reference_glyph_image(source_path, cp, opts, fit_h=kc_h)
        refs.append(ri)
        if ri is not None:
            ref_w = max(ref_w, ri.width)
    gap = pad if ref_w else 0
    cell_w, cell_h = kc_w + gap + ref_w, kc_h
    lab_h = 11
    cw, ch = cell_w + pad, cell_h + lab_h + pad
    rows = (len(glyphs) + cols - 1) // cols
    head_h = 22
    W = cols * cw + pad
    H = head_h + rows * ch + pad
    sheet = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(sheet)
    head = title or f"{getattr(pack, 'font_count', '?')} fonts · {len(glyphs)} glyphs"
    if ref_w:
        head += "    (left: keycap · right: source font)"
    draw.text((pad, 6), head, fill=255, font=fnt)

    for i, (font, cp) in enumerate(glyphs):
        r, c = divmod(i, cols)
        x0 = pad + c * cw
        y0 = head_h + r * ch
        kc = keycap_image(font, cp, base_yadv=base_yadv, scale=scale, fg=255, bg=0)
        sheet.paste(kc, (x0, y0))
        draw.rectangle([x0, y0, x0 + kc_w - 1, y0 + kc_h - 1], outline=70)
        ri = refs[i]
        if ri is not None:
            rx = x0 + kc_w + gap
            ry = y0 + max(0, (kc_h - ri.height) // 2)
            sheet.paste(ri, (rx, ry))
            draw.rectangle([rx - 1, y0, rx + ref_w, y0 + kc_h - 1], outline=40)
        draw.text((x0, y0 + cell_h + 1), f"{cp:04X}", fill=128, font=fnt)
    return sheet


def _iter_glyphs(pack):
    """Yield (font, codepoint) for every glyph in priority order, deduped by
    codepoint (the first font covering a cp wins — the firmware's front-to-back
    rule), so an inspector shows what the keyboard would actually draw."""
    seen = set()
    for font in sorted(pack.fonts, key=lambda f: f.global_index):
        for cp in range(font.first, font.last + 1):
            if cp in seen:
                continue
            seen.add(cp)
            yield font, cp


def contact_sheet(pack, cols: int = 16, scale: int = 2, pad: int = 6,
                  label: bool = True, title: str = "", max_glyphs: int = 0,
                  mode: str = "glyph", base_yadv: int = BASE_YADV):
    """Render every glyph in `pack` to a labelled grid image (mode 'L').

    `mode="glyph"` draws each glyph at native size (column width = the pack's
    largest glyph) — the inventory view.  `mode="keycap"` draws each glyph into a
    72x40 keycap window with a frame around every cell — how it actually looks on
    the key.  `max_glyphs` (>0) caps the count (with a footer note) for huge bundles.
    """
    keycap = mode == "keycap"
    # Apply the cap *during* iteration so a huge/corrupt range isn't fully
    # materialised before truncation (+1 to detect that more existed).  Only a
    # positive cap limits — 0/negative means "render everything".
    if max_glyphs > 0:
        glyphs = list(islice(_iter_glyphs(pack), max_glyphs + 1))
        capped = len(glyphs) > max_glyphs
        glyphs = glyphs[:max_glyphs]
    else:
        glyphs = list(_iter_glyphs(pack))
        capped = False
    if not glyphs:
        return Image.new("L", (200, 40), 0)

    if keycap:
        cell_w, cell_h = _px(OLED_W, scale), _px(OLED_H, scale)
    else:
        cell_w = _px(max(f.glyphs[cp - f.first]["width"] for f, cp in glyphs), scale)
        cell_h = _px(max(f.glyphs[cp - f.first]["height"] for f, cp in glyphs), scale)
    fnt = ImageFont.load_default()
    lab_h = 11 if label else 0
    cw, ch = cell_w + pad, cell_h + lab_h + pad
    rows = (len(glyphs) + cols - 1) // cols

    head_h = 22
    W = cols * cw + pad
    H = head_h + rows * ch + pad
    sheet = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(sheet)
    head = title or f"{getattr(pack, 'font_count', '?')} fonts · {len(glyphs)} glyphs"
    if capped:
        head += f"  (showing first {max_glyphs})"
    draw.text((pad, 6), head, fill=255, font=fnt)

    for i, (font, cp) in enumerate(glyphs):
        r, c = divmod(i, cols)
        x0 = pad + c * cw
        y0 = head_h + r * ch
        if keycap:
            cimg = keycap_image(font, cp, base_yadv=base_yadv, scale=scale, fg=255, bg=0)
            sheet.paste(cimg, (x0, y0))
            draw.rectangle([x0, y0, x0 + cell_w - 1, y0 + cell_h - 1], outline=70)
        else:
            gimg = glyph_to_image(font, cp, scale=scale, fg=255, bg=0)
            gx = x0 + (cell_w - gimg.width) // 2
            gy = y0 + (cell_h - gimg.height) // 2
            sheet.paste(gimg, (gx, max(y0, gy)))
        if label:
            draw.text((x0, y0 + cell_h + 1), f"{cp:04X}", fill=128, font=fnt)
    return sheet
