import unittest
from unittest import mock

from polyhost.services import add_to_startup


class WinQuoteArgsTest(unittest.TestCase):
    def test_plain_args_unquoted(self):
        self.assertEqual(add_to_startup._win_quote_args(["--debug", "1"]), "--debug 1")

    def test_empty_list(self):
        self.assertEqual(add_to_startup._win_quote_args([]), "")

    def test_arg_with_space_gets_quoted(self):
        self.assertEqual(
            add_to_startup._win_quote_args(["--host-file", "C:\\Program Files\\h.txt"]),
            '--host-file "C:\\Program Files\\h.txt"',
        )

    def test_empty_string_arg_quoted(self):
        self.assertEqual(add_to_startup._win_quote_args([""]), '""')

    def test_embedded_quote_escaped(self):
        self.assertEqual(add_to_startup._win_quote_args(['a"b']), '"a\\"b"')


class WindowsAutostartFallbackTest(unittest.TestCase):
    """The logon-task path must fall back to a Startup-folder shortcut when
    task registration is refused (e.g. Task Scheduler locked down)."""

    def test_falls_back_to_shortcut_when_task_fails(self):
        with mock.patch.object(add_to_startup, "register_windows_logon_task", return_value=False), \
             mock.patch.object(add_to_startup, "create_windows_shortcut_powershell") as mk_lnk, \
             mock.patch.object(add_to_startup, "_windows_startup_lnk") as startup, \
             mock.patch.object(add_to_startup, "_windows_startmenu_lnk") as startmenu:
            startup.return_value.exists.return_value = False
            method = add_to_startup._install_windows_autostart("pythonw.exe", "-m polyhost", "C:\\repo", None)

        self.assertIn("fallback", method.lower())
        # Start-menu launcher + Startup-folder fallback shortcut both created.
        self.assertEqual(mk_lnk.call_count, 2)

    def test_uses_task_and_removes_stale_shortcut_on_success(self):
        with mock.patch.object(add_to_startup, "register_windows_logon_task", return_value=True), \
             mock.patch.object(add_to_startup, "create_windows_shortcut_powershell") as mk_lnk, \
             mock.patch.object(add_to_startup, "_windows_startup_lnk") as startup, \
             mock.patch.object(add_to_startup, "_windows_startmenu_lnk"):
            stale = startup.return_value
            stale.exists.return_value = True
            method = add_to_startup._install_windows_autostart("pythonw.exe", "-m polyhost", "C:\\repo", None)

        self.assertIn("scheduled task", method.lower())
        stale.unlink.assert_called_once()
        # Only the Start-menu launcher shortcut is created (no Startup fallback).
        self.assertEqual(mk_lnk.call_count, 1)


if __name__ == "__main__":
    unittest.main()
