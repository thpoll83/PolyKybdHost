"""The 1-bit reading of a colour icon: the conversion set, the gate, and the
one weakness in the scorer that is KNOWN and not yet fixed.

⚠️ This module had no suite at all, while carrying the heuristic that decides
whether an app gets a keycap mark. The gap was invisible in the ordinary way: a
missing test module contributes one ERROR and zero tests, so the run still looks
substantial.
"""
import unittest

import numpy as np

from polyhost.services import icon_binarise as ib


def _blob(size=38):
    m = np.zeros((size, size), dtype=bool)
    m[4:-4, 4:-4] = True
    return m


def _checkerboard(size=38):
    y, x = np.indices((size, size))
    return ((x + y) % 2).astype(bool)


def _line_art(size=38):
    m = np.zeros((size, size), dtype=bool)
    m[8, 6:-6] = True
    m[16, 6:-6] = True
    m[24, 6:-6] = True
    m[8:25, 6] = True
    return m


def _triangle(size=38):
    """A clean solid play triangle — GNOME Totem's best 1-bit reading."""
    m = np.zeros((size, size), dtype=bool)
    for y in range(4, size - 4):
        m[y, 6:6 + int(26 * (1 - abs(y - size // 2) / 15.0))] = True
    return m


def _scribble(size=38):
    """A high-detail threshold artefact — what Totem's `luma` reading actually is."""
    m = np.zeros((size, size), dtype=bool)
    for y in range(4, size - 4):
        x = 4 + int(y * 0.8)
        m[y, x:x + 2] = True
    m[6:14, 6:12] = True
    rng = np.random.default_rng(7)
    m[rng.integers(0, size, 70), rng.integers(0, size, 70)] = True
    return m


def _fragments(size=38):
    """Thin ink at the top and bottom with an empty middle — Mousepad's shape."""
    m = np.zeros((size, size), dtype=bool)
    m[2:5, 4:-4] = True
    m[-3, 4:-4] = True
    return m


class ConversionSetTest(unittest.TestCase):

    def test_the_SIX_conversions_are_three_thresholds_then_three_dithers(self):
        # ⚠️ Still a guard against re-adding Floyd-Steinberg over BLACK, which is
        # a different proposal from the three GAMMAS here. It was implemented,
        # scored and rendered against every real icon on the dev container and is
        # measurably WORSE: it takes the top score on six of twelve and on five of
        # those replaces clean `adaptive` line art with a halftone field, while
        # not moving the mousepad regression it was proposed for. See
        # docs/generic-icons-plan.md § E5 and docs/images/binarise.png.
        self.assertEqual([name for name, _ in ib.CONVERSIONS],
                         ["alpha", "luma", "adaptive",
                          "dither-lo", "dither", "dither-hi"])
        self.assertEqual(ib.CONVERSIONS,
                         ib.THRESHOLD_CONVERSIONS + ib.DITHER_CONVERSIONS)

    def test_the_three_dither_GAMMAS_span_both_directions(self):
        # ⚠️ The set is not spaced by taste. The right gamma is per icon and
        # points OPPOSITE ways — Totem/Text Editor/Weather want 1.4-2.0, the
        # Calculator wants 0.5 — so a single tuned default cannot serve both and
        # the low/mid/high spread is the whole reason there are three.
        gammas = [g for _, g, _ in ib.DITHER_TUNINGS]
        self.assertLess(min(gammas), 1.0)
        self.assertGreater(max(gammas), 1.0)
        self.assertIn(1.0, gammas)          # the tuning that shipped before

    def test_the_MID_tuning_is_the_one_that_shipped_alone(self):
        # Keeps the name `dither` meaning what it meant, so an old log line or a
        # stored choice still reads correctly.
        self.assertEqual(dict((n, (g, c)) for n, g, c in ib.DITHER_TUNINGS)["dither"],
                         (1.0, ib.DITHER_ADJUST["contrast"]))


class DitherPreferenceTest(unittest.TestCase):
    """A dither is PREFERRED over a threshold read, not merely scored against it."""

    def _icon(self, shape, size=160):
        from PIL import Image, ImageDraw
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        shape(ImageDraw.Draw(image), size)
        return image

    def test_a_dither_wins_even_when_it_scores_LOWER(self):
        # ⚠️ This is the whole feature and it cannot be expressed as a tie-break:
        # the dither is taken while it scores as little as DITHER_PREFERENCE of
        # the best threshold reading. A plain argmax puts a dither first on 36 of
        # 88 real icons; the preference puts it first on 74.
        self.assertLess(ib.DITHER_PREFERENCE, 1.0)
        self.assertGreater(ib.DITHER_PREFERENCE, 0.0)

    def test_the_preference_is_a_FLOOR_and_a_bad_dither_is_still_refused(self):
        # "More than just snowflakes" — a dither scoring far under the threshold
        # read loses. Measured: GNOME Bluetooth's dither is 0.33 of its adaptive
        # reading and is correctly refused.
        class Stub:
            pass
        real = ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS
        try:
            good = _line_art()
            bad = _fragments()
            ib.THRESHOLD_CONVERSIONS = (("adaptive", lambda i, b: good),)
            ib.DITHER_CONVERSIONS = (("dither", lambda i, b: bad),)
            self.assertLess(ib.score(bad), ib.DITHER_PREFERENCE * ib.score(good))
            _, name, _ = ib.choose(Stub(), 38)
            self.assertEqual(name, "adaptive")
        finally:
            ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS = real

    def test_a_dither_that_scores_at_all_but_UNDER_the_threshold_still_wins(self):
        # The other side of the same rule, and the one a plain argmax gets wrong.
        # ⚠️ The fixtures must be ordered `threshold > dither` or the test passes
        # under argmax too and pins nothing — a mutation sweep caught exactly that
        # (the first version handed the DITHER slot the higher-scoring mask).
        class Stub:
            pass
        real = ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS
        try:
            strong, weaker = _triangle(), _scribble()
            self.assertGreater(ib.score(strong), ib.score(weaker))     # argmax would take `strong`
            self.assertGreaterEqual(ib.score(weaker),
                                    ib.DITHER_PREFERENCE * ib.score(strong))
            ib.THRESHOLD_CONVERSIONS = (("adaptive", lambda i, b: strong),)
            ib.DITHER_CONVERSIONS = (("dither", lambda i, b: weaker),)
            _, name, _ = ib.choose(Stub(), 38)
            self.assertEqual(name, "dither")
        finally:
            ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS = real

    def test_a_dither_that_scores_ZERO_never_wins_a_NEGATIVE_comparison(self):
        # ⚠️ The "scored at all" clause, and it only bites when the THRESHOLD
        # reading is itself rejected: multiplying a negative score by the floor
        # RAISES it, so `0.0 >= 0.5 * -1.0` is true and a pure grain field would
        # be handed back as the pick. A mutation sweep found the first version of
        # this test could not tell the clause was gone, because both sides were
        # -1.0 and the comparison came out false either way.
        class Stub:
            pass
        real = ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS
        try:
            self.assertEqual(ib.score(_blob()), -1.0)          # threshold rejected
            self.assertEqual(ib.score(_checkerboard()), 0.0)   # pure grain
            self.assertGreaterEqual(ib.score(_checkerboard()),
                                    ib.DITHER_PREFERENCE * ib.score(_blob()))
            ib.THRESHOLD_CONVERSIONS = (("adaptive", lambda i, b: _blob()),)
            ib.DITHER_CONVERSIONS = (("dither", lambda i, b: _checkerboard()),)
            mask, name, value = ib.choose(Stub(), 38)
            # ⚠️ "nothing rendered", not "the threshold read won": `pick()` seeds
            # at -1.0 and requires a STRICT improvement, so a reading that scores
            # exactly -1.0 never becomes the best. Without the clause this comes
            # back as the checkerboard at 0.0.
            self.assertIsNone(mask)
            self.assertIsNone(name)
            self.assertEqual(value, -1.0)
        finally:
            ib.THRESHOLD_CONVERSIONS, ib.DITHER_CONVERSIONS = real

    def test_the_TUNING_reaches_the_dither_and_is_not_decoration(self):
        # ⚠️ Nothing else notices if `dither_ink` stops passing its gamma along —
        # the conversions still differ by their contrast, so the set still looks
        # like three candidates. A mutation dropping `gamma_val=` escaped until
        # this existed. Driven on a real GRADIENT, which is the only input whose
        # dither gamma can change.
        from PIL import Image
        ramp = Image.new("L", (160, 160))
        ramp.putdata([min(255, x) for _ in range(160) for x in range(160)])
        ramp = ramp.convert("RGBA")
        masks = {name: convert(ramp, 38) for name, convert in ib.DITHER_CONVERSIONS}
        lo, mid, hi = masks["dither-lo"], masks["dither"], masks["dither-hi"]
        self.assertGreater(int((lo != mid).sum()), 20)
        self.assertGreater(int((hi != mid).sum()), 20)
        # and gamma moves the ink monotonically: a lower gamma lightens the ramp
        self.assertLess(float(lo.mean()), float(hi.mean()))


class ScoreTest(unittest.TestCase):
    """Each term exists because a real icon defeated the ones before it."""

    def test_a_SOLID_BLOB_is_REJECTED_OUTRIGHT_by_its_bbox_fill(self):
        # A silhouette is large and says nothing — Yelp reduces to a ring, gedit
        # to a diagonal bar. ⚠️ It used to be refused by `detail` scoring it near
        # zero, which worked only because `detail` was maximised by texture — the
        # defect the 2026-09-18 rewrite removed. `MAX_FILL` refuses it on the
        # SHAPE instead: ink filling its own bounding box is a rectangle.
        self.assertEqual(ib.score(_blob()), -1.0)

    def test_the_blob_is_refused_for_its_FILL_and_not_its_LIT(self):
        # Without this the test above passes for the wrong reason the day someone
        # lowers MAX_LIT, and the fill guard could be deleted unnoticed.
        self.assertLess(_blob().mean(), ib.MAX_LIT)
        self.assertGreater(_blob().mean(), ib.MIN_LIT)

    def test_a_SOLID_SHAPE_that_does_NOT_fill_its_box_is_kept(self):
        # The other half of that decision, and the reason it is `fill` and not
        # `detail`: GNOME Totem's icon reads best as a solid play TRIANGLE, whose
        # ink and edge statistics are nearly identical to the blob's (lit 0.55 vs
        # 0.62, detail 0.15 vs 0.13). Anything that rejects one on those rejects
        # the other — and under the old scorer Totem drew a luma scribble instead.
        rows = np.flatnonzero(_triangle().any(1))
        cols = np.flatnonzero(_triangle().any(0))
        box = (rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1)
        self.assertLess(_triangle().sum() / float(box), ib.MAX_FILL)
        self.assertGreater(ib.score(_triangle()), ib.MIN_SCORE)

    def test_a_CLEAN_SOLID_MARK_outscores_a_HIGH_DETAIL_SCRIBBLE(self):
        # ⚠️ This is what the QUARTER POWER on `detail` buys, and nothing else in
        # the suite pins it — a mutation sweep caught the omission by putting the
        # exponent back to 1.0 with every other test still green.
        #
        # The pair reproduces GNOME Totem, whose four readings are a blob, a
        # threshold scribble across the plate's gradient, a solid play triangle
        # and a heavy dither. At full strength `detail` handed it to the scribble
        # (0.258 against the triangle's 0.110) and the keycap drew noise; at ^0.25
        # the triangle wins. ⚠️ The margin is real but not wide — 0.362 against
        # 0.303 — because the scribble is genuinely detailed. Do not read a small
        # margin here as slack to spend.
        self.assertGreater(ib.score(_triangle()), ib.score(_scribble()))

    def test_the_scribble_fixture_really_IS_the_high_detail_one(self):
        # Without this the test above could pass because the scribble is bad in
        # some other way, and the exponent could be removed unnoticed.
        def detail(mask):
            p = np.pad(mask, 1)
            surrounded = (p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
            return float((mask & ~surrounded).sum()) / float(mask.sum())

        self.assertGreater(detail(_scribble()), 3 * detail(_triangle()))

    def test_THIN_FRAGMENTS_with_an_empty_middle_are_rejected(self):
        # The `spread` term. Without it `edges/lit` approaches 1.0 for anything
        # thin and this shape scored 0.55.
        self.assertLess(ib.score(_fragments()), ib.MIN_SCORE)

    def test_LINE_ART_scores_above_the_gate(self):
        self.assertGreaterEqual(ib.score(_line_art()), ib.MIN_SCORE)

    def test_an_empty_or_absent_mask_is_unusable(self):
        self.assertEqual(ib.score(None), -1.0)
        self.assertEqual(ib.score(np.zeros((38, 38), dtype=bool)), -1.0)

    def test_an_ALL_LIT_mask_is_unusable(self):
        self.assertEqual(ib.score(np.ones((38, 38), dtype=bool)), -1.0)


class HalftoneTest(unittest.TestCase):
    """The defect E5 found and E7 fixed. The inversion IS the evidence."""

    def test_LINE_ART_now_outscores_a_HALFTONE(self):
        # ⚠️ This assertion is the reverse of the one it replaces, and that is
        # the point. Until 2026-09-18 it read `assertGreater(checkerboard,
        # line_art)` with a comment saying to invert it when someone fixed
        # `score()` — because `detail` is `edges/lit` and every lit pixel of a
        # dither field touches an unlit one, so the term meant to REWARD line art
        # was MAXIMISED by texture. It handed `dither` the win on mousepad (0.669
        # vs 0.386) while rendering visibly worse.
        #
        # `survives` is what separates them: block the mask into 2x2 and a
        # halftone's blocks are all the same mid grey, while line art's are empty
        # or full. Measured here 0.850 -> 0.000 for the checkerboard.
        self.assertGreater(ib.score(_line_art()), ib.score(_checkerboard()))
        self.assertEqual(ib.score(_checkerboard()), 0.0)

    def test_the_SEPARATION_is_the_2x2_BLOCK_VARIANCE_and_nothing_else(self):
        # Pin the mechanism, not just the outcome: the checkerboard's other three
        # terms are all healthy, so anything that drops `survives` reinstates the
        # defect rather than merely changing a number.
        board = _checkerboard()
        self.assertAlmostEqual(float(board.mean()), 0.5, places=2)   # balance fine
        self.assertEqual(min(board.any(1).mean(), board.any(0).mean()), 1.0)
        padded = np.pad(board, 1)
        surrounded = (padded[:-2, 1:-1] & padded[2:, 1:-1]
                      & padded[1:-1, :-2] & padded[1:-1, 2:])
        self.assertEqual(float((board & ~surrounded).sum()) / board.sum(), 1.0)

    def test_COHESION_does_not_separate_them_either(self):
        # The obvious repair, measured and refuted: "a halftone is isolated
        # pixels, line art is not". Over every real icon on the container it
        # reads 0.78-1.0 for BOTH, because a Floyd-Steinberg field at ~50%
        # density is not a checkerboard and its pixels do touch. A perfect
        # checkerboard is the one case where it works, which is exactly why
        # testing the idea on a synthetic checkerboard would have MISLED.
        def cohesion(mask):
            p = np.pad(mask, 1)
            neigh = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
            return float((mask & neigh).sum()) / float(mask.sum())

        self.assertEqual(cohesion(_checkerboard()), 0.0)     # the tempting case
        self.assertGreater(cohesion(_line_art()), 0.9)
        # ...and the real dither this is meant to catch is nothing like it:
        rng = np.random.default_rng(0)
        realistic = rng.random((38, 38)) < 0.5
        self.assertGreater(cohesion(realistic), 0.75)


class RefutedRepairsTest(unittest.TestCase):
    """Repairs that were implemented, measured against real icons, and DROPPED.

    ⚠️ Each is the obvious next idea, which is exactly why it is pinned: the cost
    of re-proposing one is a full corpus run. The cohesion case lives in
    `HalftoneTest` because it is specifically about the halftone.
    """

    def test_a_DETAIL_CEILING_would_destroy_the_corpus_BEST_render(self):
        # The intuitive fix for "detail rewards thinness": make it peak at a
        # moderate value and fall off toward 1.0. Refuted by the data — the
        # highest-scoring render of the 235-icon Yaru set is Power Statistics'
        # dithered waveform at detail 0.996, and 33 of the 235 winners sit above
        # 0.95. Detail near 1.0 is not a defect signal.
        waveform = np.zeros((38, 38), dtype=bool)
        for x in range(2, 36):
            waveform[19 + int(8 * np.sin(x / 3.0)), x] = True
        padded = np.pad(waveform, 1)
        surrounded = (padded[:-2, 1:-1] & padded[2:, 1:-1]
                      & padded[1:-1, :-2] & padded[1:-1, 2:])
        detail = float((waveform & ~surrounded).sum()) / waveform.sum()
        self.assertGreater(detail, 0.95)          # a legitimate high-detail mark

    def test_a_STROKE_NEIGHBOURHOOD_term_does_not_separate_them_either(self):
        # "A halftone is isolated pixels, line art is not", measured on the share
        # of lit pixels having a lit 4-neighbour. Same wall cohesion hit: over the
        # Yaru set real `dither` renders read 0.85-0.99, indistinguishable from
        # line art, because Floyd-Steinberg at real densities is clumpy. Only a
        # PERFECT checkerboard reads 0 — so a synthetic test of the idea would
        # have said it works.
        def stroke(mask):
            p = np.pad(mask, 1)
            neigh = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
            return float((mask & neigh).sum()) / float(mask.sum())

        rng = np.random.default_rng(0)
        realistic = rng.random((38, 38)) < 0.25
        self.assertGreater(stroke(realistic), 0.6)
        self.assertGreater(stroke(_line_art()), 0.9)

    def test_BBOX_FILL_is_a_REJECTION_and_not_a_scoring_term(self):
        # Multiplying the score by (1 - fill) was tried and moved agreement with
        # 22 hand-judged icons DOWN (13 of 22 against 16). It is a good yes/no —
        # a rectangle is never a mark — and a bad dial, because a compact solid
        # mark legitimately fills three quarters of its box (GNOME Extensions'
        # puzzle piece, 0.783).
        self.assertEqual(ib.score(_blob()), -1.0)
        puzzle = np.zeros((38, 38), dtype=bool)
        puzzle[8:30, 8:30] = True
        puzzle[2:10, 16:24] = True
        rows = np.flatnonzero(puzzle.any(1))
        cols = np.flatnonzero(puzzle.any(0))
        fill = puzzle.sum() / float((rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1))
        self.assertGreater(fill, 0.70)
        self.assertLess(fill, ib.MAX_FILL)
        self.assertGreater(ib.score(puzzle), ib.MIN_SCORE)


class GateTest(unittest.TestCase):

    def test_MIN_SCORE_is_what_makes_OS_FIRST_safe(self):
        # `app_icons.program_overlay` reads the OS icon before the catalog and
        # falls through on a reading below this floor. Without the gate a blob
        # would be drawn on ESC instead.
        self.assertGreater(ib.MIN_SCORE, 0.0)
        self.assertLess(ib.score(_blob()), ib.MIN_SCORE)



class MinScoreFloorTest(unittest.TestCase):
    """What MIN_SCORE must stay above, whatever it is set to.

    ⚠️ The value has moved TWICE -- 0.30 -> 0.25 when the corpus grew from seven
    icons to 130, and 0.25 -> 0.08 when `score()` was rewritten (2026-09-18) and
    the scale moved under it. Both times the number was taken from where the data
    separates. These are the bounds that make any such move safe, so they are
    asserted rather than left to the comment beside the constant.
    """

    def test_it_still_refuses_the_two_measured_failures(self):
        # On the current scale, over 116 deduplicated real icons plus these
        # fixtures: checkerboard 0.000, fragments 0.037, and the lowest real
        # render 0.097. ⚠️ The blob is no longer one of these -- it is refused
        # OUTRIGHT by MAX_FILL, which is why this list lost an entry.
        self.assertLess(ib.score(_fragments()), ib.MIN_SCORE)
        self.assertLess(ib.score(_checkerboard()), ib.MIN_SCORE)

    def test_the_margin_above_them_is_a_SEPARATION_not_a_hair(self):
        # The fragments fixture is the nearest thing below the floor. 2x clear is
        # what stops the next "just a bit lower" landing on top of it.
        self.assertGreaterEqual(ib.MIN_SCORE, 2.0 * ib.score(_fragments()))

    def test_it_stays_below_every_REAL_icon_measured(self):
        # The lowest of the 116 was 0.097 (GNOME System Monitor's trace). A floor
        # above that starts refusing readable marks, which is the failure the
        # 0.25 value had: it refused GNOME Dictionary, Extensions, Games and
        # Empathy while each had a clean `adaptive` render available.
        self.assertLess(ib.MIN_SCORE, 0.097)

    def test_line_art_still_passes(self):
        # ⚠️ It passes with far less room than it used to -- 0.104 against 0.319
        # before the rewrite -- because `survives` cannot tell a 1px stroke from
        # a halftone at 2x2. That cost is documented beside the term; what must
        # not happen is the fixture dropping BELOW the floor.
        self.assertGreaterEqual(ib.score(_line_art()), ib.MIN_SCORE)

if __name__ == "__main__":
    unittest.main()
