"""Unit tests for the CBDT colour-bitmap extractor (fontgen_color).

Gated on a NotoColorEmoji font (NOTO_CEMOJI env or /tmp) + fontTools/Pillow/numpy.
Verifies the strike decode produces FreeType-shaped metrics and premultiplied BGRA
of the right size; full byte-parity vs the C tool lives in fontgen_test.
"""
import os
import unittest

try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
    import fontTools  # noqa: F401
    from polyhost.services import fontgen_color as fc
    _ERR = None
except Exception as e:  # pragma: no cover
    _ERR = e


def _find_cemoji():
    for c in (os.environ.get("NOTO_CEMOJI"), "/tmp/NotoColorEmoji.ttf"):
        if c and os.path.exists(c):
            return c
    return None


_CEMOJI = _find_cemoji()


@unittest.skipIf(_ERR is not None, f"deps unavailable: {_ERR}")
@unittest.skipUnless(_CEMOJI, "NotoColorEmoji not found (set NOTO_CEMOJI)")
class ColorBitmapFontTest(unittest.TestCase):

    def setUp(self):
        self.cf = fc.ColorBitmapFont(_CEMOJI, 20)

    def test_has_color(self):
        self.assertTrue(self.cf.has_color)

    def test_decode_smiley(self):
        import freetype
        face = freetype.Face(_CEMOJI)
        gid = face.get_char_index(0x1F600)
        r = self.cf.glyph(gid)
        self.assertIsNotNone(r)
        self.assertEqual(r.pixel_mode, fc.FT_PIXEL_MODE_BGRA)
        self.assertGreater(r.width, 0)
        self.assertGreater(r.rows, 0)
        self.assertEqual(r.pitch, r.width * 4)
        self.assertEqual(len(r.buf), r.width * r.rows * 4)
        self.assertGreaterEqual(r.advance, 0)

    def test_premultiplied_alpha(self):
        # in premultiplied BGRA no colour channel may exceed its alpha
        import freetype
        face = freetype.Face(_CEMOJI)
        r = self.cf.glyph(face.get_char_index(0x1F600))
        buf = r.buf
        bad = 0
        for i in range(0, len(buf), 4):
            a = buf[i + 3]
            if buf[i] > a or buf[i + 1] > a or buf[i + 2] > a:
                bad += 1
        self.assertEqual(bad, 0, "found channels exceeding alpha (not premultiplied)")

    def test_missing_glyph_returns_none(self):
        # ASCII has no colour bitmap in an emoji strike
        import freetype
        face = freetype.Face(_CEMOJI)
        gid = face.get_char_index(0x41)
        self.assertIsNone(self.cf.glyph(gid))

    def test_caches(self):
        import freetype
        face = freetype.Face(_CEMOJI)
        gid = face.get_char_index(0x1F600)
        self.assertIs(self.cf.glyph(gid), self.cf.glyph(gid))


if __name__ == "__main__":
    unittest.main()
