"""glyph_script_preview — the block arithmetic, and that every script draws.

Two claims are worth pinning, and only one of them is arithmetic:

* **The block table.** `script_base()` mirrors the firmware's
  `glyph_script_blocks[]`; the expected values here are copied from
  `qmk_firmware/keyboards/polykybd/poly_keymap.c`, so a script added on one side
  without the other fails here rather than previewing a neighbouring script.
* **That the previews actually have ink.** A decoder that resolves the wrong
  font, or lays glyphs out off its own canvas, still returns a perfectly valid
  image — of nothing.  So the tests render and count lit pixels, the same rule
  the keycap previews follow.
"""
import unittest

from polyhost.device.command_ids import GlyphScript
from polyhost.services import glyph_script_preview as gsp

# From the firmware's glyph_script_blocks[] — {script value: (base, has digits)}.
FIRMWARE_BLOCKS = {
    GlyphScript.TENGWAR.value:  (0xE800, True),
    GlyphScript.RUNES.value:    (0xE840, False),
    GlyphScript.AUREBESH.value: (0xE880, False),
    GlyphScript.SGA.value:      (0xE8C0, True),
    GlyphScript.CIRTH.value:    (0xE900, False),
    GlyphScript.IBMVGA.value:   (0xE940, True),
    GlyphScript.C64.value:      (0xE980, True),
    GlyphScript.AMIGA.value:    (0xE9C0, True),
    GlyphScript.APL.value:      (0xEA00, True),
    GlyphScript.BRAILLE.value:  (0xEA40, True),
}


def lit(img):
    """Lit pixels — histogram[0] is the unlit count, everything else is ink."""
    return img.width * img.height - img.histogram()[0]


class TestCodepoints(unittest.TestCase):
    def test_bases_match_the_firmware_table(self):
        for value, (base, _digits) in FIRMWARE_BLOCKS.items():
            self.assertEqual(gsp.script_base(value), base, GlyphScript(value).name)

    def test_standard_has_no_block(self):
        self.assertIsNone(gsp.script_base(GlyphScript.STANDARD.value))
        self.assertIsNone(gsp.script_base(None))

    def test_letters_and_digits_are_dense_in_keycode_order(self):
        # 'a'..'z' -> 0..25, then KC_1..KC_0 (0 LAST) -> 26..35.
        self.assertEqual(gsp.glyph_index("a"), 0)
        self.assertEqual(gsp.glyph_index("z"), 25)
        self.assertEqual(gsp.glyph_index("1"), 26)
        self.assertEqual(gsp.glyph_index("9"), 34)
        self.assertEqual(gsp.glyph_index("0"), 35)

    def test_anything_else_has_no_glyph(self):
        for ch in ("A", "!", " ", "", "ab"):
            self.assertIsNone(gsp.glyph_index(ch), repr(ch))


class TestShippedBundle(unittest.TestCase):
    """Against the real polyhost/res/fontpack/fantasy.plyf."""

    @classmethod
    def setUpClass(cls):
        cls.pack = gsp.load_pack()
        if cls.pack is None:
            raise unittest.SkipTest("fantasy.plyf is not shipped in this tree")

    def test_every_script_resolves_a_font(self):
        for script in GlyphScript:
            if script is GlyphScript.STANDARD:
                continue
            self.assertIsNotNone(gsp.font_for_script(self.pack, script.value), script.name)

    def test_digit_coverage_matches_the_firmware_flags(self):
        # The firmware gates the digit row on a per-script flag; the font's own
        # coverage is what the host reads it from, so the two must agree.
        for value, (_base, digits) in FIRMWARE_BLOCKS.items():
            font = gsp.font_for_script(self.pack, value)
            self.assertEqual(gsp.has_digits(font), digits, GlyphScript(value).name)
            self.assertEqual("123" in gsp.sample_text(font), digits, GlyphScript(value).name)

    def test_every_script_draws_something(self):
        for script in GlyphScript:
            if script is GlyphScript.STANDARD:
                continue
            img = gsp.script_preview(script.value)
            self.assertIsNotNone(img, script.name)
            self.assertGreater(lit(img), 20, f"{script.name} preview is (nearly) blank")

    def test_a_script_the_pack_does_not_carry_has_no_preview(self):
        # An index beyond the shipped set: the firmware accepts any value and
        # renders the normal legend, so the host must degrade the same way.
        self.assertIsNone(gsp.script_preview(200))

    def test_the_braille_dot_is_measured_against_the_whole_alphabet(self):
        # Braille 'a' is a single dot near the top of the cell. Measured against
        # its OWN ink it would be scaled up until it filled the icon as a solid
        # square, which is why ink_extent() spans the alphabet.
        font = gsp.font_for_script(self.pack, GlyphScript.BRAILLE.value)
        glyph = font.glyphs[0]                      # the 'a' cell
        img = gsp.script_preview(GlyphScript.BRAILLE.value, "a")
        self.assertGreater(img.height, 4 * glyph["height"])
        top_half = img.crop((0, 0, img.width, img.height // 2))
        self.assertEqual(lit(img), lit(top_half))   # the dot keeps its place too

    def test_one_script_is_not_drawn_with_another_script_s_font(self):
        images = {}
        for script in GlyphScript:
            if script is GlyphScript.STANDARD:
                continue
            images[script.name] = gsp.script_preview(script.value, "abc").tobytes()
        self.assertEqual(len(set(images.values())), len(images))


class TestStandard(unittest.TestCase):
    def test_standard_previews_the_normal_latin_face(self):
        if gsp.load_resident() is None:
            self.skipTest("res/preview/resident.plyf is not shipped in this tree")
        img = gsp.preview(GlyphScript.STANDARD.value)
        self.assertIsNotNone(img)
        self.assertGreater(lit(img), 20)

    def test_the_latin_face_is_the_one_that_wins_the_lookup(self):
        # Front-to-back precedence: the lowest global index covering the letters.
        pack = gsp.load_resident()
        if pack is None:
            self.skipTest("res/preview/resident.plyf is not shipped in this tree")
        font = gsp.latin_font(pack)
        self.assertIsNotNone(font)
        covering = [f for f in pack.fonts if f.first <= ord("a") and f.last >= ord("z")]
        self.assertEqual(font.global_index, min(f.global_index for f in covering))


class TestMissingData(unittest.TestCase):
    """A preview is optional: a missing or malformed bundle must leave the menu
    alone rather than raise into the Qt main thread."""

    def test_a_missing_file_is_not_an_error(self):
        self.assertIsNone(gsp.load_pack("/nonexistent/fantasy.plyf"))

    def test_a_malformed_file_is_not_an_error(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".plyf", delete=False) as fh:
            fh.write(b"not a pack" * 10)
        self.assertIsNone(gsp.load_pack(fh.name))

    def test_no_pack_means_no_font_and_no_crash(self):
        self.assertIsNone(gsp.font_for_script(None, GlyphScript.TENGWAR.value))
        self.assertIsNone(gsp.latin_font(None))


if __name__ == "__main__":
    unittest.main()
