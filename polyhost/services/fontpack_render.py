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
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    return img


def keycap_image(font, cp: int, base_yadv: int = BASE_YADV, scale: int = 1,
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
        img = img.resize((OLED_W * scale, OLED_H * scale), Image.NEAREST)
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
        cell_w, cell_h = OLED_W * scale, OLED_H * scale
    else:
        cell_w = max(max((f.glyphs[cp - f.first]["width"] for f, cp in glyphs)) * scale, 1)
        cell_h = max(max((f.glyphs[cp - f.first]["height"] for f, cp in glyphs)) * scale, 1)
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
