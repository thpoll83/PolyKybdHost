"""win_process.app_name_for — the WMI-free process-name lookup.

Pins the contract that replaced pywinctl's ``getAppName()`` at the two window
tick sites. The native half (``QueryFullProcessImageNameW``) can only run on
Windows, so what is testable anywhere is the DISPATCH: who gets called on which
platform, and what a failed lookup falls back to.

The fallback matters more than it looks. pywinctl's Windows ``getAppName()``
returns ``self.title`` when the PID isn't in its WMI list, and the callers
normalise the result (``raw.split(".")[0].lower()``), so returning anything
else here would quietly change which overlay mapping matches.
"""
import os
import unittest
from unittest import mock

from polyhost.handler import win_process


class FakeWindow:
    def __init__(self, handle=1234, title="Doc - Notepad", app_name="notepad.exe",
                 pid=4321):
        self._handle = handle
        self._pid = pid
        self.title = title
        self._app_name = app_name
        self.get_app_name_calls = 0

    def getHandle(self):
        return self._handle

    def getAppName(self):
        self.get_app_name_calls += 1
        return self._app_name

    def getPID(self):
        return self._pid


class TestAppNameFor(unittest.TestCase):

    def test_off_windows_delegates_to_pywinctl(self):
        # macOS returns a cached attribute and the Linux/KDE/GNOME reporters
        # already hold the name — nothing to avoid there.
        win = FakeWindow()
        with mock.patch("sys.platform", "linux"):
            self.assertEqual(win_process.app_name_for(win), "notepad.exe")
        self.assertEqual(win.get_app_name_calls, 1)

    def test_windows_uses_the_handle_lookup(self):
        win = FakeWindow(handle=4242)
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(win_process, "win32_process_name",
                               return_value="chrome.exe") as lookup:
            self.assertEqual(win_process.app_name_for(win), "chrome.exe")
        lookup.assert_called_once_with(4242)

    def test_windows_never_touches_getappname(self):
        # The whole point: no WMI walk, so pywinctl's implementation must not be
        # reached at all on the hot path.
        win = FakeWindow()
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(win_process, "win32_process_name",
                               return_value="chrome.exe"):
            win_process.app_name_for(win)
        self.assertEqual(win.get_app_name_calls, 0)

    def test_empty_lookup_falls_back_to_the_title(self):
        # Matches what pywinctl returns for an unresolvable PID.
        win = FakeWindow(title="Doc - Notepad")
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(win_process, "win32_process_name", return_value=""):
            self.assertEqual(win_process.app_name_for(win), "Doc - Notepad")

    def test_a_raising_lookup_is_swallowed(self):
        # The window can close between getActiveWindow() and here; a tick must
        # not die for it.
        win = FakeWindow(title="Doc - Notepad")
        with mock.patch("sys.platform", "win32"), \
             mock.patch.object(win_process, "win32_process_name",
                               side_effect=OSError("gone")):
            self.assertEqual(win_process.app_name_for(win), "Doc - Notepad")


class TestUninformativeProcessNames(unittest.TestCase):
    """MuseScore 4 and Audacity 4 rename their main thread to "main", and an
    AppImage whose AppRun is a symlink runs as "AppRun", so ``ps -o comm=``
    names the app by neither. The executable name is read instead, and only
    for those names."""

    def test_main_becomes_the_executable_name_on_linux(self):
        win = FakeWindow(app_name="main")
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink",
                           return_value="/tmp/.mount_x/bin/mscore4portable") as rl:
            self.assertEqual(win_process.app_name_for(win), "mscore4portable")
        rl.assert_called_once_with("/proc/4321/exe")

    def test_a_replaced_executable_drops_the_deleted_suffix(self):
        win = FakeWindow(app_name="main")
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink", return_value="/usr/bin/mscore (deleted)"):
            self.assertEqual(win_process.app_name_for(win), "mscore")

    def test_apprun_becomes_the_executable_name_on_linux(self):
        win = FakeWindow(app_name="AppRun")
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink",
                           return_value="/tmp/.mount_x/usr/bin/openscad"):
            self.assertEqual(win_process.app_name_for(win), "openscad")

    def test_an_unreadable_executable_keeps_main(self):
        win = FakeWindow(app_name="main")
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink", side_effect=PermissionError):
            self.assertEqual(win_process.app_name_for(win), "main")

    def test_no_pid_keeps_main(self):
        win = FakeWindow(app_name="main", pid=0)
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink") as rl:
            self.assertEqual(win_process.app_name_for(win), "main")
        rl.assert_not_called()

    def test_other_names_never_read_the_executable(self):
        win = FakeWindow(app_name="audacity")
        with mock.patch("sys.platform", "linux"), \
                mock.patch("os.readlink") as rl:
            self.assertEqual(win_process.app_name_for(win), "audacity")
        rl.assert_not_called()

    def test_macos_keeps_main(self):
        win = FakeWindow(app_name="main")
        with mock.patch("sys.platform", "darwin"), \
                mock.patch("os.readlink") as rl:
            self.assertEqual(win_process.app_name_for(win), "main")
        rl.assert_not_called()

    @unittest.skipUnless(os.path.exists("/proc/self/exe"), "needs /proc")
    def test_reads_the_real_proc_entry(self):
        win = FakeWindow(app_name="main", pid=os.getpid())
        expected = os.path.basename(os.readlink("/proc/self/exe"))
        with mock.patch("sys.platform", "linux"):
            self.assertEqual(win_process.app_name_for(win), expected)


class TestNativeBindings(unittest.TestCase):

    def test_open_process_returns_a_pointer_sized_handle(self):
        # ⚠️ ctypes defaults an unset restype to c_int, which truncates a 64-bit
        # HANDLE. _load_win32 sets it explicitly; this asserts it stays set.
        if win_process.sys.platform != "win32":
            self.skipTest("native bindings are Windows-only")
        _user32, kernel32, wintypes = win_process._load_win32()
        self.assertIs(kernel32.OpenProcess.restype, wintypes.HANDLE)


if __name__ == "__main__":
    unittest.main()
