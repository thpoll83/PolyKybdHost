"""The one Fusion theme both QApplications wear — dark or light, per the OS.

``PolyHost`` (the tray app) and ``PolyForwarder`` (the remote window reporter)
are separate ``QApplication`` subclasses that must look identical — a user
running the forwarder on a second machine sees the same dialogs. They each
carried a byte-identical 22-line ``set_style``; this is that code, once.

Kept as an explicit palette rather than a stylesheet because Fusion's palette
is what propagates into the stock dialogs (``QMessageBox``,
``QProgressDialog``, the file pickers) that neither app styles by hand — and
that is also why the light theme is a second explicit palette here rather than
``standardPalette()``: both are then readable, testable and symmetric.

⚠️ **The STYLE stays Fusion in both themes; only the palette changes.** Qt 5's
native Windows style has no dark mode, so dark has to be Fusion — and switching
style by theme would mean the app looked like two different programs depending
on a system setting, with the widgets that carry a Fusion-shaped stylesheet
(`cmd_menu`'s proxy style, the inspectors) only ever checked in one of them.
So this follows the OS's light/dark *choice*, not the platform's native
chrome.

⚠️ **Some developer dialogs hardcode dark colours** (`mru_inspector_dialog`,
`fontpack_inspector_dialog`, `fontpack_extend_dialog`) — mostly around OLED
previews, where a black ground is the content rather than chrome. They are
behind developer mode and are deliberately left alone; every surface a normal
user sees draws from the palette.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette

from polyhost.services.os_theme import (
    THEME_AUTO, THEME_DARK, THEME_LIGHT, THEMES, detect_os_theme, resolve_theme,
)

# The Qt-facing front door: a caller that already imports this module for
# `apply_theme` should not need a second import for the names that go with it.
# Declared rather than merely imported because a bare re-export reads as dead
# code to anything that only looks within this file — CodeQL flagged exactly
# that, and `THEME_DARK` is genuinely used (through the module, from the tests).
__all__ = [
    "THEME_AUTO", "THEME_DARK", "THEME_LIGHT", "THEMES",
    "detect_os_theme", "resolve_theme",
    "dark_palette", "light_palette", "palette_for",
    "apply_theme", "apply_dark_palette", "is_dark",
    "WINDOW_COLOR", "BASE_COLOR", "TEXT_COLOR", "HIGHLIGHT_TEXT_COLOR",
    "ACCENT_COLOR", "LIGHT_WINDOW_COLOR", "LIGHT_BASE_COLOR",
    "LIGHT_ALTERNATE_COLOR", "LIGHT_TEXT_COLOR",
]

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


#: The light counterpart, role for role. Body text is a dark grey rather than
#: pure black for the same reason the dark palette's is not pure white.
LIGHT_WINDOW_COLOR = QColor(240, 240, 240)
LIGHT_BASE_COLOR = QColor(255, 255, 255)
LIGHT_ALTERNATE_COLOR = QColor(233, 233, 233)
LIGHT_TEXT_COLOR = QColor(30, 30, 30)


def light_palette():
    """Build the shared light palette (no application needed — handy to test)."""
    palette = QPalette()
    palette.setColor(QPalette.Window, LIGHT_WINDOW_COLOR)
    palette.setColor(QPalette.WindowText, LIGHT_TEXT_COLOR)
    palette.setColor(QPalette.Base, LIGHT_BASE_COLOR)
    palette.setColor(QPalette.AlternateBase, LIGHT_ALTERNATE_COLOR)
    palette.setColor(QPalette.ToolTipBase, LIGHT_BASE_COLOR)
    palette.setColor(QPalette.ToolTipText, LIGHT_TEXT_COLOR)
    palette.setColor(QPalette.Text, LIGHT_TEXT_COLOR)
    palette.setColor(QPalette.Button, LIGHT_WINDOW_COLOR)
    palette.setColor(QPalette.ButtonText, LIGHT_TEXT_COLOR)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, ACCENT_COLOR)
    palette.setColor(QPalette.Highlight, ACCENT_COLOR)
    palette.setColor(QPalette.HighlightedText, HIGHLIGHT_TEXT_COLOR)
    return palette


def palette_for(theme):
    """The palette for a resolved theme name ('light' / 'dark')."""
    return light_palette() if theme == THEME_LIGHT else dark_palette()


def apply_theme(app, setting=THEME_AUTO):
    """Dress ``app`` for `setting` ('auto' / 'light' / 'dark') and say which one
    it settled on, so a caller can tell whether the theme actually changed."""
    theme = resolve_theme(setting, detect_os_theme())
    app.setStyle("Fusion")
    app.setPalette(palette_for(theme))
    return theme


def is_dark(palette) -> bool:
    """Whether a palette reads as dark — for the code that has to pick INK to
    draw on it (the glyph-script previews), which cannot ask the theme name
    because a caller may have tweaked a role afterwards."""
    return palette.color(QPalette.Window).lightness() < 128


def apply_dark_palette(app):
    """Switch ``app`` to the Fusion style with the shared dark palette.

    Kept for the dialogs' ``main()`` dev launchers and anything that wants dark
    regardless of the desktop; the apps themselves go through `apply_theme`."""
    app.setStyle("Fusion")
    palette = dark_palette()
    app.setPalette(palette)
    return palette
