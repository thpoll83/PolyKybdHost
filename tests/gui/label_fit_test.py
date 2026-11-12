"""Every keycode label fits its keycode-browser button and its board tile.

The browser button used to measure the caption as one line and stop at 7 pt, and the
tiles used `9 if len(main) < 5 else 7`, so multi-line captions were clipped. Both now
take the largest pixel size at which every line fits (`text_fit.py`). These tests
measure every keycode the editor offers, as the user sees them.
"""
import unittest

from PyQt5.QtWidgets import QApplication

from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
from polyhost.gui.layout_dialog.text_fit import fits_at, fit_pixel_size

_app = QApplication.instance() or QApplication([])

from polyhost.gui.layout_dialog.keycode_browser_button import (  # noqa: E402
    KeycodeBrowserButton, MAX_PX, MIN_PX)
from polyhost.gui.layout_dialog.renderable_key import (  # noqa: E402
    RenderableKey, LABEL_MAX_PX, LABEL_MIN_PX)
from polyhost.gui.layout_dialog.kb_layout_dialog import KEY_SCALE  # noqa: E402


class FitPixelSizeTest(unittest.TestCase):
    def test_a_short_label_keeps_the_largest_size(self):
        font = _app.font()
        self.assertEqual(fit_pixel_size(font, "A", 66, 66, 16, 6), 16)

    def test_height_counts_every_line(self):
        font = _app.font()
        one = fit_pixel_size(font, "AB", 66, 40, 16, 6)
        three = fit_pixel_size(font, "AB\nCD\nEF", 66, 40, 16, 6)
        self.assertLess(three, one)
        self.assertTrue(fits_at(font, "AB\nCD\nEF", three, 66, 40))

    def test_nothing_fits_returns_the_floor(self):
        self.assertEqual(fit_pixel_size(_app.font(), "W" * 200, 10, 10, 16, 6), 6)


class BrowserButtonTest(unittest.TestCase):
    def test_every_caption_fits_under_the_app_theme(self):
        """With the stylesheet the app applies: its 12 px button padding is what
        clipped the long captions, so a test without it measures another app."""
        from polyhost.gui import theme
        old_sheet, old_style, old_palette = _app.styleSheet(), _app.style().objectName(), _app.palette()
        try:
            theme.apply_theme(_app, theme.THEME_LIGHT)
            self.test_every_caption_fits()
        finally:
            _app.setStyleSheet(old_sheet)
            _app.setStyle(old_style)
            _app.setPalette(old_palette)

    def test_every_caption_fits(self):
        names = qh.editor_keycodes(qh.HEADER_FILE)
        bad = []
        for name in names:
            caption = qh.create_nice_name(name)
            btn = KeycodeBrowserButton(caption, name)
            r = btn.label_rect()
            px = btn.get_font_size()
            self.assertGreaterEqual(px, MIN_PX)
            self.assertLessEqual(px, MAX_PX)
            if not fits_at(btn.font(), caption, px, r.width(), r.height()):
                bad.append(caption.replace("\n", "/"))
        self.assertGreater(len(names), 1000)
        self.assertEqual(bad, [])

    def test_set_text_refits(self):
        btn = KeycodeBrowserButton("A", "KC_A")
        self.assertEqual(btn.get_font_size(), MAX_PX)
        btn.setText("UNICODE\nMODE\nWINCOMPOSE")
        self.assertLess(btn.get_font_size(), MAX_PX)


class TileLabelTest(unittest.TestCase):
    def _tile(self):
        return RenderableKey("", {"w": 1, "h": 1, "x": 0, "y": 0}, KEY_SCALE)

    def _fits(self, tile):
        w, h = tile.label_budget()
        r = tile.text.boundingRect()
        return r.width() <= w and r.height() <= h

    def test_every_keycode_label_fits_a_1u_tile(self):
        keycodes = qh.editor_keycodes(qh.HEADER_FILE)
        mapping = qh.build_keycode_to_name(keycodes)
        tile = self._tile()
        bad = []
        for value in keycodes.values():
            main, badge, color = qh.describe_keycode(value, mapping)
            for b in (badge, "LT"):          # also with a badge, which lowers the budget
                tile.set_display(main, b, color or "#66C2FF")
                px = tile.text.font().pixelSize()
                self.assertTrue(LABEL_MIN_PX <= px <= LABEL_MAX_PX, px)
                if not self._fits(tile):
                    bad.append((main.replace("\n", "/"), b))
        self.assertEqual(bad, [])

    def test_label_only_refits(self):
        tile = self._tile()
        tile.set_display("UNICODE\nMODE\nWINCOMPOSE")
        tile.set_label_only(True)
        self.assertTrue(self._fits(tile))


if __name__ == "__main__":
    unittest.main()
