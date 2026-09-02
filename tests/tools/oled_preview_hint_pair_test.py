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
    """The AltGr hint is drawn at HALF size on the layouts that ask for it.

    ⚠️ WHICH layouts is DATA -- `{letter.altgrhalf}` in `lang_lut.xlsx` -- and the
    measurement is why. The intuition is "Arabic and Indic have very large glyphs",
    but AltGr ink HEIGHT does not separate them: median 20 px on Arabic letters
    against 21 px on Latin ones. What actually differs is that on those layouts the
    base and the Shift hint are wide too, so the row reads crowded -- a per-LAYOUT
    judgement no glyph measurement can make. Hence a spreadsheet cell rather than a
    threshold, and hence these cases pin all four arms of the gate.

    The one size test that remains is the mark guard, whose threshold IS measured:
    the ink-height histogram over the 318 distinct AltGr cells has an EMPTY BIN at
    8 px, marks below it and letterforms from 9 px up.
    """

    # in scope, a letter, and above the mark guard -> halves.
    HALVES = [("ar-SA", "KC_F"), ("ar-SA", "KC_H"), ("ar-AE", "KC_F"),
              ("bn-BD", "KC_D"), ("bn-BD", "KC_H")]
    # Each of the three ways OUT of the gate, one fixture apiece.
    NOT_IN_SCOPE  = [("de-DE", "KC_Q"), ("de-DE", "KC_E"), ("fr-FR", "KC_E")]
    NOT_A_LETTER  = [("ar-SA", "KC_1"), ("ar-SA", "KC_SEMICOLON")]
    UNDER_THE_GAP = [("hi-IN", "KC_H"), ("hi-IN", "KC_K"), ("mr-IN", "KC_H")]

    def _drawn_height(self, lang, kc):
        """Ink height of the AltGr hint as render_key actually drew it.

        ⚠️ HEIGHT, not the box: `bbox()` and `draw()` agree on height for every
        fixture here but differ by 1 px on the WIDTH of a few glyphs (the euro sign
        measures 15 and inks 14), so a width comparison would be pinning that
        discrepancy rather than the halving.
        """
        box = self._report(lang, kc)["box"]
        self.assertIn("altgr", box, f"{lang} {kc} draws no AltGr hint")
        return box["altgr"][3] - box["altgr"][2] + 1

    def _full_height(self, lang, kc):
        """The glyph's own full-size ink height, measured straight off the renderer.

        ⚠️ NOT `render_key` with the halving disabled, which is the obvious way to
        write this and is fail-open: disabling it means moving `ALTGR_HALF_MIN_INK_H`
        out of reach, so a MUTATION of that very constant also disables the reference
        and both sides move together. Mutation-checked -- with the threshold forced
        true, the version that turned the constant up went green on the mark cases.
        """
        li = self.L.langs.index(lang)
        alt = self.L.var(li, op.ROW[kc], op.VAR_ALTGR)
        self.assertIsNotNone(alt, f"{lang} {kc} has no AltGr cell")
        _xmn, _xmx, ymn, ymx = self.R.bbox(alt)
        return ymx - ymn + 1

    def _assert_halved(self, lang, kc):
        full, drawn = self._full_height(lang, kc), self._drawn_height(lang, kc)
        # ⚠️ NOT exactly ceil(n/2): the 2x2-OR downsample halves each glyph's own
        # offsets and extents, so where the ink lands in the merged pairs depends on
        # parity and can add a row (ar-AE KC_F: 21 px -> 11, not 10). Bound it within
        # 1 of the ideal rather than overfitting to the pixel arithmetic.
        self.assertGreaterEqual(full, 9, "fixture is below the mark guard")
        self.assertLessEqual(drawn, (full + 1) // 2 + 1)
        self.assertGreaterEqual(drawn, full // 2)

    def _assert_full_size(self, lang, kc):
        self.assertEqual(self._drawn_height(lang, kc), self._full_height(lang, kc))

    def test_an_opted_in_letter_key_halves_its_AltGr_hint(self):
        for lang, kc in self.HALVES:
            with self.subTest(lang=lang, kc=kc):
                self._assert_halved(lang, kc)

    def test_a_layout_that_did_not_opt_in_is_untouched(self):
        """A Latin AltGr glyph is the same HEIGHT as an Arabic one, so only the
        spreadsheet cell distinguishes these from the cases above."""
        for lang, kc in self.NOT_IN_SCOPE:
            with self.subTest(lang=lang, kc=kc):
                self._assert_full_size(lang, kc)

    def test_a_NON_letter_key_is_untouched_even_on_an_opted_in_layout(self):
        """`{letter.altgrhalf}` names the letter category, so the digit and symbol
        rows of the same layout keep their full-size hints."""
        for lang, kc in self.NOT_A_LETTER:
            with self.subTest(lang=lang, kc=kc):
                self._assert_full_size(lang, kc)

    def test_a_tiny_AltGr_MARK_is_left_alone(self):
        """⚠️ Not a nicety: a 4 px combining mark halves to 2 px, which is a dot. This
        is the guard that carries the Indic layouts -- their letter AltGr hints are
        mostly bare marks, at a median 4 px."""
        for lang, kc in self.UNDER_THE_GAP:
            with self.subTest(lang=lang, kc=kc):
                self._assert_full_size(lang, kc)

    def test_the_threshold_sits_in_the_histogram_gap(self):
        """The claim the mark guard rests on: no AltGr cell inks exactly 8 px tall, so
        moving the constant by one cannot reclassify anything. If this fails, a new
        language has landed in the gap and the constant needs re-deriving -- from the
        histogram, not by taste."""
        heights = set()
        for lang in self.L.langs:
            for kc in op.ROW:
                box = self._report(lang, kc).get("box", {})
                if "altgr" not in box:
                    continue
                heights.add(self._full_height(lang, kc))
        self.assertNotIn(op.ALTGR_HALF_MIN_INK_H + 1, heights)

    def test_the_opted_in_set_is_the_scripts_it_claims(self):
        """The spreadsheet column, read back: every layout that opted in is an
        Arabic-script or Indic one. A stray 1 on a Latin layout is exactly the kind
        of thing a 160-column row invites, and nothing else would catch it."""
        from oled_preview import get_setting, VAR_ALTGR
        want = {"ar", "fa", "ur", "ku", "ps",            # Arabic script
                "hi", "mr", "ne", "bn", "te", "ta"}      # Indic
        on = {lang for i, lang in enumerate(self.L.langs)
              if get_setting(self.L, op.ALTGR_HALF_ROW, i, VAR_ALTGR)}
        self.assertTrue(on, "nothing opted in -- the row is missing or empty")
        self.assertEqual({l for l in on if l[:2] not in want}, set())


if __name__ == "__main__":
    unittest.main()
