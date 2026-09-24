"""StableProgressDialog — a label change must not resize the dialog.

Stock ``QProgressDialog.setLabelText()`` calls ``resize()`` on every change
(Qt's private ``ensureSizeIsAtLeastSizeHint``), and on GNOME and macOS the
update dialog grew with each progress message. The control test shows the
stock dialog does resize on a longer text, so the stable test can detect
the regression it guards.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QEvent, QObject
    from PyQt5.QtWidgets import QApplication, QLabel, QProgressDialog
    from polyhost.gui.progress_dialog import StableProgressDialog
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e

_LONG = "Installing requirements into the virtual environment, this can take a minute… " * 2


def _resize_counter(widget):
    class Counter(QObject):
        count = 0

        def eventFilter(self, obj, event):  # noqa: N802 — Qt override
            if obj is widget and event.type() == QEvent.Resize:
                self.count += 1
            return False

    counter = Counter()
    widget.installEventFilter(counter)
    return counter


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestStableProgressDialog(unittest.TestCase):

    def _shown(self, cls):
        dlg = cls("Downloading v1.0.0…", None, 0, 100, None)
        self.addCleanup(dlg.deleteLater)
        dlg.show()
        _APP.processEvents()
        return dlg

    def test_stock_dialog_resizes_on_longer_text(self):
        dlg = self._shown(QProgressDialog)
        counter = _resize_counter(dlg)
        dlg.setLabelText(_LONG)
        _APP.processEvents()
        self.assertGreater(counter.count, 0)

    def test_label_change_does_not_resize(self):
        dlg = self._shown(StableProgressDialog)
        size = dlg.size()
        counter = _resize_counter(dlg)
        for i in range(10):
            dlg.setLabelText(f"{_LONG} {i}")
            dlg.setValue(i * 10)
        _APP.processEvents()
        self.assertEqual(counter.count, 0)
        self.assertEqual(dlg.size(), size)

    def test_label_shows_new_text_word_wrapped(self):
        dlg = self._shown(StableProgressDialog)
        dlg.setLabelText("Extracting…")
        label = dlg.findChild(QLabel)
        self.assertEqual(label.text(), "Extracting…")
        self.assertEqual(dlg.labelText(), "Extracting…")
        self.assertTrue(label.wordWrap())


if __name__ == "__main__":
    unittest.main()
