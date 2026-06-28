"""Tests for the font-pack extend round-trip (polyhost.services.fontpack_extend).

Needs the [fontgen] deps (freetype-py/numpy) + a system TTF + the shipped
bundles; skips cleanly otherwise.  Builds a font from a TTF, splices it into a
shipped bundle, and verifies the result decodes valid with the new font intact
and the originals untouched.
"""
import glob
import os
import unittest

try:
    import numpy  # noqa: F401
    import freetype  # noqa: F401
    from polyhost.services import fontpack_extend as ext
    from polyhost.services import fontpack_reader as fpr
    from polyhost.services.fontgen import RenderOptions
    _ERR = None
except Exception as e:  # pragma: no cover
    _ERR = e

RES = os.path.join(os.path.dirname(__file__), "..", "..", "polyhost", "res", "fontpack")
_SYMBOL = os.path.join(RES, "symbol.plyf")


def _find_font():
    for pat in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/**/*.ttf"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return None


_FONT = _find_font()


@unittest.skipIf(_ERR is not None, f"fontgen deps unavailable: {_ERR}")
@unittest.skipUnless(_FONT and os.path.exists(_SYMBOL), "no font / shipped bundle")
class ExtendRoundTripTest(unittest.TestCase):

    def test_render_packfont_sets_index(self):
        pf = ext.render_packfont(_FONT, codepoint_range=(0x41, 0x44),
                                 opts=RenderOptions(size=16), global_index=99, name="t")
        self.assertEqual(pf.global_index, 99)
        self.assertEqual(len(pf.glyphs), 4)

    def test_render_packfont_requires_one_source(self):
        with self.assertRaises(ValueError):
            ext.render_packfont(_FONT)            # neither
        with self.assertRaises(ValueError):
            ext.render_packfont(_FONT, codepoint_range=(1, 2), sequence="41")  # both

    def test_splice_adds_font_and_bumps_version(self):
        before = fpr.decode_pack_file(_SYMBOL, "symbol")
        gidx = max(f.global_index for f in before.fonts) + 1
        new = ext.render_packfont(_FONT, codepoint_range=(0x2190, 0x2193),
                                  opts=RenderOptions(size=24), global_index=gidx)
        data = ext.splice_into_bundle(_SYMBOL, new)
        after = fpr.decode_pack(data, "symbol")

        self.assertTrue(after.crc_ok)
        self.assertEqual(after.font_count, before.font_count + 1)
        self.assertEqual(after.content_version, before.content_version + 1)
        # new font intact
        spliced = next(f for f in after.fonts if f.global_index == gidx)
        self.assertEqual(spliced.glyphs, new.glyphs)
        clen = new.bitmap_content_len()
        self.assertEqual(spliced.bitmap[:clen], new.bitmap[:clen])
        # originals untouched
        for f0 in before.fonts:
            f1 = next(x for x in after.fonts if x.global_index == f0.global_index)
            self.assertEqual((f1.first, f1.last, f1.glyphs), (f0.first, f0.last, f0.glyphs))

    def test_render_options_from_manifest(self):
        ro = ext.render_options_from_manifest(
            {"size": 18, "grayscale": True, "dither": "fs", "normalize": True,
             "invert": True, "edge": True, "outline": 1, "render_height": 40,
             "yadvance": 48, "max_width": 60, "weight": 500, "xshift": -12, "bits": 32})
        self.assertEqual((ro.size, ro.render_mode, ro.outline, ro.height, ro.yadvance,
                          ro.max_width, ro.weight, ro.xshift, ro.bits),
                         (18, 1, 1, 40, 48, 60, 500, -12, 32))
        self.assertTrue(ro.normalize and ro.invert and ro.edge_preserve)

    def test_render_options_weight_and_bits_defaults(self):
        ro = ext.render_options_from_manifest({"size": 14})
        self.assertEqual(ro.weight, -1)          # absent weight -> unset
        self.assertEqual(ro.bits, 1)             # absent bits -> 1-bit

    def test_peek_source_glyph_present_vs_absent(self):
        pf = ext.peek_source_glyph(_FONT, 0x41, {"size": 24})   # 'A' exists
        self.assertIsNotNone(pf)
        self.assertEqual(pf.first, 0x41)
        self.assertGreater(pf.glyphs[0]["width"], 0)
        # U+FDD0 is a permanent noncharacter — no font has a glyph for it
        self.assertIsNone(ext.peek_source_glyph(_FONT, 0xFDD0, {"size": 24}))

    def test_splice_replace_keeps_count(self):
        before = fpr.decode_pack_file(_SYMBOL, "symbol")
        victim = before.fonts[0]
        new = ext.render_packfont(_FONT, codepoint_range=(victim.first, victim.last),
                                  opts=RenderOptions(size=16),
                                  global_index=victim.global_index)
        data = ext.splice_into_bundle(_SYMBOL, new, content_version=42)
        after = fpr.decode_pack(data, "symbol")
        self.assertEqual(after.font_count, before.font_count)   # replaced, not added
        self.assertEqual(after.content_version, 42)
        self.assertTrue(after.crc_ok)


class LoadRenderSettingsTest(unittest.TestCase):
    """load_render_settings is pure-stdlib — runs even without the fontgen deps."""

    def test_missing_path_returns_empty(self):
        from polyhost.services import fontpack_extend as e
        self.assertEqual(e.load_render_settings("/no/such/file.json"), {})

    def test_shipped_loads(self):
        from polyhost.services import fontpack_extend as e
        m = e.load_render_settings()
        if not m:
            self.skipTest("no shipped render settings")
        self.assertIn("source_file", next(iter(m.values())))


if __name__ == "__main__":
    unittest.main()
