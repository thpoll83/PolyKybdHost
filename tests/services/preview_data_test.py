"""The shipped preview data, and which source wins over a firmware checkout."""
import json
import pathlib
import tempfile
import unittest

from polyhost.services.preview_data import (PreviewData, choose_source,
                                            parse_version)


class ChooseSourceTest(unittest.TestCase):
    """⚠️ The rule that decides whether a stale clone can break the previews.

    Reading the checkout unconditionally is what produced a blank Fn key, blank
    emoji/Intl keys and retired moon brightness icons in the field (2026-09-01) --
    all from one clone that was months behind the connected keyboard.
    """

    def test_a_newer_checkout_wins(self):
        """The whole reason to read a checkout at all: a firmware developer's tree
        is ahead of the last release, and previewing it is the point."""
        self.assertEqual(choose_source("0.16.20", "0.16.21"), "checkout")
        self.assertEqual(choose_source("0.16.20", "0.17.0"), "checkout")

    def test_an_older_checkout_LOSES(self):
        """The field bug, pinned: behind means ignored, not preferred."""
        self.assertEqual(choose_source("0.16.20", "0.15.1"), "shipped")
        self.assertEqual(choose_source("0.16.20", "0.16.19"), "shipped")

    def test_an_equal_checkout_takes_the_shipped_copy(self):
        """Re-parsing the same firmware cannot beat the export that was tested."""
        self.assertEqual(choose_source("0.16.20", "0.16.20"), "shipped")

    def test_no_checkout_uses_the_shipped_data(self):
        self.assertEqual(choose_source("0.16.20", ""), "shipped")

    def test_no_shipped_export_falls_back_to_the_checkout(self):
        """A source tree with the export not yet generated still previews."""
        self.assertEqual(choose_source("", "0.16.20"), "checkout")

    def test_an_unparseable_version_sorts_oldest_rather_than_winning(self):
        """⚠️ Fail toward the tested copy. A checkout whose config.h could not be
        read reports "unknown"; treating that as newer would hand the previews to
        the source we know least about."""
        self.assertEqual(parse_version("unknown"), (-1,))
        self.assertEqual(choose_source("0.16.20", "unknown"), "shipped")

    def test_version_compare_is_numeric_not_lexicographic(self):
        """`"0.9.54" > "0.16.20"` as strings, and that is backwards."""
        self.assertGreater(parse_version("0.16.20"), parse_version("0.9.54"))
        self.assertEqual(choose_source("0.16.20", "0.9.54"), "shipped")


class ShippedDataTest(unittest.TestCase):
    """The export that ships in res/preview/."""

    @classmethod
    def setUpClass(cls):
        cls.d = PreviewData()
        cls.loaded = cls.d.load()

    def test_it_loads(self):
        self.assertTrue(self.loaded, self.d.reason)

    def test_it_carries_the_firmware_version_it_came_from(self):
        """Without this a stale export is undetectable -- the keyboard reports its
        own version, so this is the half that makes the comparison possible."""
        self.assertRegex(self.d.fw_version, r"^\d+\.\d+")

    def test_the_layer_enum_matches_the_shipped_fallback(self):
        from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
        self.assertEqual(self.d.layer_tags, qh.LAYER_TAGS)

    def test_the_legends_are_codepoints_not_c_source(self):
        """The export resolves the display list, so the host needs no macro table
        and no C parsing to draw a key."""
        cps = self.d.legends.get("MO(_FL)")
        self.assertTrue(cps and all(isinstance(c, int) for c in cps), cps)

    def test_the_fonts_are_in_all_fonts_priority_order(self):
        """⚠️ The order IS the glyph lookup -- first font holding the codepoint
        wins, which is how a resident face shadows its pack copy. Bundles are
        globbed alphabetically, so the order has to come from the records."""
        idx = [f.global_index for f in self.d.fonts]
        self.assertEqual(idx, sorted(idx))
        self.assertGreater(len(self.d.fonts), 100)

    def test_a_language_cell_reads_back(self):
        self.assertIn("de-DE", self.d.langs)
        self.assertEqual(len(self.d.cells("de-DE", "KC_Q") or []), 4)


class MissingDataTest(unittest.TestCase):
    def test_an_absent_export_reports_why_rather_than_raising(self):
        """The editor must degrade to keycode text, not fail to open."""
        with tempfile.TemporaryDirectory() as tmp:
            d = PreviewData(tmp)
            self.assertFalse(d.load())
            self.assertTrue(d.reason)

    def test_an_empty_export_is_not_reported_as_ok(self):
        """⚠️ Files that parse but carry nothing would otherwise read as a healthy
        load and blank every keycap with no reason given."""
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            for name in ("legends.json", "layers.json", "lang_lut.json"):
                (p / name).write_text(json.dumps({"fw_version": "0.0.1"}))
            d = PreviewData(tmp)
            self.assertFalse(d.load())
            self.assertIn("empty", d.reason)


if __name__ == "__main__":
    unittest.main()
