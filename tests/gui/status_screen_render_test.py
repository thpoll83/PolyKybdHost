"""The status panel as the editor paints it.

⚠️ These exist because `_refresh_screens` is DECORATION and swallows its exceptions:
a plain `AttributeError` in the Real branch cost nothing but a `log.debug` line, and
the panel simply stayed flat. That is the right failure mode for the editor and the
wrong one for a test suite, so the happy path is pinned here -- including that the
Real branch produces a DIFFERENT, larger image, which is the half a "did it draw?"
check cannot see.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
except ImportError as e:                      # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None
    from polyhost.gui import oled_look
    from polyhost.gui.layout_dialog import status_screen_render as ssr
    from polyhost.services import preview_data as pd
    from polyhost.services import status_screen as ss
    _APP = QApplication.instance() or QApplication([])


def setUpModule():
    """Pin the QApplication reference for the life of the module.

    `_APP` looks unused -- it is not. Qt requires exactly one QApplication and it
    must outlive every widget; letting it be garbage-collected takes the Qt runtime
    with it and the next widget construction segfaults. Asserting it here is what
    says so, to a reader and to a static analyser alike.
    """
    if _IMPORT_ERR is None:
        assert _APP is not None


@unittest.skipIf(_IMPORT_ERR is not None, "PyQt5 not installed")
class StatusScreenRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = pd.PreviewData()
        if not data.load():
            raise unittest.SkipTest("no shipped preview data")
        cls.r = ssr.StatusScreenRenderer.from_preview_data(data)
        if not cls.r.usable:
            raise unittest.SkipTest("the export lacks the status faces")

    def lit(self, img):
        ground = ssr.GROUND.rgb()
        return sum(1 for y in range(img.height()) for x in range(img.width())
                   if img.pixel(x, y) != ground)

    def test_it_renders_a_panel_sized_image_with_ink_on_it(self):
        img = self.r.render("left", 0, "Qwerty")
        self.assertEqual((img.width(), img.height()), (ss.PANEL_W, ss.PANEL_H))
        self.assertGreater(self.lit(img), 50)

    def test_the_layer_changes_what_is_drawn(self):
        """The panel names the layer being edited, so it has to follow it -- a cached
        picture that does not is the same defect the keycap caches drop on a switch."""
        self.assertNotEqual(self.r.render("left", 0, "Qwerty").constBits().asstring(
                                ss.PANEL_W * ss.PANEL_H * 4),
                            self.r.render("left", 1, "Fn").constBits().asstring(
                                ss.PANEL_W * ss.PANEL_H * 4))

    def test_the_two_halves_draw_DIFFERENT_panels(self):
        """Left carries the layout name and the lock LEDs, right the RGB readout --
        so a `side` that is not threaded through renders one screen twice, which
        looks perfectly plausible on a board whose halves are small and far apart."""
        def bits(side):
            return self.r.render(side, 0, "Qwerty").constBits().asstring(
                ss.PANEL_W * ss.PANEL_H * 4)

        self.assertNotEqual(bits("left"), bits("right"))

    def test_from_preview_data_without_data_is_UNUSABLE_not_broken(self):
        """No export means no faces; the caller must get a renderer that says so
        rather than one that raises when the editor first draws the board."""
        self.assertFalse(ssr.StatusScreenRenderer.from_preview_data(None).usable)
        self.assertFalse(ssr.StatusScreenRenderer().usable)

    @unittest.skipUnless(_IMPORT_ERR is None and oled_look.available(),
                         "Pillow unavailable")
    def test_the_REAL_filter_produces_a_LARGER_different_image(self):
        """The exact failure this file exists for: the Real branch raised, the
        `except` logged it, and the panel silently kept the Preview picture. Size is
        the cheap half of the check and difference is the real one -- a filter that
        only resized would pass on size alone."""
        plain = self.r.render("left", 0, "Qwerty")
        real = oled_look.render(plain, "oled", ssr.REAL_SCALE)
        self.assertIsNotNone(real)
        self.assertEqual(real.width(), plain.width() * ssr.REAL_SCALE)
        scaled = plain.scaled(real.width(), real.height())
        self.assertNotEqual(real.constBits().asstring(real.byteCount()),
                            scaled.convertToFormat(real.format()).constBits()
                            .asstring(real.byteCount()))


if __name__ == "__main__":
    unittest.main()
