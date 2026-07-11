"""Tests for polyhost.services.fontpack_render — glyph + keycap rasterisation.

Needs PIL but no Qt / display.  Uses a tiny hand-built PackFont so pixel
positions are predictable, plus a truncated-bitmap case to prove the inspector
won't crash on a corrupt pack.
"""
import unittest

from polyhost.services import fontpack_reader as fpr
from polyhost.services import fontpack_render as rd


def _font(first, last, yadv, glyphs, bitmap):
    return fpr.PackFont(name="t", bitmap=bytes(bitmap), glyphs=glyphs,
                        first=first, last=last, yAdvance=yadv)


def _pack(fonts):
    return fpr.Pack(abi_version=1, content_version=0, font_count=len(fonts),
                    total_size=0, crc32=0, crc_ok=True, fonts=list(fonts))


class GlyphImageTest(unittest.TestCase):
    def test_native_size_and_pixels(self):
        # 4x2 glyph, first row all-lit (0xF0), second row blank (0x00)
        f = _font(0x41, 0x41,
                  yadv=8,
                  glyphs=[dict(bitmapOffset=0, width=4, height=2,
                               xAdvance=5, xOffset=0, yOffset=0)],
                  bitmap=[0xF0, 0x00])
        img = rd.glyph_to_image(f, 0x41)
        self.assertEqual(img.size, (4, 2))
        px = img.load()
        self.assertEqual([px[x, 0] for x in range(4)], [255, 255, 255, 255])
        self.assertEqual([px[x, 1] for x in range(4)], [0, 0, 0, 0])

    def test_truncated_bitmap_does_not_raise(self):
        # claims 8x8 (64 bits = 8 bytes) but only 1 byte present
        f = _font(0x41, 0x41, 8,
                  [dict(bitmapOffset=0, width=8, height=8,
                        xAdvance=9, xOffset=0, yOffset=0)],
                  [0xFF])
        img = rd.glyph_to_image(f, 0x41)   # must not IndexError
        self.assertEqual(img.size, (8, 8))


class KeycapImageTest(unittest.TestCase):
    def test_window_size_and_centring(self):
        f = _font(0x41, 0x41, 40,
                  [dict(bitmapOffset=0, width=2, height=2,
                        xAdvance=3, xOffset=0, yOffset=-2)],
                  [0xF0])   # both rows lit (2x2 -> 4 bits)
        img = rd.keycap_image(f, 0x41)
        self.assertEqual(img.size, (rd.OLED_W, rd.OLED_H))
        px = img.load()
        lit = [(x, y) for y in range(rd.OLED_H) for x in range(rd.OLED_W) if px[x, y]]
        self.assertTrue(lit)
        xs = [x for x, _ in lit]
        # centred on the 72-wide window: left edge ~ (72-2)//2 = 35
        self.assertEqual(min(xs), (rd.OLED_W - 2) // 2)

    def test_baseline_shift_with_tall_font(self):
        # yAdvance 54 (flag-like) shifts the glyph down vs the 40 base
        glyph = [dict(bitmapOffset=0, width=2, height=2, xAdvance=3, xOffset=0, yOffset=0)]
        low = rd.keycap_image(_font(0x41, 0x41, 40, glyph, [0xF0]), 0x41)
        high = rd.keycap_image(_font(0x41, 0x41, 54, glyph, [0xF0]), 0x41)

        def top_lit(img):
            px = img.load()
            for y in range(img.height):
                if any(px[x, y] for x in range(img.width)):
                    return y
            return None
        self.assertEqual(top_lit(high) - top_lit(low), 14)   # 54 - 40

    def test_offscreen_pixels_clipped(self):
        # a glyph taller than the window must not raise and must stay 72x40
        f = _font(0x41, 0x41, 40,
                  [dict(bitmapOffset=0, width=2, height=60,
                        xAdvance=3, xOffset=0, yOffset=-30)],
                  [0xFF] * 16)
        img = rd.keycap_image(f, 0x41)
        self.assertEqual(img.size, (rd.OLED_W, rd.OLED_H))


class ContactSheetTest(unittest.TestCase):
    def _two_glyph_pack(self):
        f = _font(0x41, 0x42, 12,
                  [dict(bitmapOffset=0, width=3, height=4, xAdvance=5, xOffset=0, yOffset=-4),
                   dict(bitmapOffset=2, width=3, height=4, xAdvance=5, xOffset=0, yOffset=-4)],
                  [0xFF, 0xF0, 0xAA, 0xA0])
        return _pack([f])

    def test_glyph_mode(self):
        img = rd.contact_sheet(self._two_glyph_pack(), cols=4, mode="glyph")
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

    def test_keycap_mode_cells_are_72x40(self):
        img = rd.contact_sheet(self._two_glyph_pack(), cols=4, scale=1, pad=6,
                               label=False, mode="keycap")
        # 4 cols * (72 + 6) + 6 pad
        self.assertEqual(img.width, 4 * (rd.OLED_W + 6) + 6)

    def test_empty_pack(self):
        img = rd.contact_sheet(_pack([]))
        self.assertEqual(img.size, (200, 40))


class SimulateOledTest(unittest.TestCase):
    def _keycap(self):
        # A 72x40 'L' keycap with a lit block near the centre and black elsewhere.
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 0)
        for y in range(16, 24):
            for x in range(30, 42):
                img.putpixel((x, y), 255)
        return img

    def test_returns_rgb_same_size(self):
        out = rd.simulate_oled(self._keycap(), scale=1)
        self.assertEqual(out.mode, "RGB")
        self.assertEqual(out.size, (rd.OLED_W, rd.OLED_H))

    def test_black_stays_true_black(self):
        # A far corner is unlit and far from the bloom -> pure black.
        out = rd.simulate_oled(self._keycap(), scale=1, glow=0.0)
        self.assertEqual(out.getpixel((0, 0)), (0, 0, 0))

    def test_lit_pixel_is_pale_cyan(self):
        out = rd.simulate_oled(self._keycap(), scale=1, glow=0.0)
        r, g, b = out.getpixel((35, 20))
        # blue >= green > red — the measured pale-cyan tint, never pure white.
        self.assertGreater(b, g)
        self.assertGreater(g, r)
        self.assertLess(r, 255)

    def test_glow_brightens_neighbourhood(self):
        # A pixel just outside the lit block is black without glow, lit with it.
        kc = self._keycap()
        near = (44, 20)                       # 2px right of the lit block edge
        self.assertEqual(rd.simulate_oled(kc, scale=1, glow=0.0).getpixel(near), (0, 0, 0))
        self.assertGreater(sum(rd.simulate_oled(kc, scale=3, glow=0.6).getpixel(near)), 0)

    def test_pixel_grid_textures_a_flat_fill(self):
        # A fully-lit keycap at zoom must NOT read as one flat colour: the staggered
        # grid + per-pixel jitter give it structure (multiple brightness levels).
        import numpy as np
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 255)   # fully lit
        s = 6
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)
        out = np.asarray(rd.simulate_oled(up, scale=s, glow=0.0))
        # Structured, not flat: real variance, and not saturated white everywhere.
        self.assertGreater(out.std(), 2.0)
        self.assertLess(out.mean(), 255.0)

    def test_per_pixel_jitter_varies_brightness(self):
        # Sample the interior centre of each logical OLED cell (away from the grid
        # seams): with jitter those centres differ cell-to-cell; without, every
        # cell interior is identical.
        import numpy as np
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 255)
        s = 5
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)

        def centres(arr):
            # local (1,1) inside each s-cell — never a grid seam (seams sit at
            # local x in {2, s-1} across the brick stagger, y at s-1).
            ys = np.arange(rd.OLED_H) * s + 1
            xs = np.arange(rd.OLED_W) * s + 1
            return arr[np.ix_(ys, xs)][..., 2]             # blue in each cell

        jit = centres(np.asarray(rd.simulate_oled(up, scale=s, glow=0.0,
                                                  diffusion=0.0, jitter=0.16)))
        flat = centres(np.asarray(rd.simulate_oled(up, scale=s, glow=0.0,
                                                   diffusion=0.0, jitter=0.0)))
        self.assertEqual(flat.std(), 0.0)                   # every cell identical
        self.assertGreater(jit.std(), 0.0)                  # cells vary

    def test_diffusion_softens_edges(self):
        # Diffusion blurs the hard pixel edge, so a lit/black boundary becomes a
        # gradient (more distinct intermediate values than the crisp version).
        import numpy as np
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 0)
        for y in range(rd.OLED_H):
            for x in range(0, rd.OLED_W // 2):
                img.putpixel((x, y), 255)
        s = 6
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)
        soft = np.asarray(rd.simulate_oled(up, scale=s, glow=0.0, diffusion=0.4))[:, :, 2]
        crisp = np.asarray(rd.simulate_oled(up, scale=s, glow=0.0, diffusion=0.0))[:, :, 2]
        self.assertGreater(len(np.unique(soft)), len(np.unique(crisp)))

    def test_brightness_gain_lifts_output(self):
        # brightness > 1 makes lit pixels brighter (applied after the diffusion blur
        # so it compensates the dimming a stroke loses to the spread).
        import numpy as np
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 0)
        for y in range(14, 26):
            for x in range(28, 44):
                img.putpixel((x, y), 255)
        s = 6
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)
        base = np.asarray(rd.simulate_oled(up, scale=s, brightness=1.0)).astype(float)
        bright = np.asarray(rd.simulate_oled(up, scale=s, brightness=1.5)).astype(float)
        self.assertGreater(bright.sum(), base.sum())

    def test_diffusion_varies_across_the_keycap(self):
        # The blur amount is modulated by a seeded low-frequency mask, so different
        # seeds give a different soft/sharp distribution (non-uniform diffusion).
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 255)   # uniform fill
        s = 8
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)
        a = rd.simulate_oled(up, scale=s, seed=1).tobytes()
        b = rd.simulate_oled(up, scale=s, seed=2).tobytes()
        self.assertNotEqual(a, b)

    def test_jitter_is_deterministic(self):
        # Same input + seed -> identical render (no flicker on re-render / zoom).
        from PIL import Image
        img = Image.new("L", (rd.OLED_W, rd.OLED_H), 200)
        s = 4
        up = img.resize((rd.OLED_W * s, rd.OLED_H * s), Image.NEAREST)
        a = rd.simulate_oled(up, scale=s).tobytes()
        b = rd.simulate_oled(up, scale=s).tobytes()
        self.assertEqual(a, b)


class PreviewSheetOledTest(unittest.TestCase):
    def _pack(self):
        # yAdvance == BASE_YADV and yOffset ~ -4 so the 8x8 block lands inside the
        # 72x40 window (else keycap_image clips it and every style is blank).
        f = _font(0x41, 0x41, rd.BASE_YADV,
                  [dict(bitmapOffset=0, width=8, height=8, xAdvance=10, xOffset=0, yOffset=-4)],
                  [0xFF] * 8)
        return _pack([f])

    def test_oled_style_sheet_is_rgb(self):
        self.assertEqual(rd.preview_sheet(self._pack(), cols=4, scale=3,
                                          style="oled").mode, "RGB")
        self.assertEqual(rd.preview_sheet(self._pack(), cols=4, scale=3,
                                          style="keycap").mode, "RGB")

    def test_normal_style_sheet_is_grayscale(self):
        img = rd.preview_sheet(self._pack(), cols=4, scale=3)     # default normal
        self.assertEqual(img.mode, "L")
        self.assertEqual(rd.preview_sheet(self._pack(), cols=4, scale=3,
                                          style="normal").mode, "L")

    def test_oled_and_keycap_styles_differ(self):
        # The two OLED styles render the keycap differently (crisp vs diffused/
        # jittered), so their sheets are not identical.  (The crisp-vs-diffused
        # detail is covered at the simulate_oled level.)
        import numpy as np
        p = self._pack()
        oled = np.asarray(rd.preview_sheet(p, cols=4, scale=6, style="oled"))
        keycap = np.asarray(rd.preview_sheet(p, cols=4, scale=6, style="keycap"))
        self.assertTrue((oled != keycap).any())


class BaseYadvForTest(unittest.TestCase):
    def _font(self, yadv):
        return _font(0xE000, 0xE000, yadv,
                     [dict(bitmapOffset=0, width=1, height=1, xAdvance=1, xOffset=0, yOffset=0)],
                     [0x80])

    def test_flag_band_uses_own_yadvance(self):
        f = self._font(54)
        # A flag (PUA 0xE000 band) is drawn via a single-font array (adjustment 0),
        # so its own yAdvance is the reference — not IconsFont's 40.
        self.assertEqual(rd.base_yadv_for(f, 0xE000), 54)
        self.assertEqual(rd.base_yadv_for(f, 0xE0FF), 54)

    def test_non_flag_keeps_default(self):
        f = self._font(48)
        self.assertEqual(rd.base_yadv_for(f, 0x1F600), rd.BASE_YADV)   # emoji: keep shift
        self.assertEqual(rd.base_yadv_for(f, 0xE100), rd.BASE_YADV)    # matra band: default

    def test_flag_bottom_not_clipped(self):
        # A tall flag (h > OLED_H) placed with base_yadv=40 clips its bottom off the
        # window; with the flag's own yAdvance it sits so the bottom is visible.
        import numpy as np
        g = dict(bitmapOffset=0, width=8, height=54, xAdvance=8, xOffset=0, yOffset=-42)
        f = _font(0xE000, 0xE000, 54, [g], [0xFF] * 54)   # every row lit

        def glyph_bottom(base_yadv):
            # Window row of the glyph's LAST row, using keycap_image's own placement
            # geometry — derived, not hardcoded, so a BASELINE tweak can't stale it.
            y_base = rd.BASELINE + (f.yAdvance - base_yadv)
            return y_base + g["yOffset"] + (g["height"] - 1)

        # Buggy (base_yadv=40): the glyph's bottom lands past the window edge → clipped.
        self.assertGreaterEqual(glyph_bottom(40), rd.OLED_H)
        # Fixed (flag's own yAdvance): the glyph's bottom lands inside the window.
        fixed_by = rd.base_yadv_for(f, 0xE000)
        self.assertLess(glyph_bottom(fixed_by), rd.OLED_H)

        # And the rendered result agrees: the fixed render's last lit row sits inside
        # (not jammed at OLED_H-1 the way the clipped, buggy render is).
        shifted = np.asarray(rd.keycap_image(f, 0xE000, base_yadv=40))
        fixed = np.asarray(rd.keycap_image(f, 0xE000, base_yadv=fixed_by))
        shifted_last = max(y for y in range(rd.OLED_H) if shifted[y].max() > 0)
        fixed_last = max(y for y in range(rd.OLED_H) if fixed[y].max() > 0)
        self.assertEqual(shifted_last, rd.OLED_H - 1)   # buggy: runs to the very edge
        self.assertEqual(fixed_last, glyph_bottom(fixed_by))   # fixed: exactly its bottom


class GlyphCellOledModeTest(unittest.TestCase):
    def _font(self):
        return _font(0x41, 0x41, rd.BASE_YADV,
                     [dict(bitmapOffset=0, width=8, height=8, xAdvance=10, xOffset=0, yOffset=-4)],
                     [0xFF] * 8)

    def test_oled_modes_return_rgb(self):
        f = self._font()
        for mode in ("oled", "keycap_cover"):
            img = rd.glyph_cell(f, 0x41, 72 * 3, 40 * 3, scale=3, mode=mode)
            self.assertEqual(img.mode, "RGB", mode)

    def test_plain_modes_return_l(self):
        f = self._font()
        for mode in ("glyph", "keycap"):
            img = rd.glyph_cell(f, 0x41, 72 * 3, 40 * 3, scale=3, mode=mode)
            self.assertEqual(img.mode, "L", mode)


class GlyphCellTest(unittest.TestCase):
    def _font(self):
        # 0x41 present (2x2 lit), 0x42 empty (w=0)
        return _font(0x41, 0x42, 8,
                     [dict(bitmapOffset=0, width=2, height=2, xAdvance=3, xOffset=0, yOffset=0),
                      dict(bitmapOffset=1, width=0, height=0, xAdvance=0, xOffset=0, yOffset=0)],
                     [0xF0])

    def test_cell_size_includes_label(self):
        f = self._font()
        img = rd.glyph_cell(f, 0x41, cell_w=20, cell_h=16, scale=2, label=True)
        self.assertEqual(img.size, (20, 16 + 11))

    def test_present_vs_empty_differ(self):
        f = self._font()
        present = rd.glyph_cell(f, 0x41, 20, 16, scale=2)
        empty = rd.glyph_cell(f, 0x42, 20, 16, scale=2)
        self.assertNotEqual(present.tobytes(), empty.tobytes())
        # the empty cell has some lit (grey) marker pixels but no full-white glyph
        empty_bytes = empty.tobytes()
        self.assertTrue(any(empty_bytes))
        self.assertLess(max(empty_bytes), 255)


if __name__ == "__main__":
    unittest.main()
