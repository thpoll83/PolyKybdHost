"""Render decoded font-pack glyphs to images — the visual half of the inspector.

Takes the `PackFont` objects from `fontpack_reader` and rasterises them exactly
the way the keycap OLED does: 1-bit, MSB-first, ``bit = yy*width + xx`` into the
glyph's own ``width × height`` box (the packing gotcha from the firmware's
``base/disp_array.c`` — continuous-bit-packed, byte-padded per *glyph*, never per
scanline).  This mirrors ``tools/gfx_font.GfxGlyphRenderer._blit`` but draws each
glyph at native size in its own cell instead of compositing into the 72×40 keycap
window — the right view for browsing/extending a bundle's glyph inventory.

PIL only; no Qt.  The Qt inspector window builds on these (a QImage is one
``ImageQt(img)`` away), and the same functions back the headless CLI contact-sheet
export, so the rendering path is identical whether you view it in a window or on
disk.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def glyph_to_image(font, cp: int, scale: int = 1, fg: int = 255, bg: int = 0):
    """Rasterise one glyph at native size (optionally nearest-scaled).

    Returns an ('L', (w*scale, h*scale)) image, or a 1×1 `bg` image for a
    zero-area glyph (e.g. space).  `font` is any object with .first/.glyphs/.bitmap.
    """
    g = font.glyphs[cp - font.first]
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
                  label: bool = True, title: str = "", max_glyphs: int = 0):
    """Render every glyph in `pack` to a labelled grid image (mode 'L').

    Each cell is sized to the pack's largest glyph so columns line up; glyphs are
    nearest-scaled by `scale` for legibility and labelled with their codepoint.
    `max_glyphs` (>0) caps the count (with a note in the footer) for huge bundles.
    """
    glyphs = list(_iter_glyphs(pack))
    capped = max_glyphs and len(glyphs) > max_glyphs
    if capped:
        glyphs = glyphs[:max_glyphs]
    if not glyphs:
        return Image.new("L", (200, 40), 0)

    cell_w = max(f.glyphs[cp - f.first]["width"] for f, cp in glyphs) * scale
    cell_h = max(f.glyphs[cp - f.first]["height"] for f, cp in glyphs) * scale
    cell_w = max(cell_w, 1)
    cell_h = max(cell_h, 1)
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
        gimg = glyph_to_image(font, cp, scale=scale, fg=255, bg=0)
        gx = x0 + (cell_w - gimg.width) // 2
        gy = y0 + (cell_h - gimg.height) // 2
        sheet.paste(gimg, (gx, max(y0, gy)))
        if label:
            draw.text((x0, y0 + cell_h + 1), f"{cp:04X}", fill=128, font=fnt)
    return sheet
