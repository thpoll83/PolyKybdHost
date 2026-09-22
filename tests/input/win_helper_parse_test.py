"""Regression test for WindowsInputHelper._parse_current_culture.

The get_current_language query once let PowerShell default-format the
InputLanguage object, which renders as a TABLE ("Culture  Handle  LayoutName"
header + data row). The parser matched the *header* line and returned the
literal "Culture   Handle LayoutName" as the current language, so no comparison
in set_language ever matched and OS language switching always failed
(field log 2026-06-19). The query now emits an explicit "Culture: <name>" line;
this pins the parse so the header can never be mistaken for the value again.

Importing win_helper pulls pynput (an X server), so this skips without a
display — like the other GUI-adjacent tests.
"""
import os
import sys
import ctypes
import unittest
from unittest.mock import MagicMock, patch

# Importing win_helper pulls pynput, which needs an X server only on Linux. Skip
# just that case — Windows/macOS (where DISPLAY is naturally absent) must keep
# coverage of the parser this test guards.
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    raise unittest.SkipTest("win_helper import needs pynput/X on Linux (no DISPLAY)")

from polyhost.input.win_helper import WindowsInputHelper

_parse = WindowsInputHelper._parse_current_culture
_parse_tags = WindowsInputHelper._parse_language_tags


class ParseCurrentCultureTest(unittest.TestCase):
    def test_value_line_is_parsed(self):
        self.assertEqual(_parse("Culture: en-US"), (True, "en-US"))

    def test_value_line_as_bytes(self):
        self.assertEqual(_parse(b"Culture: de-DE"), (True, "de-DE"))

    def test_tolerates_space_before_colon(self):
        # The legacy Start-Job list format ("Culture : en-US") must still parse.
        self.assertEqual(_parse("Culture : en-US"), (True, "en-US"))

    def test_table_header_is_not_mistaken_for_value(self):
        # The exact shape that broke switching: a header row (no colon) followed
        # by a data row. Must NOT return the header text.
        table = ("Culture   Handle LayoutName\n"
                 "-------   ------ ----------\n"
                 "en-US        123 US")
        ok, value = _parse(table)
        self.assertFalse(ok)
        self.assertNotIn("LayoutName", str(value) if ok else "")

    def test_value_line_among_other_output(self):
        out = b"\n\nCulture: en-GB\n"
        self.assertEqual(_parse(out), (True, "en-GB"))

    def test_no_culture_line_returns_false(self):
        ok, _ = _parse("nothing useful here")
        self.assertFalse(ok)


class ParseLanguageTagsTest(unittest.TestCase):
    def test_single_tag(self):
        self.assertEqual(_parse_tags("LanguageTag: en-US"), ["en-US"])

    def test_multiple_tags_as_bytes(self):
        out = b"LanguageTag: en-US\nLanguageTag: de-DE\n"
        self.assertEqual(_parse_tags(out), ["en-US", "de-DE"])

    def test_table_header_is_ignored(self):
        # Multi-language default formatting would put a value-less header first.
        table = ("LanguageTag Autonym  EnglishName\n"
                 "----------- -------  -----------\n"
                 "en-US       English  English")
        # The header has no colon -> not collected; the (mangled) data row also
        # lacks our 'LanguageTag:' shape, so nothing bogus is returned.
        self.assertEqual(_parse_tags(table), [])

    def test_space_joined_tags_on_one_line(self):
        # Some Windows/PowerShell builds don't enumerate the language list in the
        # pipeline, so 'LanguageTag: ' + $_.LanguageTag member-enumerates it and
        # joins every tag with the default $OFS (a space) onto a single line.
        # That must expand to one tag per language, not a single bogus tag
        # 'en-AT en-US de-AT' (field log 2026-06-20).
        self.assertEqual(
            _parse_tags("LanguageTag: en-AT en-US de-AT"),
            ["en-AT", "en-US", "de-AT"])

    def test_space_joined_tags_as_bytes(self):
        self.assertEqual(
            _parse_tags(b"LanguageTag: en-AT en-US de-AT\n"),
            ["en-AT", "en-US", "de-AT"])

    def test_empty_output(self):
        self.assertEqual(_parse_tags(""), [])



class ForegroundLayoutReadTest(unittest.TestCase):
    """Reading the current input language off the FOREGROUND WINDOW.

    ⚠️ The bug this replaces: `InputLanguage.CurrentInputLanguage` read in a
    fresh PowerShell process reports the per-THREAD default, not what the
    window in front is typing in. It returned the same `ko-KR` on eight
    consecutive reads while eight Win+Space presses were landing, so
    `set_language` never saw its target and called a working switch a
    failure (field, Windows 11, 2026-09-22)."""

    def _helper(self):
        from polyhost.input.win_helper import WindowsInputHelper
        return WindowsInputHelper()

    @staticmethod
    def _user32(hwnd=0x1234, thread_id=42, hkl=0x0C070C07):
        """A fake user32. 0x0C07 is de-AT; an HKL's low word is its LANGID."""
        u = MagicMock()
        u.GetForegroundWindow.return_value = hwnd
        u.GetWindowThreadProcessId.return_value = thread_id
        u.GetKeyboardLayout.return_value = hkl
        return u

    def test_the_foreground_windows_layout_is_what_is_reported(self):
        u = self._user32()
        with patch.object(ctypes, "windll", MagicMock(user32=u), create=True):
            ok, value = self._helper()._current_language_win32()
        self.assertTrue(ok)
        self.assertEqual(value, "de-AT")
        # …and it asked about the FOREGROUND thread, not the calling one.
        u.GetKeyboardLayout.assert_called_once_with(42)

    def test_a_korean_layout_round_trips_too(self):
        u = self._user32(hkl=0x04120412)
        with patch.object(ctypes, "windll", MagicMock(user32=u), create=True):
            ok, value = self._helper()._current_language_win32()
        self.assertTrue(ok)
        self.assertEqual(value, "ko-KR")

    def test_no_foreground_window_REFUSES_rather_than_asking_thread_zero(self):
        """⚠️ `GetKeyboardLayout(0)` means "the calling thread" — the exact
        question whose answer was useless. Falling back to it here would
        reintroduce the bug in a new place."""
        u = self._user32(hwnd=0)
        with patch.object(ctypes, "windll", MagicMock(user32=u), create=True):
            ok, reason = self._helper()._current_language_win32()
        self.assertFalse(ok)
        self.assertIn("no foreground window", reason)
        u.GetKeyboardLayout.assert_not_called()

    def test_an_unknown_langid_is_a_miss_not_a_wrong_answer(self):
        u = self._user32(hkl=0xFFFFFFFF)
        with patch.object(ctypes, "windll", MagicMock(user32=u), create=True):
            ok, reason = self._helper()._current_language_win32()
        self.assertFalse(ok)
        self.assertIn("LANGID", reason)

    def test_get_current_language_falls_back_to_powershell(self):
        """The fallback is what covers a process with no foreground window."""
        h = self._helper()
        u = self._user32(hwnd=0)
        with patch.object(ctypes, "windll", MagicMock(user32=u), create=True), \
             patch.object(type(h), "_current_language_powershell",
                          return_value=(True, "en-US")) as ps:
            ok, value = h.get_current_language()
        self.assertTrue(ok)
        self.assertEqual(value, "en-US")
        ps.assert_called_once()

    def test_win32_success_does_not_spawn_powershell(self):
        """The read happens inside the cycling loop, once per press — it must
        not be a process spawn."""
        h = self._helper()
        with patch.object(ctypes, "windll", MagicMock(user32=self._user32()), create=True), \
             patch.object(type(h), "_current_language_powershell") as ps:
            ok, value = h.get_current_language()
        self.assertTrue(ok)
        self.assertEqual(value, "de-AT")
        ps.assert_not_called()

if __name__ == "__main__":
    unittest.main()
