"""The cairo-free SVG rasteriser behind the program icon.

⚠️ These tests exist because `cairosvg` cannot be installed on Windows (see the
module docstring), so this is the ONLY rasteriser most users will ever run --
and a wrong parse here does not raise, it draws a wrong picture. The parser
tests therefore assert geometry rather than "it returned something", and the
render tests assert WHERE the ink landed, since an upside-down or mirrored icon
is a perfectly valid array.
"""

import math
import unittest

from polyhost.services import svg_raster


def _square(d, box="0 0 10 10"):
    return f'<svg viewBox="{box}"><path d="{d}"/></svg>'


def _points(segments):
    """Every on-curve endpoint a parsed path visits."""
    out = []
    for seg in segments:
        if seg[0] == "M" or seg[0] == "L":
            out.append((seg[1], seg[2]))
        elif seg[0] == "C":
            out.append((seg[5], seg[6]))
        elif seg[0] == "Q":
            out.append((seg[3], seg[4]))
    return out


class TestParsePath(unittest.TestCase):

    def test_absolute_moveto_and_lineto(self):
        self.assertEqual(svg_raster.parse_path("M1 2 L3 4"),
                         [("M", 1.0, 2.0), ("L", 3.0, 4.0)])

    def test_relative_lineto_accumulates_from_the_current_point(self):
        self.assertEqual(svg_raster.parse_path("M1 1 l2 3"),
                         [("M", 1.0, 1.0), ("L", 3.0, 4.0)])

    def test_a_repeated_moveto_argument_is_an_implicit_lineto(self):
        # The spec says so, and Simple Icons relies on it -- read as a second
        # moveto it would start a new contour and the fill would come out wrong.
        self.assertEqual(svg_raster.parse_path("M0 0 1 1 2 2"),
                         [("M", 0.0, 0.0), ("L", 1.0, 1.0), ("L", 2.0, 2.0)])

    def test_a_repeated_RELATIVE_moveto_argument_is_a_relative_lineto(self):
        self.assertEqual(svg_raster.parse_path("m1 1 1 1"),
                         [("M", 1.0, 1.0), ("L", 2.0, 2.0)])

    def test_horizontal_and_vertical_keep_the_other_axis(self):
        self.assertEqual(svg_raster.parse_path("M1 2 H5 V7"),
                         [("M", 1.0, 2.0), ("L", 5.0, 2.0), ("L", 5.0, 7.0)])

    def test_relative_horizontal_and_vertical(self):
        self.assertEqual(svg_raster.parse_path("M1 2 h4 v5"),
                         [("M", 1.0, 2.0), ("L", 5.0, 2.0), ("L", 5.0, 7.0)])

    def test_closepath_returns_the_cursor_to_the_subpath_start(self):
        segs = svg_raster.parse_path("M1 1 L5 5 Z l1 1")
        self.assertEqual(segs[2], ("Z",))
        # after Z the cursor is back at (1,1), so the relative line lands at (2,2)
        self.assertEqual(segs[3], ("L", 2.0, 2.0))

    def test_a_cubic_keeps_both_control_points(self):
        self.assertEqual(svg_raster.parse_path("M0 0 C1 2 3 4 5 6"),
                         [("M", 0.0, 0.0), ("C", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)])

    def test_smooth_cubic_reflects_the_previous_control_point(self):
        segs = svg_raster.parse_path("M0 0 C1 1 2 2 3 3 S4 4 5 5")
        # reflection of (2,2) about the endpoint (3,3) is (4,4)
        self.assertEqual(segs[2], ("C", 4.0, 4.0, 4.0, 4.0, 5.0, 5.0))

    def test_smooth_cubic_with_no_previous_curve_uses_the_current_point(self):
        segs = svg_raster.parse_path("M2 2 S4 4 6 6")
        self.assertEqual(segs[1], ("C", 2.0, 2.0, 4.0, 4.0, 6.0, 6.0))

    def test_a_quadratic_is_kept_quadratic(self):
        self.assertEqual(svg_raster.parse_path("M0 0 Q1 2 3 4"),
                         [("M", 0.0, 0.0), ("Q", 1.0, 2.0, 3.0, 4.0)])

    def test_smooth_quadratic_reflects_the_previous_control_point(self):
        segs = svg_raster.parse_path("M0 0 Q1 1 2 2 T4 4")
        # reflection of (1,1) about (2,2) is (3,3)
        self.assertEqual(segs[2], ("Q", 3.0, 3.0, 4.0, 4.0))

    def test_a_cubic_does_NOT_seed_the_quadratic_reflection(self):
        # They are separate state; sharing one would bend the wrong way.
        segs = svg_raster.parse_path("M0 0 C1 1 2 2 3 3 T5 5")
        self.assertEqual(segs[2], ("Q", 3.0, 3.0, 5.0, 5.0))

    def test_an_arc_becomes_cubics_ending_at_the_arc_endpoint(self):
        segs = svg_raster.parse_path("M0 0 A5 5 0 0 1 10 0")
        self.assertEqual(segs[0], ("M", 0.0, 0.0))
        self.assertTrue(all(s[0] == "C" for s in segs[1:]))
        self.assertAlmostEqual(segs[-1][5], 10.0, places=6)
        self.assertAlmostEqual(segs[-1][6], 0.0, places=6)

    def test_ARC_FLAGS_MAY_RUN_INTO_THE_NEXT_COORDINATE(self):
        """`a1.5 1.5 0 01.5.5` is large=0 sweep=1 x=.5 y=.5, not a number `01`.

        This is the bug that broke Firefox and Docker: a flat tokeniser reads
        `01` as one number and everything after it is garbage -- and it does not
        raise, it draws a mangled icon.
        """
        segs = svg_raster.parse_path("M1 1 a1.5 1.5 0 01.5.5")
        self.assertTrue(any(s[0] == "C" for s in segs))
        self.assertAlmostEqual(segs[-1][5], 1.5, places=6)
        self.assertAlmostEqual(segs[-1][6], 1.5, places=6)

    def test_a_zero_radius_arc_degenerates_to_a_line(self):
        # Required by the spec, and it keeps the endpoint reachable.
        self.assertEqual(svg_raster.parse_path("M0 0 A0 0 0 0 1 4 4"),
                         [("M", 0.0, 0.0), ("L", 4.0, 4.0)])

    def test_an_arc_to_the_current_point_degenerates_to_a_line(self):
        segs = svg_raster.parse_path("M3 3 A5 5 0 0 1 3 3")
        self.assertEqual(segs[1], ("L", 3.0, 3.0))

    def test_radii_too_small_are_scaled_up_so_the_endpoint_is_reached(self):
        # F.6.6: without the correction the arc cannot span the chord and the
        # sub-path ends somewhere else entirely.
        segs = svg_raster.parse_path("M0 0 A1 1 0 0 1 10 0")
        self.assertAlmostEqual(segs[-1][5], 10.0, places=6)
        self.assertAlmostEqual(segs[-1][6], 0.0, places=6)

    def test_sweep_1_bulges_UPWARD_and_sweep_0_downward(self):
        """⚠️ Checked against cairosvg's render, not reasoned about.

        SVG's y runs down, so the "positive angle direction" of sweep=1 is
        clockwise ON SCREEN -- left to right over the TOP, i.e. negative y. It
        is easy to talk yourself into the opposite, and getting it backwards
        mirrors every rounded corner in the catalog while still drawing a
        plausible icon.
        """
        clockwise = _points(svg_raster.parse_path("M0 0 A5 5 0 0 1 10 0"))
        counter = _points(svg_raster.parse_path("M0 0 A5 5 0 0 0 10 0"))
        self.assertLess(min(y for _, y in clockwise), -4.0)
        self.assertGreater(max(y for _, y in counter), 4.0)

    def test_the_sweep_flag_decides_the_CENTRE_the_arc_curves_around(self):
        """⚠️ A chord equal to the diameter cannot see this, which is why the
        test above is not enough on its own.

        The centre offset is `sqrt(...)` of a numerator that is exactly ZERO for
        a semicircle, so its sign — the `large_arc == sweep` term — has no
        effect there. Flipping that term mirrors every rounded corner in the
        catalog and the semicircle case stays green. Measured: this pair does
        change, so a shorter chord is what pins it.
        """
        def reach(d):
            return [round(v, 3) for seg in svg_raster.parse_path(d) for v in seg[1:]]
        self.assertNotEqual(reach("M0 0 A5 5 0 0 1 6 0"),
                            reach("M0 0 A5 5 0 0 0 6 0"))
        # ...and each bulges to its own side, by a little and no further. The
        # UPPER bound is what matters: get the centre's sign wrong and the
        # small-arc case silently takes the long way round instead (measured, y
        # reaches 9), which a sign-only check passes.
        up = reach("M0 0 A5 5 0 0 1 6 0")[1::2]
        down = reach("M0 0 A5 5 0 0 0 6 0")[1::2]
        self.assertLess(min(up), -0.5)
        self.assertLess(max(-y for y in up), 3.0)
        self.assertGreater(max(down), 0.5)
        self.assertLess(max(down), 3.0)

    def test_a_rotated_arc_uses_the_rotation(self):
        flat = svg_raster.parse_path("M0 0 A6 2 0 0 1 8 0")
        turned = svg_raster.parse_path("M0 0 A6 2 90 0 1 8 0")
        self.assertNotEqual([tuple(round(v, 4) for v in s[1:]) for s in flat[1:]],
                            [tuple(round(v, 4) for v in s[1:]) for s in turned[1:]])

    def test_a_large_arc_is_split_into_several_cubics(self):
        # One cubic cannot approximate more than ~90 degrees usefully, so a
        # >180-degree sweep has to become at least three. (A chord equal to the
        # diameter is exactly a semicircle whichever flag is set, so this uses a
        # shorter chord to make the large-arc choice actually mean something.)
        segs = svg_raster.parse_path("M0 0 A5 5 0 1 1 6 0")
        self.assertGreaterEqual(len([s for s in segs if s[0] == "C"]), 3)

    def test_the_large_arc_flag_picks_the_LONG_way_round(self):
        # Same endpoints, same sweep: the long way reaches the far side of the
        # circle (~ -9 here), the short way stays within a radius of the chord.
        def reach(d):
            return min(v for seg in svg_raster.parse_path(d) for v in seg[2::2])
        self.assertGreater(reach("M0 0 A5 5 0 0 1 6 0"), -3.0)
        self.assertLess(reach("M0 0 A5 5 0 1 1 6 0"), -8.0)

    def test_a_repeated_command_letter_is_implicit(self):
        self.assertEqual(svg_raster.parse_path("M0 0 L1 1 2 2"),
                         [("M", 0.0, 0.0), ("L", 1.0, 1.0), ("L", 2.0, 2.0)])

    def test_commas_and_negatives_need_no_separator(self):
        self.assertEqual(svg_raster.parse_path("M0,0L-1-2"),
                         [("M", 0.0, 0.0), ("L", -1.0, -2.0)])

    def test_exponent_notation_parses(self):
        self.assertEqual(svg_raster.parse_path("M0 0 L1e1 2E-1"),
                         [("M", 0.0, 0.0), ("L", 10.0, 0.2)])

    def test_malformed_input_keeps_WHAT_PARSED_rather_than_raising(self):
        # A partly drawn icon beats an exception on the overlay path.
        segs = svg_raster.parse_path("M1 1 L2 2 L")
        self.assertEqual(segs, [("M", 1.0, 1.0), ("L", 2.0, 2.0)])

    def test_a_path_that_starts_with_a_number_parses_nothing(self):
        self.assertEqual(svg_raster.parse_path("1 2 3 4"), [])

    def test_an_empty_path_parses_nothing(self):
        self.assertEqual(svg_raster.parse_path(""), [])


class TestViewbox(unittest.TestCase):

    def test_a_plain_viewbox(self):
        self.assertEqual(svg_raster.viewbox('<svg viewBox="0 0 24 24">'),
                         (0.0, 0.0, 24.0, 24.0))

    def test_a_non_zero_origin_is_kept(self):
        # Material Symbols use "0 -960 960 960"; dropping the origin puts the
        # whole glyph off-canvas.
        self.assertEqual(svg_raster.viewbox('<svg viewBox="0 -960 960 960">'),
                         (0.0, -960.0, 960.0, 960.0))

    def test_commas_are_accepted_as_separators(self):
        self.assertEqual(svg_raster.viewbox('<svg viewBox="0,0,24,24">'),
                         (0.0, 0.0, 24.0, 24.0))

    def test_a_missing_viewbox_is_none(self):
        self.assertIsNone(svg_raster.viewbox("<svg><path d='M0 0'/></svg>"))

    def test_a_degenerate_viewbox_is_none(self):
        # Scaling by it would divide by zero inside the transform.
        self.assertIsNone(svg_raster.viewbox('<svg viewBox="0 0 0 24">'))


@unittest.skipUnless(svg_raster.available(), "freetype-py is not installed")
class TestRasterise(unittest.TestCase):
    """These assert WHERE the ink is, not merely that some arrived.

    An icon drawn upside down, mirrored or at the wrong scale is a perfectly
    valid array -- nothing downstream would notice, and the first report would
    be a screenshot nobody could explain.
    """

    def test_a_full_square_covers_everything(self):
        cov = svg_raster.rasterise(_square("M0 0 H10 V10 H0 Z"), 8, 8)
        self.assertEqual(cov.shape, (8, 8))
        self.assertGreater(cov.min(), 0.9)

    def test_an_empty_area_is_blank(self):
        cov = svg_raster.rasterise(_square("M0 0 L10 10"), 8, 8)
        self.assertLess(cov.max(), 0.5)

    def test_the_TOP_of_the_viewbox_is_the_TOP_of_the_array(self):
        # SVG's y runs down and FreeType's runs up. Without the flip in the
        # transform this renders perfectly, upside down.
        cov = svg_raster.rasterise(_square("M0 0 H10 V2 H0 Z"), 20, 20)
        self.assertGreater(cov[:4].mean(), 0.8)
        self.assertLess(cov[-4:].mean(), 0.05)

    def test_the_LEFT_of_the_viewbox_is_the_LEFT_of_the_array(self):
        cov = svg_raster.rasterise(_square("M0 0 H2 V10 H0 Z"), 20, 20)
        self.assertGreater(cov[:, :4].mean(), 0.8)
        self.assertLess(cov[:, -4:].mean(), 0.05)

    def test_a_non_zero_viewbox_origin_is_translated_away(self):
        # The same top band, expressed in a Material-Symbols-style viewBox.
        cov = svg_raster.rasterise(
            _square("M0 -960 H960 V-768 H0 Z", box="0 -960 960 960"), 20, 20)
        self.assertGreater(cov[:4].mean(), 0.8)
        self.assertLess(cov[-4:].mean(), 0.05)

    def test_a_non_square_target_stretches_each_axis_independently(self):
        cov = svg_raster.rasterise(_square("M0 0 H10 V10 H0 Z"), 30, 10)
        self.assertEqual(cov.shape, (10, 30))

    def test_each_AXIS_is_scaled_by_ITS_OWN_ratio(self):
        # ⚠️ The shape above comes from `pen.array(width=, height=)` and says
        # nothing about the transform, so swapping sx and sy passes it while
        # drawing the icon at the wrong aspect inside a correctly-sized array.
        # A band across the top of a WIDE target has to stay a band across the
        # top.
        cov = svg_raster.rasterise(_square("M0 0 H10 V2 H0 Z"), 40, 20)
        self.assertGreater(cov[:3].mean(), 0.8)
        self.assertLess(cov[-3:].mean(), 0.05)
        self.assertGreater(cov[:3, :3].mean(), 0.8)
        self.assertGreater(cov[:3, -3:].mean(), 0.8)

    def test_two_paths_both_draw(self):
        svg = ('<svg viewBox="0 0 10 10">'
               '<path d="M0 0 H10 V2 H0 Z"/>'
               '<path d="M0 8 H10 V10 H0 Z"/></svg>')
        cov = svg_raster.rasterise(svg, 20, 20)
        self.assertGreater(cov[:4].mean(), 0.8)
        self.assertGreater(cov[-4:].mean(), 0.8)
        self.assertLess(cov[8:12].mean(), 0.05)

    def test_an_unclosed_contour_still_fills(self):
        """Icons routinely omit the trailing Z.

        ⚠️ The `closePath()` the renderer makes for them is INERT — measured,
        FreeType closes an open contour itself and the array is identical either
        way — so this test cannot fail on its removal and a mutation sweep will
        report it escaped. It is kept because the pen protocol says a contour is
        closed explicitly, and because relying on the implicit close is a
        property of fontTools rather than of anything we control.
        """
        cov = svg_raster.rasterise(_square("M0 0 H10 V10 H0"), 8, 8)
        self.assertGreater(cov.min(), 0.9)

    def test_a_hole_is_cut_by_the_NONZERO_rule(self):
        # Outer clockwise, inner counter-clockwise -> the middle is empty.
        svg = ('<svg viewBox="0 0 10 10">'
               '<path d="M0 0 H10 V10 H0 Z M3 3 V7 H7 V3 Z"/></svg>')
        cov = svg_raster.rasterise(svg, 20, 20)
        self.assertLess(cov[9:11, 9:11].mean(), 0.05)
        self.assertGreater(cov[0:2, 0:2].mean(), 0.9)

    def test_an_svg_with_no_path_is_none(self):
        self.assertIsNone(svg_raster.rasterise('<svg viewBox="0 0 10 10"></svg>', 8, 8))

    def test_an_svg_with_no_viewbox_is_none(self):
        # None rather than a guess, so the caller can fall through to cairosvg.
        self.assertIsNone(svg_raster.rasterise('<svg><path d="M0 0 H1"/></svg>', 8, 8))

    def test_garbage_input_is_none_rather_than_an_exception(self):
        self.assertIsNone(svg_raster.rasterise("not an svg at all", 8, 8))

    def test_a_real_simple_icons_style_path_draws_ink(self):
        # Rounded corners are arcs, which is the half most likely to be wrong.
        svg = ('<svg viewBox="0 0 24 24"><path d="M4 2h16a2 2 0 012 2v16'
               'a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2z"/></svg>')
        cov = svg_raster.rasterise(svg, 24, 24)
        # The rect spans 20 of the 24 units in each axis, so ~0.69 before the
        # corners are cut away.
        self.assertGreater(cov.mean(), 0.6)
        # ...and the rounded corner is genuinely cut away.
        self.assertLess(cov[0, 0], 0.5)


class TestAvailable(unittest.TestCase):

    def test_available_agrees_with_the_import(self):
        try:
            from fontTools.pens.freetypePen import FreeTypePen  # noqa: F401
            expected = True
        except Exception:
            expected = False
        self.assertEqual(svg_raster.available(), expected)


if __name__ == "__main__":
    unittest.main()
