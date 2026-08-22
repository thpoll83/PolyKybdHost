#!/usr/bin/env python3
"""Reusable KLE-driven keyboard renderer.

Lays out a keyboard from a www.keyboard-layout-editor.com JSON (the same file
``polyhost``'s layout editor uses) and renders frames where you decide, per
physical key, what its little OLED keycap should display.  A list of frames can
be written straight to an animated GIF.

It is deliberately decoupled from any one keyboard or layer: feed it a KLE file
plus, per frame, a ``{matrix_pos: KeyContent}`` mapping and it produces an image.
See ``emoji_demo.py`` for a concrete driver (the emoji layer walk-through).

Key geometry is taken from the KLE exactly like the editor does — including the
rotated thumb cluster (``r``/``rx``/``ry``).  Glyphs are rendered the way the
real hardware shows them: scaled into a 72x40 monochrome buffer and drawn white
on a dark "OLED" rectangle, so the output reads like the actual keycaps.

Dependencies: Pillow, fontTools.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

# Reuse the *exact* parser the PolyHost layout editor uses, so geometry never
# drifts from the app.  Fall back to an inline copy if run outside the repo.
try:  # pragma: no cover - import shim
    import sys
    _REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO not in sys.path:
        sys.path.insert(0, _REPO)
    from polyhost.kle.kle_praser import parse_kle  # type: ignore
except ImportError:  # pragma: no cover — running outside the repo
    def parse_kle(json_data: list):
        key_matrix = {}
        y_cursor = 0.0
        current_rotation = current_rx = current_ry = 0.0
        cols = rows = 0
        for row in json_data:
            x_cursor = 0.0
            row_defaults: dict = {}
            if isinstance(row, dict) and 'name' in row:
                continue
            if isinstance(row, dict):
                continue
            for item in row:
                if isinstance(item, dict):
                    row_defaults.update(item)
                    if 'r' in item:
                        current_rotation = float(item['r'])
                    if 'rx' in item:
                        current_rx = float(item['rx']); x_cursor = current_rx
                    if 'ry' in item:
                        current_ry = float(item['ry']); y_cursor = current_ry
                    if 'x' in item:
                        x_cursor += float(item['x'])
                    if 'y' in item:
                        y_cursor += float(item['y'])
                    continue
                matrix_pos = str(item)
                idx = matrix_pos.split(',')
                col = int(idx[1]); row_i = int(idx[0])
                cols = max(cols, col + 1); rows = max(rows, row_i + 1)
                w = float(row_defaults.get('w', 1)); h = float(row_defaults.get('h', 1))
                key_matrix[matrix_pos] = {
                    'x': x_cursor, 'y': y_cursor, 'w': w, 'h': h,
                    'r': current_rotation, 'rx': current_rx, 'ry': current_ry,
                    'col': col, 'row': row_i,
                }
                x_cursor += w
                row_defaults.clear()
            if current_rotation == 0:
                y_cursor += 1.0
        return rows, cols, key_matrix


# Logical resolution of one keycap OLED (matches the firmware: 72x40, monochrome).
OLED_W, OLED_H = 72, 40


@dataclass
class KeyContent:
    """What one physical key shows in a single frame."""
    glyph: str | None = None      # a unicode character to draw on the OLED
    label: str | None = None      # short text fallback when no glyph is given
    dim: bool = False             # inactive key (KC_NO/unused): drawn darker, blank OLED
    frame: str | None = None      # 'cap' = active-tab ∩ border, 'bar' = inactive-tab bottom bar
    selected: bool = False        # highlight (e.g. the just-pressed key)
    blank: bool = False           # a real key, but its OLED is intentionally empty
    invert: bool = False          # invert the OLED (dark glyph on lit bg) — the kdisp_invert
                                  # press-feedback flash the firmware does on key-down
    scale: float = 1.0            # glyph size within the OLED (e.g. 0.5 for small page arrows)
    image: 'Image.Image | None' = None   # pre-rendered RGB for this key's OLED, used
                                  # as-is (no dither/colourise). For callers that
                                  # already produce a finished panel — e.g. the
                                  # simulate_oled look. None keeps the normal path.


@dataclass
class Theme:
    bg: tuple = (32, 33, 36)
    key_bg: tuple = (53, 53, 53)
    key_dim_bg: tuple = (42, 42, 42)
    key_outline: tuple = (17, 17, 17)
    oled_bg: tuple = (20, 21, 26)
    oled_dim_bg: tuple = (14, 14, 16)
    oled_on: tuple = (236, 240, 245)     # "lit" OLED pixel
    bezel_light: tuple = (64, 64, 64)
    bezel_dark: tuple = (80, 80, 80)
    selected: tuple = (255, 225, 0)


class GlyphRenderer:
    """Renders a single unicode char into a 1-bit OLED-sized buffer, choosing a
    font from a fallback chain by actual cmap coverage."""

    def __init__(self, font_chain: list[tuple[str, str]], mono_px: int = 110):
        from fontTools.ttLib import TTFont
        self.fonts = []  # (coverage:set[int], PIL font, kind)
        for path, kind in font_chain:
            if not path or not os.path.exists(path):
                continue
            try:
                tt = TTFont(path, fontNumber=0, lazy=True)
                cov = set(tt.getBestCmap().keys())
                tt.close()
                size = 109 if kind == 'color' else mono_px
                pil = ImageFont.truetype(path, size)
                self.fonts.append((cov, pil, kind))
            except Exception as exc:  # pragma: no cover
                print(f"  [glyph] skipping {path}: {exc}")
        self._cache: dict[str, Image.Image] = {}

    def _font_for(self, cp: int):
        for cov, pil, kind in self.fonts:
            if cp in cov:
                return pil, kind
        return None

    def render(self, ch: str, scale: float = 1.0) -> Image.Image:
        """Return an OLED_W x OLED_H mode-'L' image (white glyph on black)."""
        key = (ch, round(scale, 3))
        if key in self._cache:
            return self._cache[key]
        canvas = Image.new('L', (OLED_W, OLED_H), 0)
        pick = self._font_for(ord(ch)) if ch else None
        if pick is not None:
            pil, kind = pick
            glyph = self._raster(ch, pil, kind)
            if glyph is not None:
                # Fit within the OLED with a small margin, preserving aspect.
                max_w, max_h = (OLED_W - 4) * scale, (OLED_H - 4) * scale
                gw, gh = glyph.size
                scale = min(max_w / gw, max_h / gh)
                nw, nh = max(1, round(gw * scale)), max(1, round(gh * scale))
                glyph = glyph.resize((nw, nh), Image.LANCZOS)
                ox = (OLED_W - nw) // 2
                oy = (OLED_H - nh) // 2
                canvas.paste(glyph, (ox, oy))
        self._cache[key] = canvas
        return canvas

    @staticmethod
    def _raster(ch: str, pil, kind: str) -> Image.Image | None:
        if kind == 'color':
            tmp = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
            d = ImageDraw.Draw(tmp)
            try:
                d.text((10, 10), ch, font=pil, embedded_color=True)
            except Exception:
                return None
            bbox = tmp.getbbox()
            if not bbox:
                return None
            glyph = tmp.crop(bbox)
            bg = Image.new('RGBA', glyph.size, (0, 0, 0, 255))
            bg.alpha_composite(glyph)
            return bg.convert('L')
        # monochrome / outline font: white on black
        tmp = Image.new('L', (220, 220), 0)
        d = ImageDraw.Draw(tmp)
        d.text((20, 20), ch, font=pil, fill=255)
        bbox = tmp.getbbox()
        if not bbox:
            return None
        return tmp.crop(bbox)


class KleRenderer:
    def __init__(self, kle_json: list, unit: int = 72, key_pad: int = 3,
                 theme: Theme | None = None, glyphs: GlyphRenderer | None = None,
                 bezel: bool = True, dither: bool = True, margin: int = 24,
                 exclude: set[str] | None = None,
                 panels: list[tuple[float, float, float, float]] | None = None):
        # ``panels``: optional extra rectangles in KEY UNITS (x0, y0, x1, y1) that
        # are not keys — e.g. the status OLEDs, whose real position and size come
        # from the PCB. They only widen the canvas here; render_frame() draws them.
        # Left as None the renderer behaves exactly as before.
        self.rows, self.cols, self.km = parse_kle(kle_json)
        self.unit = unit
        self.key_pad = key_pad
        self.theme = theme or Theme()
        self.glyphs = glyphs
        self.bezel = bezel
        self.dither = dither
        self.margin = margin
        self.exclude = set(exclude or ())   # matrix positions with no display (e.g. encoder)
        self.panels = list(panels or ())
        self._geom()
        self._bezel_tile = self._make_bezel_tile() if bezel else None

    def compact_halves(self, side_of, gap_px: int = 10):
        """Slide the two halves together to a fixed pixel gap. ``side_of`` maps a
        matrix position to 'L' / 'R' / None; right-half keys (origin included) are
        translated left so the inner gap becomes ``gap_px``."""
        U = self.unit
        left_max, right_min = [], []
        for mp, p in self.km.items():
            if mp in self.exclude:
                continue
            xs = [x for x, _ in self._corners_px(p)]
            side = side_of(mp)
            if side == 'L':
                left_max.append(max(xs))
            elif side == 'R':
                right_min.append(min(xs))
        if not left_max or not right_min:
            return
        delta_units = ((min(right_min) - max(left_max)) - gap_px) / U
        if abs(delta_units) < 1e-9:
            return
        for mp, p in self.km.items():
            if side_of(mp) == 'R':
                p['x'] -= delta_units
                p['rx'] -= delta_units   # shift rotation pivot too, so rotated keys translate cleanly
        self._geom()

    # -- geometry ------------------------------------------------------------
    def _rot(self, px, py, rx, ry, deg):
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)   # +deg == clockwise in screen (y-down)
        dx, dy = px - rx, py - ry
        return (rx + dx * ca - dy * sa, ry + dx * sa + dy * ca)

    def _corners_px(self, p):
        U = self.unit
        X, Y, W, H = p['x'] * U, p['y'] * U, p['w'] * U, p['h'] * U
        pts = [(X, Y), (X + W, Y), (X + W, Y + H), (X, Y + H)]
        if p['r']:
            rx, ry = p['rx'] * U, p['ry'] * U
            pts = [self._rot(x, y, rx, ry, p['r']) for (x, y) in pts]
        return pts

    def _geom(self):
        xs, ys = [], []
        for mp, p in self.km.items():
            if mp in self.exclude:
                continue
            for (x, y) in self._corners_px(p):
                xs.append(x); ys.append(y)
        for (x0, y0, x1, y1) in getattr(self, 'panels', ()):
            xs += [x0 * self.unit, x1 * self.unit]
            ys += [y0 * self.unit, y1 * self.unit]
        m = self.margin
        self.ox = min(xs) - m
        self.oy = min(ys) - m
        self.cw = int(math.ceil(max(xs) - self.ox + m))
        self.ch = int(math.ceil(max(ys) - self.oy + m))

    def _make_bezel_tile(self) -> Image.Image:
        # Diagonal hatch, echoing the editor's striped keycap "attachment".
        t = 16
        tile = Image.new('RGBA', (t, t), self.theme.bezel_light + (255,))
        d = ImageDraw.Draw(tile)
        for k in range(-t, t * 2, 8):
            d.line([(k, t), (k + t, 0)], fill=self.theme.bezel_dark + (255,), width=4)
        return tile

    # -- per-key tile --------------------------------------------------------
    def _oled_buffer(self, c: KeyContent) -> Image.Image | None:
        """Build the 72x40 monochrome OLED image (RGB) for a key, or None."""
        if c.dim or (c.glyph is None and c.label is None and not c.frame
                     and not c.blank and not c.invert and c.image is None):
            return None
        if c.image is not None:
            return c.image
        buf = Image.new('L', (OLED_W, OLED_H), 0)
        if c.glyph and self.glyphs is not None:
            buf = self.glyphs.render(c.glyph, c.scale).copy()
        elif c.label:
            d = ImageDraw.Draw(buf)
            try:
                f = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            except Exception:
                f = ImageFont.load_default()
            tb = d.textbbox((0, 0), c.label, font=f)
            d.text(((OLED_W - (tb[2] - tb[0])) / 2 - tb[0],
                    (OLED_H - (tb[3] - tb[1])) / 2 - tb[1]), c.label, font=f, fill=255)
        # tab decorations, drawn on top exactly like emj_draw_tab_* on the device
        if c.frame == 'cap':
            d = ImageDraw.Draw(buf)
            d.rectangle([2, 0, OLED_W - 3, 0], fill=255)
            d.rectangle([1, 1, OLED_W - 2, 1], fill=255)
            d.rectangle([0, 2, 2, OLED_H - 1], fill=255)
            d.rectangle([OLED_W - 3, 2, OLED_W - 1, OLED_H - 1], fill=255)
        elif c.frame == 'bar':
            ImageDraw.Draw(buf).rectangle([0, OLED_H - 3, OLED_W - 1, OLED_H - 1], fill=255)
        # to 1-bit: dither (authentic OLED look) then colourise
        one = buf.convert('1') if self.dither else buf.point(lambda v: 255 if v >= 110 else 0).convert('1')
        on = self.theme.oled_on
        bg = self.theme.oled_dim_bg if c.dim else self.theme.oled_bg
        if c.invert:   # kdisp_invert: lit background, dark glyph
            rgb = Image.new('RGB', (OLED_W, OLED_H), on)
            rgb.paste(Image.new('RGB', (OLED_W, OLED_H), bg), (0, 0), one)
        else:
            rgb = Image.new('RGB', (OLED_W, OLED_H), bg)
            rgb.paste(Image.new('RGB', (OLED_W, OLED_H), on), (0, 0), one)
        return rgb

    def _key_tile(self, p, c: KeyContent) -> Image.Image:
        U = self.unit
        tw, th = max(1, round(p['w'] * U)), max(1, round(p['h'] * U))
        tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        pad = self.key_pad
        rect = [pad, pad, tw - pad - 1, th - pad - 1]
        radius = max(2, int(min(tw, th) * 0.10))
        body = self.theme.key_dim_bg if c.dim else self.theme.key_bg
        d.rounded_rectangle(rect, radius=radius, fill=body, outline=self.theme.key_outline, width=2)

        # OLED display rect: width == key height minus margins, centred, anchored top
        kx, ky, kw, kh = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        m = max(3, U // 16)
        disp_w = max(2, kh - 2 * m)
        disp_h = int(disp_w * (OLED_H / OLED_W))
        dx = int(kx + m + (kw - kh) / 2)
        dy = int(ky + m)
        d.rounded_rectangle([dx, dy, dx + disp_w, dy + disp_h],
                            radius=2, fill=self.theme.oled_dim_bg if c.dim else self.theme.oled_bg)
        # striped keycap "attachment" below the display (subtle)
        if self.bezel and self._bezel_tile is not None and not c.dim:
            band_h = max(1, disp_h // 2)
            band = Image.new('RGBA', (disp_w, band_h))
            for yy in range(0, band_h, self._bezel_tile.height):
                for xx in range(0, disp_w, self._bezel_tile.width):
                    band.paste(self._bezel_tile, (xx, yy))
            mask = Image.new('L', (disp_w, band_h), 60)
            tile.paste(band, (dx, dy + disp_h), mask)

        oled = self._oled_buffer(c)
        if oled is not None:
            oled = oled.resize((disp_w, disp_h), Image.NEAREST)
            tile.paste(oled, (dx, dy))

        if c.selected:
            d.rounded_rectangle(rect, radius=radius, outline=self.theme.selected, width=3)
        return tile

    # -- frames --------------------------------------------------------------
    def panel_box_px(self, rect: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        """Key-unit rect -> image pixel box, in this frame's coordinates."""
        x0, y0, x1, y1 = rect
        return (int(round(x0 * self.unit - self.ox)), int(round(y0 * self.unit - self.oy)),
                int(round(x1 * self.unit - self.ox)), int(round(y1 * self.unit - self.oy)))

    def render_frame(self, contents: dict[str, KeyContent],
                     panel_images: list[Image.Image] | None = None) -> Image.Image:
        img = Image.new('RGB', (self.cw, self.ch), self.theme.bg)
        for mp, p in self.km.items():
            if mp in self.exclude:
                continue
            c = contents.get(mp, KeyContent(dim=True))
            tile = self._key_tile(p, c)
            if p['r']:
                rot = tile.rotate(-p['r'], resample=Image.BICUBIC, expand=True)
                cor = self._corners_px(p)
                minx = min(x for x, _ in cor); miny = min(y for _, y in cor)
                img.paste(rot, (int(round(minx - self.ox)), int(round(miny - self.oy))), rot)
            else:
                x = int(round(p['x'] * self.unit - self.ox))
                y = int(round(p['y'] * self.unit - self.oy))
                img.paste(tile, (x, y), tile)
        for rect, panel in zip(self.panels, panel_images or ()):
            x0, y0, x1, y1 = self.panel_box_px(rect)
            img.paste(panel.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.NEAREST), (x0, y0))
        return img

    def save_gif(self, frames: Iterable[dict[str, KeyContent]], path: str,
                 durations, loop: int = 0, scale: float = 1.0,
                 colors: int = 64, palette_from_all: bool = False):
        imgs = [self.render_frame(f) for f in frames]
        if not imgs:
            raise ValueError("save_gif() requires at least one frame")
        if scale != 1.0:
            size = (int(self.cw * scale), int(self.ch * scale))
            imgs = [im.resize(size, Image.LANCZOS) for im in imgs]
        # Quantise to a shared palette for a compact, clean GIF. By default the
        # palette comes from frame 0 — fine when every frame looks alike, but a
        # sequence whose LATER frames are the bright ones (an inverted key, a lit
        # legend) then has its whites mapped to whatever grey frame 0 happened to
        # contain. palette_from_all samples the whole sequence instead.
        if palette_from_all:
            # ⚠️ Sample by CROPPING, never by resizing. A downscaled sample blurs
            # thin lit text into greys, so the palette ends up without the very
            # whites it was built to capture and every frame quantises dim — the
            # exact artefact this option exists to prevent.
            step = max(1, len(imgs) // 12)
            sample = imgs[::step]
            band = max(1, sample[0].height // 3)
            strip = Image.new('RGB', (sample[0].width, band * len(sample)))
            for i, im in enumerate(sample):
                top = max(0, (im.height - band) // 2)
                strip.paste(im.crop((0, top, im.width, top + band)), (0, i * band))
            # Anchor the extremes. Median-cut allocates palette entries by
            # POPULATION, and lit text is a tiny minority of a mostly-dark frame,
            # so pure white gets merged into a mid grey and every legend ships
            # dim (measured: peak 187 instead of 255). Two swatches force the
            # endpoints into the palette.
            # One swatch pair PER BAND: a single pair is ~0.08% of a 12-band
            # strip, still small enough for median-cut to merge away.
            sw = max(24, band // 3)
            for i in range(len(sample)):
                strip.paste((255, 255, 255), (0, i * band, sw, i * band + sw))
                strip.paste((0, 0, 0), (sw, i * band, 2 * sw, i * band + sw))
            pal = strip.quantize(colors=colors, method=Image.MEDIANCUT)
        else:
            pal = imgs[0].quantize(colors=colors, method=Image.MEDIANCUT)
        pimgs = [im.quantize(palette=pal, dither=Image.NONE) for im in imgs]
        if isinstance(durations, (int, float)):
            durations = [durations] * len(pimgs)
        else:
            durations = list(durations)
            if len(durations) != len(pimgs):
                raise ValueError(f"durations ({len(durations)}) != frames ({len(pimgs)})")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        pimgs[0].save(path, save_all=True, append_images=pimgs[1:],
                      duration=durations, loop=loop, optimize=True, disposal=2)
        return path
