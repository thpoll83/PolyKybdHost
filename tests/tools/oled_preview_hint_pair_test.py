"""The Shift and AltGr hints are laid out as a PAIR, not independently.

Both sit right of the base legend -- Shift upper, AltGr lower -- and until
2026-09-02 it was only their per-language VERTICAL offsets that held them apart.
That works for a narrow Latin pair and fails for a tall script: measured over all
160 layouts x 49 keys, **24 keys across 19 layouts** drew the two hints through
each other -- every `ar-*` layout on `KC_F` (13 px), and `bn-BD` up to 57 px on
`KC_D`. It is what the field report "for a lot of arabic keys i saw collision"
was looking at.

⚠️ It is NOT fixable in `lang_lut.xlsx`. The offsets are per LANGUAGE while the
room left over is decided by the WIDTH of this key's three glyphs, so one number
would have to satisfy the worst key of the layout and would crush every other key
into the base. Hence the rule lives in `render_key()` (and in `poly_keymap.c`,
which this module mirrors): when the two ink boxes intersect in BOTH axes, pull
the Shift hint left into the gap between the base and the right-clamped AltGr.

⚠️ A Python model of C checked only against itself proves nothing -- the standing
caveat on this module. These cases are therefore stated as PROPERTIES of the
rendered ink (no overlap; nothing pushed off the panel; the Shift never crosses
the base's margin), which hold for the firmware or for neither.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))
try:
    import oled_preview as op
    from gfx_font import load_all_fonts
    from polyhost.services import macro_label as ml
    TOOLS_ERR = ""
except Exception as exc:                              # pragma: no cover - env gate
    op = load_all_fonts = ml = None
    TOOLS_ERR = f"preview tools unavailable: {type(exc).__name__}: {exc}"


def _fw():
    """<fw>/keyboards/polykybd, or "" when there is no checkout beside this repo."""
    try:
        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
    except Exception:
        return ""
    return pk if os.path.isdir(pk) else ""


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class HintPairTest(unittest.TestCase):
    # The keys the sweep found, worst first. Every one of these drew the two hints
    # through each other before the pair rule.
    COLLIDED = [("ar-SA", "KC_F"), ("ar-EG", "KC_F"), ("ar-AE", "KC_F"),
                ("bn-BD", "KC_D"), ("bn-BD", "KC_S"), ("bn-BD", "KC_K"),
                ("bn-BD", "KC_I"), ("bn-BD", "KC_C")]

    # ⚠️ The one the PULL ALONE could not fix: base 22 px + Shift 27 px + AltGr 37 px
    # will not fit a 72 px panel at full size, and the pull could only shrink it
    # (29 -> 22 px). Halving the AltGr hint is what closes it. Kept as its own case
    # so a change that reverted the halving would fail here and nowhere else.
    CANNOT_FIT = [("bn-BD", "KC_H")]

    @classmethod
    def setUpClass(cls):
        pk = _fw()
        if not pk:
            raise unittest.SkipTest("no firmware checkout beside this repo")
        xlsx = os.path.join(pk, "lang", "lang_lut.xlsx")
        if not os.path.isfile(xlsx):
            raise unittest.SkipTest("lang_lut.xlsx not in this checkout")
        cls.R = op.Renderer(load_all_fonts(os.path.join(pk, "base", "fonts")))
        cls.L = op.Lang(xlsx, op.load_named_glyphs(
            os.path.join(pk, "lang", "named_glyphs.h")))

    def _report(self, lang, kc):
        """Render off-panel with a wide margin so clipped ink is still counted."""
        if lang not in self.L.langs:
            self.skipTest(f"{lang} not in this checkout's LUT")
        save = op.OVERSHOOT
        op.OVERSHOOT = 60
        try:
            rep = {}
            op.render_key(self.L, self.R, lang, kc, False, False,
                          channels=True, report=rep)
            return rep
        finally:
            op.OVERSHOOT = save

    def test_the_two_hints_no_longer_overlap(self):
        for lang, kc in self.COLLIDED:
            with self.subTest(lang=lang, kc=kc):
                rep = self._report(lang, kc)
                self.assertEqual(rep["overlap_detail"]["shift^altgr"], 0)

    def test_pulling_the_shift_left_does_not_push_it_into_the_base(self):
        """The pull is floored at the base's own 2 px margin, so it can only ever
        spend space the base is not using."""
        for lang, kc in self.COLLIDED + self.CANNOT_FIT:
            with self.subTest(lang=lang, kc=kc):
                rep = self._report(lang, kc)
                self.assertEqual(rep["overlap_detail"]["base^shift"], 0)

    def test_pulling_the_shift_left_does_not_push_it_off_the_panel(self):
        """A hint that cleared the other one by leaving the keycap would be worse
        than the collision -- and this is the direction the floor does NOT bound."""
        for lang, kc in self.COLLIDED + self.CANNOT_FIT:
            with self.subTest(lang=lang, kc=kc):
                rep = self._report(lang, kc)
                self.assertEqual(rep["oob"]["shift"], 0)

    def test_the_key_the_pull_alone_could_not_fix(self):
        """bn-BD KC_H: 29 px of overlap before the pair rule, 22 px after the pull
        alone, 0 once the AltGr hint is halved."""
        rep = self._report(*self.CANNOT_FIT[0])
        self.assertEqual(rep["overlap_detail"]["shift^altgr"], 0)


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class HalfSizeAltGrTest(HintPairTest):
    """The AltGr hint is drawn at HALF size -- it is a hint, not a legend.

    ⚠️ The exception is what needs a guard: a mark that is already tiny comes out a
    dot. The threshold is measured rather than chosen -- over the 318 distinct AltGr
    cells the ink-height histogram has an EMPTY BIN at 8 px, marks below it and
    letterforms from 9 px up -- so these cases pin BOTH sides of that gap.
    """

    # (lang, kc, full-size ink height) -- comfortably above the gap, so they halve.
    TALL = [("de-DE", "KC_Q"), ("de-DE", "KC_E"), ("fr-FR", "KC_0"),
            ("ar-AE", "KC_F"), ("bn-BD", "KC_D")]
    # Below the gap: Hebrew nikud (2-3 px) and a diaeresis. Halving these destroys
    # them, so they must render byte-identically to the full-size draw.
    TINY = [("he-IL", "KC_W"), ("he-IL", "KC_EQUAL"), ("af-ZA", "KC_SEMICOLON"),
            ("ay-BO", "KC_3")]

    def _altgr_box(self, lang, kc):
        box = self._report(lang, kc)["box"]
        self.assertIn("altgr", box, f"{lang} {kc} draws no AltGr hint")
        x0, x1, y0, y1 = box["altgr"]
        return x1 - x0 + 1, y1 - y0 + 1

    def _full_size_box(self, lang, kc):
        """The same key with the halving disabled, so the comparison is like-for-like."""
        save = op.ALTGR_HALF_MIN_INK_H
        op.ALTGR_HALF_MIN_INK_H = 127          # nothing is taller than this
        try:
            return self._altgr_box(lang, kc)
        finally:
            op.ALTGR_HALF_MIN_INK_H = save

    def test_a_tall_AltGr_hint_is_drawn_at_half_size(self):
        for lang, kc in self.TALL:
            with self.subTest(lang=lang, kc=kc):
                fw, fh = self._full_size_box(lang, kc)
                hw, hh = self._altgr_box(lang, kc)
                # ⚠️ NOT exactly ceil(n/2): the 2x2-OR downsample halves each glyph's
                # own offsets and extents, so where the ink lands in the merged pairs
                # depends on parity and can add a row (ar-AE KC_F: 20 px -> 11, not
                # 10). Bound it within 1 of the ideal rather than overfitting to the
                # pixel arithmetic -- the property is "materially smaller", and an
                # exact figure here would just re-encode the implementation.
                for got, full, axis in ((hw, fw, "width"), (hh, fh, "height")):
                    self.assertLessEqual(got, (full + 1) // 2 + 1, axis)
                    self.assertGreaterEqual(got, full // 2, axis)

    def test_a_tiny_AltGr_MARK_is_left_alone(self):
        """⚠️ Not a nicety: a 2x3 nikud halves to 1x2, which is a dot, not a mark."""
        for lang, kc in self.TINY:
            with self.subTest(lang=lang, kc=kc):
                self.assertEqual(self._altgr_box(lang, kc),
                                 self._full_size_box(lang, kc))

    def test_the_threshold_sits_in_the_histogram_gap(self):
        """The claim the threshold rests on: no AltGr cell inks exactly 8 px tall, so
        moving the constant by one cannot reclassify anything. If this fails, a new
        language has landed in the gap and the constant needs re-deriving -- from the
        histogram, not by taste."""
        heights = set()
        for lang in self.L.langs:
            for kc in op.ROW:
                box = self._report(lang, kc).get("box", {})
                if "altgr" not in box:
                    continue
                fw, fh = self._full_size_box(lang, kc)
                heights.add(fh)
        self.assertNotIn(op.ALTGR_HALF_MIN_INK_H + 1, heights)

    def test_a_key_with_only_ONE_hint_is_untouched(self):
        """The pull is gated on BOTH hints existing, so the long-standing single-hint
        placement cannot move -- which is what bounds the change to the 53 keys the
        sweep says moved, out of 160 x 49.

        ⚠️ `en-US` hides the Shift hint on LETTERS, not on digits: `KC_1` really does
        draw the `!`. The boxes below are what the pre-pair code rendered, so a rule
        that fired on a lone hint would move them and fail here."""
        for lang, kc, want in [("en-US", "KC_1", (37, 39, 1, 20)),
                               ("de-DE", "KC_1", (29, 31, 1, 20))]:
            with self.subTest(lang=lang, kc=kc):
                rep = self._report(lang, kc)
                self.assertNotIn("altgr", rep["box"])   # a lone Shift hint
                self.assertEqual(rep["box"]["shift"], want)
                self.assertEqual(rep["overlap"], 0)


if __name__ == "__main__":
    unittest.main()
