"""The Fluent -> Material Symbols fallback in the shared overlay fetch helper.

Network is mocked throughout: the decision under test is WHICH source a spec
resolves against, not whether GitHub is up.
"""

import unittest
import urllib.error
from unittest.mock import patch

from polyhost.res.overlay_sources import icon_fetch


def _404(url):
    return urllib.error.HTTPError(url, 404, "Not Found", None, None)


class SpecResolutionTest(unittest.TestCase):

    def test_a_fluent_name_that_exists_never_reaches_material(self):
        with patch.object(icon_fetch, "_get", return_value=b"<svg/>") as get, \
             patch.object(icon_fetch.material_symbols, "fetch_svg") as ms:
            svg, asset, source = icon_fetch._fetch_svg("Save")
        self.assertEqual(source, "ms-fluent")
        self.assertEqual(svg, b"<svg/>")
        self.assertIn("ic_fluent_save_24_regular.svg", asset)
        get.assert_called_once()
        ms.assert_not_called()

    def test_an_explicit_ms_spec_skips_fluent_entirely(self):
        # The form to prefer: Material's vocabulary is its own, so naming the
        # glyph is the only way to get the right one.
        with patch.object(icon_fetch, "_get") as get, \
             patch.object(icon_fetch.material_symbols, "fetch_svg",
                          return_value=b"<ms/>") as ms:
            svg, asset, source = icon_fetch._fetch_svg("ms:filter_b_and_w")
        self.assertEqual((svg, asset, source),
                         (b"<ms/>", "filter_b_and_w", "material-symbols"))
        get.assert_not_called()
        ms.assert_called_once_with("filter_b_and_w",
                                   weight=icon_fetch.MS_WEIGHT)

    def test_the_keycap_weight_is_requested_not_the_font_default(self):
        # wght200 does not survive the 1-bit/40px downscale and the ~400
        # default is heavy; 250-300 is the measured band. A default-weight
        # fetch renders, so nothing but this asserts it.
        with patch.object(icon_fetch.material_symbols, "fetch_svg",
                          return_value=b"<ms/>") as ms:
            icon_fetch._fetch_svg("ms:undo")
        self.assertEqual(ms.call_args.kwargs.get("weight"), 300)

    def test_a_fluent_miss_falls_back_to_material(self):
        with patch.object(icon_fetch, "_get", side_effect=_404("u")), \
             patch.object(icon_fetch.material_symbols, "fetch_svg",
                          return_value=b"<ms/>") as ms:
            svg, asset, source = icon_fetch._fetch_svg("undo")
        self.assertEqual((svg, asset, source), (b"<ms/>", "undo", "material-symbols"))
        ms.assert_called_once_with("undo", weight=icon_fetch.MS_WEIGHT)

    def test_a_multiword_name_is_snake_cased_for_material(self):
        with patch.object(icon_fetch, "_get", side_effect=_404("u")), \
             patch.object(icon_fetch.material_symbols, "fetch_svg",
                          return_value=b"<ms/>") as ms:
            icon_fetch._fetch_svg("Arrow Undo")
        ms.assert_called_once_with("arrow_undo", weight=icon_fetch.MS_WEIGHT)

    def test_a_PINNED_fluent_asset_path_does_NOT_fall_back(self):
        # A full path names one exact cut. Silently substituting a different
        # icon set for a glyph that was pinned on purpose is worse than failing.
        with patch.object(icon_fetch, "_get", side_effect=_404("u")), \
             patch.object(icon_fetch.material_symbols, "fetch_svg") as ms:
            with self.assertRaises(FileNotFoundError):
                icon_fetch._fetch_svg("Save/SVG/ic_fluent_save_24_regular.svg")
        ms.assert_not_called()

    def test_missing_in_BOTH_names_both_sources_and_the_explicit_form(self):
        with patch.object(icon_fetch, "_get", side_effect=_404("u")), \
             patch.object(icon_fetch.material_symbols, "fetch_svg",
                          side_effect=_404("u")):
            with self.assertRaises(FileNotFoundError) as ctx:
                icon_fetch._fetch_svg("No Such Glyph")
        msg = str(ctx.exception)
        self.assertIn("Fluent", msg)
        self.assertIn("no_such_glyph", msg)
        self.assertIn("ms:", msg, "the error should say how to pick one by hand")

    def test_a_non_404_error_is_not_swallowed_as_a_miss(self):
        # A 403 from the proxy is "try again", not "this icon does not exist".
        # Treating it as a miss would silently substitute a Material glyph for
        # a Fluent one that is perfectly available.
        err = urllib.error.HTTPError("u", 403, "Forbidden", None, None)
        with patch.object(icon_fetch.material_symbols, "fetch_svg",
                          side_effect=err):
            with self.assertRaises(urllib.error.HTTPError):
                icon_fetch._fetch_svg("ms:undo")


if __name__ == "__main__":
    unittest.main()
