"""glyph_script_icon — the menu icon and the tooltip, checked by rendering.

The interesting claims are both about Qt rather than about the pixels, and both
fail SILENTLY if they are wrong: a `QIcon` built from a bad pixmap is simply
empty (the trap `icon_assets_test` exists for), and a rich-text tooltip whose
image Qt cannot load renders as an empty box.  So the tooltip test draws the
HTML through a `QTextDocument` and counts what came out, rather than trusting
that the `data:` URI is a form Qt accepts.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtGui import QColor, QImage, QPainter, QPalette, QTextDocument
    from PyQt5.QtWidgets import QApplication
    from polyhost.device.command_ids import GlyphScript
    from polyhost.gui import glyph_script_icon as gsi
    from polyhost.gui import theme
    from polyhost.services import glyph_script_preview as gsp
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR, f"PyQt5 unavailable: {_IMPORT_ERR}")
class TestGlyphScriptIcon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if gsp.load_pack() is None:
            raise unittest.SkipTest("fantasy.plyf is not shipped in this tree")

    def test_every_script_gets_a_non_empty_icon(self):
        for script in GlyphScript:
            if script is GlyphScript.STANDARD:
                continue
            icon = gsi.glyph_script_icon(script.value)
            self.assertIsNotNone(icon, script.name)
            self.assertFalse(icon.isNull(), script.name)
            for size in gsi.ICON_SIZES:
                pm = icon.pixmap(size, size)
                self.assertFalse(pm.isNull(), f"{script.name} @{size}")

    def test_the_icon_carries_ink_at_the_size_a_menu_asks_for(self):
        # A menu draws the icon at PM_SmallIconSize (16 on most styles), so an
        # icon that only reads at 48 is not one anybody sees.
        img = gsi.glyph_script_icon(GlyphScript.RUNES.value).pixmap(16, 16).toImage()
        lit = sum(1 for y in range(img.height()) for x in range(img.width())
                  if QColor.fromRgba(img.pixel(x, y)).alpha() > 40)
        self.assertGreater(lit, 8, "the 16 px icon is (nearly) blank")

    def test_unlit_pixels_are_transparent(self):
        # The menu's own colour has to show through — the ink is drawn on
        # transparency, not on a black tile.
        img = gsi.glyph_script_icon(GlyphScript.C64.value).pixmap(32, 32).toImage()
        alphas = {QColor.fromRgba(img.pixel(x, y)).alpha()
                  for y in range(img.height()) for x in range(img.width())}
        self.assertIn(0, alphas)
        self.assertTrue(any(a > 200 for a in alphas))

    def test_two_scripts_do_not_get_the_same_icon(self):
        seen = set()
        for script in GlyphScript:
            pm = gsi.glyph_script_icon(script.value)
            if pm is None:
                continue
            img = pm.pixmap(32, 32).toImage()
            seen.add(bytes(img.bits().asstring(img.byteCount())))
        self.assertEqual(len(seen), len(GlyphScript))

    def test_an_unknown_script_has_no_icon(self):
        self.assertIsNone(gsi.glyph_script_icon(200))


@unittest.skipIf(_IMPORT_ERR, f"PyQt5 unavailable: {_IMPORT_ERR}")
class TestTooltip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if gsp.load_pack() is None:
            raise unittest.SkipTest("fantasy.plyf is not shipped in this tree")

    def setUp(self):
        self._palette = _APP.palette()

    def tearDown(self):
        _APP.setPalette(self._palette)

    def _ink_pixels(self, html, ground):
        """Pixels of the rendered tooltip that differ from the ground it is drawn
        on — the ink, whichever way round the theme has it."""
        doc = QTextDocument()
        doc.setHtml(html)
        doc.adjustSize()
        size = doc.size().toSize()
        self.assertGreater(size.width(), 20)
        out = QImage(max(1, size.width()), max(1, size.height()), QImage.Format_ARGB32)
        out.fill(ground)
        painter = QPainter(out)
        doc.drawContents(painter)
        painter.end()
        return sum(1 for y in range(out.height()) for x in range(out.width())
                   if abs(QColor(out.pixel(x, y)).lightness() - ground.lightness()) > 40)

    def test_the_tooltip_image_actually_renders_in_either_theme(self):
        # Qt loads `data:` URIs in rich text; if it ever stops, the tooltip is an
        # empty box and nothing else says so. Draw it against the ground the
        # tooltip actually gets (ToolTipBase) and count what stands out — which
        # also catches ink drawn in the wrong theme's colour, i.e. invisible.
        for palette in (theme.dark_palette(), theme.light_palette()):
            _APP.setPalette(palette)
            html = gsi.glyph_script_tooltip(GlyphScript.TENGWAR.value)
            self.assertIsNotNone(html)
            ground = palette.color(QPalette.ToolTipBase)
            self.assertGreater(self._ink_pixels(html, ground), 30,
                               "the tooltip image drew nothing readable")

    def test_the_tooltip_shows_more_than_the_icon(self):
        # The icon is two glyphs because that is what fits; the tooltip is the
        # whole sample, so it must be wider than the icon's aspect.
        icon_img = gsi.preview_image(GlyphScript.IBMVGA.value, gsi.ICON_SAMPLE)
        full = gsi.preview_image(GlyphScript.IBMVGA.value)
        self.assertGreater(full.width, icon_img.width)

    def test_an_unknown_script_has_no_tooltip(self):
        self.assertIsNone(gsi.glyph_script_tooltip(200))


@unittest.skipIf(_IMPORT_ERR, f"PyQt5 unavailable: {_IMPORT_ERR}")
class TestInkFollowsTheTheme(unittest.TestCase):
    """The apps follow the OS theme, so the preview ink cannot be a constant:
    near-white glyphs on a light menu are an invisible icon."""

    @classmethod
    def setUpClass(cls):
        if gsp.load_pack() is None:
            raise unittest.SkipTest("fantasy.plyf is not shipped in this tree")

    def setUp(self):
        self._palette = _APP.palette()

    def tearDown(self):
        _APP.setPalette(self._palette)

    def _ink_of(self, script_value):
        """The brightest pixel of the rendered icon — its ink."""
        img = gsi.glyph_script_icon(script_value).pixmap(32, 32).toImage()
        best, lightness = None, -1
        for y in range(img.height()):
            for x in range(img.width()):
                colour = QColor.fromRgba(img.pixel(x, y))
                if colour.alpha() > 200 and colour.lightness() > lightness:
                    best, lightness = colour, colour.lightness()
        return best

    def test_a_dark_palette_draws_the_oled_white(self):
        _APP.setPalette(theme.dark_palette())
        self.assertEqual(gsi.preview_ink(), gsi.OLED_TINT)
        self.assertGreater(self._ink_of(GlyphScript.C64.value).lightness(), 200)

    def test_a_light_palette_draws_the_palette_s_own_text_colour(self):
        _APP.setPalette(theme.light_palette())
        self.assertEqual(gsi.preview_ink(), (30, 30, 30))
        self.assertLess(self._ink_of(GlyphScript.C64.value).lightness(), 80)

    def test_the_tooltip_image_follows_the_theme_too(self):
        import base64, io, re
        from PIL import Image

        def tooltip_ink(script):
            html = gsi.glyph_script_tooltip(script)
            data = base64.b64decode(re.search(r"base64,([^\"]+)", html).group(1))
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            # The ink is one flat colour under a varying alpha, so the per-channel
            # maximum IS the tint (and needs no per-pixel walk).
            return tuple(hi for _lo, hi in img.getextrema()[:3])

        _APP.setPalette(theme.dark_palette())
        self.assertGreater(sum(tooltip_ink(GlyphScript.C64.value)), 600)
        _APP.setPalette(theme.light_palette())
        self.assertLess(sum(tooltip_ink(GlyphScript.C64.value)), 200)


if __name__ == "__main__":
    unittest.main()
