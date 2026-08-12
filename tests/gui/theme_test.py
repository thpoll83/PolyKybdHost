"""apply_dark_palette — the one dark Fusion theme shared by both QApplications.

PolyHost (tray) and PolyForwarder (remote reporter) each carried a
byte-identical 22-line ``set_style``. These pin the palette so the extracted
helper cannot drift from what both apps rendered before, and assert both
entry points route through it.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QPalette
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import theme
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


# The exact colours both apps rendered before the extraction. Kept as literals
# (not read back from the module) so a change to theme.py has to be deliberate.
BASE = (35, 35, 35)
WINDOW = (80, 80, 80)
TEXT = (200, 200, 200)
HIGHLIGHT_TEXT = (255, 255, 255)
ACCENT = (42, 130, 218)


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestApplyDarkPalette(unittest.TestCase):

    def setUp(self):
        self.palette = QPalette()
        self.style_names = []

        class _FakeApp:
            def __init__(self, outer):
                self._outer = outer

            def setStyle(self, name):
                self._outer.style_names.append(name)

            def setPalette(self, palette):
                self._outer.palette = palette

        self.app = _FakeApp(self)

    def _rgb(self, role):
        c = self.palette.color(role)
        return (c.red(), c.green(), c.blue())

    def test_sets_fusion_style(self):
        theme.apply_dark_palette(self.app)
        self.assertEqual(self.style_names, ["Fusion"])

    def test_palette_roles_match_the_previous_inline_theme(self):
        theme.apply_dark_palette(self.app)
        self.assertEqual(self._rgb(QPalette.Window), WINDOW)
        self.assertEqual(self._rgb(QPalette.WindowText), TEXT)
        self.assertEqual(self._rgb(QPalette.Base), BASE)
        self.assertEqual(self._rgb(QPalette.AlternateBase), WINDOW)
        self.assertEqual(self._rgb(QPalette.ToolTipBase), BASE)
        self.assertEqual(self._rgb(QPalette.ToolTipText), TEXT)
        self.assertEqual(self._rgb(QPalette.Text), TEXT)
        self.assertEqual(self._rgb(QPalette.Button), WINDOW)
        self.assertEqual(self._rgb(QPalette.ButtonText), TEXT)
        self.assertEqual(self._rgb(QPalette.Link), ACCENT)
        self.assertEqual(self._rgb(QPalette.Highlight), ACCENT)
        self.assertEqual(self._rgb(QPalette.HighlightedText), HIGHLIGHT_TEXT)

    def test_bright_text_is_red(self):
        theme.apply_dark_palette(self.app)
        self.assertEqual(self.palette.color(QPalette.BrightText),
                         QColor(Qt.red))

    def test_returns_the_palette_it_applied(self):
        returned = theme.apply_dark_palette(self.app)
        self.assertIs(returned, self.palette)


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestBothAppsUseTheSharedTheme(unittest.TestCase):
    """The point of the extraction: neither app may keep its own copy."""

    def _source(self, module_path):
        import pathlib
        import polyhost
        root = pathlib.Path(polyhost.__file__).parent
        return (root / module_path).read_text(encoding="utf-8")

    def test_host_does_not_build_its_own_palette(self):
        src = self._source("host.py")
        self.assertNotIn("QPalette.HighlightedText", src)
        self.assertIn("apply_dark_palette", src)

    def test_forwarder_does_not_build_its_own_palette(self):
        src = self._source("forwarder.py")
        self.assertNotIn("QPalette.HighlightedText", src)
        self.assertIn("apply_dark_palette", src)


if __name__ == "__main__":
    unittest.main()
