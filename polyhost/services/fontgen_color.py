"""Decode colour-bitmap (CBDT/CBLC) emoji glyphs without a PNG-enabled FreeType.

NotoColorEmoji stores glyphs as PNG-compressed colour bitmaps (CBDT).  FreeType
needs a PNG-enabled build to rasterise them; freetype-py's bundled lib lacks PNG.
This module reads the CBDT strike with fontTools and decodes the PNG with Pillow,
producing the *exact* premultiplied-BGRA buffer + metrics FreeType would — so the
colour path works from pure wheels on every OS (no system FreeType, no Windows
DLL).  Verified byte-identical to FreeType 2.13.2: the per-glyph CBDT
SmallGlyphMetrics (Advance/BearingX/BearingY) equal FreeType's advance/left/top,
and premultiply `(c*a + 127)//255` reproduces FT_PIXEL_MODE_BGRA exactly.

fontTools / Pillow / numpy are imported lazily (callers already gate on the
[fontgen] extra).  Only CBDT (bitmap) colour fonts are handled here; outline
colour (COLR/CPAL) still goes through FreeType, which needs no PNG for those.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

DPI = 141   # matches font_render.c setup_face_size
FT_PIXEL_MODE_BGRA = 7


@dataclass
class ColorRaster:
    """A decoded colour glyph in the shape the dither pipeline expects."""
    pixel_mode: int           # always FT_PIXEL_MODE_BGRA
    width: int
    rows: int
    pitch: int                # width * 4
    buf: bytes                # premultiplied BGRA, FreeType-identical
    advance: int              # px (CBDT Advance == FreeType advance>>6 at the strike)
    left: int                 # bearingX == FreeType bitmap_left
    top: int                  # bearingY == FreeType bitmap_top


class ColorBitmapFont:
    """fontTools-backed reader for one CBDT strike (picked like FreeType's
    setup_face_size: the strike whose ppemY is closest to the -s target)."""

    def __init__(self, path: str, size: int):
        from fontTools.ttLib import TTFont
        self.tt = TTFont(path, lazy=True, fontNumber=0)
        self.has_color = "CBDT" in self.tt and "CBLC" in self.tt
        self._strike = None
        if not self.has_color:
            return
        cblc = self.tt["CBLC"]
        cbdt = self.tt["CBDT"]
        target = (size * DPI + 36) // 72
        best, best_diff = 0, 1 << 30
        for i, st in enumerate(cblc.strikes):
            ppem = st.bitmapSizeTable.ppemY
            if abs(ppem - target) < best_diff:
                best_diff, best = abs(ppem - target), i
        self._strike = cbdt.strikeData[best]
        self._cache: dict[int, ColorRaster | None] = {}

    def glyph(self, gid: int) -> ColorRaster | None:
        """Decoded colour glyph for `gid`, or None if the strike has no bitmap for
        it (e.g. an ASCII codepoint in an emoji font — caller emits a 0-size glyph,
        as FreeType/the C tool do)."""
        if not self.has_color or self._strike is None:
            return None
        if gid in self._cache:
            return self._cache[gid]
        name = self.tt.getGlyphName(gid)
        cg = self._strike.get(name)
        png = getattr(cg, "imageData", None) if cg is not None else None
        if not png:
            self._cache[gid] = None
            return None
        ras = _decode(png, cg.metrics)
        self._cache[gid] = ras
        return ras


def _decode(png: bytes, metrics) -> ColorRaster:
    import numpy as np
    from PIL import Image
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    w, h = img.size
    px = np.asarray(img, dtype=np.uint32)            # H,W,4 straight RGBA
    r, g, b, a = px[..., 0], px[..., 1], px[..., 2], px[..., 3]

    def pm(c):                                        # FreeType premultiply, exact
        return ((c * a + 127) // 255).astype(np.uint8)
    bgra = np.dstack([pm(b), pm(g), pm(r), a.astype(np.uint8)]).tobytes()
    return ColorRaster(FT_PIXEL_MODE_BGRA, w, h, w * 4, bgra,
                       advance=metrics.Advance, left=metrics.BearingX,
                       top=metrics.BearingY)
