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

    # ⚠️ The one that does NOT come clean, and it is not a bug in the rule: base 22 px
    # + Shift 27 px + AltGr 37 px cannot be laid out on a 72 px panel at all. The pull
    # shrinks it (29 -> 22 px) and stops there. Listed so a future change that "fixes"
    # it has to explain what it dropped.
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

    def test_the_unfixable_key_is_only_IMPROVED(self):
        """bn-BD KC_H cannot fit; the rule must still not make it worse. 29 px was
        the overlap before the pair rule."""
        rep = self._report(*self.CANNOT_FIT[0])
        self.assertLess(rep["overlap_detail"]["shift^altgr"], 29)

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
