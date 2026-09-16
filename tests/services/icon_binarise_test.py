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


def _fragments(size=38):
    """Thin ink at the top and bottom with an empty middle — Mousepad's shape."""
    m = np.zeros((size, size), dtype=bool)
    m[2:5, 4:-4] = True
    m[-3, 4:-4] = True
    return m


class ConversionSetTest(unittest.TestCase):

    def test_there_are_exactly_FOUR_conversions(self):
        # ⚠️ A guard against re-adding the fifth (Floyd-Steinberg over BLACK).
        # It was implemented, scored and rendered against every real icon on the
        # dev container and it is measurably WORSE: it takes the top score on six
        # of twelve and on five of those replaces clean `adaptive` line art with
        # a halftone field, while not moving the mousepad regression it was
        # proposed for. See docs/generic-icons-plan.md § E5 and the evidence
        # sheet docs/images/binarise.png before changing this number.
        self.assertEqual([name for name, _ in ib.CONVERSIONS],
                         ["alpha", "luma", "adaptive", "dither"])

    def test_the_DITHER_is_last_so_a_tie_goes_to_a_threshold(self):
        # A thresholded reading has no texture to misread.
        self.assertEqual(ib.CONVERSIONS[-1][0], "dither")


class ScoreTest(unittest.TestCase):
    """Each term exists because a real icon defeated the ones before it."""

    def test_a_SOLID_BLOB_scores_near_zero(self):
        # The `edge` term. A silhouette is large and says nothing — Yelp reduces
        # to a ring, gedit to a diagonal bar.
        self.assertLess(ib.score(_blob()), ib.MIN_SCORE)

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


class KnownWeaknessTest(unittest.TestCase):
    """The defect E5 found and did NOT fix — pinned so it is read, not rediscovered."""

    def test_a_HALFTONE_outscores_LINE_ART_and_that_is_WRONG(self):
        # ⚠️ NOT a contract worth preserving — a statement of the open problem.
        # `detail` is `edges/lit`, and every lit pixel of a dither field touches
        # an unlit one, so the term meant to REWARD line art is MAXIMISED by
        # texture. This is why `dither` beats `adaptive` on mousepad (0.669 vs
        # 0.386) while rendering visibly worse, and why adding a second dither
        # ground made five more icons worse.
        #
        # When someone finally fixes `score()`, THIS TEST SHOULD FAIL. Invert it
        # then; do not delete it, because the inversion is the evidence the fix
        # worked.
        self.assertGreater(ib.score(_checkerboard()), ib.score(_line_art()))

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


class GateTest(unittest.TestCase):

    def test_MIN_SCORE_is_what_makes_OS_FIRST_safe(self):
        # `app_icons.program_overlay` reads the OS icon before the catalog and
        # falls through on a reading below this floor. Without the gate a blob
        # would be drawn on ESC instead.
        self.assertGreater(ib.MIN_SCORE, 0.0)
        self.assertLess(ib.score(_blob()), ib.MIN_SCORE)


if __name__ == "__main__":
    unittest.main()
