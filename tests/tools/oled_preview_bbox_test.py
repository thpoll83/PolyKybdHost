"""`oled_preview.Renderer.bbox` against the FIRMWARE's own bbox expectations.

Every case here is ported from ``qmk_firmware/keyboards/polykybd/base/tests/
font_bbox_tests.cpp`` -- the same synthetic fonts, the same display lists, the same
expected boxes. That is the point: the renderer is a Python model of
``kdisp_gfx_text_bbox_in``, and a model checked only against itself proves nothing
(the standing caveat on ``oled_preview.py``). These fixtures are the C's, so a
divergence fails here rather than showing up as a keycap drawn slightly wrong.

Keep them in step with the C suite when either side gains a case.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "tools"))

from gfx_font import GfxFont                      # noqa: E402
import oled_preview as op                         # noqa: E402


def _font(first, last, yadv, metrics):
    """A TestFont: every slot a 0x0 gap, then `metrics` {cp: (w,h,adv,xo,yo)}."""
    glyphs = [dict(bitmapOffset=0, width=0, height=0, xAdvance=0, xOffset=0, yOffset=0)
              for _ in range(last - first + 1)]
    for cp, (w, h, adv, xo, yo) in metrics.items():
        glyphs[cp - first] = dict(bitmapOffset=0, width=w, height=h,
                                  xAdvance=adv, xOffset=xo, yOffset=yo)
    return GfxFont("t", b"\0", glyphs, first, last, yadv)


def make_base():
    m = {ord(' '): (0, 0, 9, 0, 0), ord('!'): (2, 12, 4, 0, -12)}
    for cp in range(ord('a'), ord('z') + 1):
        m[cp] = (6, 10, 8, 1, -10)
    m[ord('b')] = (5, 9, 7, 3, -9)          # ODD negative offsets: the floor test
    return _font(0x20, 0x7A, 40, m)


def make_tall():
    return _font(0xE000, 0xE00F, 54, {cp: (20, 30, 22, 2, -28)
                                      for cp in range(0xE000, 0xE010)})


def make_mid():
    m = {ord(' '): (0, 0, 5, 0, 0)}
    for cp in range(ord('!'), 0x7F):
        m[cp] = (4, 7, 5, 0, -7)
    return _font(0x20, 0x7E, 26, m)


def make_gappy():
    f = _font(0x100, 0x10F, 40, {cp: (3, 5, 4, 0, -5) for cp in range(0x100, 0x110)})
    f.glyphs[0x105 - 0x100] = dict(bitmapOffset=0, width=0, height=0,
                                   xAdvance=0, xOffset=0, yOffset=0)
    return f


def make_gap_filler():
    return _font(0x100, 0x10F, 44, {0x105: (7, 8, 9, 1, -8)})


A = ord('a')
B = ord('b')
BANG = ord('!')
SP = ord(' ')


class FontBboxTest(unittest.TestCase):
    def setUp(self):
        self.pool = [make_base(), make_tall()]
        self.mid = [make_mid()]
        self.R = op.Renderer(self.pool)
        self.Rm = op.Renderer(self.pool, mid_fonts=self.mid)

    def measure(self, cps):
        return self.R.bbox(list(cps))

    def measure_mid(self, cps):
        return self.Rm.bbox(list(cps))

    # -- plain glyph arithmetic -------------------------------------------
    def test_single_glyph_box_matches_its_metrics(self):
        self.assertEqual(self.measure([A]), (1, 6, -10, -1))

    def test_whitespace_only_reports_zeros(self):
        self.assertEqual(self.measure([SP, SP]), (0, 0, 0, 0))

    def test_leading_space_advances_without_ink(self):
        self.assertEqual(self.measure([SP, A]), (10, 15, -10, -1))

    def test_missing_glyph_is_measured_as_bang(self):
        self.assertEqual(self.measure([0x4000]), self.measure([BANG]))
        self.assertEqual(self.measure([BANG]), (0, 1, -12, -1))

    # -- the per-glyph yAdvance baseline shift ----------------------------
    def test_taller_font_shifts_by_yadvance_difference(self):
        self.assertEqual(self.measure([0xE000]), (2, 21, -14, 15))

    def test_single_font_array_zeroes_the_baseline_shift(self):
        self.assertEqual(op.Renderer([self.pool[1]]).bbox([0xE000]), (2, 21, -28, 1))

    def test_mixed_run_unions_both_fonts_boxes(self):
        self.assertEqual(self.measure([A, 0xE000]), (1, 29, -14, 15))

    # -- cursor ops --------------------------------------------------------
    def test_vertical_nudges_move_the_baseline(self):
        self.assertEqual(self.measure([0x05, A]), (1, 6, -8, 1))
        # Ported with the C (font_bbox_tests.cpp): up 2 really moves the RELATIVE box
        # up 2. The draw clamps its cursor at buffer 0, which in a relative walk
        # starting at 0 would swallow the lift and make \f a no-op -- the disagreement
        # that had 73 layout legends (`\f\f <letter>` on AZERTY) measuring up to 12 px
        # below their own ink, invisible to render_key()'s panel clamp.
        self.assertEqual(self.measure([0x0C, A]), (1, 6, -12, -3))
        self.assertEqual(self.measure([0x05, 0x05, 0x0C, A]), (1, 6, -8, 1))

    def test_horizontal_nudges_move_the_cursor(self):
        self.assertEqual(self.measure([0x06, A]), (3, 8, -10, -1))
        self.assertEqual(self.measure([0x08, A]), (-1, 4, -10, -1))   # same rule as \f
        self.assertEqual(self.measure([A, 0x08, A]), (1, 12, -10, -1))

    def test_carriage_return_restarts_x_only(self):
        self.assertEqual(self.measure([A, A, 0x0D, A]), (1, 14, -10, -1))

    def test_tab_adds_a_36px_stop_sized_step(self):
        self.assertEqual(self.measure([A, 0x09, A]), (1, 50, -10, -1))

    def test_line_feed_steps_a_fixed_15_and_keeps_x(self):
        self.assertEqual(self.measure([0x0B, A]), (1, 6, 5, 14))

    def test_newline_advances_by_fonts_zero_yadvance_and_restarts_x(self):
        self.assertEqual(self.measure([A, A, 0x0A, A]), (1, 14, -10, 39))

    def test_reset_returns_the_cursor_to_the_origin(self):
        self.assertEqual(self.measure([A, 0x05, 0x06, 0x18, A]), self.measure([A]))

    # -- display-list op argument consumption ------------------------------
    def test_half_and_thin_consume_their_glyph_argument(self):
        self.assertEqual(self.measure([0x0F, A]), (0, 0, 0, 0))
        self.assertEqual(self.measure([0x11, A]), (0, 0, 0, 0))
        self.assertEqual(self.measure([0x0F, 0xE000, A]), self.measure([A]))

    def test_an_argument_that_is_an_op_byte_is_still_just_an_argument(self):
        self.assertEqual(self.measure([0x0F, 0x0F, A]), self.measure([A]))

    def test_move_consumes_both_coordinates(self):
        self.assertEqual(self.measure([0x0E, ord('x'), ord('y'), A]), self.measure([A]))

    def test_move_coordinates_that_are_op_bytes_do_not_latch_a_font(self):
        self.assertEqual(self.measure_mid([0x0E, 0x16, 0x16, A]), self.measure([A]))

    def test_rot_frame_and_badge_consume_their_arguments(self):
        self.assertEqual(self.measure([0x15, ord('r'), 0xE000, A]), self.measure([A]))
        self.assertEqual(self.measure([0x12, ord('w'), ord('h'), A]), self.measure([A]))
        self.assertEqual(self.measure([0x13, ord('w'), ord('h'), ord('s'), A]),
                         self.measure([A]))

    def test_erase_is_a_mode_with_no_extent_and_no_arguments(self):
        self.assertEqual(self.measure([0x14, A]), self.measure([A]))

    def test_a_truncated_op_never_skips_past_the_terminator(self):
        self.assertEqual(self.measure([0x0E, A]), self.measure([A]))
        self.assertEqual(self.measure([0x13, ord('w'), ord('h')]), self.measure([A, A]))

    # -- HINT_SMALL --------------------------------------------------------
    def test_small_halves_extents_offsets_and_advance(self):
        self.assertEqual(self.measure([0x10, A]), (0, 2, -5, -1))
        self.assertEqual(self.measure([0x10, A, A]), (0, 6, -5, -1))

    def test_small_floors_a_negative_offset_instead_of_truncating(self):
        self.assertEqual(self.measure([0x10, B]), (1, 3, -5, -1))

    def test_small_latches_for_the_rest_of_the_run(self):
        self.assertEqual(self.measure([0x10, A, 0x18, A]), (0, 2, -5, -1))

    def test_small_skips_a_missing_glyph_instead_of_substituting_bang(self):
        """Ported from the C's SmallSkipsAMissingGlyphInsteadOfSubstitutingBang.

        The one place the measure and the draw used to disagree by construction:
        the half writer returns 0 for a glyph it cannot find -- no ink, no advance --
        while the measure substituted `'!'` unconditionally, so a SMALL run with an
        uncovered codepoint measured a half-`'!'` AND spent its advance, putting every
        following glyph at the wrong x. Fixed in `base/font_lookup.c` (qmk#252) and
        mirrored here; this file used to pin the OLD behaviour as deliberate C parity.
        """
        self.assertEqual(self.measure([0x10, 0x4000]), (0, 0, 0, 0))
        # ...and the phantom advance is gone too: it measures as if it weren't there.
        self.assertEqual(self.measure([0x10, 0x4000, A]), self.measure([0x10, A]))
        # FULL size still substitutes, because kdisp_write_gfx_char does.
        self.assertEqual(self.measure([0x4000]), self.measure([BANG]))
        # ...and the DRAW skips it in a SMALL run, which is the half the box now matches.
        drawn = []
        self.R.draw(lambda vx, vy: drawn.append((vx, vy)), [0x10, 0x4000], 0, 0)
        self.assertEqual(drawn, [])

    # -- HINT_MID ----------------------------------------------------------
    def test_mid_measures_from_the_mid_face_with_its_own_baseline(self):
        self.assertEqual(self.measure_mid([0x16, A]), (0, 3, -7, -1))

    def test_mid_falls_back_per_glyph_for_codepoints_outside_the_mid_face(self):
        self.assertEqual(self.measure_mid([0x16, 0xE000]), self.measure([0xE000]))

    def test_mid_mixed_run_advances_with_each_glyphs_own_face(self):
        self.assertEqual(self.measure_mid([0x16, A, 0xE000]), (0, 26, -14, 15))

    def test_mid_missing_everywhere_substitutes_bang_from_the_pool(self):
        self.assertEqual(self.measure_mid([0x16, 0x4000]), self.measure([BANG]))

    def test_a_null_mid_pool_makes_every_mid_glyph_fall_back(self):
        self.assertEqual(self.measure([0x16, A]), self.measure([A]))

    # -- the resolver ------------------------------------------------------
    def test_gap_record_falls_through_to_the_next_font(self):
        R = op.Renderer([make_gappy(), make_gap_filler()])
        self.assertEqual(R._font_in(R.fonts, 0x105).yAdvance, 44)
        self.assertEqual(R._font_in(R.fonts, 0x104).yAdvance, 40)

    # -- what the caller is allowed to draw --------------------------------
    def test_unsupported_ops_names_only_what_the_renderer_cannot_follow(self):
        self.assertEqual(self.Rm.unsupported_ops([0x10, 0x16, A]), set())
        # MOVE / BADGE / ERASE / ROT are DRAWN now (2026-09-01), so the only ops
        # left are the ones still needing a primitive this model lacks.
        self.assertEqual(self.Rm.unsupported_ops([0x0E, 1, 2]), set())
        self.assertEqual(self.Rm.unsupported_ops([0x13, 1, 2, 3]), set())
        self.assertEqual(self.Rm.unsupported_ops([0x12, 1, 2]), {0x12})   # FRAME
        self.assertEqual(self.Rm.unsupported_ops([0x0F, A]), {0x0F})      # HALF
        # ...and HINT_MID counts as unsupported with no mid face loaded, since the
        # run would silently render at full size instead.
        self.assertEqual(self.R.unsupported_ops([0x16, A]), {0x16})


if __name__ == "__main__":
    unittest.main()
