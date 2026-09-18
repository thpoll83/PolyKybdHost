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


def _source(shape, size=152):
    """A real RGBA source image, so `fidelity` has something to compare against."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shape(ImageDraw.Draw(image), size)
    return image


class FidelityTest(unittest.TestCase):
    """The measure that looks at the SOURCE — the one `score()` never had."""

    def _plate(self, draw, size):
        draw.rounded_rectangle([4, 4, size - 4, size - 4], 24, fill=(60, 60, 60, 255))
        draw.polygon([(size * 0.38, size * 0.28), (size * 0.38, size * 0.72),
                      (size * 0.72, size * 0.5)], fill=(250, 250, 250, 255))

    def test_a_faithful_render_outscores_an_unfaithful_one(self):
        # The whole point: `score()` grades the mask alone, `fidelity` grades it
        # against the picture it came from.
        image = _source(self._plate)
        masks = {name: convert(image, 38) for name, convert in ib.CONVERSIONS}
        best = max(masks, key=lambda n: ib.fidelity(masks[n], image))
        self.assertGreater(ib.fidelity(masks[best], image), 0.8)

    def test_an_INVERTED_render_is_EQUALLY_faithful(self):
        # ⚠️ Absolute value, and it is load-bearing rather than defensive: a
        # dark-plate icon reads correctly either way round and both keep the
        # proportions. Signed correlation refuses seven of the 87 Yaru arts for
        # nothing but the sign — Terminal, Dictionary, Backups among them.
        image = _source(self._plate)
        mask = dict(ib.CONVERSIONS)["adaptive"](image, 38)
        self.assertAlmostEqual(ib.fidelity(mask, image),
                               ib.fidelity(~mask, image), places=6)

    def test_a_BLANK_render_scores_NOTHING_not_almost_everything(self):
        # ⚠️ The refutation of the obvious form. `1 - mean|render - source|` looks
        # right and is degenerate: an icon source is mostly light, so an EMPTY
        # render matches its mean and scores ~0.9 — measured, it picked a blank
        # mask for baobab, empathy, engrampa and eog. A correlation has no
        # variance to correlate and returns nothing at all.
        image = _source(self._plate)
        blank = np.zeros((38, 38), dtype=bool)
        self.assertEqual(ib.fidelity(blank, image), -1.0)
        self.assertEqual(ib.fidelity(np.ones((38, 38), dtype=bool), image), -1.0)

    def test_the_BLOCK_SIZE_is_the_scale_a_keycap_is_READ_at(self):
        # At 2px it grades the dither's texture rather than the picture (a dither
        # then wins only 56 of 87 Yaru arts against 65 at 4px); at 6 it stops
        # separating the gammas.
        self.assertEqual(ib.FIDELITY_BLOCK, 4)

    def test_the_SOURCE_is_cropped_to_its_INK_before_comparing(self):
        # ⚠️ A render is cropped to its own ink and scaled to the box, so the
        # reference has to be cropped the same way or the two are compared at
        # different scales and offsets. Measured on a small shape in a large
        # transparent canvas: cropped 0.87, uncropped 0.10 — the change is
        # invisible on an icon that fills its frame, which is most of them, and
        # that is why it needs a fixture that does not.
        image = _source(lambda d, s: d.ellipse(
            [s * 0.06, s * 0.06, s * 0.34, s * 0.34], fill=(20, 20, 20, 255)))
        grid = np.mgrid[0:38, 0:38]
        disc = np.sqrt((grid[0] - 18.5) ** 2 + (grid[1] - 18.5) ** 2) <= 17
        self.assertGreater(ib.fidelity(disc, image), 0.8)

    def test_it_is_ROBUST_to_the_mask_being_a_different_shape(self):
        # A render is fitted to the box preserving aspect, so it is often not
        # square; the reference is cropped and resized to whatever it is.
        image = _source(self._plate)
        tall = np.zeros((38, 22), dtype=bool)
        tall[6:32, 4:18] = True
        self.assertGreater(ib.fidelity(tall, image), -1.0)


class ChooseTest(unittest.TestCase):
    """`score()` gates, `fidelity()` ranks — and the gate comes first."""

    class _Stub:
        pass

    def _with(self, conversions, image=None):
        real = ib.CONVERSIONS
        try:
            ib.CONVERSIONS = conversions
            return ib.choose(image if image is not None else self._Stub(), 38)
        finally:
            ib.CONVERSIONS = real

    def test_the_MOST_FAITHFUL_usable_render_wins_not_the_HIGHEST_SCORING(self):
        # ⚠️ This replaced a hardcoded `DITHER_PREFERENCE` thumb, and pinning the
        # ORDER is what stops it being rebuilt: a dither was being forced to the
        # front with a tuned constant because the owner kept preferring it, when
        # the real defect was that `score()` ranks crispness and a human ranks
        # recognisability.
        #
        # The pair is the whole argument in miniature — the source is a solid
        # disc, so a crisp RING is the better-scoring render and the wrong
        # picture, while a halftoned disc scores lower and is the right one.
        image = _source(lambda d, s: d.ellipse(
            [s * 0.18, s * 0.18, s * 0.82, s * 0.82], fill=(45, 45, 45, 255)))
        radius = np.sqrt((np.mgrid[0:38, 0:38][0] - 18.5) ** 2
                         + (np.mgrid[0:38, 0:38][1] - 18.5) ** 2)
        ring = (radius > 12) & (radius < 14.5)
        halftone = (radius <= 14.5) & ((np.mgrid[0:38, 0:38][0]
                                        + np.mgrid[0:38, 0:38][1]) % 2 == 0)
        self.assertGreater(ib.score(ring), ib.score(halftone))          # argmax takes the ring
        self.assertGreater(ib.fidelity(halftone, image), ib.fidelity(ring, image))
        self.assertGreater(min(ib.score(ring), ib.score(halftone)), ib.MIN_SCORE)
        _, name, _ = self._with((("ring", lambda i, b: ring),
                                 ("disc", lambda i, b: halftone)), image)
        self.assertEqual(name, "disc")

    def test_a_render_BELOW_THE_GATE_never_wins_however_faithful(self):
        # ⚠️ The gate is not advisory, and the fixture has to make it BITE: the
        # sub-gate render must be the MORE faithful one or the test passes with
        # the gate deleted. A mutation sweep caught exactly that.
        #
        # The source is two thin bands with an empty middle — the shape the
        # `_fragments` fixture exists to refuse. It correlates with the source
        # far better than anything usable does, and it is still grain on a keycap.
        image = _source(lambda d, s: (
            d.rectangle([s * 0.10, s * 0.05, s * 0.90, s * 0.13], fill=(30, 30, 30, 255)),
            d.rectangle([s * 0.10, s * 0.92, s * 0.90, s * 0.95], fill=(30, 30, 30, 255))))
        self.assertLess(ib.score(_fragments()), ib.MIN_SCORE)
        self.assertGreaterEqual(ib.score(_line_art()), ib.MIN_SCORE)
        self.assertGreater(ib.fidelity(_fragments(), image),
                           ib.fidelity(_line_art(), image))
        _, name, _ = self._with((("usable", lambda i, b: _line_art()),
                                 ("faithful_junk", lambda i, b: _fragments())), image)
        self.assertEqual(name, "usable")

    def test_when_NOTHING_clears_the_gate_the_best_of_a_bad_lot_is_returned(self):
        # A caller drawing a mark it has no alternative for may take whatever
        # comes back — `app_icons` is the one that compares against MIN_SCORE.
        image = _source(lambda d, s: d.ellipse([4, 4, s - 4, s - 4],
                                               fill=(30, 30, 30, 255)))
        _, name, value = self._with((("a", lambda i, b: _fragments()),
                                     ("b", lambda i, b: _checkerboard())), image)
        self.assertIn(name, ("a", "b"))
        self.assertLess(value, ib.MIN_SCORE)

    def test_a_render_that_does_not_RENDER_is_dropped_before_ranking(self):
        # -1.0 means "nothing came back", and it must not reach `fidelity`.
        image = _source(lambda d, s: d.ellipse([4, 4, s - 4, s - 4],
                                               fill=(30, 30, 30, 255)))
        _, name, _ = self._with((("dead", lambda i, b: _blob()),
                                 ("live", lambda i, b: _line_art())), image)
        self.assertEqual(name, "live")

    def test_nothing_at_all_is_still_the_documented_triple(self):
        image = _source(lambda d, s: d.ellipse([4, 4, s - 4, s - 4],
                                               fill=(30, 30, 30, 255)))
        self.assertEqual(self._with((("dead", lambda i, b: _blob()),), image),
                         (None, None, -1.0))


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
