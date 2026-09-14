"""Picking a shortcut backend, and what happens on a platform that has none.

The backends themselves cannot be exercised here — there is no accessibility bus
in this container and no Windows at all — so what is pinned is the SURROUNDING
contract: which platform gets which backend, that an unusable one is refused
rather than returned, and that nothing raises out of any of it.

⚠️ That last one matters more than it looks. `harvest()` runs on a background
thread for a cosmetic feature, and an escape there reaches
`threading.excepthook`, which this app routes into crash_log.txt — so a dead
accessibility bridge would put a spurious crash in every later problem report.
"""

import unittest
from unittest.mock import patch

from polyhost.services import shortcut_source as ss


class BackendChoiceTest(unittest.TestCase):

    def test_each_platform_gets_its_own_backend(self):
        for platform, expected in (("linux", "atspi"), ("win32", "uia"),
                                   ("freebsd13", "atspi")):
            with patch.object(ss.sys, "platform", platform):
                self.assertEqual(ss.backend_name(), expected)

    def test_macOS_has_NO_BACKEND_and_says_so(self):
        """Not built: the Accessibility API is a third unrelated interface, and
        it needs pyobjc plus a consent prompt neither other platform has. The
        fall-back simply never fires there, which is a gap and not a failure."""
        with patch.object(ss.sys, "platform", "darwin"):
            self.assertEqual(ss.backend_name(), "")
            self.assertIsNone(ss.pick())

    def test_an_UNAVAILABLE_backend_is_refused_rather_than_returned(self):
        """⚠️ The import succeeds on a machine with no accessibility bus at all,
        so the availability probe is part of the pick — otherwise "the bridge is
        not running" and "this app exposes nothing" would be indistinguishable,
        which is exactly the distinction the log line has to draw."""
        fake = type("B", (), {"available": staticmethod(lambda: False)})()
        with patch.dict("sys.modules",
                        {"polyhost.services.shortcut_source.atspi": fake}), \
             patch.object(ss.sys, "platform", "linux"):
            self.assertIsNone(ss.pick())

    def test_an_import_that_raises_is_no_backend_not_a_crash(self):
        with patch.object(ss.sys, "platform", "linux"), \
             patch("builtins.__import__", side_effect=ImportError("no gi")):
            self.assertIsNone(ss.pick())


class HarvestTest(unittest.TestCase):

    def test_no_backend_harvests_nothing(self):
        with patch.object(ss, "pick", return_value=None):
            self.assertEqual(ss.harvest("mousepad"), [])

    def test_a_backend_that_RAISES_harvests_nothing(self):
        boom = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app: (_ for _ in ()).throw(OSError("bus gone")))})()
        with patch.object(ss, "pick", return_value=boom):
            self.assertEqual(ss.harvest("mousepad"), [])

    def test_a_working_backend_is_passed_the_app_name(self):
        seen = []
        ok = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app: seen.append(app) or ["shortcut"])})()
        with patch.object(ss, "pick", return_value=ok):
            self.assertEqual(ss.harvest("mousepad"), ["shortcut"])
        self.assertEqual(seen, ["mousepad"])

    def test_this_container_really_has_none(self):
        """Not a tautology: it is the state every other test here assumes, and
        it is what makes the Phase-2 path unexercisable offline. If this ever
        starts failing, the harvest CAN be tested end to end and should be."""
        self.assertIsNone(ss.pick())


class ProbeParityTest(unittest.TestCase):
    """The probe is a CLI over this package, not a second implementation."""

    def test_the_accelerator_formats_agree_on_one_chord(self):
        """Both backends fold L/R modifiers onto one nibble, so the same chord
        has to arrive identically however it was spelled."""
        gtk = ss.parse_accel("<Control><Shift>s")
        win = ss.parse_win_accel("Ctrl+Shift+S")
        self.assertEqual((gtk.mods, gtk.hid), (win.mods, win.hid))

    def test_a_localized_windows_string_still_parses(self):
        de = ss.parse_win_accel("Strg+Umschalt+S")
        self.assertEqual((de.mods, de.hid), (0x03, 0x16))

    def test_an_unknown_modifier_is_REFUSED_not_read_as_a_key(self):
        """Reporting 'Wibble+S' as the single key "Wibble+S" would be worse than
        reporting nothing."""
        self.assertIsNone(ss.parse_win_accel("Wibble+S"))

    def test_the_system_menu_chord_is_NOT_an_app_shortcut(self):
        """`Alt+Space 'System'` is the window manager's, on every window.

        Field daemon_log.txt (2026-09-14): Calculator and Photos each reported it
        as their ONLY harvested shortcut, so the diagnostic claimed "1
        shortcut(s) harvested" for two apps that expose none.
        """
        accel = ss.parse_win_accel("Alt+Space")
        self.assertTrue(ss.is_window_manager_chord(accel.mods, accel.keysym))

    def test_close_window_is_the_same_case(self):
        accel = ss.parse_win_accel("Alt+F4")
        self.assertTrue(ss.is_window_manager_chord(accel.mods, accel.keysym))

    def test_an_ordinary_chord_on_the_same_KEY_survives(self):
        """The rule is the whole chord, not the key: Ctrl+Space is a real
        binding in plenty of apps and must not be swept up with Alt+Space."""
        for text in ("Ctrl+Space", "Shift+Space", "Ctrl+Alt+Space", "Ctrl+F4"):
            accel = ss.parse_win_accel(text)
            self.assertFalse(ss.is_window_manager_chord(accel.mods, accel.keysym),
                             f"{text} was dropped as a window-manager chord")

    def test_the_rule_keys_on_the_CHORD_and_never_on_the_LABEL(self):
        """"System" is localized -- German reports "Systemmenü" -- so a label
        test would drop these on an English desktop and nowhere else. The
        signature takes no label at all, which is what pins that."""
        import inspect
        params = inspect.signature(ss.is_window_manager_chord).parameters
        self.assertEqual(list(params), ["mods", "keysym"])
        de = ss.parse_win_accel("Alt+Leertaste")   # unknown key token, still Alt
        self.assertTrue(de is None or de.mods == ss.MOD_ALT)


if __name__ == "__main__":
    unittest.main()
