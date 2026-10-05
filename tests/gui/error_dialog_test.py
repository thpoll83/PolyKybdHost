"""CopyableErrorDialog: the full text is shown and Copy puts it on the clipboard.

Runs under the offscreen Qt platform against the real widget.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.error_dialog import CopyableErrorDialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"PyQt5 unavailable: {_IMPORT_ERR}")
class CopyableErrorDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # On the class, not a module global: CodeQL reports a global kept only
        # to hold the QApplication alive as unused (docs/testing.md).
        cls.app = QApplication.instance() or QApplication([])

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

    def test_copy_fix_commands_puts_only_the_commands_on_the_clipboard(self):
        d = CopyableErrorDialog("Update failed", "The update did not finish.",
                                "long report", commands="cmd one\ncmd two")
        QApplication.clipboard().clear()
        d.copy_cmds_btn.click()
        self.assertEqual(QApplication.clipboard().text(), "cmd one\ncmd two")

    def test_no_commands_no_button(self):
        d = CopyableErrorDialog("Update failed", "The update did not finish.", "x")
        self.assertIsNone(d.copy_cmds_btn)


if __name__ == "__main__":
    unittest.main()
