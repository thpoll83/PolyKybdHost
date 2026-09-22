"""Tests for the on-demand icon catalog.

Every test here runs OFFLINE. The service exists to fetch from the network, but
a suite that needs the network is one that fails for reasons unrelated to the
code, so the fetch is exercised through its no-network path and the rest --
cache keying, format validation, placement geometry -- is checked directly.
"""

import os
import shutil
import tempfile
import unittest
import unittest.mock as mock

from polyhost.services import icon_catalog as ic


class HeightTest(unittest.TestCase):
    def test_clamped_to_what_the_panel_can_hold(self):
        self.assertGreaterEqual(ic.icon_height(), ic.MIN_ICON_HEIGHT)
        self.assertLessEqual(ic.icon_height(), ic.MAX_ICON_HEIGHT)

    def test_the_default_leaves_a_margin(self):
        # 40 would sit flush against the panel edge; the default must not.
        self.assertLess(ic.DEFAULT_ICON_HEIGHT, ic.PANEL_H)

    def test_the_default_height_KEEPS_ITS_MARGIN_in_the_default_corner(self):
        """⚠️ Strictly less than PANEL_H is not enough, and the gap between the
        two is where the silent clip lives.

        At `MAX_ICON_HEIGHT` the nominal box IS the panel, so `place()` clamps
        the top margin to zero rather than reporting anything -- see its own
        docstring. A default that large draws to the panel edge on one side
        only, which reads as a rendering fault rather than a size choice. So the
        default has to leave room in BOTH axes, in the corner it actually uses.
        """
        h = ic.DEFAULT_ICON_HEIGHT
        x, y = ic.place(h, h, ic.DEFAULT_PLACEMENT)
        self.assertGreaterEqual(y, ic.ICON_MARGIN, "no top margin")
        self.assertGreaterEqual(ic.PANEL_H - (y + h), ic.ICON_MARGIN, "no bottom margin")
        self.assertGreaterEqual(ic.PANEL_W - (x + h), ic.ICON_MARGIN, "no right margin")


class CacheKeyTest(unittest.TestCase):
    def test_the_key_is_the_SET_of_names_not_their_order(self):
        self.assertEqual(ic.subset_path(["save", "undo"]),
                         ic.subset_path(["undo", "save", "undo"]))

    def test_a_different_set_is_a_different_file(self):
        """Growing the lexicon must fetch a new subset, not reuse the old one."""
        self.assertNotEqual(ic.subset_path(["save"]), ic.subset_path(["save", "undo"]))

    def test_a_different_WEIGHT_is_a_different_file(self):
        """Otherwise a weight change reaches only people who never used it.

        The cache is keyed on what the file CONTAINS. `MATERIAL_WEIGHT` decides
        that as much as the name set does, so leaving it out of the key means
        every machine that has already fetched a set keeps serving the old
        weight for good -- visible on a fresh install and nowhere else, which is
        the worst way for a visual change to half-land.
        """
        before = ic.subset_path(["save", "undo"])
        with mock.patch.object(ic, "MATERIAL_WEIGHT", ic.MATERIAL_WEIGHT + 100):
            after = ic.subset_path(["save", "undo"])
        self.assertNotEqual(before, after)

    def test_the_weight_is_READABLE_in_the_cache_filename(self):
        """A mismatch should be diagnosable by listing the directory.

        Folded into the hash it would still invalidate correctly and be one
        opaque digest against another, which is no use to somebody asking why
        an icon looks heavy.
        """
        self.assertIn(f"w{ic.MATERIAL_WEIGHT}", ic.subset_path(["save"]))


class MaterialWeightTest(unittest.TestCase):
    """The `wght` axis, and the two ways asking for one silently does nothing."""

    def test_the_fetched_family_CARRIES_the_weight(self):
        """Without the axis the endpoint serves 400, which is the heavy default.

        Measured over eight concepts both catalogs carry, at the shipped 36 px
        1-bit render: Material inks 1.30x Fluent at 400 and 0.85x at 300. The
        two faces sit side by side on one keycap row, so that reads as a
        different stroke weight rather than a different icon set.
        """
        family = f"{ic.FAMILY}:{ic.MATERIAL_AXES.format(wght=ic.MATERIAL_WEIGHT)}"
        self.assertIn(f",{ic.MATERIAL_WEIGHT},", family)
        self.assertTrue(family.startswith(ic.FAMILY + ":"))

    def test_the_axis_ORDER_is_the_one_the_API_accepts(self):
        """`opsz,wght,FILL,GRAD` -- registered axes first, then custom, each
        alphabetically. The CSS2 endpoint rejects any other ordering, and a
        rejection here is not an exception: `fetch_subset` catches everything
        and returns None, so the icons simply stop drawing.
        """
        axes = ic.MATERIAL_AXES.split("@")[0].split(",")
        self.assertEqual(axes, ["opsz", "wght", "FILL", "GRAD"])
        lower = [a for a in axes if a.islower()]
        upper = [a for a in axes if not a.islower()]
        self.assertEqual(lower, sorted(lower))
        self.assertEqual(upper, sorted(upper))
        self.assertEqual(axes, lower + upper)

    def test_the_weight_is_one_the_endpoint_actually_SERVES(self):
        """⚠️ The endpoint QUANTISES to the named instances, so this is not a
        free dial. Measured against the live CSS endpoint: 200 and 250 return a
        BYTE-IDENTICAL font, as do 300 and 350 -- only 200 / 300 / 400 are
        reachable. The overlay generator prescribes "250-300" for Material and
        really can hit 250, because it fetches per-icon SVGs; through THIS path
        250 silently becomes 200, which that same note calls too thin to survive
        the downscale. (`wght250` 404s at the asset repo too, so no part of this
        codebase can reach it -- `weight=300` is the only value any generator
        passes.)
        """
        self.assertIn(ic.MATERIAL_WEIGHT, (200, 300, 400))


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


class ConcurrentStoreTest(unittest.TestCase):
    """⚠️ A SHARED temp name, and `generate_app_overlays.py` now renders through
    this same module (E18) -- so the generator and the running host really can
    fetch the Fluent font at once.

    `_store_font` wrote `<path>.part` under a FIXED name: two processes then
    truncate each other's file, and whichever replaces second moves an
    incomplete TTF into the cache (or finds no `.part` at all and raises). Same
    defect `PolySettings._save_merged` already records one module over -- "unique
    per SAVE, not per process" (Greptile P2, #240).
    """

    def test_two_stores_do_not_share_a_temp_name(self):
        moved = []
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "fluent-regular.ttf")
            real = os.replace
            with mock.patch.object(ic.os, "replace",
                                   side_effect=lambda a, b: (moved.append(a), real(a, b))[1]):
                ic._store_font(path, b"\x00\x01\x00\x00one")
                ic._store_font(path, b"\x00\x01\x00\x00two")
        self.assertEqual(len(moved), 2)
        self.assertNotEqual(moved[0], moved[1], "both stores used one temp file")

    def test_a_store_leaves_no_temp_behind_on_SUCCESS_or_FAILURE(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.ttf")
            ic._store_font(path, b"\x00\x01\x00\x00ok")
            with mock.patch.object(ic.os, "replace", side_effect=OSError("nope")):
                self.assertIsNone(ic._store_font(path, b"\x00\x01\x00\x00bad"))
            leftovers = [n for n in os.listdir(d) if n != "f.ttf"]
            self.assertEqual(leftovers, [], leftovers)


class CachedFontIsValidatedTest(unittest.TestCase):
    """⚠️ The module refuses a non-TTF DOWNLOAD so the failure cannot surface
    "much later, at render time, where the cause is invisible" -- and then
    accepted any CACHED file over four bytes. Same reasoning, opposite
    conclusion, four lines apart. A cache corrupted once stayed broken for good.
    """

    def test_a_corrupt_cached_font_is_refused_and_refetched(self):
        with tempfile.TemporaryDirectory() as d:
            path = ic.subset_path(["save"], d, ic.FLUENT)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(b"<!DOCTYPE html>truncated rubbish")
            # Offline, so there is no way to re-fetch: it must answer None
            # rather than hand back the rubbish.
            self.assertIsNone(ic.fetch_subset(["save"], cache_dir=d,
                                              allow_network=False,
                                              face=ic.FLUENT))

    def test_a_VALID_cached_font_is_still_served_offline(self):
        with tempfile.TemporaryDirectory() as d:
            path = ic.subset_path(["save"], d, ic.FLUENT)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(b"\x00\x01\x00\x00 a real sfnt header")
            self.assertEqual(ic.fetch_subset(["save"], cache_dir=d,
                                             allow_network=False,
                                             face=ic.FLUENT), path)


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
    """Which corners share columns with the legend, and which cannot.

    The base legend is left-aligned and its ink ends near x=24 (measured through
    the shipped renderer -- the table lives in `icon_catalog`). So an icon that
    grows leftward from the right edge can never reach it, while one in either
    left corner shares the same columns and the height decides the damage.

    ⚠️ This measurement used to sit under a default that CONTRADICTED it: the
    default was `lower_left`, i.e. the corner these tests show overlaps the
    legend on every key, chosen to keep clear of the Shift/AltGr hints instead.
    It moved after a hardware report, so the geometry and the default now agree
    -- but the test that matters is the template one, not this one.

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
        """The trade a left corner makes, and the reason it is not the default."""
        for name in ("lower_left", "upper_left"):
            with self.subTest(name):
                self.assertLessEqual(self._left_edge(name), self.LEGEND_RIGHT)

    def test_the_DEFAULT_clears_the_legend_and_matches_the_templates(self):
        """⚠️ Two independent reasons, and the second is the binding one.

        The measurement above says a right-hand corner clears the legend
        columns. What DECIDES it is that every hand-made template sets
        `anchor: bottom-right`, so any other default makes a generic app look
        different from a templated one on the same keyboard -- the one-key-two-
        behaviours defect E3 removed for the program mark. Reported from
        hardware once the relay made the icons visible at all.
        """
        self.assertEqual(ic.DEFAULT_PLACEMENT, "lower_right")
        self.assertGreater(self._left_edge(ic.DEFAULT_PLACEMENT), self.LEGEND_RIGHT)

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

    def test_the_default_places_it_bottom_RIGHT(self):
        """Drawn small on purpose: at the shipped height the icon spans more
        than half the panel, so a quadrant test would say nothing.

        This is the END of the chain the setting only starts -- `place()` can
        return the right corner while `render()` draws somewhere else, and that
        is what the user sees.
        """
        mask = self._mask(height=12)
        rows = mask.any(axis=1).nonzero()[0]
        cols = mask.any(axis=0).nonzero()[0]
        self.assertGreater(cols.min(), ic.PANEL_W // 2, "ink in the left half")
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


class FaceTest(unittest.TestCase):
    """Two catalogs behind one API — and they are NOT interchangeable by name.

    Fluent's vocabulary is systematically its own (`undo` is `arrow_undo`,
    `close` is `dismiss`), so a concept names its Fluent icon explicitly. What
    this class pins is the plumbing that keeps the two apart: the qualified
    name, the per-face parse, and the caches that must not poison each other.
    """

    FLUENT_JSON = ('{"ic_fluent_copy_24_regular": 62252,'
                   ' "ic_fluent_save_24_regular": 61000,'
                   ' "ic_fluent_copy_16_regular": 1,'
                   ' "ic_fluent_copy_24_filled": 2,'
                   ' "ic_fluent_bad_24_regular": "not-a-number",'
                   ' "junk": 3}')

    def test_a_QUALIFIED_name_pins_its_catalog(self):
        self.assertEqual(ic.split_face("fluent:copy"), (ic.FLUENT, "copy"))
        self.assertEqual(ic.split_face("material:save"), (ic.MATERIAL, "save"))

    def test_a_BARE_name_takes_the_default(self):
        self.assertEqual(ic.split_face("save"), (ic.DEFAULT_FACE, "save"))

    def test_an_UNKNOWN_prefix_is_part_of_the_NAME_not_a_face(self):
        # ⚠️ Otherwise a colon in an icon name silently eats the first segment
        # and looks up something else entirely.
        self.assertEqual(ic.split_face("weird:thing"), (ic.DEFAULT_FACE, "weird:thing"))

    def test_the_fluent_table_keeps_only_24px_REGULAR_and_keys_on_the_STEM(self):
        # It ships every size and weight; 24/regular is the one drawn here, and
        # the stem is what a lexicon entry names.
        got = ic._fluent_codepoints(self.FLUENT_JSON)
        self.assertEqual(got, {"copy": 62252, "save": 61000})

    def test_a_MALFORMED_fluent_table_is_empty_rather_than_an_exception(self):
        # It is fetched over the network for a cosmetic feature; nothing here
        # may raise on the render path.
        for junk in ("", "not json", "[]", "null"):
            with self.subTest(junk=junk):
                self.assertEqual(ic._fluent_codepoints(junk), {})

    def test_the_two_faces_cache_their_tables_SEPARATELY(self):
        """⚠️ One shared path would have whichever face ran first answer for
        both — and the parse differs, so the second face would read the first
        one's bytes and come back empty rather than wrong-looking."""
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(ic.codepoints_path(d, ic.MATERIAL),
                                ic.codepoints_path(d, ic.FLUENT))

    def test_fluent_ignores_the_NAME_SET_because_it_has_no_subset_endpoint(self):
        """⚠️ The property that stops a growing lexicon re-downloading 2.8 MB.

        Material is content-keyed because Google serves exactly the icons asked
        for; Fluent ships one whole font, so keying it on the names would make
        every new concept a fresh download of the same file.
        """
        with tempfile.TemporaryDirectory() as d:
            one = ic.subset_path(["copy"], d, ic.FLUENT)
            many = ic.subset_path(["copy", "save", "dismiss"], d, ic.FLUENT)
            self.assertEqual(one, many)
            # Material must keep the opposite behaviour.
            self.assertNotEqual(ic.subset_path(["copy"], d, ic.MATERIAL),
                                ic.subset_path(["copy", "save"], d, ic.MATERIAL))

    def test_the_two_faces_cache_their_FONTS_separately(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(ic.subset_path(["copy"], d, ic.FLUENT),
                                ic.subset_path(["copy"], d, ic.MATERIAL))

    def test_a_cached_fluent_font_is_served_with_NO_network(self):
        with tempfile.TemporaryDirectory() as d:
            path = ic.subset_path(["copy"], d, ic.FLUENT)
            with open(path, "wb") as fh:
                fh.write(b"\x00\x01\x00\x00" + b"pretend-this-is-a-font")
            self.assertEqual(
                ic.fetch_subset(["copy"], d, allow_network=False, face=ic.FLUENT),
                path)

    def test_a_missing_fluent_font_with_no_network_is_None_not_a_raise(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ic.fetch_subset(["copy"], d, allow_network=False,
                                              face=ic.FLUENT))

    def test_a_NON_TTF_body_is_refused_rather_than_cached(self):
        """⚠️ GitHub serves an HTML error page with a 200 on some failures, and
        caching that leaves a file that fails at RENDER time, once per keycap,
        forever — the cache makes a transient failure permanent."""
        with tempfile.TemporaryDirectory() as d:
            path = ic.subset_path(["copy"], d, ic.FLUENT)
            self.assertIsNone(ic._store_font(path, b"<!DOCTYPE html><html>nope"))
            self.assertFalse(__import__("os").path.exists(path))

    def test_fluent_is_PINNED_to_an_immutable_ref_not_a_branch(self):
        """⚠️ The pin is load-bearing twice, so it gets a test rather than a
        comment alone.

        The hand-made template overlays are generated from this font and
        COMMITTED as PNGs. If the app fetched `main`, an upstream redraw would
        move the generic path off the templates and split every shared pool
        slot -- the byte dedupe is exact, so one pixel is a full miss. It also
        restores the generator's contract that re-running it reproduces the
        overlays byte for byte.

        A commit, not a tag: a tag can be moved.
        """
        self.assertRegex(ic.FLUENT_REF, r"^[0-9a-f]{40}$")
        for url in (ic.FLUENT_FONT_URL, ic.FLUENT_CODEPOINTS_URL):
            with self.subTest(url=url):
                self.assertIn(ic.FLUENT_REF, url)
                self.assertNotIn("/main/", url)

    def test_FACES_is_a_PREFERENCE_ORDER_with_fluent_first(self):
        # The order is the feature: Fluent is the house style every hand-made
        # template already uses, Material fills what it lacks.
        self.assertEqual(ic.FACES[0], ic.FLUENT)
        self.assertIn(ic.MATERIAL, ic.FACES)




class CacheAndFetchTest(unittest.TestCase):
    """`_cached_text`, `_store_font` and `fetch_subset` — the network seam.

    ⚠️ All three were **0% covered**. Nothing in the suite reaches the network
    (correctly), so the cache-hit / fetch-and-store / give-up structure around
    it had never executed, and the two faces' download paths are as different as
    the code gets: Fluent has no subset endpoint, so it fetches one 2.8 MB font
    for every name set, while Material asks Google for exactly the names given.
    Flattening them is silent -- Fluent stems sent to `icon_names=` return a font
    that renders nothing.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _patch_get(self, fn):
        real = ic._get
        ic._get = fn
        self.addCleanup(lambda: setattr(ic, "_get", real))

    def _forbid_network(self):
        """A spy that RECORDS a call instead of failing inside the callback.

        ⚠️ `self.fail()` here does not work, and the way it fails is instructive:
        both `_cached_text` and `fetch_subset` wrap `_get` in `except Exception`,
        which swallows the AssertionError and returns the give-up value -- so the
        test passes while the network was used. Found by mutation (deleting
        `fetch_subset`'s empty-name guard escaped), which is the only thing that
        could have found it: every such test was green.
        """
        used = []
        self._patch_get(lambda url, ua=None: used.append(url) or b"")
        return used

    # ---- _cached_text -------------------------------------------------
    def test_a_CACHED_body_is_read_without_touching_the_network(self):
        path = os.path.join(self.tmp, "codepoints.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("save e161")
        used = self._forbid_network()
        self.assertEqual(ic._cached_text(path, "http://x", allow_network=True),
                         "save e161")
        self.assertEqual(used, [])

    def test_a_FETCHED_body_is_STORED_so_the_next_read_is_free(self):
        path = os.path.join(self.tmp, "codepoints.txt")
        calls = []
        self._patch_get(lambda url, ua=None: calls.append(url) or b"save e161")
        first = ic._cached_text(path, "http://x", allow_network=True)
        second = ic._cached_text(path, "http://x", allow_network=True)
        self.assertEqual((first, second), ("save e161", "save e161"))
        self.assertEqual(len(calls), 1, "the second read must come from disk")

    def test_NO_NETWORK_and_no_cache_is_an_EMPTY_string_not_an_error(self):
        """The caller draws the label text instead; nothing here may raise."""
        used = self._forbid_network()
        self.assertEqual(
            ic._cached_text(os.path.join(self.tmp, "nope.txt"), "http://x",
                            allow_network=False), "")
        self.assertEqual(used, [])

    def test_a_FAILED_fetch_is_an_EMPTY_string(self):
        def boom(*a, **k):
            raise OSError("no route to host")
        self._patch_get(boom)
        self.assertEqual(
            ic._cached_text(os.path.join(self.tmp, "nope.txt"), "http://x",
                            allow_network=True), "")

    def test_an_UNCACHEABLE_answer_is_still_RETURNED(self):
        """⚠️ The rule in the code's own comment. A read-only cache dir must
        cost the fetch, not the answer -- otherwise a locked-down machine draws
        no icons at all while the data is sitting in memory."""
        path = os.path.join(self.tmp, "unwritable", "codepoints.txt")
        self._patch_get(lambda *a, **k: b"save e161")
        real_makedirs = ic.os.makedirs

        def refuse(*a, **k):
            raise OSError("read-only file system")
        ic.os.makedirs = refuse
        self.addCleanup(lambda: setattr(ic.os, "makedirs", real_makedirs))
        self.assertEqual(ic._cached_text(path, "http://x", allow_network=True),
                         "save e161")

    # ---- _store_font --------------------------------------------------
    def test_a_stored_font_is_moved_into_place_ATOMICALLY(self):
        """⚠️ Never a half file under the real name: `fetch_subset` treats any
        existing path over 4 bytes as a usable cached font, so a truncated
        download left under it would be served forever."""
        path = os.path.join(self.tmp, "sub", "symbols.ttf")
        self.assertEqual(ic._store_font(path, b"\x00\x01\x00\x00rest"), path)
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(path + ".part"),
                         "the temporary file must not survive")

    # ---- fetch_subset -------------------------------------------------
    def test_FLUENT_fetches_the_WHOLE_font_and_ignores_the_names(self):
        urls = []
        self._patch_get(lambda url, ua=None: urls.append(url) or b"\x00\x01\x00\x00f")
        got = ic.fetch_subset(["text_bold"], self.tmp, face=ic.FLUENT)
        self.assertIsNotNone(got)
        self.assertEqual(len(urls), 1)
        self.assertNotIn("icon_names", urls[0],
                         "Fluent has no subset endpoint to ask")
        self.assertIn(ic.FLUENT_REF, urls[0], "and it must use the pinned ref")

    def test_MATERIAL_asks_for_EXACTLY_the_names_given(self):
        urls = []

        def fake(url, ua=None):
            urls.append(url)
            if "css" in url or "icon_names" in url:
                return b"src: url(http://font.example/x.ttf) format('truetype');"
            return b"\x00\x01\x00\x00f"
        self._patch_get(fake)
        got = ic.fetch_subset(["content_copy", "save"], self.tmp, face=ic.MATERIAL)
        self.assertIsNotNone(got)
        self.assertIn("icon_names=content_copy,save", urls[0])

    def test_a_CACHED_subset_costs_no_fetch(self):
        path = ic.subset_path(["save"], self.tmp, ic.MATERIAL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(b"\x00\x01\x00\x00already here")
        used = self._forbid_network()
        self.assertEqual(ic.fetch_subset(["save"], self.tmp, face=ic.MATERIAL), path)
        self.assertEqual(used, [])

    def test_an_EMPTY_name_list_is_None_before_any_path_work(self):
        used = self._forbid_network()
        self.assertIsNone(ic.fetch_subset([], self.tmp))
        self.assertIsNone(ic.fetch_subset(["", None], self.tmp))
        self.assertEqual(used, [], "an empty name set must not reach the network")

    def test_a_SERVER_ERROR_is_None_rather_than_an_exception(self):
        def boom(*a, **k):
            raise OSError("500")
        self._patch_get(boom)
        self.assertIsNone(ic.fetch_subset(["save"], self.tmp, face=ic.MATERIAL))
        self.assertIsNone(ic.fetch_subset(["save"], self.tmp, face=ic.FLUENT))

    def test_an_HTML_error_page_is_REFUSED_rather_than_cached_as_a_font(self):
        """⚠️ The reason `_is_ttf` exists. Cached under the font's name, a proxy
        error page fails much later at render time, where the cause is gone."""
        self._patch_get(lambda *a, **k: b"<!DOCTYPE html><html>nope")
        self.assertIsNone(ic.fetch_subset(["save"], self.tmp, face=ic.FLUENT))
        self.assertFalse(os.path.exists(ic.subset_path(["save"], self.tmp, ic.FLUENT)))


class WhyTheFontIsUnreachableTest(unittest.TestCase):
    """⚠️ "neither cached nor reachable" reads the same for FOUR causes.

    Every path to `fetch_subset`'s None was a bare `except: return None` with
    no logging at any level, so a refused download, an unwritable cache, a
    proxy page served with a 200 and a stylesheet carrying no font url all
    produced one sentence — and they need four different remedies.

    Measured on macOS 2026-09-21: both faces failed on a machine where both
    endpoints answer fine from elsewhere, and the log could not narrow it at
    all. Same treatment `app_icons.fetch_icon` already got.
    """

    def _reason(self, face=ic.DEFAULT_FACE, **kw):
        reasons = {}
        with tempfile.TemporaryDirectory() as tmp:
            ic.fetch_subset(["content_copy"], tmp, face=face,
                            reasons=reasons, **kw)
        return reasons.get(face)

    def test_the_network_being_DISALLOWED_is_named(self):
        for face in (ic.MATERIAL, ic.FLUENT):
            self.assertIn("network was not allowed",
                          self._reason(face=face, allow_network=False), face)

    def test_a_REFUSED_download_is_named_for_BOTH_faces(self):
        """⚠️ Both, because the two take completely different code paths — one
        fetches a TTF directly, the other a stylesheet first."""
        with mock.patch.object(ic, "_get", side_effect=OSError("proxy refused")):
            self.assertIn("proxy refused", self._reason(face=ic.FLUENT))
            self.assertIn("proxy refused", self._reason(face=ic.MATERIAL))

    def test_a_200_THAT_IS_NOT_THE_STYLESHEET_is_named(self):
        """A captive portal or a proxy notice. Silent before this, and
        indistinguishable from an outage."""
        with mock.patch.object(ic, "_get", return_value=b"<html>portal</html>"):
            self.assertIn("carried no font url", self._reason(face=ic.MATERIAL))

    def test_a_reply_THAT_IS_NOT_A_TTF_is_named(self):
        with mock.patch.object(ic, "_get",
                               return_value=b"@font-face{src:url(https://x/f.ttf)}"):
            self.assertIn("not a usable TTF", self._reason(face=ic.MATERIAL))
        with mock.patch.object(ic, "_get", return_value=b"<html>portal</html>"):
            self.assertIn("not a usable TTF", self._reason(face=ic.FLUENT))

    def test_the_reason_is_OPTIONAL_and_costs_callers_nothing(self):
        """`reasons` defaults to None; every existing caller passes nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ic.fetch_subset(["content_copy"], tmp,
                                              allow_network=False))

    def test_a_CACHED_font_records_no_reason(self):
        """Success must not leave a reason behind for the caller to report."""
        reasons = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = ic.subset_path(["content_copy"], tmp, ic.MATERIAL)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(b"\x00\x01\x00\x00" + b"\x00" * 64)
            got = ic.fetch_subset(["content_copy"], tmp, reasons=reasons)
        self.assertEqual(got, path)
        self.assertEqual(reasons, {})


if __name__ == "__main__":
    unittest.main()
