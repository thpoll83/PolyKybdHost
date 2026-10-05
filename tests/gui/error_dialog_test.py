"""CopyableErrorDialog: the full text is shown and Copy puts it on the clipboard.

Runs under the offscreen Qt platform against the real widget.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.error_dialog import CopyableErrorDialog
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


def setUpModule():
    """Pin the QApplication for the life of the module -- see macro_tab_test."""
    if _IMPORT_ERR is None:
        assert _APP is not None


@unittest.skipIf(_IMPORT_ERR is not None, f"PyQt5 unavailable: {_IMPORT_ERR}")
class CopyableErrorDialogTest(unittest.TestCase):
    def test_long_details_are_kept_whole(self):
        details = "\n".join(f"line {i}" for i in range(200))
        d = CopyableErrorDialog("Update failed", "The update did not finish.", details)
        self.assertEqual(d.detail.toPlainText(), details)
        self.assertTrue(d.detail.isReadOnly())

    def test_copy_puts_headline_and_details_on_the_clipboard(self):
        d = CopyableErrorDialog("Update failed", "The update did not finish.",
                                "ERROR: [Errno 13] Permission denied")
        QApplication.clipboard().clear()
        d.copy_btn.click()
        self.assertEqual(QApplication.clipboard().text(),
                         "The update did not finish.\n\n"
                         "ERROR: [Errno 13] Permission denied")
        self.assertIn("Copied", d.status.text())


if __name__ == "__main__":
    unittest.main()
