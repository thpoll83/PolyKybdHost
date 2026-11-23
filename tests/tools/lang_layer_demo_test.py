"""`lang_layer_demo` reads glyphs and flags the way the firmware does.

Two things broke the demo's keycaps without an error: glyph bitmaps decoded as
row-major Adafruit bits (the firmware stores them column by column, OLED page
layout), which sheared every flag and label, and the flag glyph taken as the
language index (the flags font has one glyph per country, looked up through
LANG_FLAG_GLYPH).
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools"))

import lang_layer_demo as lld  # noqa: E402


class _Font:
    def __init__(self, bitmap):
        self.bitmap = bitmap


class GlyphBitsTest(unittest.TestCase):
    def test_pixels_are_read_column_by_column(self):
        # A 2x10 glyph: 2 bytes per column (ceil(10/8)). Column 0 lights rows 0 and
        # 9, column 1 lights row 3 only.
        g = dict(bitmapOffset=1, width=2, height=10)
        font = _Font(bytes([0xFF, 0b00000001, 0b00000010, 0b00001000, 0b00000000]))
        lit = {(x, y) for x in range(2) for y in range(10) if lld._lit(font, g, x, y)}
        self.assertEqual(lit, {(0, 0), (0, 9), (1, 3)})


class FlagGlyphTableTest(unittest.TestCase):
    def test_table_is_read_from_the_generated_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "generated"))
            with open(os.path.join(tmp, "generated", "lang_flag_glyph.h"), "w",
                      encoding="utf-8") as fh:
                fh.write("static const uint8_t LANG_FLAG_GLYPH[4] = {\n"
                         "      0,   1,   1,   2,\n};\n")
            self.assertEqual(lld.load_flag_glyphs(tmp, 4), [0, 1, 1, 2])

    def test_no_table_means_one_glyph_per_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(lld.load_flag_glyphs(tmp, 3), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
