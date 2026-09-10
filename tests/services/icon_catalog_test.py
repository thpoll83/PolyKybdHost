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
    """Pure geometry -- no font, no network, no rendering."""

    def test_every_placement_lands_inside_the_panel(self):
        for name in ic.PLACEMENTS:
            with self.subTest(name):
                x, y = ic.place(20, 16, name)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + 20, ic.PANEL_W)
                self.assertLessEqual(y + 16, ic.PANEL_H)

    def test_there_is_a_margin_at_all(self):
        """Derived expectations below move with ICON_MARGIN, so pin it here.

        Without this a margin of 0 -- an icon flush against the panel edge --
        satisfies every other test in this class.
        """
        self.assertGreaterEqual(ic.ICON_MARGIN, 1)

    def test_each_corner_is_the_corner_it_names(self):
        w, h = 20, 16
        left, top = ic.ICON_MARGIN, ic.ICON_MARGIN
        right, bottom = ic.PANEL_W - w - left, ic.PANEL_H - h - top
        self.assertEqual(ic.place(w, h, "lower_left"), (left, bottom))
        self.assertEqual(ic.place(w, h, "lower_right"), (right, bottom))
        self.assertEqual(ic.place(w, h, "upper_left"), (left, top))
        self.assertEqual(ic.place(w, h, "upper_right"), (right, top))

    def test_right_is_vertically_centred(self):
        """The roomy option: it grows leftward from the right edge, mid-height."""
        w, h = 20, 16
        x, y = ic.place(w, h, "right")
        self.assertEqual(x, ic.PANEL_W - w - ic.ICON_MARGIN)
        self.assertEqual(y, (ic.PANEL_H - h) // 2)

    def test_the_BIGGEST_allowed_icon_still_lands_on_the_panel(self):
        """The margin does not fit at MAX_ICON_HEIGHT, so it is what gives.

        `PANEL_H - 40 - 1` is -1; PIL draws at a negative y and clips the top
        row with no error. An icon that fills its box -- an SVG mark rasterised
        square -- hits that exactly.
        """
        h = ic.MAX_ICON_HEIGHT
        for name in ic.PLACEMENTS:
            with self.subTest(name):
                x, y = ic.place(h, h, name)
                self.assertGreaterEqual(min(x, y), 0, "off the panel")
                self.assertLessEqual(x + h, ic.PANEL_W)
                self.assertLessEqual(y + h, ic.PANEL_H)

    def test_an_unknown_placement_falls_back_to_the_default(self):
        self.assertEqual(ic.place(20, 16, "middle-of-nowhere"),
                         ic.place(20, 16, ic.DEFAULT_PLACEMENT))
        self.assertIn(ic.DEFAULT_PLACEMENT, ic.PLACEMENTS)


class LegendClearanceTest(unittest.TestCase):
    """Why the default corner is the CONTESTED one, and why the right trio is not.

    The base legend is left-aligned and its ink ends near x=24 (measured through
    the shipped renderer -- the table lives in `icon_catalog`). So an icon that
    grows leftward from the right edge can never reach it, while one in either
    left corner shares the same columns and the height decides the damage.

    This is geometry, so it is checkable offline; the pixel-against-pixel counts
    behind it are not, and are recorded in the module comment instead.
    """

    LEGEND_RIGHT = 24          # measured: plain S B W M Q @ ink x 0..24

    def _left_edge(self, placement, size=16):
        return ic.place(size, size, placement)[0]

    def test_the_right_hand_placements_clear_the_legend_COLUMNS(self):
        for name in ("lower_right", "upper_right", "right"):
            with self.subTest(name):
                self.assertGreater(self._left_edge(name), self.LEGEND_RIGHT)

    def test_the_left_hand_placements_do_NOT(self):
        """Including the default -- that is the trade, not an oversight."""
        for name in ("lower_left", "upper_left"):
            with self.subTest(name):
                self.assertLessEqual(self._left_edge(name), self.LEGEND_RIGHT)
        self.assertIn(ic.DEFAULT_PLACEMENT, ("lower_left", "upper_left"))

    def test_the_default_height_fits_the_panel_in_every_corner(self):
        """The real constraint, now that overlap is not one.

        The firmware clears a courtyard around the overlay, so an icon over the
        legend reads cleanly rather than muddling -- what a bigger icon costs is
        legend pixels, which is a judgement (32 keeps about half) rather than a
        bound. What is NOT a judgement is fitting: an icon taller than the panel
        would be clipped by the transport, silently.
        """
        h = ic.DEFAULT_ICON_HEIGHT
        for name in ic.PLACEMENTS:
            with self.subTest(name):
                x, y = ic.place(h, h, name)
                self.assertGreaterEqual(min(x, y), 0)
                self.assertLessEqual(x + h, ic.PANEL_W)
                self.assertLessEqual(y + h, ic.PANEL_H)


class RenderTest(unittest.TestCase):
    """Rendering, with an ordinary system font so it needs no catalog."""

    def _font(self):
        import glob
        for pattern in ("/usr/share/fonts/**/DejaVuSans.ttf",
                        "/usr/share/fonts/**/*.ttf"):
            hits = glob.glob(pattern, recursive=True)
            if hits:
                return hits[0]
        return None

    def _mask(self, **kw):
        font = self._font()
        if font is None:
            self.skipTest("no system TTF to render with")
        mask = ic.render_overlay("x", font, {"x": ord("X")}, **kw)
        self.assertIsNotNone(mask)
        self.assertEqual(mask.shape, (ic.PANEL_H, ic.PANEL_W))
        return mask

    def test_most_of_the_frame_is_blank_so_the_legend_survives(self):
        """The property the whole design rests on.

        The firmware clears a courtyard around the overlay's ink and draws it, so
        blank areas leave the legend underneath intact. A full-frame icon would
        erase the letter; a corner one punches in beside it.
        """
        mask = self._mask()                     # the SHIPPED height, not a small one
        self.assertTrue(mask.any(), "no ink drawn at all")
        self.assertLess(mask.sum(), ic.PANEL_W * ic.PANEL_H // 2)

    def test_the_default_places_it_bottom_LEFT(self):
        """Drawn small on purpose: at the shipped height the icon spans more
        than half the panel, so a quadrant test would say nothing."""
        mask = self._mask(height=12)
        rows = mask.any(axis=1).nonzero()[0]
        cols = mask.any(axis=0).nonzero()[0]
        self.assertLess(cols.max(), ic.PANEL_W // 2, "ink in the right half")
        self.assertGreater(rows.min(), ic.PANEL_H // 2, "ink in the top half")

    def test_render_HONOURS_the_placement_it_is_given(self):
        """Not just the default -- an ignored argument passes every other test."""
        quadrant = {
            "lower_left": (False, True), "lower_right": (True, True),
            "upper_left": (False, False), "upper_right": (True, False),
        }
        for name, (want_right, want_low) in quadrant.items():
            with self.subTest(name):
                mask = self._mask(height=12, placement=name)
                rows = mask.any(axis=1).nonzero()[0]
                cols = mask.any(axis=0).nonzero()[0]
                is_right = cols.min() > ic.PANEL_W // 2
                is_low = rows.min() > ic.PANEL_H // 2
                self.assertEqual(is_right, want_right, "wrong side")
                self.assertEqual(is_low, want_low, "wrong half")

    def test_nothing_touches_the_panel_edge(self):
        """Literal bounds -- deriving them from ICON_MARGIN hides a zero margin."""
        for name in ic.PLACEMENTS:
            with self.subTest(name):
                mask = self._mask(height=16, placement=name)
                self.assertFalse(mask[0].any() or mask[-1].any(), "top/bottom edge")
                self.assertFalse(mask[:, 0].any() or mask[:, -1].any(), "side edge")

    def test_a_glyph_the_FONT_lacks_is_refused_not_drawn_as_notdef(self):
        """A missing glyph inks a box, so the bbox guard alone cannot see it.

        This is the shape that reaches a keycap: `icon_names=` is a request, and
        Google returns whatever it recognised -- one renamed name comes back
        absent while the rest of the subset is fine. `.notdef` then covers most
        of the corner, means nothing, and wipes the legend under it.
        """
        font = self._font()
        if font is None:
            self.skipTest("no system TTF to render with")
        missing = 0x10FFFD          # plane-16 noncharacter: in no real font
        # ⚠️ Establish that INDEPENDENTLY -- gating the skip on `ic.font_covers`
        # lets a mutation that makes it always return True skip this test rather
        # than fail it, which is the one result that means "untested".
        from fontTools.ttLib import TTFont
        with TTFont(font, lazy=True) as probe:
            if missing in probe.getBestCmap():
                self.skipTest("this font somehow covers the probe codepoint")

        # The half that makes the guard necessary: it is NOT blank.
        from PIL import Image, ImageDraw, ImageFont
        d = ImageDraw.Draw(Image.new("L", (ic.PANEL_W, ic.PANEL_H), 0))
        box = d.textbbox((0, 0), chr(missing),
                         font=ImageFont.truetype(font, 16))
        self.assertGreater(box[2] - box[0], 0, "notdef would have measured blank")
        self.assertGreater(box[3] - box[1], 0)

        self.assertIsNone(ic.render_overlay("x", font, {"x": missing}))

    def test_an_unknown_name_yields_nothing(self):
        font = self._font()
        if font is None:
            self.skipTest("no system TTF to render with")
        self.assertIsNone(ic.render_overlay("nope", font, {"x": ord("X")}))


if __name__ == "__main__":
    unittest.main()
