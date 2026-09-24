"""A ``QProgressDialog`` whose size does not follow its label text.

``QProgressDialog.setLabelText()`` ends in Qt's private
``ensureSizeIsAtLeastSizeHint()``, which calls ``resize()`` on the dialog on
EVERY text change: the new size hint, expanded to the current size. So the
dialog only ever grows. Without a fixed size (the forwarder) it grows to the
widest message it has shown. With ``setFixedSize`` (the tray) Qt clamps the
call, but the window system still receives a resize request per progress tick.
On GNOME and macOS the dialog grew with every text change, most likely because
each request adds the window frame to a size that already includes it.

The fix is to not call ``resize()`` at all: :meth:`setLabelText` writes the
text straight into the dialog's label. ``QProgressDialog`` has no layout. Its
``resizeEvent`` gives the label every pixel between the top margin and the
bar, so a word-wrapped label shows a longer text without a relayout.

The override is a Python method, so it only intercepts calls made from Python.
Every caller in this repo (``UpdateProgressController``, the firmware and
WinCompose progress in ``host.py``) is one.
"""
from PyQt5.QtWidgets import QLabel, QProgressDialog


class StableProgressDialog(QProgressDialog):
    """``QProgressDialog`` with a word-wrapped label and a size set once."""

    def __init__(self, label, cancel_text, minimum, maximum, parent=None):
        super().__init__(label, cancel_text, minimum, maximum, parent)
        self._label = self.findChild(QLabel)
        if self._label is not None:
            self._label.setWordWrap(True)

    def setLabelText(self, text):  # noqa: N802 — Qt override
        if self._label is None:
            super().setLabelText(text)
            return
        self._label.setText(text)
