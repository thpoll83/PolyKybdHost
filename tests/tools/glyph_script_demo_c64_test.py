"""`glyph_script_demo`'s C64 keycap layout (glyph script 11).

`c64_keycap_image()` mirrors the firmware's `render_c64_keycap()`: the letter at
0xEAC0 + i with its top on y=1, the Commodore graphic at 0xEB00 + i and the Shift
graphic at 0xEB1A + i with their tops on y=25, on columns 12 px either side of the
centre. A wrong index or offset changes only the docs GIF, which nothing else
checks, so these tests pin both against the SHIPPED fantasy bundle.

Qt-free; reads polyhost/res/fontpack/fantasy.plyf.
"""
import copy
import os
import sys
import unittest

HOST = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(HOST, "tools"))

import glyph_script_demo as gsd  # noqa: E402
from polyhost.services import fontpack_render as FR  # noqa: E402
from polyhost.services.fontpack_reader import decode_pack_file  # noqa: E402

PACK = os.path.join(HOST, "polyhost", "res", "fontpack", "fantasy.plyf")


def _glyph(fonts, cp):
    font = next(f for f in fonts if f.first <= cp <= f.last)
    return FR.glyph_to_image(font, cp, scale=1, fg=255, bg=0)


def _ink_box(img, box):
    """Ink bbox of `img` inside `box` (left, top, right, bottom), in image coords."""
    region = img.crop(box)
    bb = region.getbbox()
    if bb is None:
        return None
    return (bb[0] + box[0], bb[1] + box[1], bb[2] + box[0], bb[3] + box[1])


class C64KeycapImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = decode_pack_file(PACK, "fantasy").fonts

    def _expected(self, cp, cx, top):
        """The glyph pasted alone at the documented spot, for comparison."""
        g = _glyph(self.fonts, cp)
        canvas = gsd.Image.new("L", (FR.OLED_W, FR.OLED_H), 0)
        canvas.paste(g, (cx - g.width // 2, top), g)
        return canvas, g

    def test_every_letter_draws_its_three_documented_glyphs(self):
        for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
            with self.subTest(letter=ch):
                img = gsd.c64_keycap_image(self.fonts, ch)
                self.assertIsNotNone(img)
                self.assertEqual(img.size, (FR.OLED_W, FR.OLED_H))
                parts = (
                    (0xEAC0 + i, FR.OLED_W // 2, 1),           # letter
                    (0xEB00 + i, FR.OLED_W // 2 - 12, 25),     # Commodore + key
                    (0xEB00 + 26 + i, FR.OLED_W // 2 + 12, 25),  # Shift + key
                )
                union = gsd.Image.new("L", (FR.OLED_W, FR.OLED_H), 0)
                for cp, cx, top in parts:
                    alone, g = self._expected(cp, cx, top)
                    box = (cx - g.width // 2, top, cx - g.width // 2 + g.width, top + g.height)
                    # Each glyph sits inside the 72x40 window...
                    self.assertGreaterEqual(box[0], 0)
                    self.assertLessEqual(box[2], FR.OLED_W)
                    self.assertLessEqual(box[3], FR.OLED_H)
                    # ...and its pixels are exactly what the composite shows there.
                    self.assertEqual(img.crop(box).tobytes(),
                                     alone.crop(box).tobytes(), hex(cp))
                    union.paste(alone, (0, 0), alone)
                # Nothing else is drawn anywhere on the key.
                self.assertEqual(img.tobytes(), union.tobytes())

    def test_letter_sits_above_the_cells_and_cells_do_not_touch(self):
        for ch in "aqwz":
            with self.subTest(letter=ch):
                img = gsd.c64_keycap_image(self.fonts, ch)
                letter = _ink_box(img, (0, 0, FR.OLED_W, 24))
                left = _ink_box(img, (0, 25, FR.OLED_W // 2, FR.OLED_H))
                right = _ink_box(img, (FR.OLED_W // 2, 25, FR.OLED_W, FR.OLED_H))
                self.assertIsNotNone(letter)
                self.assertIsNotNone(left)
                self.assertIsNotNone(right)
                self.assertEqual(letter[1], 1)            # letter top on y=1
                self.assertLess(letter[3], 25)            # clear of the cells
                self.assertLess(left[2], right[0])        # cells apart

    def test_cells_differ_per_side(self):
        # The Commodore and Shift graphics of a key are different glyphs; a
        # swapped or duplicated block offset would make them equal.
        for i in range(26):
            with self.subTest(index=i):
                a = _glyph(self.fonts, 0xEB00 + i)
                b = _glyph(self.fonts, 0xEB00 + 26 + i)
                self.assertNotEqual(a.tobytes(), b.tobytes())

    def test_missing_petscii_font_returns_none(self):
        without = [f for f in self.fonts if not (f.first <= 0xEB00 <= f.last)]
        self.assertIsNone(gsd.c64_keycap_image(without, "a"))


class _Cell:
    def __init__(self, oled):
        self._oled = oled


class ScriptFrameFallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = decode_pack_file(PACK, "fantasy").fonts
        cls.c64keys = next(f for f in cls.fonts if f.first == gsd.C64KEYS_BASE)
        blank = gsd.Image.new("L", (FR.OLED_W, FR.OLED_H), 0)
        cls.base = {"0,0": _Cell(blank), "0,1": _Cell(blank)}
        cls.kc = {"0,0": "KC_A", "0,1": "KC_1"}

    def test_letter_uses_the_keycap_layout_with_the_helper_fonts(self):
        out = gsd.script_frame(self.base, self.kc, self.c64keys, self.fonts)
        self.assertEqual(out["0,0"]._oled.tobytes(),
                         gsd.c64_keycap_image(self.fonts, "a").tobytes())

    def test_letter_falls_back_to_the_large_glyph_without_the_helper_fonts(self):
        out = gsd.script_frame(self.base, self.kc, self.c64keys, [self.c64keys])
        self.assertEqual(out["0,0"]._oled.tobytes(),
                         gsd.script_glyph_image(self.c64keys, "a").tobytes())

    def test_digit_always_uses_the_large_glyph(self):
        out = gsd.script_frame(self.base, self.kc, self.c64keys, self.fonts)
        self.assertEqual(out["0,1"]._oled.tobytes(),
                         gsd.script_glyph_image(self.c64keys, "1").tobytes())

    def test_untouched_cells_are_copied_not_mutated(self):
        before = copy.copy(self.base["0,0"]._oled)
        gsd.script_frame(self.base, self.kc, self.c64keys, self.fonts)
        self.assertEqual(self.base["0,0"]._oled.tobytes(), before.tobytes())


if __name__ == "__main__":
    unittest.main()
