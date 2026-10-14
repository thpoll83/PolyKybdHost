"""The update confirmation dialog (gui/update_dialog.py)."""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QDialog
    from polyhost.gui import update_dialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e

# Five lines at the dialog's minimum width, the third one wrapping: the shape
# of the firmware prompt when the keyboard did not report its version.
_MESSAGE = ("Firmware 1.9.4 is available.\nReleased: 2026-10-14\n"
            "Installed: unknown (the keyboard did not report its version and "
            "this line is long enough to wrap)\n\n"
            "Both halves update over HID and reboot automatically.")


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class UpdateDialogMessageTest(unittest.TestCase):
    """The lead message lost its last line whenever a line wrapped: a top-level
    layout does not ask a label for its height-for-width (field render,
    2026-10-14)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _message_label(self, widths=()):
        """Show the dialog, then resize it to each of `widths` in turn while it
        is open. Returns one (height, needed, minimum) sample per state: the
        first as shown, then one after each resize."""
        samples = []

        def fake_exec(dlg):
            dlg.show()
            self.app.processEvents()
            label = next(lbl for lbl in dlg.findChildren(update_dialog.QLabel)
                         if lbl.text() == _MESSAGE)

            def sample():
                samples.append((label.height(), label.heightForWidth(label.width()),
                                label.minimumHeight()))

            sample()
            for w in widths:
                dlg.resize(w, dlg.height())
                self.app.processEvents()
                sample()
            dlg.close()
            return QDialog.Rejected

        with mock.patch.object(QDialog, "exec_", fake_exec):
            update_dialog.confirm_update("Update", _MESSAGE, notes="- n",
                                         html_url="https://example.invalid",
                                         question="Download and flash now?")
        return samples

    def test_a_wrapped_message_is_shown_whole(self):
        (height, needed, _), = self._message_label()
        self.assertGreater(needed, 0)
        self.assertGreaterEqual(height, needed)

    def test_the_height_follows_a_live_resize(self):
        # An open dialog, widened and narrowed back: the text fits after each
        # change, and the minimum height drops when the wider label needs
        # fewer lines (resizeEvent recomputes it; it is not fixed once).
        shown, wide, narrow = self._message_label(widths=(1200, 540))
        for height, needed, _ in (shown, wide, narrow):
            self.assertGreaterEqual(height, needed)
        self.assertLess(wide[2], shown[2])
        self.assertEqual(narrow[2], shown[2])


if __name__ == "__main__":
    unittest.main()
