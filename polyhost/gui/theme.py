"""The one dark Fusion theme both QApplications wear.

``PolyHost`` (the tray app) and ``PolyForwarder`` (the remote window reporter)
are separate ``QApplication`` subclasses that must look identical — a user
running the forwarder on a second machine sees the same dialogs. They each
carried a byte-identical 22-line ``set_style``; this is that code, once.

Kept as an explicit palette rather than a stylesheet because Fusion's palette
is what propagates into the stock dialogs (``QMessageBox``,
``QProgressDialog``, the file pickers) that neither app styles by hand.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

#: Panel/window chrome, and the ground for buttons and alternating rows.
WINDOW_COLOR = QColor(80, 80, 80)
#: Text-entry / list backgrounds and tooltips — a step darker than the chrome.
BASE_COLOR = QColor(35, 35, 35)
#: Body text. Deliberately not pure white: full-contrast body text on this
#: ground reads as glare, so white is reserved for selected text.
TEXT_COLOR = QColor(200, 200, 200)
HIGHLIGHT_TEXT_COLOR = QColor(255, 255, 255)
#: Links and selection — the one accent in the palette.
ACCENT_COLOR = QColor(42, 130, 218)


def dark_palette():
    """Build the shared dark palette (no application needed — handy to test)."""
    palette = QPalette()
    palette.setColor(QPalette.Window, WINDOW_COLOR)
    palette.setColor(QPalette.WindowText, TEXT_COLOR)
    palette.setColor(QPalette.Base, BASE_COLOR)
    palette.setColor(QPalette.AlternateBase, WINDOW_COLOR)
    palette.setColor(QPalette.ToolTipBase, BASE_COLOR)
    palette.setColor(QPalette.ToolTipText, TEXT_COLOR)
    palette.setColor(QPalette.Text, TEXT_COLOR)
    palette.setColor(QPalette.Button, WINDOW_COLOR)
    palette.setColor(QPalette.ButtonText, TEXT_COLOR)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, ACCENT_COLOR)
    palette.setColor(QPalette.Highlight, ACCENT_COLOR)
    palette.setColor(QPalette.HighlightedText, HIGHLIGHT_TEXT_COLOR)
    return palette


def apply_dark_palette(app):
    """Switch ``app`` to the Fusion style with the shared dark palette.

    Returns the applied palette so a caller can tweak a role afterwards."""
    app.setStyle("Fusion")
    palette = dark_palette()
    app.setPalette(palette)
    return palette
