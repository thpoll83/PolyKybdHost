"""Tests for the host unicode input-method detection.

The WinCompose probe drives two things — which unicode mode the keyboard is put
into, and whether the tray offers "Install WinCompose…" — so it must be both
correct and unable to throw on the connect path.
"""
import subprocess
import unittest
from unittest import mock

from polyhost.input import unicode_input
from polyhost.input.unicode_input import InputMethod


class ProcessExistsTest(unittest.TestCase):
    def test_true_when_tasklist_lists_the_image(self):
        out = b'wincompose.exe   1234 Console   1   42,000 K'
        with mock.patch.object(subprocess, "check_output", return_value=out):
            self.assertTrue(unicode_input.process_exists("wincompose.exe"))

    def test_false_when_tasklist_reports_no_match(self):
        out = b'INFO: No tasks are running which match the specified criteria.'
        with mock.patch.object(subprocess, "check_output", return_value=out):
            self.assertFalse(unicode_input.process_exists("wincompose.exe"))

    def test_never_raises_when_tasklist_fails(self):
        """This runs on the post-connect path — an exception there would abort the
        whole connect flow over a cosmetic detection."""
        for exc in (FileNotFoundError("no TASKLIST"),
                    subprocess.CalledProcessError(1, "TASKLIST")):
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(subprocess, "check_output", side_effect=exc):
                    self.assertFalse(unicode_input.process_exists("wincompose.exe"))


class WinComposeRunningTest(unittest.TestCase):
    def test_false_off_windows_without_probing(self):
        with mock.patch.object(unicode_input.sys, "platform", "linux"), \
             mock.patch.object(unicode_input, "process_exists") as probe:
            self.assertFalse(unicode_input.wincompose_running())
        probe.assert_not_called()

    def test_true_on_windows_when_the_process_is_up(self):
        with mock.patch.object(unicode_input.sys, "platform", "win32"), \
             mock.patch.object(unicode_input, "process_exists", return_value=True):
            self.assertTrue(unicode_input.wincompose_running())


class GetInputMethodTest(unittest.TestCase):
    def test_windows_with_wincompose(self):
        with mock.patch.object(unicode_input.sys, "platform", "win32"), \
             mock.patch.object(unicode_input, "process_exists", return_value=True):
            self.assertIs(unicode_input.get_input_method(), InputMethod.WinCompose)

    def test_windows_without_wincompose_falls_back_to_native(self):
        with mock.patch.object(unicode_input.sys, "platform", "win32"), \
             mock.patch.object(unicode_input, "process_exists", return_value=False):
            self.assertIs(unicode_input.get_input_method(), InputMethod.Windows)

    def test_other_platforms(self):
        for platform, expected in (("linux", InputMethod.Linux),
                                   ("darwin", InputMethod.Mac),
                                   ("freebsd14", InputMethod.BSD),
                                   ("sunos5", InputMethod.Unknown)):
            with self.subTest(platform=platform):
                with mock.patch.object(unicode_input.sys, "platform", platform):
                    self.assertIs(unicode_input.get_input_method(), expected)


if __name__ == "__main__":
    unittest.main()
