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
import unittest
from unittest import mock

from polyhost.handler import win_process


class FakeWindow:
    def __init__(self, handle=1234, title="Doc - Notepad", app_name="notepad.exe"):
        self._handle = handle
        self.title = title
        self._app_name = app_name
        self.get_app_name_calls = 0

    def getHandle(self):
        return self._handle

    def getAppName(self):
        self.get_app_name_calls += 1
        return self._app_name


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
