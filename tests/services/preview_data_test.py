"""The shipped preview data, and which source wins over a firmware checkout."""
import json
import os
import pathlib
import sys
import tempfile
import unittest

# The preview renderers live in this repo's tools/, which is not a package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "tools"))
try:
    import lang_demo as ld
    import oled_preview as op
    from PIL import Image

    from polyhost.gui.layout_dialog import keycap_preview as kp
    from polyhost.services import macro_label as ml
    from polyhost.services import macro_look as mkl

    TOOLS_ERR = ""
except Exception as exc:                              # pragma: no cover - env gate
    ld = op = Image = kp = ml = mkl = None
    TOOLS_ERR = f"preview tools unavailable: {type(exc).__name__}: {exc}"

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

    def test_the_languages_are_all_there(self):
        self.assertIn("de-DE", self.d.langs)
        self.assertGreater(len(self.d.langs), 100)

    @unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
    def test_the_lang_reader_is_the_REAL_Lang(self):
        """⚠️ Not a shim. `render_key` reads letter cells AND setting cells (ints /
        HIDE, on other rows) out of one grid; a shim that handled only the first
        drew 628 of 686 sample keycaps wrong. Only the storage is replaced."""
        L = self.d.lang_reader()
        self.assertIsInstance(L, op.Lang)
        self.assertIn("de-DE", L.langs)


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
            for name in ("legends.json", "layers.json", "lang_lut.json",
                         "named_glyphs.json"):
                (p / name).write_text(json.dumps({"fw_version": "0.0.1"}))
            d = PreviewData(tmp)
            self.assertFalse(d.load())
            self.assertIn("empty", d.reason)


@unittest.skipIf(TOOLS_ERR, TOOLS_ERR)
class ShippedRendersLikeTheCheckoutTest(unittest.TestCase):
    """⚠️ The guarantee the whole export rests on, checked by DRAWING.

    Everything else here compares counts and keys; this renders every legend twice
    -- once from the shipped codepoints through the shipped fonts, once from the
    firmware's own C through the headers -- and requires the pixels to match. A
    faithful-looking export that resolved one macro differently, or assembled the
    font pool in the wrong priority, would pass every other test in this file and
    draw a subtly wrong keycap.

    Skips without a firmware checkout, which is the only way to obtain the
    second opinion.
    """

    def test_every_shipped_legend_draws_the_same_pixels(self):

        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
        if not os.path.exists(os.path.join(pk, "keycode_helper.c")):
            self.skipTest("no firmware checkout beside this repo")

        d = PreviewData()
        self.assertTrue(d.load(), d.reason)
        shipped = op.Renderer(d.fonts, mid_fonts=[d.ui_fonts[mkl.MID_FONT_SYMBOL]])
        checkout = op.load_renderer(ml.default_font_dir())

        named = op.load_named_glyphs(os.path.join(pk, "lang", "named_glyphs.h"))
        named.update(op.load_named_glyphs(os.path.join(pk, "keycode_helper.h")))
        macros = kp.parse_function_macros(*(kp._read(pk, f) for f in (
            "lang/named_glyphs.h", "keycode_helper.h", "keycode_helper.c",
            "poly_keymap.c")))
        legends_c = {**ld.parse_to_static_text_map(os.path.join(pk, "poly_keymap.c")),
                     **ld.parse_static_text_map(os.path.join(pk, "keycode_helper.c"))}
        resolver = object.__new__(op.Lang)
        resolver.named = named

        def draw(renderer, cps):
            img = Image.new("L", (op.OLED_W, op.OLED_H), 0)
            px = img.load()

            def sp(x, y):
                if 0 <= x < op.OLED_W and 0 <= y < op.OLED_H:
                    px[x, y] = 255

            renderer.draw(sp, cps, op.BUFFER_X, op.BASELINE)
            return list(img.getdata())

        checked, differ = 0, []
        for token, cps in d.legends.items():
            expr = legends_c.get(token)
            if expr is None:
                continue
            checked += 1
            if draw(shipped, cps) != draw(
                    checkout, resolver.resolve(kp.expand_function_macros(expr, macros))):
                differ.append(token)
        self.assertGreater(checked, 150, "the export lost most of its legends")
        self.assertEqual(differ, [], f"{len(differ)} legends draw differently")

    def test_letter_keycaps_draw_the_same_pixels(self):
        """The other half of the surface: the per-language letters, which are the
        bulk of the working previews.

        Sampled across scripts rather than exhaustive -- the full sweep is 15,680
        keycaps over 160 languages and all of them match, but that belongs in a
        one-off check, not in a suite that runs on every change.
        """

        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
        if not os.path.exists(os.path.join(pk, "lang", "lang_lut.xlsx")):
            self.skipTest("no firmware checkout beside this repo")

        d = PreviewData()
        self.assertTrue(d.load(), d.reason)
        named = op.load_named_glyphs(os.path.join(pk, "lang", "named_glyphs.h"))
        named.update(op.load_named_glyphs(os.path.join(pk, "keycode_helper.h")))
        shipped = (d.lang_reader(),
                   op.Renderer(d.fonts, mid_fonts=[d.ui_fonts[mkl.MID_FONT_SYMBOL]]))
        checkout = (op.Lang(os.path.join(pk, "lang", "lang_lut.xlsx"), named),
                    op.load_renderer(ml.default_font_dir()))

        differ, checked = [], 0
        # One per script family, plus the two the setting rows matter most for.
        for lang in ("en-US", "de-DE", "fr-FR", "ru-RU", "el-GR", "ar-SA", "ja-JP"):
            if lang not in shipped[0].langs:
                continue
            for kc in list(op.ROW)[:20]:
                for shift in (False, True):
                    checked += 1
                    a = op.render_key(*shipped, lang, kc, shift=shift, caps=False)
                    b = op.render_key(*checkout, lang, kc, shift=shift, caps=False)
                    if list(a.getdata()) != list(b.getdata()):
                        differ.append((lang, kc, shift))
        self.assertGreater(checked, 100)
        self.assertEqual(differ[:5], [], f"{len(differ)}/{checked} keycaps differ")


if __name__ == "__main__":
    unittest.main()
