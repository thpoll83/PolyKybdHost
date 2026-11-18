"""The About dialog (gui/about_dialog.py): its About and Basics sections."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QLabel, QScrollArea
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - no PyQt5
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui import about_dialog as ad


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class AboutDialogTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self):
        dlg = ad.build_about_dialog(
            heading=ad.heading_html("1.2.3", "", "Linux"), description="Host app.",
            boxed="<b>Keyboard:</b> Split72", muted="<b>Log:</b> /tmp/log",
            diagnostics_cb=lambda: "diag", clipboard=self.app.clipboard())
        self.addCleanup(dlg.deleteLater)
        dlg.resize(820, 640)
        dlg.show()
        self.app.processEvents()
        return dlg

    def test_two_sections_with_a_sidebar_entry_each(self):
        dlg = self._dialog()
        self.assertEqual([s.title for s in dlg.about_sections], ["About", "Basics"])
        self.assertEqual(dlg.about_nav.count(), 2)

    def test_the_about_section_keeps_the_version_and_the_blocks(self):
        dlg = self._dialog()
        text = " ".join(lbl.text() for lbl in dlg.about_sections[0].findChildren(QLabel))
        for part in ("1.2.3", "Split72", "/tmp/log", "polykybd.org"):
            self.assertIn(part, text)

    def test_every_basics_entry_has_its_card_and_picture(self):
        dlg = self._dialog()
        text = " ".join(lbl.text() for lbl in dlg.about_sections[1].findChildren(QLabel))
        for title, _body, picture in ad.BASICS:
            self.assertIn(title, text)
            if picture.endswith(".png"):
                self.assertTrue((ad.BASICS_DIR / picture).is_file(), picture)

    def test_a_png_picture_is_never_wider_than_its_card(self):
        dlg = self._dialog()
        dlg.resize(640, 480)
        self.app.processEvents()
        scroll = dlg.findChild(QScrollArea)
        width = scroll.viewport().width()
        pictures = dlg.findChildren(ad._FitPicture)
        self.assertEqual(len(pictures), sum(p.endswith(".png") for _t, _b, p in ad.BASICS))
        for pic in pictures:
            self.assertGreater(pic.pixmap().width(), 0)
            self.assertLessEqual(pic.pixmap().width(), width)

    def test_the_sidebar_follows_the_scrolling(self):
        dlg = self._dialog()
        bar = dlg.findChild(QScrollArea).verticalScrollBar()
        bar.setValue(bar.maximum())
        self.app.processEvents()
        self.assertEqual(dlg.about_nav.currentRow(), 1)
        dlg.about_nav.setCurrentRow(0)
        self.app.processEvents()
        # 8 px above the About section, so its colour band shows.
        self.assertEqual(bar.value(), max(0, dlg.about_sections[0].y() - ad.px(8)))


if __name__ == "__main__":
    unittest.main()
