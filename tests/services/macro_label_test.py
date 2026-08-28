"""Tests for the macro label pixel measurement.

The firmware truncates by measured width, so an editor that counted characters would
promise the user letters the keycap will not draw. These pin the arithmetic against the
COMMITTED font rather than a fixture: the numbers below were read out of the shipped
nano_font.h, so a regenerated face that changed them fails here rather than on hardware.
"""

import os
import unittest

from polyhost.services import macro_label as ml

FONT_DIR = ml.default_font_dir()
HAVE_FONT = os.path.isfile(os.path.join(FONT_DIR, "nano_font.h"))


@unittest.skipUnless(HAVE_FONT, f"firmware fonts not found at {FONT_DIR}")
class MeasureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = ml.load_nano_font(FONT_DIR)

    def test_the_font_is_the_ascii_only_nano_face(self):
        # The whole reason poly_macro_label_set drops non-ASCII at the door.
        self.assertEqual(self.font.first, 0x20)
        self.assertEqual(self.font.last, 0x7E)

    def test_empty_string_has_no_width(self):
        # Not a negative one: a naive xmax - xmin + 1 over an empty box returns 0 only
        # by accident, and -1 + 1 for a box that was never opened.
        self.assertEqual(ml.measure("", self.font), 0)

    def test_known_widths_from_the_shipped_font(self):
        for text, width in [("email", 25), ("work mail", 48), ("password", 49),
                            ("Hello World!", 61), ("WWWWWWWW", 72)]:
            with self.subTest(text=text):
                self.assertEqual(ml.measure(text, self.font), width)

    def test_a_w_is_about_three_times_an_i(self):
        # This ratio is the entire argument for measuring instead of counting.
        self.assertGreater(ml.measure("W" * 8, self.font),
                           2.5 * ml.measure("i" * 8, self.font))


@unittest.skipUnless(HAVE_FONT, f"firmware fonts not found at {FONT_DIR}")
class FitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = ml.load_nano_font(FONT_DIR)

    def test_a_label_that_fits_is_untouched(self):
        r = ml.fit("work mail", self.font)
        self.assertEqual(r.text, "work mail")
        self.assertFalse(r.truncated)
        self.assertEqual(r.dropped, "")

    def test_exactly_the_panel_width_still_fits(self):
        # 72 px is the panel, so <= must not be <.
        r = ml.fit("WWWWWWWW", self.font)
        self.assertEqual(r.text, "WWWWWWWW")
        self.assertEqual(r.width, ml.PANEL_W)

    def test_one_character_too_wide_drops_exactly_one(self):
        r = ml.fit("WWWWWWWWW", self.font)
        self.assertEqual(r.text, "WWWWWWWW")
        self.assertEqual(r.dropped, "W")

    def test_narrow_letters_keep_more_of_the_string(self):
        # The point of measuring: the same character count fits or does not depending
        # entirely on which characters they are.
        self.assertEqual(ml.fit("i" * 12, self.font).text, "i" * 12)
        self.assertLess(len(ml.fit("m" * 12, self.font).text), 12)

    def test_the_storage_stride_is_applied_before_the_pixel_fit(self):
        # A label is cut to POLY_MACRO_LABEL_LEN before it ever reaches the panel test,
        # so a very long narrow string is limited by the stride, not by the width.
        r = ml.fit("i" * 40, self.font)
        self.assertEqual(len(r.text), ml.LABEL_MAX_CHARS)

    def test_full_width_reports_the_whole_input(self):
        # So a UI can render the overflow greyed instead of just hiding it.
        r = ml.fit("WWWWWWWWW", self.font)
        self.assertGreater(r.full_width, ml.PANEL_W)
        self.assertLessEqual(r.width, ml.PANEL_W)

    def test_fit_is_idempotent(self):
        once = ml.fit("mmmmmmmmmmmm", self.font).text
        self.assertEqual(ml.fit(once, self.font).text, once)


if __name__ == "__main__":
    unittest.main()
