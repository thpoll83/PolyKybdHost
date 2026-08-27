"""The font ladder and icon lookup behind a macro keycap's style.

These assert against the SHIPPED fonts rather than fixtures, for the same reason the
label measurements do: a regenerated face that changed what fits should fail here
rather than on hardware.
"""
import unittest

from polyhost.services import macro_label as ml
from polyhost.services import macro_look as mk

try:
    _FONTS, _SOURCE = mk.load_render_fonts()
    _PACKS = mk.load_pack_fonts()
    _NANO = ml.load_nano_font(ml.default_font_dir())
    _MID = mk.load_ui_font(ml.default_font_dir(), "util_font.h", mk.MID_FONT_SYMBOL)
    _ERR = None
except Exception as e:  # pragma: no cover - depends on a firmware checkout
    _ERR = e


@unittest.skipIf(_ERR, f"fonts unavailable: {_ERR}")
class LadderTest(unittest.TestCase):
    def _ladder(self):
        return mk.caption_ladder(_PACKS, mid_font=_MID, nano_font=_NANO)

    def test_a_tier_is_a_SET_of_faces_not_one(self):
        """latinbig emits twelve sub-fonts per tier, one per latin range. Requiring a
        single font to cover the whole caption would reject any caption with an accent
        -- exactly what the tier exists to draw."""
        ladder = self._ladder()
        big = [entry for entry in ladder if entry[2].startswith("latinbig")]
        self.assertTrue(big, "the shipped latinbig bundle should provide both tiers")
        for fonts, _base, name in big:
            self.assertGreater(len(fonts), 1, f"{name} collapsed to a single face")

    def test_the_ladder_runs_biggest_first(self):
        names = [n for _f, _b, n in self._ladder()]
        self.assertEqual(names[:2], ["latinbig L", "latinbig M"])
        self.assertEqual(names[-1], "nano")

    def test_a_short_caption_reaches_the_big_tier(self):
        got = mk.plan_caption("M", self._ladder())
        self.assertIsNotNone(got)
        self.assertEqual(got[3], "latinbig L")

    def test_a_long_caption_falls_through_to_a_smaller_face(self):
        """The point of the ladder: 'password' cannot fit the panel at 39 px, so it has
        to come out at a face that does rather than being clipped."""
        got = mk.plan_caption("password", self._ladder())
        self.assertIsNotNone(got)
        self.assertNotIn("latinbig", got[3])
        self.assertLessEqual(got[2][1] - got[2][0] + 1, ml.PANEL_W)

    def test_every_planned_caption_fits_the_panel(self):
        ladder = self._ladder()
        for cap in ("email", "work mail", "password", "Hello World!", "M", "WWWWWWWW",
                    "iiiiiiiiiiii", "café"):
            got = mk.plan_caption(cap, ladder)
            self.assertIsNotNone(got, cap)
            _f, _b, box, _n = got
            self.assertLessEqual(box[1] - box[0] + 1, ml.PANEL_W, cap)
            self.assertLessEqual(box[3] - box[2] + 1, ml.PANEL_H, cap)

    def test_an_empty_caption_plans_nothing(self):
        """STYLE_TEXT with no caption has nothing to draw, and the firmware falls back
        to a captioned style rather than blanking the key."""
        self.assertIsNone(mk.plan_caption("", self._ladder()))

    def test_a_tier_is_all_or_nothing(self):
        """One missing glyph rejects the WHOLE tier. A partial hit would mix two faces
        in one caption, which by the baseline-align rule is also two baselines.

        ⚠️ The caption has to be MIXED. An all-missing one ('中') returns None whether
        the rule is enforced or not -- nothing drawable was ever added to the box -- so
        it passes against an implementation that happily skips what it cannot find.
        Mutation-checked: dropping the guard fails this and nothing else.
        """
        fonts, base, _n = self._ladder()[0]
        self.assertIsNotNone(mk.bbox("M", fonts, base), "fixture broken: 'M' should fit")
        self.assertIsNone(mk.bbox("M中", fonts, base))
        self.assertIsNone(mk.bbox("中M", fonts, base))


@unittest.skipIf(_ERR, f"fonts unavailable: {_ERR}")
class IconLookupTest(unittest.TestCase):
    def test_it_finds_a_glyph_the_keyboard_can_draw(self):
        for cp in (0x1F4E7, 0x2699, ord("A")):
            self.assertIsNotNone(mk.find_glyph(_FONTS, cp), hex(cp))

    def test_it_reports_nothing_for_a_codepoint_no_font_covers(self):
        """The firmware falls back to the index for exactly this case, so the editor
        has to be able to tell the difference rather than showing an empty mark."""
        self.assertIsNone(mk.find_glyph(_FONTS, 0x10FFFD))

    def test_a_gap_record_is_not_a_hit(self):
        """The build empties any pack glyph a higher-priority font already draws
        identically. A gap is all-zero, and reading it as a hit would render nothing
        while reporting success."""
        gapped = None
        for f in _FONTS:
            for i, g in enumerate(f.glyphs):
                if not (g["width"] or g["height"]):
                    gapped = (f, f.first + i)
                    break
            if gapped:
                break
        if gapped is None:
            self.skipTest("no gap records in the shipped fonts")
        font, cp = gapped
        hit = mk.find_glyph([font], cp)
        self.assertIsNone(hit, f"{font.name} gap at {cp:#x} read as drawable")


if __name__ == "__main__":
    unittest.main()
