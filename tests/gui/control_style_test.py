"""gui/theme.control_style(): the rounded-control style sheet."""
import os
import pathlib
import re
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

from polyhost.gui import theme  # noqa: E402

_APP = QApplication.instance() or QApplication([])


class ControlStyleTest(unittest.TestCase):

    def test_the_arrow_images_exist(self):
        for path in re.findall(r'url\("([^"]+)"\)', theme.control_style(theme.THEME_LIGHT)):
            self.assertTrue(pathlib.Path(path).is_file(), path)
            self.assertNotIn("\\", path)

    def test_each_theme_has_its_own_colours(self):
        light = theme.control_style(theme.THEME_LIGHT)
        dark = theme.control_style(theme.THEME_DARK)
        self.assertNotEqual(light, dark)
        # The shared palettes leave Midlight at a light grey on the dark theme;
        # the sheet must not read palette roles for the button states.
        self.assertNotIn("palette(midlight)", dark)

    def test_the_corner_scales_with_the_display(self):
        from polyhost.gui import ui_kit
        with mock.patch.object(ui_kit, "ui_scale", return_value=1.5):
            self.assertIn("border-radius: 9px", theme.control_style(theme.THEME_LIGHT))

    def test_apply_theme_sets_the_sheet_once(self):
        theme.apply_theme(_APP, theme.THEME_DARK)
        self.assertEqual(_APP.styleSheet(), theme.control_style(theme.THEME_DARK))
        with mock.patch.object(_APP, "setStyleSheet") as set_sheet:
            theme.apply_theme(_APP, theme.THEME_DARK)
        set_sheet.assert_not_called()
        theme.apply_theme(_APP, theme.THEME_LIGHT)
        self.assertEqual(_APP.styleSheet(), theme.control_style(theme.THEME_LIGHT))

    def test_a_button_still_gets_its_size(self):
        theme.apply_theme(_APP, theme.THEME_LIGHT)
        btn = QPushButton("OK")
        btn.ensurePolished()
        self.assertGreater(btn.sizeHint().height(), 20)


class ButtonWidthTest(unittest.TestCase):

    def test_text_buttons_in_a_row_match_and_arrows_keep_their_width(self):
        from PyQt5.QtWidgets import QDialog, QHBoxLayout
        from polyhost.gui import ui_kit
        theme.apply_theme(_APP, theme.THEME_LIGHT)
        dlg = QDialog()
        self.addCleanup(dlg.deleteLater)
        row = QHBoxLayout(dlg)
        short, long_, arrow = QPushButton("OK"), QPushButton("Collect logs and report"), QPushButton("↑")
        for b in (short, long_, arrow):
            row.addWidget(b)
        dlg.show()
        _APP.processEvents()
        self.assertEqual(short.width(), long_.width())
        self.assertLess(arrow.width(), long_.width())
        self.assertIsNotNone(getattr(_APP, "_polyhost_button_widths", None))
        ui_kit.install_button_width_matching(_APP)   # a second call adds nothing


class RowGrowsTest(unittest.TestCase):
    """The log bundle's "Show in Folder" appears after a save; the matched row
    then needed more than the window had, and the buttons overlapped
    (reported on Windows at 150 %)."""

    def test_show_in_folder_appearing_widens_the_log_bundle_dialog(self):
        from polyhost.gui.log_bundle_dialog import LogBundleDialog
        theme.apply_theme(_APP, theme.THEME_LIGHT)
        dlg = LogBundleDialog()
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        _APP.processEvents()
        dlg.reveal_btn.setVisible(True)
        for _ in range(3):
            _APP.processEvents()
        close = next(b for b in dlg.findChildren(QPushButton)
                     if b.isVisible() and b not in (dlg.reveal_btn, dlg.copy_btn, dlg.save_btn))
        row = [dlg.reveal_btn, dlg.copy_btn, dlg.save_btn, close]
        xs = [(b.mapTo(dlg, b.rect().topLeft()).x(), b.width()) for b in row]
        for (x1, w1), (x2, _w2) in zip(xs, xs[1:]):
            self.assertLessEqual(x1 + w1, x2, xs)
        for b in row:
            self.assertGreaterEqual(b.width(), b.sizeHint().width(), b.text())
        self.assertLessEqual(xs[-1][0] + xs[-1][1], dlg.width())


class OverlappingGroupsTest(unittest.TestCase):
    """CodeRabbit on #788: a button box's buttons are in their own row and in
    the outer row; with two widths a pass changed them back and forth."""

    def test_a_button_box_beside_a_button_settles_on_one_width(self):
        from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout
        from polyhost.gui import ui_kit
        theme.apply_theme(_APP, theme.THEME_LIGHT)
        dlg = QDialog()
        self.addCleanup(dlg.deleteLater)
        row = QHBoxLayout(dlg)
        wide = QPushButton("Collect logs and open the report form")
        row.addWidget(wide)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        row.addWidget(box)
        dlg.show()
        _APP.processEvents()
        widths = [b.minimumWidth() for b in [wide] + box.buttons()]
        self.assertEqual(len(set(widths)), 1, widths)
        with mock.patch.object(QPushButton, "setMinimumWidth") as set_width:
            ui_kit.match_button_widths(dlg)      # a second pass changes nothing
        set_width.assert_not_called()


if __name__ == "__main__":
    unittest.main()
