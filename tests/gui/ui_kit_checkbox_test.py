"""ui_kit.wrapped_checkbox: a checkbox whose text wraps."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QPoint, Qt
    from PyQt5.QtTest import QTest
    from PyQt5.QtWidgets import QApplication, QLabel
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - no PyQt5
    _IMPORT_ERR = e
if _IMPORT_ERR is None:
    # Outside the guard: a broken module must fail the run, not skip its tests.
    from polyhost.gui.ui_kit import wrapped_checkbox

LONG = "Also show Codex in the title (wraps the codex command) " * 3


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class WrappedCheckBoxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_long_text_sets_no_wide_minimum(self):
        box, row = wrapped_checkbox(LONG)
        self.addCleanup(row.deleteLater)
        self.assertLess(row.minimumSizeHint().width(), 250)

    def test_a_click_on_the_text_clicks_the_box(self):
        box, row = wrapped_checkbox("Option")
        self.addCleanup(row.deleteLater)
        row.resize(300, 40)
        row.show()
        self.app.processEvents()
        clicks = []
        box.clicked.connect(lambda: clicks.append(box.isChecked()))
        label = row.findChild(QLabel)
        QTest.mouseClick(label, Qt.LeftButton, Qt.NoModifier, QPoint(5, 5))
        self.assertEqual(clicks, [True])
        self.assertTrue(box.isChecked())

    def test_the_box_has_the_text_as_its_name(self):
        box, row = wrapped_checkbox("Option")
        self.addCleanup(row.deleteLater)
        self.assertEqual(box.accessibleName(), "Option")


if __name__ == "__main__":
    unittest.main()
