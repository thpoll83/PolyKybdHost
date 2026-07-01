#!/usr/bin/env python3
"""Render glyphs exactly like the PolyKybd firmware does — from the generated
Adafruit-GFX pixel-font headers, not a live TTF.

This reproduces ``kdisp_write_gfx_char`` / ``kdisp_write_gfx_text``
(``base/disp_array.c``): pick the first ``ALL_FONTS`` entry whose 32-bit
``[first,last]`` covers the codepoint, take the native 1-bit glyph bitmap, and
blit it at ``(BUFFER_X + xOffset, baseline + yOffset)`` into the 72x40 visible
window. Result: a keycap rendered with the same pixels, sizes and positions the
hardware draws — including the real ICON_LEFT/RIGHT page arrows.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass

from PIL import Image

# Visible OLED window and the firmware's text origin (base/disp_array.{h,c}).
OLED_W, OLED_H = 72, 40
BUFFER_X = 28          # (128-buffer − 72-visible) / 2  → buffer x 28 == visible x 0
BASELINE = 23          # the y passed to kdisp_write_gfx_text for keycap glyphs
EMOJI_PREFIX = "  "    # make_emoji_str(): two leading spaces before the glyph


@dataclass
class GfxFont:
    name: str
    bitmap: bytes
    glyphs: list           # list of dict(bitmapOffset,width,height,xAdvance,xOffset,yOffset)
    first: int
    last: int
    yAdvance: int


def _parse_header(text: str, bitmaps: dict, glyph_arrays: dict, fonts: dict) -> None:
    # Bitmap arrays — strip /* ... */ first (range comments contain 4-digit hex).
    for m in re.finditer(r'const\s+uint8_t\s+(\w+)\s*\[\]\s*PROGMEM\s*=\s*\{(.*?)\};', text, re.S):
        body = re.sub(r'/\*.*?\*/', '', m.group(2), flags=re.S)
        bitmaps[m.group(1)] = bytes(int(b, 16) for b in re.findall(r'0x([0-9A-Fa-f]{2})', body))
    # Glyph arrays — {bitmapOffset,width,height,xAdvance,xOffset,yOffset}, signed.
    for m in re.finditer(r'const\s+GFXglyph\s+(\w+)\s*\[\]\s*(?:PROGMEM\s*)?=\s*\{(.*?)\};', text, re.S):
        body = re.sub(r'//[^\n]*', '', m.group(2))
        arr = []
        for g in re.finditer(r'\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}', body):
            v = list(map(int, g.groups()))
            arr.append(dict(bitmapOffset=v[0], width=v[1], height=v[2],
                            xAdvance=v[3], xOffset=v[4], yOffset=v[5]))
        glyph_arrays[m.group(1)] = arr
    # Font structs.
    for m in re.finditer(r'const\s+GFXfont\s+(\w+)\s+PROGMEM\s*=\s*\{(.*?)\};', text, re.S):
        parts = [p.strip() for p in re.sub(r'//[^\n]*', '', m.group(2)).split(',')]
        bmp = re.findall(r'\w+', parts[0])[-1]
        gly = re.findall(r'\w+', parts[1])[-1]
        fonts[m.group(1)] = dict(name=m.group(1), bmp=bmp, gly=gly,
                                 first=int(parts[2], 0), last=int(parts[3], 0),
                                 yAdvance=int(parts[4], 0))


def load_all_fonts(font_dir: str) -> list[GfxFont]:
    """Parse every header under ``font_dir`` (+ generated/) and return the fonts
    in ``ALL_FONTS[]`` priority order (the exact list the firmware links)."""
    bitmaps: dict = {}
    glyph_arrays: dict = {}
    raw_fonts: dict = {}
    paths = sorted(glob.glob(os.path.join(font_dir, '*.h')) +
                   glob.glob(os.path.join(font_dir, 'generated', '*.h')))
    for p in paths:
        _parse_header(open(p, encoding='utf-8', errors='replace').read(),
                      bitmaps, glyph_arrays, raw_fonts)

    # Font priority order (front-to-back, first match wins), mirroring the
    # firmware's g_all_fonts = RESIDENT_FONTS ++ pack:
    #   1. generated/all_fonts_order.json — the exact full global order (resident
    #      + every pack bundle), emitted by generate_fonts.py. Preferred.
    #   2. the RESIDENT_FONTS[] table in gfx_used_fonts.h (the font-pack split
    #      renamed it from ALL_FONTS[]), then any remaining parsed fonts appended
    #      so pack scripts still resolve after the resident set.
    #   3. bare glob order (last resort).
    # NOTE: matching only ALL_FONTS used to silently fail after the RESIDENT_FONTS
    # rename, dropping to glob order — which sorted a stray 56px FreeSansBold24pt
    # to index 0, so every ASCII letter rendered in that giant font (oversized
    # keycaps). Keep this resilient to the table name.
    names = None
    order_json = os.path.join(font_dir, 'generated', 'all_fonts_order.json')
    if os.path.exists(order_json):
        import json
        names = json.load(open(order_json, encoding='utf-8')).get('order')
    if not names:
        used = os.path.join(font_dir, 'gfx_used_fonts.h')
        order = re.search(r'(?:RESIDENT|ALL)_FONTS\s*\[\]\s*=\s*\{(.*?)\};',
                          open(used, encoding='utf-8').read(), re.S) if os.path.exists(used) else None
        if order:
            names = re.findall(r'&\s*(\w+)', order.group(1))
            names += [n for n in raw_fonts if n not in names]   # append pack fonts after resident
        else:
            names = list(raw_fonts)

    out = []
    for n in names:
        f = raw_fonts.get(n)
        if not f or f['bmp'] not in bitmaps or f['gly'] not in glyph_arrays:
            continue
        out.append(GfxFont(n, bitmaps[f['bmp']], glyph_arrays[f['gly']],
                           f['first'], f['last'], f['yAdvance']))
    return out


class GfxGlyphRenderer:
    """Drop-in for kle_render.GlyphRenderer, but pixel-exact from the GFX headers.
    ``render(ch)`` returns the 72x40 'L' OLED for make_emoji_str(ch) = "  "+ch."""

    def __init__(self, font_dir: str):
        self.fonts = load_all_fonts(font_dir)
        if not self.fonts:
            raise RuntimeError(f"no GFX fonts parsed from {font_dir}")
        self.base_yadv = self.fonts[0].yAdvance     # fonts[0] == IconsFont
        self._cache: dict[str, Image.Image] = {}

    def _font_for(self, cp: int):
        for f in self.fonts:
            if f.first <= cp <= f.last:
                g = f.glyphs[cp - f.first]
                # Skip non-contiguous-range padding (a blank gap glyph): the
                # firmware's kdisp_gfx_glyph_font does the same and falls through
                # to a later font that actually provides this codepoint (e.g. the
                # dedicated WinSwitch font for U+1F5BD, which the wider Util range
                # would otherwise shadow).
                if g['width'] == 0 and g['height'] == 0 and g['xAdvance'] == 0:
                    continue
                return f
        return None

    def _blit(self, px, cp: int, x_cursor: int) -> int:
        f = self._font_for(cp)
        if f is None:                       # firmware falls back to fonts[0] '!'
            f = self.fonts[0]
            cp = ord('!')
            if not (f.first <= cp <= f.last):
                return x_cursor
        g = f.glyphs[cp - f.first]
        y = BASELINE + (f.yAdvance - self.base_yadv)
        bo, bit, bits = g['bitmapOffset'], 0, 0
        for yy in range(g['height']):
            for xx in range(g['width']):
                if (bit & 7) == 0:
                    bits = f.bitmap[bo]; bo += 1
                if bits & 0x80:
                    vx = x_cursor + g['xOffset'] + xx - BUFFER_X
                    vy = y + g['yOffset'] + yy
                    if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
                        px[vx, vy] = 255
                bits = (bits << 1) & 0xFF
                bit += 1
        return x_cursor + g['xAdvance']

    def render(self, ch: str, scale: float = 1.0) -> Image.Image:
        # `scale` is accepted for interface parity but ignored — the hardware
        # draws every glyph at its native size; that's the whole point.
        if ch in self._cache:
            return self._cache[ch]
        img = Image.new('L', (OLED_W, OLED_H), 0)
        px = img.load()
        x = BUFFER_X
        for c in EMOJI_PREFIX + ch:
            x = self._blit(px, ord(c), x)
        self._cache[ch] = img
        return img
