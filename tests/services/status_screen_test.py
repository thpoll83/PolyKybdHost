"""The status-OLED preview's composition.

Pixel-exact and Qt-free, so what is checked is WHERE things land: the panel is drawn
at `split72/status_oled.c`'s own coordinates, and a test that only asked "did anything
get drawn" would pass with every row in the wrong place.

⚠️ It is a SUBSET of that screen on purpose (the editor has no RGB effect, WPM,
brightness or language to draw), so there is a test for what must NOT appear too --
otherwise the natural next edit is to fill the empty rows with plausible numbers.
"""
import unittest

from polyhost.services import preview_data as pd
from polyhost.services import status_screen as ss


def faces():
    d = pd.PreviewData()
    if not d.load():
        return None
    ui = d.ui_fonts or {}
    return {"icons": next((f for f in d.fonts if f.first <= ss.ICON_LAYER <= f.last),
                          None),
            "mid": ui.get("NotoSans_Regular_Mid_19px7b"),
            "small": ui.get("NotoSans_Regular_Small_15px7b")}


def rows(pts):
    return {y for _x, y in pts}


class RenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.faces = faces()
        if cls.faces is None:
            raise unittest.SkipTest("no shipped preview data")
        missing = [k for k, v in cls.faces.items() if v is None]
        if missing:
            raise unittest.SkipTest("the export lacks %s" % ", ".join(missing))

    def test_it_draws_the_layer_and_the_side_marker_on_both_panels(self):
        for side in ("left", "right"):
            pts = ss.render(3, "Qwerty", side, self.faces)
            self.assertTrue(pts, "%s panel drew nothing" % side)

    def test_the_coordinates_are_the_FIRMWARES_OWN_NUMBERS(self):
        """Pinned as LITERALS, against `split72/status_oled.c`.

        ⚠️ Asserting the ink against `ss.TOP_BASE` instead reads as a placement check
        and is not one: move the constant and the expectation moves with it, so the
        row can slide anywhere and the suite stays green (measured -- that mutation
        escaped until this test was written this way). The constants are the contract
        with the firmware, so they are what gets pinned; the ink test below then only
        has to show the drawing follows them.
        """
        self.assertEqual((ss.TOP_BASE, ss.LOCK_ROW_B, ss.SIDE_MARKER_BASE),
                         (15, 29, 63))
        self.assertEqual(ss.SIDES["left"], (0, 108, 6))
        self.assertEqual(ss.SIDES["right"], (20, 0, 5))
        self.assertEqual((ss.PANEL_W, ss.PANEL_H), (128, 64))

    def test_the_top_row_is_drawn_ON_that_baseline(self):
        """The icon has no descender there, so its ink ends on the baseline."""
        pts = ss.render(0, "", "left", {"icons": self.faces["icons"]})
        self.assertTrue(pts)
        self.assertLessEqual(max(rows(pts)), ss.TOP_BASE)
        self.assertGreater(max(rows(pts)), ss.TOP_BASE - 16)

    def test_the_name_row_is_the_layout_panels_ALONE(self):
        """The RGB panel has no layout name on hardware, and inventing one there
        would put the same string on two screens that never both show it."""
        band = range(ss.LOCK_ROW_B - 12, ss.LOCK_ROW_B + 1)
        left = ss.render(0, "Colemak", "left", self.faces)
        right = ss.render(0, "Colemak", "right", self.faces)
        self.assertTrue(rows(left) & set(band), "the layout panel drew no name")
        # The right panel's only ink is the top row and its marker.
        self.assertFalse(rows(right) & set(range(ss.TOP_BASE + 1, ss.LOCK_ROW_B + 20)),
                         "the RGB panel drew a layout name")

    def test_the_side_marker_is_on_each_HALFS_INNER_edge(self):
        """Mirror images, so the marker swaps sides with the panel -- drawing both at
        one x would put one of them under the keys."""
        left = ss.render(0, "", "left", {"small": self.faces["small"]})
        right = ss.render(0, "", "right", {"small": self.faces["small"]})
        self.assertGreater(min(x for x, _y in left), ss.PANEL_W // 2)
        self.assertLess(max(x for x, _y in right), ss.PANEL_W // 2)
        for pts in (left, right):
            self.assertLessEqual(max(rows(pts)), ss.SIDE_MARKER_BASE)

    def test_a_two_digit_layer_is_drawn_in_HEX(self):
        """Twelve layers and one character of room, which is why the firmware prints
        hex -- a decimal '11' would be two glyphs and run into the role word.

        ⚠️ Checked by WIDTH, not by comparing `render(10)` with `render(0xA)`: those
        are the same integer, so both sides move together under a decimal mutation
        and the comparison is vacuous (measured -- it escaped exactly that way).
        """
        mid = {"mid": self.faces["mid"]}
        got = ss.render(11, "", "left", mid)
        self.assertTrue(got)

        def drawn(text):
            """The same face, same origin -- so this is what each scheme WOULD draw.

            Exact rather than a width heuristic: 'B' is a wide glyph and '1' a narrow
            one, so "hex is narrower than two digits" is not even true here (both
            measure 10 px), and that guess failed on correct code.
            """
            pts = set()
            x, base = ss.SIDES["left"][0] + ss.LAYER_DIGIT_X, ss.TOP_BASE
            ss._draw(pts, mid["mid"], x, base, text)
            return pts

        self.assertEqual(got, drawn("B"))
        self.assertNotEqual(got, drawn("11"))

    def test_nothing_is_drawn_outside_the_panel(self):
        """The hardware's SET_PIXEL_CLIPPED drops such pixels, so a long name has to
        go missing here the same way rather than wrapping or widening the image."""
        pts = ss.render(11, "WWWWWWWWWWWWWWWWWWWW", "left", self.faces)
        for x, y in pts:
            self.assertTrue(0 <= x < ss.PANEL_W and 0 <= y < ss.PANEL_H)

    def test_a_MISSING_face_drops_only_what_it_draws(self):
        """The faces come from the preview export, and an older one has fewer. Losing
        the name row is worth having the layer digit; failing outright is not."""
        whole = ss.render(2, "Qwerty", "left", self.faces)
        no_small = ss.render(2, "Qwerty", "left",
                             {"icons": self.faces["icons"], "mid": self.faces["mid"]})
        self.assertTrue(no_small)
        self.assertTrue(no_small < whole, "dropping _Small_ changed the other rows")
        self.assertFalse(ss.render(2, "Qwerty", "left", {}))

    def test_an_unknown_side_falls_back_rather_than_raising(self):
        self.assertTrue(ss.render(0, "Qwerty", "middle", self.faces))


if __name__ == "__main__":
    unittest.main()
