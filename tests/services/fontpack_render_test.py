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
        self.assertTrue(any(p for p in empty.tobytes()))


if __name__ == "__main__":
    unittest.main()
