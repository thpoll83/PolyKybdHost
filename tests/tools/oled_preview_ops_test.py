"""The composite display-list ops — MOVE, BADGE, ERASE and ROT.

These were skipped by the preview until 2026-09-01, so the keycaps that use them
either drew nothing (the Context-menu key) or drew their text without their mark
(Scroll Lock's lock badge). They are ported from the firmware:
`kdisp_draw_badge_rect` / `rr_row_inset` / `kdisp_draw_glyph_rot_half_at`
(base/disp_array.c) and `kdisp_gfx_rot_half_extent` (base/font_lookup.c).

⚠️ A Python model of C checked only against itself proves nothing — the standing
caveat on this module. So the badge is checked against FIRMWARE DATA: the baked
`ICON_CAPSLOCK_OFF` glyph, which the firmware's own comment says the drawn box must
be indistinguishable from. That fixture is the C's, so a wrong radius or a Bresenham
arc (which insets 1,0 where this must inset 2,1,0) fails here rather than showing up
as a keycap drawn slightly wrong.
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
class RowInsetTest(unittest.TestCase):
    """`rr_row_inset` — the scanline formula, not a Bresenham arc."""

    def test_radius_two_insets_2_1_0(self):
        """⚠️ The whole reason the badge is not drawn with `draw_round_rect`: a
        Bresenham arc renders r=2 as insets 1,0, and the badge has to match the
        baked lock glyphs, whose corners inset 2,1,0."""
        self.assertEqual([op._rr_row_inset(j, 0, 16, 2) for j in range(3)], [2, 1, 0])

    def test_the_bottom_corner_mirrors_the_top(self):
        self.assertEqual([op._rr_row_inset(j, 0, 16, 2) for j in (16, 15, 14)],
                         [2, 1, 0])

    def test_a_zero_radius_never_insets(self):
        self.assertEqual({op._rr_row_inset(j, 0, 16, 0) for j in range(17)}, {0})


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class BadgeAgainstTheBakedGlyphTest(unittest.TestCase):
    """The badge's silhouette, against the firmware's own baked art."""

    def setUp(self):
        pk = _fw()
        if not pk:
            self.skipTest("no firmware checkout beside this repo")
        named = op.load_named_glyphs(os.path.join(pk, "lang", "named_glyphs.h"))
        cps = named.get("ICON_CAPSLOCK_OFF")
        if not cps:
            self.skipTest("ICON_CAPSLOCK_OFF not in this checkout")
        fonts = load_all_fonts(os.path.join(pk, "base", "fonts"))
        cp = cps[-1]
        self.g = self.f = None
        for f in fonts:
            if f.first <= cp <= f.last and f.glyphs[cp - f.first]['width']:
                self.f, self.g = f, f.glyphs[cp - f.first]
                break
        if self.g is None:
            self.skipTest("the baked glyph is not in this font pool")

    def _baked(self):
        g, f = self.g, self.f
        h, cb, bo = g['height'], (g['height'] + 7) >> 3, g['bitmapOffset']
        return {(x, y) for y in range(h) for x in range(g['width'])
                if f.bitmap[bo + x * cb + (y >> 3)] & (1 << (y & 7))}

    @staticmethod
    def _silhouette(pix, h):
        """First and last lit x per row — the outline, ignoring what is inside it."""
        out = {}
        for y in range(h):
            xs = [x for x, yy in pix if yy == y]
            if xs:
                out[y] = (min(xs), max(xs))
        return out

    def test_the_drawn_badge_matches_the_baked_lock_glyph_outline(self):
        """⚠️ Compared as a SILHOUETTE, because the baked glyph carries a letter 'A'
        inside its ring and the badge deliberately draws only the box. The outline
        is the claim the firmware comment actually makes, and it is what a wrong
        radius would break."""
        w, h = self.g['width'], self.g['height']
        drawn = set()
        op.draw_badge_rect(lambda x, y: drawn.add((x, y)), 0, 0, w, h,
                           op.KDISP_BADGE_RADIUS, op.KDISP_BADGE_BORDER)
        self.assertEqual(self._silhouette(drawn, h), self._silhouette(self._baked(), h))

    def test_the_released_ring_keeps_its_1px_inner_corner_nick(self):
        """⚠️ NOT a true concentric offset. That would give an inner radius of
        `r - border` — at r == border a perfectly square inner corner, one pixel
        short of the baked glyph, whose hole still insets 1 on its first row.
        Reported from hardware as "it misses a single pixel on the inside corner"."""
        drawn = set()
        op.draw_badge_rect(lambda x, y: drawn.add((x, y)), 0, 0, 17, 17,
                           op.KDISP_BADGE_RADIUS, op.KDISP_BADGE_BORDER)
        # row 2 is the first row of the hole; a square inner corner would light
        # exactly `border` pixels each side, the nick lights one more.
        left = sorted(x for x, y in drawn if y == 2)
        self.assertEqual(left[:3], [0, 1, 2], f"row 2 = {left}")

    def test_a_solid_badge_has_no_hole(self):
        solid, ring = set(), set()
        op.draw_badge_rect(lambda x, y: solid.add((x, y)), 0, 0, 17, 17, 2, 0)
        op.draw_badge_rect(lambda x, y: ring.add((x, y)), 0, 0, 17, 17, 2, 2)
        self.assertGreater(len(solid), len(ring))
        self.assertTrue(ring <= solid, "the ring must be the solid badge's border")


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class RotExtentTest(unittest.TestCase):
    def test_a_quarter_turn_swaps_the_axes(self):
        """6 steps = 90 deg, so a wide box becomes a tall one."""
        *_, w, h = op.rot_half_extent(20, 10, 6)
        self.assertEqual((w, h), (5, 10))

    def test_no_turn_is_just_the_halved_glyph(self):
        """⚠️ step 0 is unreachable through the op — a 0 codepoint terminates the
        string, which is why HINT_ROT's angle starts at 1 — but the geometry must
        still degenerate correctly, or every angle is measured against a wrong base."""
        *_, w, h = op.rot_half_extent(20, 10, 0)
        self.assertEqual((w, h), (10, 5))

    def test_a_diagonal_turn_grows_the_box(self):
        """A rotated box is wider than the original — the reason the extent comes
        from forward-rotating the four corners rather than from w and h."""
        *_, w, h = op.rot_half_extent(20, 20, 3)      # 45 deg
        self.assertGreater(w, 10)
        self.assertGreater(h, 10)

    def test_the_turn_is_COUNTER_clockwise_on_screen(self):
        """⚠️ Screen y runs DOWN, so a visually counter-clockwise turn is a NEGATIVE
        angle in the arithmetic — hence the (24 - step) index. Getting the sign
        backwards mirrors the arrowhead this op exists to place, which reads as a
        plausible glyph rather than as a bug."""
        ct_ccw, st_ccw, *_ = op.rot_half_extent(10, 10, 6)     # +90 CCW
        self.assertEqual((ct_ccw, st_ccw), (0, -256))


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class Int8ArgTest(unittest.TestCase):
    def test_an_argument_above_127_is_NEGATIVE(self):
        """The firmware reads each MOVE/BADGE argument as `(int8_t)text[n]`, so a
        coordinate written as a high byte is a negative position. Reading it
        unsigned puts the mark off the panel instead."""
        self.assertEqual(op._int8(0x48), 72)
        self.assertEqual(op._int8(0xFF), -1)
        self.assertEqual(op._int8(0x80), -128)
