"""Tests for the on-demand icon catalog.

Every test here runs OFFLINE. The service exists to fetch from the network, but
a suite that needs the network is one that fails for reasons unrelated to the
code, so the fetch is exercised through its no-network path and the rest --
cache keying, format validation, placement geometry -- is checked directly.
"""

import os
import tempfile
import unittest

from polyhost.services import icon_catalog as ic


class HeightTest(unittest.TestCase):
    def test_clamped_to_what_the_panel_can_hold(self):
        self.assertGreaterEqual(ic.icon_height(), ic.MIN_ICON_HEIGHT)
        self.assertLessEqual(ic.icon_height(), ic.MAX_ICON_HEIGHT)

    def test_the_default_leaves_a_margin(self):
        # 40 would sit flush against the panel edge; the default must not.
        self.assertLess(ic.DEFAULT_ICON_HEIGHT, ic.PANEL_H)


class CacheKeyTest(unittest.TestCase):
    def test_the_key_is_the_SET_of_names_not_their_order(self):
        self.assertEqual(ic.subset_path(["save", "undo"]),
                         ic.subset_path(["undo", "save", "undo"]))

    def test_a_different_set_is_a_different_file(self):
        """Growing the lexicon must fetch a new subset, not reuse the old one."""
        self.assertNotEqual(ic.subset_path(["save"]), ic.subset_path(["save", "undo"]))


class FormatValidationTest(unittest.TestCase):
    def test_only_truetype_is_accepted(self):
        """A woff2 or an HTML error page must never reach the cache.

        Google decides TTF vs woff2 from the User-Agent, and Pillow cannot open
        woff2 -- so without this the failure surfaces much later, at render time,
        where the cause is invisible.
        """
        self.assertTrue(ic._is_ttf(b"\x00\x01\x00\x00rest"))
        self.assertFalse(ic._is_ttf(b"wOF2rest"))
        self.assertFalse(ic._is_ttf(b"<!DOCTYPE html><html>"))
        self.assertFalse(ic._is_ttf(b""))


class OfflineTest(unittest.TestCase):
    def test_an_uncached_subset_returns_none_rather_than_raising(self):
        """Offline is a normal state -- the caller then draws the label text."""
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ic.fetch_subset(["save"], cache_dir=d,
                                              allow_network=False))

    def test_no_names_needs_no_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ic.fetch_subset([], cache_dir=d))

    def test_codepoints_are_empty_offline_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ic.load_codepoints(cache_dir=d, allow_network=False), {})

    def test_codepoints_parse_from_the_cached_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(ic.codepoints_path(d), "w", encoding="utf-8") as fh:
                fh.write("save e161\nundo e166\nrubbish\n")
            cps = ic.load_codepoints(cache_dir=d, allow_network=False)
            self.assertEqual(cps, {"save": 0xE161, "undo": 0xE166})


class PlacementTest(unittest.TestCase):
    """Geometry, checked with an ordinary system font so it needs no catalog."""

    def _font(self):
        import glob
        for pattern in ("/usr/share/fonts/**/DejaVuSans.ttf",
                        "/usr/share/fonts/**/*.ttf"):
            hits = glob.glob(pattern, recursive=True)
            if hits:
                return hits[0]
        return None

    def test_the_icon_is_right_aligned_and_leaves_the_legend_side_blank(self):
        """The property the whole design rests on.

        The firmware clears a courtyard around the overlay's ink and draws it, so
        blank areas leave the legend underneath intact. A full-frame icon would
        erase the letter; a right-aligned one punches in beside it.
        """
        font = self._font()
        if font is None:
            self.skipTest("no system TTF to render with")
        mask = ic.render_overlay("x", font, {"x": ord("X")}, height=30)
        self.assertIsNotNone(mask)
        self.assertEqual(mask.shape, (ic.PANEL_H, ic.PANEL_W))
        columns = mask.any(axis=0)
        self.assertFalse(columns[:ic.PANEL_W // 2].any(),
                         "ink in the left half would overwrite the legend")
        self.assertTrue(columns[ic.PANEL_W // 2:].any(), "no ink drawn at all")
        # And it must not run off the panel: the right margin is respected.
        self.assertFalse(columns[ic.PANEL_W - ic.ICON_MARGIN:].any())

    def test_an_unknown_name_yields_nothing(self):
        font = self._font()
        if font is None:
            self.skipTest("no system TTF to render with")
        self.assertIsNone(ic.render_overlay("nope", font, {"x": ord("X")}))


if __name__ == "__main__":
    unittest.main()
