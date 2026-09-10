"""Offline tests for the program-icon service — no network, no device.

The geometry claim these exist to hold is arithmetic, and a regression in it
would be SILENT: the mark would simply start a column or two further left, the
firmware's courtyard clear would eat into the ESC glyph, and the keycap would
look slightly wrong on hardware with nothing failing anywhere.
"""
import os
import tempfile
import unittest

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

    def test_every_shipped_slug_has_the_shape_a_slug_can_have(self):
        # A slug with a capital or a dash is a URL that 404s on every switch to
        # that app — cheap to typo, and invisible until someone watches the log.
        for app, slug in ai.load_slug_map().items():
            if slug is None:
                continue
            self.assertRegex(slug, r"^[a-z0-9]+$", f"{app} -> {slug}")

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


class OfflineTest(unittest.TestCase):

    def test_an_uncached_mark_returns_none_rather_than_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(ai.fetch_icon("gimp", tmp, allow_network=False))

    def test_a_cached_mark_needs_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _svg(tmp, SQUARE, "gimp.svg")
            self.assertEqual(ai.fetch_icon("gimp", tmp, allow_network=False), path)

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

    def test_the_slug_comes_back_even_when_the_catalog_lacks_the_mark(self):
        # An unresolvable NAME and a resolvable one the catalog does not carry
        # want different curation entries, so the caller has to be able to tell
        # them apart.
        with tempfile.TemporaryDirectory() as tmp:
            mask, slug = ai.program_overlay("Inkscape", {}, tmp, allow_network=False)
            self.assertIsNone(mask)
            self.assertEqual(slug, "inkscape")

    def test_a_suppressed_app_reports_no_slug_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                ai.program_overlay("java", {"java": None}, tmp, allow_network=False),
                (None, None))

    def test_a_cached_mark_renders_with_no_network(self):
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "inkscape.svg")
            mask, slug = ai.program_overlay("Inkscape", {}, tmp, allow_network=False)
            self.assertEqual(slug, "inkscape")
            self.assertIsNotNone(mask)
            self.assertTrue(mask.any())


if __name__ == "__main__":
    unittest.main()
