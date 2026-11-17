"""gui/menu_tiles.py: tile captions, and gui/keycap_tiles.py: the tile pictures."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from polyhost.gui import keycap_tiles, menu_tiles  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class PanelTest(unittest.TestCase):

    def test_every_panel_has_ink_except_off(self):
        panels = (keycap_tiles.size_panels([0, 1, 2])
                  + [keycap_tiles.brightness_panel(v) for v in (2, 25, 50)]
                  + [keycap_tiles.idle_panel(s) for s in range(4)]
                  + [keycap_tiles.script_panel(0)])
        for panel in panels:
            self.assertEqual(panel.size, (keycap_tiles.PANEL_W, keycap_tiles.PANEL_H))
            self.assertGreater(panel.getextrema()[1], 0)

    def test_sizes_grow(self):
        heights = [p.getbbox()[3] - p.getbbox()[1] for p in keycap_tiles.size_panels([0, 1, 2])]
        self.assertLess(heights[0], heights[1])
        self.assertLess(heights[1], heights[2])

    def test_the_automatic_brightness_tile_has_ink(self):
        panel = keycap_tiles.auto_brightness_panel()
        self.assertEqual(panel.size, (keycap_tiles.PANEL_W, keycap_tiles.PANEL_H))
        self.assertGreater(panel.getextrema()[1], 0)

    def test_brightness_rises_with_the_level(self):
        tops = [keycap_tiles.brightness_panel(v).getextrema()[1] for v in (2, 25, 50)]
        self.assertEqual(tops, sorted(tops))
        self.assertLess(tops[0], tops[2])


class ReviewFixes786Test(unittest.TestCase):
    """Caption wrapping (CodeRabbit and Revix findings on #786)."""

    def _fm(self):
        from PyQt5.QtGui import QFontMetrics, QFont
        return QFontMetrics(QFont())

    def test_a_caption_without_spaces_wraps(self):
        fm = self._fm()
        text = "\u30ad\u30fc\u30dc\u30fc\u30c9\u306e\u30af\u30e9\u30c3\u30b7\u30e5\u8a18\u9332"
        width = fm.horizontalAdvance(text) * 6 // 10
        out = menu_tiles.wrap_caption(text, fm, width)
        self.assertEqual(out.replace("\n", ""), text)       # whole, on two lines
        self.assertEqual(len(out.split("\n")), 2)

    def test_the_space_before_a_cjk_word_is_kept(self):
        # Revix on #786: "Firmware 固件" was drawn as "Firmware固件".
        fm = self._fm()
        text = "Firmware \u56fa\u4ef6\u66f4\u65b0\u68c0\u67e5\u5de5\u5177"
        # Room for the Latin word and three CJK characters on the first line.
        out = menu_tiles.wrap_caption(text, fm, fm.horizontalAdvance("Firmware \u56fa\u4ef6\u66f4"))
        self.assertTrue(out.startswith("Firmware \u56fa\u4ef6"), out)

    def test_latin_words_still_break_only_at_spaces(self):
        fm = self._fm()
        out = menu_tiles.wrap_caption("Report a Problem", fm, fm.horizontalAdvance("Report a"))
        self.assertEqual(out, "Report a\nProblem")



if __name__ == "__main__":
    unittest.main()
