"""theme — the one Fusion theme shared by both QApplications, dark or light.

PolyHost (tray) and PolyForwarder (remote reporter) each carried a
byte-identical 22-line ``set_style``. These pin the palette so the extracted
helper cannot drift from what both apps rendered before, and assert both
entry points route through it.

The apps follow the OS now (`apply_theme`), so the tests also cover the light
palette and the `is_dark` predicate the glyph-script previews pick their ink
from — an always-True `is_dark` would make every preview near-white, which on a
light menu is an invisible icon.
"""
import unittest

# No QApplication and no Qt platform: every test here either drives a fake
# application object or reads source text, and QPalette/QColor construct fine
# without one. Only a MISSING PyQt5 may skip this module — importing `theme`
# is deliberately outside the guard so a real defect in theme.py surfaces as an
# error rather than silently turning the whole module into a skip.
try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QPalette
except ImportError as e:  # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None
    from polyhost.gui import theme


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
        self.assertIn("apply_theme", src)

    def test_forwarder_does_not_build_its_own_palette(self):
        src = self._source("forwarder.py")
        self.assertNotIn("QPalette.HighlightedText", src)
        self.assertIn("apply_theme", src)

    def test_neither_app_pins_itself_to_dark(self):
        """`apply_dark_palette` survives for the dialogs\' dev launchers; an app
        calling it would ignore the desktop, which is the bug this replaced."""
        for module in ("host.py", "forwarder.py"):
            self.assertNotIn("apply_dark_palette", self._source(module), module)


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestLightTheme(unittest.TestCase):
    """The light half, and the predicate that reads a palette back."""

    def test_the_light_palette_is_actually_light(self):
        palette = theme.light_palette()
        self.assertGreater(palette.color(QPalette.Window).lightness(), 200)
        self.assertLess(palette.color(QPalette.WindowText).lightness(), 60)

    def test_the_light_palette_sets_every_role_the_dark_one_does(self):
        # A role the light palette forgot falls back to Qt's default, which can
        # be the wrong side of the theme (near-white text on white). `isBrushSet`
        # is the question — several roles (the accent, BrightText) are the same
        # colour in both ON PURPOSE, so comparing values would not answer it.
        dark, light = theme.dark_palette(), theme.light_palette()
        for role in range(QPalette.NColorRoles):
            if dark.isBrushSet(QPalette.Active, role):
                self.assertTrue(light.isBrushSet(QPalette.Active, role),
                                f"the light palette leaves role {role} unset")

    def test_text_and_ground_contrast_in_both(self):
        for name, palette in (("dark", theme.dark_palette()),
                              ("light", theme.light_palette())):
            window = palette.color(QPalette.Window).lightness()
            text = palette.color(QPalette.WindowText).lightness()
            self.assertGreater(abs(window - text), 80, name)

    def test_is_dark_reads_the_palette_it_is_given(self):
        self.assertTrue(theme.is_dark(theme.dark_palette()))
        self.assertFalse(theme.is_dark(theme.light_palette()))

    def test_palette_for_picks_by_name(self):
        self.assertTrue(theme.is_dark(theme.palette_for(theme.THEME_DARK)))
        self.assertFalse(theme.is_dark(theme.palette_for(theme.THEME_LIGHT)))


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestApplyTheme(unittest.TestCase):
    """What both apps call at startup: the palette that reaches the application
    has to be the one the setting and the desktop resolve to — an `apply_theme`
    that always applied dark would pass every palette test above."""

    def setUp(self):
        from unittest import mock
        self.mock = mock
        self.applied = None
        self.styles = []

        class _FakeApp:
            def __init__(self, outer):
                self._outer = outer

            def setStyle(self, name):
                self._outer.styles.append(name)

            def setPalette(self, palette):
                self._outer.applied = palette

        self.app = _FakeApp(self)

    def _apply(self, setting, detected):
        with self.mock.patch.object(theme, "detect_os_theme", return_value=detected):
            return theme.apply_theme(self.app, setting)

    def test_auto_applies_what_the_desktop_says(self):
        for detected, dark in ((theme.THEME_LIGHT, False), (theme.THEME_DARK, True)):
            with self.subTest(detected=detected):
                self.assertEqual(self._apply(theme.THEME_AUTO, detected), detected)
                self.assertEqual(theme.is_dark(self.applied), dark)

    def test_an_explicit_setting_overrides_the_desktop(self):
        self.assertEqual(self._apply(theme.THEME_LIGHT, theme.THEME_DARK),
                         theme.THEME_LIGHT)
        self.assertFalse(theme.is_dark(self.applied))
        self.assertEqual(self._apply(theme.THEME_DARK, theme.THEME_LIGHT),
                         theme.THEME_DARK)
        self.assertTrue(theme.is_dark(self.applied))

    def test_a_silent_desktop_keeps_the_historical_look(self):
        self.assertEqual(self._apply(theme.THEME_AUTO, None), theme.THEME_DARK)
        self.assertTrue(theme.is_dark(self.applied))

    def test_the_style_is_fusion_in_both_themes(self):
        self._apply(theme.THEME_LIGHT, None)
        self._apply(theme.THEME_DARK, None)
        self.assertEqual(self.styles, ["Fusion", "Fusion"])

    def test_a_pinned_theme_does_not_ask_the_desktop(self):
        # Detection is a subprocess on macOS and Linux, and `_refresh_theme`
        # drops the cache and re-applies on EVERY tray-menu open — so asking
        # when the setting already decides is a subprocess per open for an
        # answer that is then discarded.
        with self.mock.patch.object(theme, "detect_os_theme") as detect:
            for setting in (theme.THEME_LIGHT, theme.THEME_DARK, " Dark "):
                theme.apply_theme(self.app, setting)
            detect.assert_not_called()

    def test_auto_and_a_nonsense_setting_still_ask(self):
        # The skip must be narrow: anything that does NOT decide on its own has
        # to fall through to the desktop, or "auto" silently stops following it.
        for setting in (theme.THEME_AUTO, None, "", "sepia"):
            with self.subTest(setting=setting):
                with self.mock.patch.object(theme, "detect_os_theme",
                                            return_value=theme.THEME_LIGHT) as detect:
                    self.assertEqual(theme.apply_theme(self.app, setting),
                                     theme.THEME_LIGHT)
                    detect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
