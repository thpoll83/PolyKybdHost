"""Offline tests for the program-icon service — no network, no device.

The geometry claim these exist to hold is arithmetic, and a regression in it
would be SILENT: the mark would simply start a column or two further left, the
firmware's courtyard clear would eat into the ESC glyph, and the keycap would
look slightly wrong on hardware with nothing failing anywhere.
"""
import os
import tempfile
import unittest
from unittest import mock

from polyhost.services import app_icons as ai

# The ESC glyph (U+238B) inks x 2..27 on the 72x40 panel, and
# `copy_overlay_to_buffer` clears a Chebyshev-3 courtyard around the overlay's
# ink before drawing it. So a mark whose ink starts at x >= 31 clears from 28,
# one column past the glyph. Both numbers are the firmware's, not this module's:
# ESC_INK_RIGHT is re-derived from the shipped preview data below so it cannot
# go stale in silence, and COURTYARD is KDISP_CY_DEFAULT.
ESC_INK_RIGHT = 27
COURTYARD = 3

SQUARE = ('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
          '<rect x="0" y="0" width="24" height="24"/></svg>')
WIDE = ('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="0" y="10" width="24" height="4"/></svg>')
TALL = ('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="10" y="0" width="4" height="24"/></svg>')
PADDED = ('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
          '<rect x="6" y="6" width="12" height="12"/></svg>')


def _svg(tmpdir, text, name="m.svg"):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _needs_render(case):
    try:
        import cairosvg          # noqa: F401
        import numpy             # noqa: F401
        from PIL import Image    # noqa: F401
    except Exception:
        case.skipTest("cairosvg/Pillow/numpy not installed")


class NormaliseTest(unittest.TestCase):

    def test_a_reverse_dns_id_keeps_its_LAST_component(self):
        # As themselves these reduce to `orggimpgimp` / `orginkscapeinkscape`,
        # which are nothing in the catalog — so without this rule every Linux
        # desktop/flatpak id resolves to no icon at all.
        self.assertEqual(ai.normalise("org.gimp.GIMP"), "gimp")
        self.assertEqual(ai.normalise("org.inkscape.Inkscape"), "inkscape")

    def test_a_trailing_version_goes(self):
        for name in ("gimp-2.0", "gimp-2.8", "gimp-3.0", "gimp 3"):
            self.assertEqual(ai.normalise(name), "gimp", name)
        self.assertEqual(ai.normalise("clion64"), "clion")

    def test_an_executable_suffix_goes(self):
        self.assertEqual(ai.normalise("soffice.bin"), "soffice")
        self.assertEqual(ai.normalise("Discord.exe"), "discord")

    def test_punctuation_goes_the_way_the_catalog_drops_it(self):
        # Simple Icons derives its slug by lowercasing the brand title and
        # dropping every non-alphanumeric, so the same reduction is what makes
        # an executable name land on a slug at all.
        self.assertEqual(ai.normalise("Sublime_Text"), "sublimetext")
        self.assertEqual(ai.normalise("Google Chrome"), "googlechrome")

    def test_nothing_in_nothing_out(self):
        self.assertEqual(ai.normalise(""), "")
        self.assertEqual(ai.normalise(None), "")


class SlugMapTest(unittest.TestCase):

    def test_the_SHIPPED_map_loads_and_splits_its_comma_keys(self):
        mapping = ai.load_slug_map()
        self.assertTrue(mapping, "the shipped app_icons.yaml did not load")
        for key in ("soffice", "soffice.bin", "startcenter"):
            self.assertEqual(mapping[key], "libreoffice", key)

    def test_every_shipped_ENTRY_names_a_real_source_and_a_usable_name(self):
        # A capital, a stray space or a source nobody serves is a URL that 404s
        # on every switch to that app — cheap to typo, and invisible until
        # someone watches the log.
        for app, value in ai.load_slug_map().items():
            if value is None:
                continue
            source, name = ai.split_name(value)
            self.assertIn(source, ai.SOURCES, f"{app} -> {value}")
            self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$", f"{app} -> {value}")

    def test_the_adobe_products_share_the_COMPANY_mark(self):
        # Not a compromise reached by shrugging: the `logos:` collection's
        # per-product Adobe marks were rendered at 1-bit and all six flatten to
        # the SAME solid rounded square (the "Ps"/"Ai" letters are separate
        # coloured paths, not knockouts). One shared "A" at least says Adobe.
        mapping = ai.load_slug_map()
        for app in ("photoshop", "illustrator", "afterfx", "premiere"):
            self.assertEqual(ai.candidates(app, mapping), ["mdi:adobe"], app)
        # Acrobat has a mark of its own and keeps it.
        self.assertEqual(ai.candidates("acrobat", mapping), ["mdi:adobe-acrobat"])

    def test_a_DIFFERENT_product_is_never_substituted(self):
        # The Adobe "A" is the true company for Photoshop. Chrome is not
        # Chromium and Windows is not File Explorer, so those stay unmapped and
        # fall through to the curation file.
        mapping = ai.load_slug_map()
        self.assertNotIn("chromium", mapping)
        self.assertNotIn("explorer", mapping)

    def test_the_map_may_name_EITHER_catalog(self):
        # One column, two catalogs: Simple Icons has no Microsoft at all, so the
        # Office family can only be expressed as an mdi entry.
        mapping = ai.load_slug_map()
        self.assertEqual(ai.candidates("winword", mapping), ["mdi:microsoft-word"])
        self.assertEqual(ai.candidates("chrome", mapping), ["si:googlechrome"])

    def test_a_missing_file_costs_the_icons_not_the_overlay(self):
        self.assertEqual(ai.load_slug_map("/nonexistent/app_icons.yaml"), {})

    def test_a_broken_file_costs_the_icons_not_the_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("[: not: yaml: at all\n")
            self.assertEqual(ai.load_slug_map(path), {})


class SlugForTest(unittest.TestCase):

    MAP = {"chrome": "googlechrome", "java": None}

    def test_the_explicit_map_WINS_over_the_guess(self):
        # `chrome` is a perfectly good guess and there is no `chrome` slug —
        # measured against the catalog, the brand is `googlechrome`.
        self.assertEqual(ai.slug_for("chrome", self.MAP), "googlechrome")

    def test_a_null_entry_SUPPRESSES_the_guess(self):
        # The one way to say "never draw an icon for this app": a guess that
        # happens to hit a different brand's slug is a wrong logo, which is the
        # failure the resolver cannot detect for itself.
        self.assertIsNone(ai.slug_for("java", self.MAP))

    def test_the_map_is_consulted_by_the_NORMALISED_name_too(self):
        # The tracker reports `Chrome.exe` on one platform and `chrome` on
        # another; one entry has to cover both.
        self.assertEqual(ai.slug_for("Chrome.exe", self.MAP), "googlechrome")

    def test_an_unmapped_app_falls_back_to_the_guess(self):
        self.assertEqual(ai.slug_for("Inkscape", self.MAP), "inkscape")

    def test_no_app_no_slug(self):
        self.assertIsNone(ai.slug_for("", self.MAP))
        self.assertIsNone(ai.slug_for(None, self.MAP))

    def test_a_map_key_that_does_NOT_survive_normalisation_still_matches(self):
        # `notepad++` reduces to `notepad`, which is a different string and not
        # a slug — so the raw-name lookup is what carries this entry, and a
        # normalised-only resolver would silently return the wrong slug rather
        # than nothing. Mutation-checked: dropping the raw lookup fails here and
        # nowhere else, because for most apps the two forms are identical.
        mapping = ai.load_slug_map()
        self.assertEqual(ai.slug_for("notepad++", mapping), "notepadplusplus")

    def test_a_null_read_from_a_REAL_yaml_file_suppresses_the_guess(self):
        # Driven through the loader rather than a literal dict: `null` has to
        # survive YAML -> map -> resolve, and a loader that turned it into the
        # key itself would look fine in a hand-built fixture.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("inkscape: null\n")
            mapping = ai.load_slug_map(path)
            self.assertIsNone(mapping["inkscape"])
            self.assertIsNone(ai.slug_for("Inkscape", mapping))

    def test_a_map_key_written_with_CAPITALS_still_matches(self):
        # app_icons.yaml is hand-edited, and the resolver lowercases the app
        # name it is given — so a key typed as the brand writes it would match
        # nothing at all, silently, on the one app someone bothered to add.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.yaml")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Notepad++: notepadplusplus\n")
            self.assertEqual(ai.slug_for("notepad++", ai.load_slug_map(path)),
                             "notepadplusplus")


class CandidatesTest(unittest.TestCase):
    """Which names an app is tried under, in which order."""

    def test_simple_icons_is_tried_FIRST(self):
        # It carries the real brand mark where it has one; mdi's is an
        # interpretation. Order is preference, not a set of equals.
        self.assertEqual(ai.candidates("Inkscape", {})[0], "si:inkscape")

    def test_the_BARE_mdi_name_is_never_tried(self):
        # ⚠️ mdi is 7400 icons and most are generic UI symbols, so a bare hit is
        # not evidence of a brand: `code` resolves to a generic `</>` glyph,
        # which on VS Code is a wrong icon by this module's own rule. Measured,
        # allowing it would gain four apps on a 151-app list and one of the four
        # would be wrong.
        self.assertNotIn("mdi:code", ai.candidates("code", {}))
        self.assertNotIn("mdi:terminal", ai.candidates("terminal", {}))

    def test_the_PREFIXED_mdi_names_are_tried(self):
        # These are what reach Office at all — an executable called `word` has
        # to become `microsoft-word`. Safe because every mdi `microsoft-*` stem
        # is a genuine product name (measured over all 50 of them).
        self.assertIn("mdi:microsoft-word", ai.candidates("word", {}))
        self.assertIn("mdi:adobe-acrobat", ai.candidates("acrobat", {}))

    def test_kebab_keeps_the_separators_normalise_drops(self):
        # The catalogs name the same brand differently, so one normalised form
        # cannot address both.
        self.assertEqual(ai.normalise("Visual Studio Code"), "visualstudiocode")
        self.assertEqual(ai.kebab("Visual Studio Code"), "visual-studio-code")
        self.assertEqual(ai.kebab("org.gimp.GIMP"), "gimp")
        self.assertEqual(ai.kebab("gimp-2.0"), "gimp")

    def test_an_unqualified_map_value_means_simple_icons(self):
        self.assertEqual(ai.qualify("gimp"), "si:gimp")
        self.assertEqual(ai.qualify("mdi:microsoft-word"), "mdi:microsoft-word")
        self.assertEqual(ai.split_name("gimp"), ("si", "gimp"))

    def test_a_suppressed_app_has_NO_candidates_at_all(self):
        self.assertEqual(ai.candidates("java", {"java": None}), [])
        self.assertEqual(ai.candidates("", {}), [])


class FormatValidationTest(unittest.TestCase):

    def test_only_an_svg_document_is_accepted(self):
        self.assertTrue(ai._is_svg(b'<svg viewBox="0 0 24 24"></svg>'))
        self.assertTrue(ai._is_svg(b'<?xml version="1.0"?><svg/>'))
        self.assertTrue(ai._is_svg(b'\n  <svg/>'))

    def test_an_error_page_is_refused_rather_than_cached(self):
        # A proxy or CDN error returning 200 would otherwise be stored under the
        # mark's name and fail at render time, where the cause is invisible.
        self.assertFalse(ai._is_svg(b"<!DOCTYPE html><html>404</html>"))
        self.assertFalse(ai._is_svg(b"Couldn't find the requested file"))
        self.assertFalse(ai._is_svg(b""))


class UserAgentTest(unittest.TestCase):

    def test_a_user_agent_is_SENT(self):
        # ⚠️ Load-bearing, not politeness: the Iconify API answers 403 to
        # `Python-urllib/<v>` and 200 to anything else, so without a UA the whole
        # second catalog is unreachable and every Office app reads as "no icon".
        seen = {}

        class FakeResponse:
            def read(self): return b'<svg viewBox="0 0 24 24"/>'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_open(request, timeout=None):
            seen["ua"] = request.get_header("User-agent")
            seen["url"] = request.full_url
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", fake_open), \
                tempfile.TemporaryDirectory() as tmp:
            ai.fetch_icon("mdi:microsoft-word", tmp, allow_network=True)
        self.assertEqual(seen["ua"], ai.USER_AGENT)
        self.assertNotIn("urllib", seen["ua"].lower())
        self.assertIn("microsoft-word", seen["url"])


class OfflineTest(unittest.TestCase):

    def test_an_uncached_mark_returns_none_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ai.fetch_icon("gimp", tmp, allow_network=False))

    def test_a_cached_mark_needs_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _svg(tmp, SQUARE, "si-gimp.svg")
            self.assertEqual(ai.fetch_icon("gimp", tmp, allow_network=False), path)

    def test_the_cache_filename_carries_the_SOURCE(self):
        # The catalogs share names — `mdi:slack` and `si:slack` are different
        # drawings of the same brand — so a bare filename would let whichever was
        # fetched first answer for both.
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "mdi-slack.svg")
            self.assertIsNone(ai.fetch_icon("si:slack", tmp, allow_network=False))
            self.assertTrue(ai.fetch_icon("mdi:slack", tmp, allow_network=False))

    def test_an_unknown_source_is_refused_rather_than_fetched(self):
        # ⚠️ A temp cache dir, not the default one. With the real dir this test
        # wrote `nosuchcatalog-gimp.svg` into the user cache during a mutation
        # sweep and then PASSED FOR THE WRONG REASON on every later run — the
        # file existed, so the cache short-circuit returned it. Same shape as the
        # default_log_dir trap: a green test pinning the environment's accident.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ai.fetch_icon("nosuchcatalog:gimp", tmp,
                                            allow_network=True))
            _svg(tmp, SQUARE, "nosuchcatalog-gimp.svg")
            self.assertIsNone(ai.fetch_icon("nosuchcatalog:gimp", tmp,
                                            allow_network=False))

    def test_no_slug_needs_no_fetch(self):
        self.assertIsNone(ai.fetch_icon("", allow_network=False))

    def test_the_brand_name_comes_off_the_svgs_own_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _svg(tmp, '<svg><title>GIMP</title><path d="M0 0"/></svg>')
            self.assertEqual(ai.title_of(path), "GIMP")
            self.assertIsNone(ai.title_of(os.path.join(tmp, "nope.svg")))


class GeometryTest(unittest.TestCase):
    """The arithmetic that keeps the mark off the ESC glyph."""

    def test_the_BOX_clears_the_esc_glyph_and_its_courtyard(self):
        # This is the whole reason the box is 40 rather than a rounder 44 or 48:
        # flush right, a box of B starts at 72 - B, and the courtyard clears
        # three columns further left again. 44 reads as a safe compromise and is
        # not — it clears from 25 against ink reaching 27.
        left = ai.PANEL_W - ai.PROGRAM_ICON_BOX
        self.assertGreater(left - COURTYARD, ESC_INK_RIGHT,
                           "the program icon would eat into the ESC legend")

    def test_the_ESC_INK_yardstick_still_matches_the_shipped_legend(self):
        # ESC_INK_RIGHT above is a firmware fact, and a firmware fact written
        # into a test goes stale in silence. Re-derive it from the same data the
        # layout editor previews from, so a changed glyph fails here instead.
        try:
            import numpy as np
            from polyhost.services import preview_data as pdata
            import sys
            sys.path.insert(0, os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)))), "tools"))
            import oled_preview
        except Exception:
            self.skipTest("preview data / renderer unavailable")
        data = pdata.PreviewData()
        if not data.load():
            self.skipTest("no shipped preview data")
        mask = np.zeros((ai.PANEL_H, ai.PANEL_W), dtype=bool)

        def setpix(x, y):
            if 0 <= x < ai.PANEL_W and 0 <= y < ai.PANEL_H:
                mask[y, x] = True

        oled_preview.Renderer(data.fonts).draw(setpix, [0x238B], 28, 23)
        self.assertTrue(mask.any(), "the ESC glyph drew nothing")
        self.assertEqual(int(mask.any(0).nonzero()[0].max()), ESC_INK_RIGHT)


class RenderTest(unittest.TestCase):

    def setUp(self):
        _needs_render(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def render(self, text):
        return ai.render_overlay(_svg(self.tmp.name, text))

    def test_the_mark_is_FLUSH_RIGHT(self):
        for name, text in (("square", SQUARE), ("wide", WIDE), ("tall", TALL)):
            mask = self.render(text)
            cols = mask.any(0).nonzero()[0]
            self.assertEqual(int(cols.max()), ai.PANEL_W - 1, name)

    def test_the_mark_CLEARS_the_esc_glyph_and_its_courtyard(self):
        for name, text in (("square", SQUARE), ("wide", WIDE), ("tall", TALL)):
            mask = self.render(text)
            first = int(mask.any(0).nonzero()[0].min())
            self.assertGreater(first - COURTYARD, ESC_INK_RIGHT, name)

    def test_the_mark_is_vertically_CENTRED(self):
        mask = self.render(WIDE)
        rows = mask.any(1).nonzero()[0]
        top, bottom = int(rows.min()), int(rows.max())
        self.assertLessEqual(abs(top - (ai.PANEL_H - 1 - bottom)), 1)

    def test_a_square_mark_FILLS_the_box(self):
        mask = self.render(SQUARE)
        rows, cols = mask.any(1).nonzero()[0], mask.any(0).nonzero()[0]
        self.assertEqual(len(rows), ai.PROGRAM_ICON_BOX)
        self.assertEqual(len(cols), ai.PROGRAM_ICON_BOX)

    def test_a_PADDED_mark_is_scaled_up_to_fill_the_box_too(self):
        # Marks are not all drawn edge to edge in their 24x24 viewBox. Rendering
        # straight into the box would leave those visibly small on a panel that
        # has 40 pixels to give; measuring the INK and scaling that is what makes
        # every mark the same visual size.
        mask = self.render(PADDED)
        self.assertEqual(len(mask.any(0).nonzero()[0]), ai.PROGRAM_ICON_BOX)

    def test_a_wide_mark_keeps_its_ASPECT(self):
        # A wordmark (KiCad, Zoom) reads BECAUSE the panel is landscape; stretching
        # it to a square would be the one change that throws that away.
        mask = self.render(WIDE)
        rows, cols = mask.any(1).nonzero()[0], mask.any(0).nonzero()[0]
        self.assertEqual(len(cols), ai.PROGRAM_ICON_BOX)
        self.assertLess(len(rows), ai.PROGRAM_ICON_BOX // 2)

    def test_nothing_lands_outside_the_panel(self):
        for text in (SQUARE, WIDE, TALL, PADDED):
            mask = self.render(text)
            self.assertEqual(mask.shape, (ai.PANEL_H, ai.PANEL_W))

    def test_the_LEFT_third_stays_blank_for_the_legend(self):
        # The whole point of a corner overlay: the firmware clears only around
        # the ink, so blank frame leaves the legend underneath intact.
        mask = self.render(SQUARE)
        self.assertFalse(mask[:, :ai.PANEL_W - ai.PROGRAM_ICON_BOX].any())

    def test_a_file_that_is_not_a_drawing_is_refused_not_drawn(self):
        self.assertIsNone(ai.render_overlay(
            _svg(self.tmp.name, "<html>nope</html>", "bad.svg")))
        self.assertIsNone(ai.render_overlay("/nonexistent/mark.svg"))

    def test_an_EMPTY_drawing_yields_nothing_rather_than_a_blank_overlay(self):
        # An overlay of no ink still costs a pool slot and a send, and the
        # keycap would look identical to having none.
        self.assertIsNone(ai.render_overlay(
            _svg(self.tmp.name,
                 '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"/>',
                 "empty.svg")))


class ProgramOverlayTest(unittest.TestCase):

    def test_the_name_comes_back_even_when_no_catalog_has_the_mark(self):
        # An unresolvable NAME and a resolvable one no catalog carries want
        # different curation entries, so the caller has to tell them apart.
        with tempfile.TemporaryDirectory() as tmp:
            mask, name = ai.program_overlay("Inkscape", {}, tmp, allow_network=False)
            self.assertIsNone(mask)
            self.assertEqual(name, "si:inkscape")

    def test_a_suppressed_app_reports_no_slug_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                ai.program_overlay("java", {"java": None}, tmp, allow_network=False),
                (None, None))

    def test_a_cached_mark_renders_with_no_network(self):
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            mask, name = ai.program_overlay("Inkscape", {}, tmp, allow_network=False)
            self.assertEqual(name, "si:inkscape")
            self.assertIsNotNone(mask)
            self.assertTrue(mask.any())

    def test_the_SECOND_catalog_is_tried_when_the_first_has_nothing(self):
        # The whole reason there are two: Simple Icons carries no Microsoft at
        # all, so Word can only come from mdi.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "mdi-microsoft-word.svg")
            mask, name = ai.program_overlay("word", {}, tmp, allow_network=False)
            self.assertEqual(name, "mdi:microsoft-word")
            self.assertIsNotNone(mask)

    def test_the_FIRST_catalog_wins_when_both_have_the_mark(self):
        # Simple Icons is the real brand mark; mdi's is an interpretation of it.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-slack.svg")
            _svg(tmp, WIDE, "mdi-slack.svg")
            _, name = ai.program_overlay("slack", {}, tmp, allow_network=False)
            self.assertEqual(name, "si:slack")


if __name__ == "__main__":
    unittest.main()
