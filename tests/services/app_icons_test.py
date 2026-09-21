"""Offline tests for the program-icon service — no network, no device.

The geometry claim these exist to hold is arithmetic, and a regression in it
would be SILENT: the mark would simply start a column or two further left, the
firmware's courtyard clear would eat into the ESC glyph, and the keycap would
look slightly wrong on hardware with nothing failing anywhere.
"""
import os
import sys
import tempfile
import urllib.error
import unittest
# ⚠️ Mock is reached by a plain import, not by the repo's prevailing
# import-from idiom (28 test files use that). Mixing the two forms for one
# module trips CodeQL's py/import-and-import-from, which reports on changed
# files -- so it is a new alert on a new file, not on the 28 that predate it.
import unittest.mock as mock

from polyhost.services import app_icons as ai
from polyhost.services import os_app_icon

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


def _identity(icon=None, icon_path="", names=()):
    """An `os_app_icon.AppIdentity` the way a real platform read would hand it
    over -- the icon and the display names from ONE resolution, so a test cannot
    accidentally describe two different applications either."""
    return os_app_icon.AppIdentity(icon=icon, icon_path=icon_path, names=names)


def _ring(draw, size):
    draw.ellipse([10, 10, size - 10, size - 10], outline=(20, 20, 20, 255), width=12)


def _disc(draw, size):
    draw.ellipse([0, 0, size, size], fill=(120, 120, 120, 255))


def _png(shape, size=128):
    """A real PNG, not a stub: the score these tests turn on is `icon_binarise`'s
    reading of actual pixels, and a mocked score would pin nothing."""
    import io
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shape(ImageDraw.Draw(image), size)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


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


class CandidatesTest(unittest.TestCase):
    """Which names an app is tried under, in which order."""

    def test_the_DISPLAY_name_is_tried_before_the_executable_name(self):
        # The whole of B.2. An executable name is what the process happens to be
        # called; the display name is what the vendor calls the product, which
        # is what a catalog is indexed by.
        tried = ai.candidates("WINWORD.EXE", ("Microsoft Word",))
        self.assertLess(tried.index("mdi:microsoft-word"),
                        min(i for i, n in enumerate(tried) if "winword" in n))

    def test_a_display_name_reaches_mdi_s_OWN_SPELLING(self):
        # `kebab("Microsoft Word")` IS mdi's slug. That is the mechanism the
        # whole no-config approach rests on, and `winword` can never reach it:
        # no amount of fuzziness bridges an abbreviation to a brand.
        self.assertIn("mdi:microsoft-word",
                      ai.candidates("WINWORD.EXE", ("Microsoft Word",)))
        self.assertIn("mdi:visual-studio-code",
                      ai.candidates("code", ("Visual Studio Code",)))

    def test_a_bare_mdi_name_needs_a_HYPHEN(self):
        # ⚠️ The safety rule for the display name, and it is load-bearing. mdi
        # is 7400 icons of which most are generic UI symbols, so a bare hit is
        # not evidence of a brand -- and a display name fails in exactly that
        # direction: measured on a stock container, `yelp` reports "Help" and
        # `xdg-desktop-portal-gtk` reports "Portal", while `mdi:help` and
        # `mdi:settings` both return 200. Requiring a hyphen keeps
        # `microsoft-word` and refuses those; measured, 13/14 real names still
        # resolve and 1/10 generic ones leak.
        self.assertNotIn("mdi:help", ai.candidates("yelp", ("Help",)))
        self.assertNotIn("mdi:settings", ai.candidates("gnome-control-center",
                                                       ("Settings",)))
        self.assertIn("mdi:microsoft-word",
                      ai.candidates("winword", ("Microsoft Word",)))

    def test_simple_icons_is_tried_FIRST(self):
        # It carries the real brand mark where it has one; mdi's is an
        # interpretation. Order is preference, not a set of equals.
        self.assertEqual(ai.candidates("Inkscape")[0], "si:inkscape")
        self.assertEqual(ai.candidates("code", ("Visual Studio Code",))[0],
                         "si:visualstudiocode")

    def test_the_names_are_tried_in_the_ORDER_GIVEN(self):
        # `display_names()` returns them best first -- on Windows
        # `FileDescription` ("Microsoft Word") before `ProductName` ("Microsoft
        # Office"), which names the suite rather than the app.
        tried = ai.candidates("winword", ("Microsoft Word", "Microsoft Office"))
        self.assertLess(tried.index("si:microsoftword"),
                        tried.index("si:microsoftoffice"))

    def test_a_name_is_offered_ONCE(self):
        # Two display names can reduce to one slug, and a repeat costs a
        # round-trip to a 404 that the first one already proved.
        tried = ai.candidates("Inkscape", ("Inkscape", "inkscape"))
        self.assertEqual(len(tried), len(set(tried)))

    def test_the_BARE_mdi_name_is_never_tried_for_an_EXECUTABLE(self):
        # ⚠️ Stricter than the display-name rule above, and deliberately: an
        # executable name has none of the display name's multi-word structure to
        # lean on. `code` resolves to a generic `</>` glyph, which on VS Code is
        # a wrong icon by this module's own rule.
        self.assertNotIn("mdi:code", ai.candidates("code"))
        self.assertNotIn("mdi:terminal", ai.candidates("terminal"))

    def test_the_PREFIXED_mdi_names_are_tried(self):
        # These are what reach Office from the executable alone -- the fallback
        # for when the OS gave us no display name at all. Safe because every mdi
        # `microsoft-*` stem is a genuine product name (measured over all 50).
        self.assertIn("mdi:microsoft-word", ai.candidates("word"))
        self.assertIn("mdi:adobe-acrobat", ai.candidates("acrobat"))

    def test_no_names_at_all_still_yields_the_executable_route(self):
        # The honest degradation when the OS says nothing: fewer candidates,
        # not zero.
        self.assertEqual(ai.candidates("Inkscape", ()),
                         ai.candidates("Inkscape"))
        self.assertTrue(ai.candidates("Inkscape", ()))

    def test_kebab_keeps_the_separators_normalise_drops(self):
        # The catalogs name the same brand differently, so one normalised form
        # cannot address both.
        self.assertEqual(ai.normalise("Visual Studio Code"), "visualstudiocode")
        self.assertEqual(ai.kebab("Visual Studio Code"), "visual-studio-code")
        self.assertEqual(ai.kebab("org.gimp.GIMP"), "gimp")
        self.assertEqual(ai.kebab("gimp-2.0"), "gimp")

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
        # Flush right, a box of B starts at 72 - B, and the courtyard clears
        # three columns further left again. 44 reads as a safe compromise and is
        # not — it clears from 25 against ink reaching 27, so 40 is the ceiling.
        for box in (ai.PROGRAM_ICON_BOX, ai.PROGRAM_ICON_BOX_MAX):
            left = ai.PANEL_W - box
            self.assertGreater(left - COURTYARD, ESC_INK_RIGHT,
                               f"a box of {box} would eat into the ESC legend")

    def test_the_SHIPPED_box_leaves_a_border_inside_that_ceiling(self):
        """⚠️ Two different constraints, and only one of them is arithmetic.

        The CEILING (40) is the courtyard: past it the clear eats the ESC glyph.
        The SHIPPED box (38) is a look: at the ceiling a mark that is square in
        its viewBox inks the panel edge to edge — measured, 10 of 15 shipped
        marks did — and a keycap reads as a cropped picture rather than an icon
        sitting on it. Reported from hardware as "a bit too big".

        So this pins the border, not the number: raising the box back to the
        ceiling passes the courtyard test above and fails this one.
        """
        self.assertLess(ai.PROGRAM_ICON_BOX, ai.PANEL_H,
                        "a full-height mark leaves no border top or bottom")
        self.assertLessEqual(ai.PROGRAM_ICON_BOX, ai.PROGRAM_ICON_BOX_MAX)
        # ...and not so small that the only keycap with a whole free half of
        # panel is spent on whitespace.
        self.assertGreaterEqual(ai.PROGRAM_ICON_BOX, ai.PANEL_H - 6)

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
        except Exception as exc:
            # RAISE rather than self.skipTest(): skipTest raises SkipTest too,
            # but a static analyser cannot see that it never returns, so every
            # name bound in the try above reads as possibly-uninitialised on the
            # lines below (CodeQL py/uninitialized-local-variable, 3 errors).
            raise unittest.SkipTest(
                f"preview data / renderer unavailable: {exc}") from exc
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
    """The resolution order: OS icon, then catalog, then nothing."""

    def test_the_name_comes_back_even_when_no_catalog_has_the_mark(self):
        # An unresolvable NAME and a resolvable one no catalog carries want
        # different diagnoses, so the caller has to tell them apart.
        with tempfile.TemporaryDirectory() as tmp:
            mask, name = ai.program_overlay("Inkscape", cache_dir=tmp,
                                            allow_network=False)
            self.assertIsNone(mask)
            self.assertEqual(name, "si:inkscape")

    def test_a_cached_mark_renders_with_no_network(self):
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            mask, name = ai.program_overlay("Inkscape", cache_dir=tmp,
                                            allow_network=False)
            self.assertEqual(name, "si:inkscape")
            self.assertIsNotNone(mask)
            self.assertTrue(mask.any())

    def test_the_SECOND_catalog_is_tried_when_the_first_has_nothing(self):
        # The whole reason there are two: Simple Icons carries no Microsoft at
        # all, so Word can only come from mdi.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "mdi-microsoft-word.svg")
            mask, name = ai.program_overlay("word", cache_dir=tmp,
                                            allow_network=False)
            self.assertEqual(name, "mdi:microsoft-word")
            self.assertIsNotNone(mask)

    def test_the_FIRST_catalog_wins_when_both_have_the_mark(self):
        # Simple Icons is the real brand mark; mdi's is an interpretation of it.
        # Driven through a DISPLAY name because that is the only route on which
        # a bare mdi name is offered at all (the hyphen rule above).
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-visualstudiocode.svg")
            _svg(tmp, WIDE, "mdi-visual-studio-code.svg")
            _, name = ai.program_overlay("code", _identity(names=("Visual Studio Code",)),
                                         tmp, allow_network=False)
            self.assertEqual(name, "si:visualstudiocode")

    def test_TWO_APPS_WITH_THE_SAME_ICON_FILENAME_get_DIFFERENT_slugs(self):
        """⚠️ THE SLUG IS THE MRU CACHE KEY, and on macOS nearly every system
        app ships its icon as literally `AppIcon.icns` — Maps, Photos, Notes,
        Safari, Freeform. Keyed on the basename they all collapsed to
        `os:AppIcon.icns`, so the MRU filed Maps' mark under it and then served
        Maps' icon to every app that followed: an MRU HIT, no upload, nothing
        in the log to notice. Reported from the field as "the maps icon kept
        showing for every following app" (2026-09-21).
        """
        _needs_render(self)
        icns = "/System/Applications/%s.app/Contents/Resources/AppIcon.icns"
        with tempfile.TemporaryDirectory() as tmp:
            maps = ai.program_overlay("Maps", _identity(
                icon=_png(_ring), icon_path=icns % "Maps"),
                tmp, allow_network=False)[1]
            # ⚠️ Another SCOREABLE shape, not just different bytes: a mark
            # that fails the 1-bit gate falls through to the catalog and
            # returns `si:photos`, so the test would assert nothing about the
            # slug. A ring at a different size is both.
            photos = ai.program_overlay("Photos", _identity(
                icon=_png(_ring, 96), icon_path=icns % "Photos"),
                tmp, allow_network=False)[1]
            self.assertTrue(maps.startswith("os:AppIcon.icns@"), maps)
            self.assertTrue(photos.startswith("os:AppIcon.icns@"), photos)
            self.assertNotEqual(maps, photos)

    def test_THE_SAME_ICON_from_two_paths_SHARES_a_slug(self):
        """⚠️ The better half of the fix, not a side effect: the digest is of
        the ICON BYTES, so two apps that genuinely ship the same icon still
        share one pool slot — and an icon that CHANGES under a fixed path (a
        theme switch) gets a new slug and is redrawn instead of being served
        stale."""
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            a = ai.program_overlay("One", _identity(
                icon=_png(_ring), icon_path="/A/One.app/AppIcon.icns"),
                tmp, allow_network=False)[1]
            b = ai.program_overlay("Two", _identity(
                icon=_png(_ring), icon_path="/B/Two.app/AppIcon.icns"),
                tmp, allow_network=False)[1]
            self.assertEqual(a, b)

    def test_the_OS_ICON_IS_ASKED_BEFORE_THE_CATALOG(self):
        # ⚠️ The E2 reversal, and the whole point of it: the OS's own icon is
        # exact by construction -- no name matching, no network, nothing to
        # guess wrong -- so a catalog mark that WOULD have resolved must not
        # win over it.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            mask, name = ai.program_overlay(
                "Inkscape", _identity(icon=_png(_ring), icon_path="/t/inkscape.png"),
                tmp, allow_network=False)
            self.assertTrue(name.startswith("os:inkscape.png@"), name)
            self.assertIsNotNone(mask)
            self.assertTrue(mask.any())

    def test_an_OS_icon_that_does_not_survive_1_BIT_falls_through(self):
        # ⚠️ `MIN_SCORE` is the ONLY thing that makes OS-first safe. Catalog art
        # is one path drawn for small monochrome use and cannot be unreadable;
        # an OS icon is full-colour art that has to survive thresholding, and
        # measurably not all of it does. A flat filled disc scores 0.06 -- it
        # would draw a blob over the ESC keycap, so the catalog gets it instead.
        _needs_render(self)
        blob = _png(_disc)
        _, _, score = ai.render_os_overlay(blob)
        self.assertLess(score, ai.icon_binarise.MIN_SCORE)   # the premise
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            mask, name = ai.program_overlay(
                "Inkscape", _identity(icon=blob, icon_path="/t/inkscape.png"),
                tmp, allow_network=False)
            self.assertEqual(name, "si:inkscape")
            self.assertIsNotNone(mask)

    def test_an_UNDECODABLE_OS_icon_falls_through_rather_than_ending_it(self):
        # A truncated .ico or an HTML error page under a .png name must not cost
        # the app the catalog route it would otherwise have had.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            _, name = ai.program_overlay(
                "Inkscape", _identity(icon=b"<html>404</html>",
                                      icon_path="/t/inkscape.png"),
                tmp, allow_network=False)
            self.assertEqual(name, "si:inkscape")

    def test_the_identity_s_DISPLAY_NAMES_are_what_the_catalog_is_keyed_on(self):
        # The identity carries both halves, so an app whose icon is unreadable
        # still gets the better catalog key. `winword` alone never reaches
        # `microsoft-word` by the display route.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "mdi-microsoft-word.svg")
            _, name = ai.program_overlay(
                "WINWORD.EXE", _identity(names=("Microsoft Word",)),
                tmp, allow_network=False)
            self.assertEqual(name, "mdi:microsoft-word")

    def test_NO_identity_is_a_degradation_not_an_error(self):
        # The honest shape for a caller with no pid -- a forwarded window
        # report, say. Fewer candidates, no crash, no OS lookup attempted.
        _needs_render(self)
        with tempfile.TemporaryDirectory() as tmp:
            _svg(tmp, SQUARE, "si-inkscape.svg")
            mask, name = ai.program_overlay("Inkscape", None, tmp,
                                            allow_network=False)
            self.assertEqual(name, "si:inkscape")
            self.assertIsNotNone(mask)


class SvgOsIconIsReadAsColourArtTest(unittest.TestCase):
    """An OS SVG icon must not be reduced to its silhouette.

    Reported from a live forwarder (2026-09-17): gnome-terminal and PolyHost's
    own log window drew marks while GNOME Text Editor drew nothing. `_alpha`
    gives coverage, which is exactly right for a catalog mark -- one monochrome
    path whose alpha IS the drawing -- and throws away everything inside a
    modern desktop icon, a filled plate with art on top.

    ⚠️ **The numbers that motivated this come from the REAL
    `org.gnome.TextEditor.svg`, measured, and are deliberately not asserted
    here**: silhouette 71.8% lit scoring **0.10** against `MIN_SCORE` 0.30, the
    same file read as colour scoring **0.48** and drawing a recognisable pen.
    Four synthetic plate icons were tried as a stand-in and none of them clears
    the gate in colour either (0.15-0.25) -- they are flat fills where the real
    one has gradients and shading. Tuning a fixture until it agreed would have
    been the suite measuring itself, so what is pinned below is the MECHANISM,
    which holds for every one of them: on a plate icon the colour reading beats
    the silhouette. Whether a given icon then clears `MIN_SCORE` is a property
    of that icon, not of this change.
    """

    # A plate drawn as a PATH -- `svg_raster` renders `<path>` only, so a
    # `<rect>` plate is silently skipped and the fixture stops being a plate at
    # all. That cost a round here.
    PLATE = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        '<path d="M32 8h64a24 24 0 0 1 24 24v64a24 24 0 0 1-24 24H32'
        'A24 24 0 0 1 8 96V32A24 24 0 0 1 32 8z" fill="#f6f5f4"/>'
        '<path d="M92 28l14 14-46 46-18 4 4-18z" fill="#241f31"/>'
        '</svg>'
    ).encode()

    MONO = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M12 2L2 22h20L12 2zm0 6l6 12H6l6-12z"/></svg>'
    ).encode()

    def _cairo(self):
        try:
            import cairosvg  # noqa: F401
        except Exception:
            self.skipTest("cairosvg not installed; the silhouette path is used")

    def _silhouette(self, svg):
        handle, path = tempfile.mkstemp(suffix=".svg")
        try:
            with os.fdopen(handle, "wb") as fh:
                fh.write(svg)
            return ai.render_overlay(path, ai.PROGRAM_ICON_BOX)
        finally:
            os.unlink(path)

    def test_the_silhouette_reading_of_a_plate_icon_is_a_BLOB(self):
        # Pins the premise. If this stops being true the change below is
        # solving a problem that no longer exists.
        mask = self._silhouette(self.PLATE)
        window = mask[:, ai.PANEL_W - ai.PROGRAM_ICON_BOX:]
        self.assertGreater(window.sum() / window.size, 0.6,
                           "the plate should swallow the drawing")
        self.assertLess(ai.icon_binarise.score(window),
                        ai.icon_binarise.MIN_SCORE,
                        "and MIN_SCORE should refuse it")

    def test_the_colour_reading_BEATS_the_silhouette_on_a_plate_icon(self):
        self._cairo()
        window = self._silhouette(self.PLATE)[:, ai.PANEL_W - ai.PROGRAM_ICON_BOX:]
        _, _, colour = ai._svg_colour_candidate(self.PLATE, ai.PROGRAM_ICON_BOX)
        self.assertGreater(colour, ai.icon_binarise.score(window))

    def test_render_os_overlay_returns_the_colour_candidate_for_a_plate(self):
        self._cairo()
        _, conversion, _ = ai.render_os_overlay(self.PLATE)
        self.assertNotEqual(conversion, "svg",
                            "the silhouette must not win on a plate icon")

    def test_a_monochrome_svg_reads_THE_SAME_either_way(self):
        # The safety property: for a single-path mark, whose alpha IS the
        # drawing, competing the colour reading against the silhouette cannot
        # change what a catalog-style icon draws.
        #
        # ⚠️ It used to assert ZERO differing pixels, and that became too strict
        # when `choose()` started PREFERRING a dither: the winner here is now
        # `dither-hi`, which reproduces the shape exactly in its interior (a flat
        # mark has no midtones to diffuse) and differs on 20 ANTI-ALIASED EDGE
        # pixels of 1444. Rendered side by side the two are indistinguishable.
        # So the property is intact and the measurement of it had to widen; a
        # tolerance this tight still fails if a real dither field appears.
        self._cairo()
        silhouette = self._silhouette(self.MONO)
        colour, _, _ = ai._svg_colour_candidate(self.MONO, ai.PROGRAM_ICON_BOX)
        self.assertIsNotNone(colour)
        differing = int((silhouette != colour).sum())
        self.assertLess(differing, 0.02 * silhouette.size,
                        "a flat mark must not come back textured")

    def test_the_conversion_WITHOUT_diffusion_still_matches_exactly(self):
        # The half of the old assertion that is still exact, kept so the claim
        # above ("a flat mark has no midtones to diffuse") is pinned rather than
        # asserted in a comment.
        self._cairo()
        import io
        from PIL import Image
        import cairosvg
        raster = Image.open(io.BytesIO(cairosvg.svg2png(
            bytestring=self.MONO, output_width=160, output_height=160)))
        raster.load()
        alpha = dict(ai.icon_binarise.CONVERSIONS)["alpha"](raster, ai.PROGRAM_ICON_BOX)
        plain = dict(ai.icon_binarise.CONVERSIONS)["dither"](raster, ai.PROGRAM_ICON_BOX)
        self.assertEqual(int((alpha != plain).sum()), 0)

    def test_without_cairosvg_the_silhouette_is_still_used(self):
        # Windows has no cairosvg wheel, and `svg_raster` fills paths into a
        # coverage mask by construction, so it cannot answer this. The
        # degradation has to be today's behaviour, not a blank keycap.
        with mock.patch.dict(sys.modules, {"cairosvg": None}):
            mask, conversion, _ = ai.render_os_overlay(self.MONO)
        self.assertIsNotNone(mask)
        self.assertEqual(conversion, "svg")

    def test_the_colour_candidate_never_raises_on_junk(self):
        self.assertIsNone(
            ai._svg_colour_candidate(b"<svg not really", 38)[0])


class WhyTheCatalogMissedTest(unittest.TestCase):
    """⚠️ A MISS must say which KIND of miss it was.

    Every failure path in `fetch_icon` was `log.debug` or nothing at all, so at
    the default level the only thing a user saw was the aggregate "the catalog
    carries none of ...". That line reads the same for a 404 (this brand is not
    in the catalog -- nothing to do), a refused download (network, proxy, an
    unwritable cache -- fix your machine) and auto-fetch being switched off
    (flip the setting). Three different actions behind one sentence.

    Measured on macOS 2026-09-21: `si:googlechrome` is a real slug that answers
    200, and the log still said only "carries none of" -- so the reason could
    not be worked out from the field log at all.
    """

    def _reason(self, slug, **kw):
        reasons = {}
        with tempfile.TemporaryDirectory() as tmp:
            ai.fetch_icon(slug, tmp, reasons=reasons, **kw)
        return reasons.get(slug)

    def test_auto_fetch_being_OFF_is_named(self):
        self.assertIn("auto-fetch is off",
                      self._reason("si:gimp", allow_network=False))

    def test_an_unknown_SOURCE_is_named(self):
        self.assertEqual(self._reason("nosuchcatalog:gimp", allow_network=True),
                         "unknown source")

    def test_a_404_is_named_as_an_ORDINARY_answer(self):
        """Not a fault: the brand is not in the catalog and never will be."""
        err = urllib.error.HTTPError("u", 404, "Not Found", None, None)
        with mock.patch.object(ai.urllib.request, "urlopen", side_effect=err):
            self.assertEqual(self._reason("si:nope"), "not in the catalog (404)")

    def test_another_HTTP_status_is_NOT_called_a_missing_brand(self):
        err = urllib.error.HTTPError("u", 503, "Unavailable", None, None)
        with mock.patch.object(ai.urllib.request, "urlopen", side_effect=err):
            self.assertEqual(self._reason("si:nope"), "HTTP 503")

    def test_a_REFUSED_download_is_named(self):
        with mock.patch.object(ai.urllib.request, "urlopen",
                               side_effect=OSError("proxy refused")):
            self.assertIn("download failed", self._reason("si:nope"))

    def test_a_200_THAT_IS_NOT_AN_SVG_is_named(self):
        """Silent before this: a proxy error page returning 200 was refused by
        `_is_svg` and reported as if the brand did not exist."""
        body = b"<!DOCTYPE html><html>nope</html>"
        response = mock.MagicMock()
        response.read.return_value = body
        response.__enter__ = lambda self_: response
        response.__exit__ = lambda *a: False
        with mock.patch.object(ai.urllib.request, "urlopen", return_value=response):
            self.assertIn("not an SVG", self._reason("si:nope"))

    def test_the_MISS_LINE_carries_the_reason(self):
        """The reason is useless if `program_overlay` drops it."""
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertLogs(ai.log, level="INFO") as captured:
                mask, _ = ai.program_overlay("gimp", None, tmp,
                                             allow_network=False)
        self.assertIsNone(mask)
        line = "\n".join(captured.output)
        self.assertIn("No program mark for gimp", line)
        self.assertIn("auto-fetch is off", line)


if __name__ == "__main__":
    unittest.main()
