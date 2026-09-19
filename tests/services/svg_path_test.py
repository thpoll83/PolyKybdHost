"""The SVG path parser's CURVE commands, which nothing exercised.

⚠️ `parse_path` resolves every SVG path form -- relative, the H/V/S/T
shorthands and arcs -- down to four absolute commands, so that `rasterise`
only has to handle M/L/C/Q. Measured before this file existed: the C, S, Q and
T branches and the whole arc conversion were **0% covered**. They are pure
arithmetic with no observable output short of a rendered icon, which is the
combination that goes wrong in silence -- a reflected control point computed
from the wrong operand still draws *a* curve.

The expectations here are derived from the SVG spec's own rules (a smooth
curve reflects the previous control point through the current point; a
relative command adds to the current point), never from what the function
returns -- a test that asks the implementation what to expect agrees with it
by construction, which is the trap the firmware's ROT-geometry tests record.
"""

import unittest

from polyhost.services.svg_raster import parse_path


class CubicTest(unittest.TestCase):

    def test_an_ABSOLUTE_cubic_passes_its_points_through(self):
        self.assertEqual(parse_path("M0 0 C1 2 3 4 5 6"),
                         [("M", 0.0, 0.0), ("C", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)])

    def test_a_RELATIVE_cubic_is_resolved_against_the_current_point(self):
        # every coordinate offset from (10, 10), not from the origin
        self.assertEqual(parse_path("M10 10 c1 2 3 4 5 6"),
                         [("M", 10.0, 10.0),
                          ("C", 11.0, 12.0, 13.0, 14.0, 15.0, 16.0)])

    def test_a_SMOOTH_cubic_REFLECTS_the_previous_control_point(self):
        """⚠️ The rule is `2*current - previous_second_control`, and getting the
        operands backwards still yields a plausible curve. After C…(3,4) ends at
        (5,6), S's implied first control is (2*5-3, 2*6-4) = (7, 8)."""
        out = parse_path("M0 0 C1 2 3 4 5 6 S9 10 11 12")
        self.assertEqual(out[2], ("C", 7.0, 8.0, 9.0, 10.0, 11.0, 12.0))

    def test_a_SMOOTH_cubic_with_NO_previous_curve_uses_the_current_point(self):
        """The spec's other half: with no preceding C/S the reflection has
        nothing to reflect, so the control point IS the current point."""
        out = parse_path("M4 5 S9 10 11 12")
        self.assertEqual(out[1], ("C", 4.0, 5.0, 9.0, 10.0, 11.0, 12.0))

    def test_a_LINE_between_two_curves_CLEARS_the_reflection(self):
        """⚠️ A smooth command may only reflect a preceding CURVE. Carrying the
        stale control point across an intervening L would bend the next curve
        toward a point the path had already left."""
        out = parse_path("M0 0 C1 2 3 4 5 6 L20 20 S9 10 11 12")
        self.assertEqual(out[3], ("C", 20.0, 20.0, 9.0, 10.0, 11.0, 12.0))


class QuadraticTest(unittest.TestCase):

    def test_an_ABSOLUTE_quadratic_passes_through(self):
        self.assertEqual(parse_path("M0 0 Q1 2 3 4"),
                         [("M", 0.0, 0.0), ("Q", 1.0, 2.0, 3.0, 4.0)])

    def test_a_SMOOTH_quadratic_reflects_the_previous_control_point(self):
        # Q's control (1,2) ends at (3,4) -> T's implied control is (5, 6)
        out = parse_path("M0 0 Q1 2 3 4 T7 8")
        self.assertEqual(out[2], ("Q", 5.0, 6.0, 7.0, 8.0))

    def test_the_two_reflections_are_kept_APART(self):
        """⚠️ One shared 'last control point' would make a T after a C reflect a
        CUBIC's control, and an S after a Q reflect a quadratic's. Both are
        wrong, and both still draw something."""
        after_cubic = parse_path("M0 0 C1 2 3 4 5 6 T7 8")
        self.assertEqual(after_cubic[2], ("Q", 5.0, 6.0, 7.0, 8.0))  # no reflection
        after_quad = parse_path("M0 0 Q1 2 3 4 S9 10 11 12")
        self.assertEqual(after_quad[2], ("C", 3.0, 4.0, 9.0, 10.0, 11.0, 12.0))


class MalformedPathTest(unittest.TestCase):

    def test_a_malformed_segment_ENDS_the_path_rather_than_raising(self):
        """⚠️ A documented rule with a reason: this runs on the overlay path,
        where a partly drawn icon beats an exception. Pinned because the natural
        'fix' for a parser is to raise."""
        out = parse_path("M0 0 L5 5 C1 2 oops")
        self.assertEqual(out, [("M", 0.0, 0.0), ("L", 5.0, 5.0)])

    def test_an_EMPTY_path_is_empty_not_an_error(self):
        self.assertEqual(parse_path(""), [])

    def test_a_path_that_starts_with_a_CURVE_still_parses(self):
        """No moveto: `rasterise` drops it later, but the parser must not raise
        on its way there."""
        self.assertEqual(parse_path("C1 2 3 4 5 6"),
                         [("C", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)])


class ArcTest(unittest.TestCase):

    def test_an_arc_becomes_CUBICS_that_END_where_the_arc_ends(self):
        """The conversion's one checkable invariant without re-deriving the
        maths: whatever curves come out, the last one has to land on the arc's
        stated endpoint."""
        out = parse_path("M0 0 A5 5 0 0 1 10 0")
        self.assertTrue(out[1:], "the arc produced no segments")
        self.assertTrue(all(seg[0] == "C" for seg in out[1:]),
                        "an arc must be resolved to cubics")
        self.assertAlmostEqual(out[-1][-2], 10.0, places=6)
        self.assertAlmostEqual(out[-1][-1], 0.0, places=6)

    def test_a_ZERO_RADIUS_arc_degrades_to_a_LINE(self):
        """The spec says so, and it is the case a naive implementation divides
        by zero on."""
        self.assertEqual(parse_path("M0 0 A0 0 0 0 1 10 10"),
                         [("M", 0.0, 0.0), ("L", 10.0, 10.0)])


if __name__ == "__main__":
    unittest.main()
