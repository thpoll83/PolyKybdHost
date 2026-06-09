import unittest
from pathlib import Path
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

    def test_returns_none_when_task_and_fallback_both_fail(self):
        # Task refused AND the fallback shortcut creation fails -> nothing is
        # actually installed, so the reported method must be "none".
        with mock.patch.object(add_to_startup, "register_windows_logon_task", return_value=False), \
             mock.patch.object(add_to_startup, "create_windows_shortcut_powershell", return_value=False), \
             mock.patch.object(add_to_startup, "_windows_startup_lnk") as startup, \
             mock.patch.object(add_to_startup, "_windows_startmenu_lnk"):
            startup.return_value.exists.return_value = False
            method = add_to_startup._install_windows_autostart("pythonw.exe", "-m polyhost", "C:\\repo", None)
        self.assertEqual(method, "none")

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


class HiddenInvocationTest(unittest.TestCase):
    """A .bat launcher must be wrapped in wscript + hidden .vbs (no console
    flash); a frozen exe is windowless and passed through unchanged."""

    def test_bat_wrapped_in_wscript(self):
        with mock.patch.object(add_to_startup, "create_windows_hidden_vbs",
                               return_value=r"C:\x\start_polyhost_hidden.vbs"), \
             mock.patch.object(add_to_startup, "_wscript_path",
                               return_value=r"C:\Windows\System32\wscript.exe"):
            exe, args = add_to_startup._windows_hidden_invocation(r"C:\x\start_polyhost.bat", "")
        self.assertTrue(exe.lower().endswith("wscript.exe"))
        self.assertEqual(args, '"C:\\x\\start_polyhost_hidden.vbs"')

    def test_exe_passed_through(self):
        result = add_to_startup._windows_hidden_invocation(r"C:\x\PolyHost.exe", "--debug 1")
        self.assertEqual(result, (r"C:\x\PolyHost.exe", "--debug 1"))

    def test_vbs_content_is_hidden_launch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            bat = Path(tmp) / "start_polyhost.bat"
            vbs = add_to_startup.create_windows_hidden_vbs(str(bat))
            content = Path(vbs).read_text()
        self.assertIn(", 0, False", content)  # window style 0 == hidden
        self.assertIn(str(bat), content)
        self.assertIn("Wscript.Shell", content)


class AutostartStatusTest(unittest.TestCase):
    """get_autostart_status reports the autostart mechanism(s) in place."""

    def _lnk(self, exists):
        lnk = mock.MagicMock()
        lnk.exists.return_value = exists
        return lnk

    def test_only_scheduled_task(self):
        with mock.patch.object(add_to_startup.platform, "system", return_value="Windows"), \
             mock.patch.object(add_to_startup, "windows_task_exists", return_value=True), \
             mock.patch.object(add_to_startup, "_windows_startup_lnk", return_value=self._lnk(False)):
            status = add_to_startup.get_autostart_status()
        self.assertIn("scheduled task", status.lower())
        self.assertNotIn("startup folder", status.lower())

    def test_task_and_startup_shortcut(self):
        with mock.patch.object(add_to_startup.platform, "system", return_value="Windows"), \
             mock.patch.object(add_to_startup, "windows_task_exists", return_value=True), \
             mock.patch.object(add_to_startup, "_windows_startup_lnk", return_value=self._lnk(True)):
            status = add_to_startup.get_autostart_status()
        self.assertIn("scheduled task", status.lower())
        self.assertIn("startup folder", status.lower())

    def test_none_when_nothing_registered(self):
        with mock.patch.object(add_to_startup.platform, "system", return_value="Windows"), \
             mock.patch.object(add_to_startup, "windows_task_exists", return_value=False), \
             mock.patch.object(add_to_startup, "_windows_startup_lnk", return_value=self._lnk(False)):
            self.assertEqual(add_to_startup.get_autostart_status(), "none")


class RemoveAutostartTest(unittest.TestCase):
    """remove_autostart tears down every artifact and is idempotent."""

    def _lnk(self, exists):
        lnk = mock.MagicMock()
        lnk.exists.return_value = exists
        return lnk

    def test_removes_task_and_both_shortcuts(self):
        startup, startmenu = self._lnk(True), self._lnk(True)
        with mock.patch.object(add_to_startup.platform, "system", return_value="Windows"), \
             mock.patch.object(add_to_startup, "unregister_windows_logon_task") as unreg, \
             mock.patch.object(add_to_startup, "_windows_startup_lnk", return_value=startup), \
             mock.patch.object(add_to_startup, "_windows_startmenu_lnk", return_value=startmenu):
            add_to_startup.remove_autostart()
        unreg.assert_called_once()
        startup.unlink.assert_called_once()
        startmenu.unlink.assert_called_once()

    def test_idempotent_when_nothing_exists(self):
        startup, startmenu = self._lnk(False), self._lnk(False)
        with mock.patch.object(add_to_startup.platform, "system", return_value="Windows"), \
             mock.patch.object(add_to_startup, "unregister_windows_logon_task") as unreg, \
             mock.patch.object(add_to_startup, "_windows_startup_lnk", return_value=startup), \
             mock.patch.object(add_to_startup, "_windows_startmenu_lnk", return_value=startmenu):
            add_to_startup.remove_autostart()  # must not raise
        unreg.assert_called_once()
        startup.unlink.assert_not_called()
        startmenu.unlink.assert_not_called()


if __name__ == "__main__":
    unittest.main()
