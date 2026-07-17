"""Unit tests for the per-desktop file-dialog policy (pure logic, no display).

Policy: native picker on Windows/macOS and on Linux KDE/Plasma (the modern
KFileWidget/portal dialog); Qt's own widget dialog on other Linux desktops
(GNOME, …) where "native" would be the foreign-looking GTK dialog.
"""
import unittest
from unittest.mock import patch

from polyhost.gui import file_dialogs as fd
from PyQt5.QtWidgets import QFileDialog


class FileDialogPolicyTest(unittest.TestCase):
    def _opts(self, environ, platform):
        with patch.object(fd, "sys") as m_sys, \
             patch.dict(fd.os.environ, environ, clear=True):
            m_sys.platform = platform
            return fd.use_native(), fd._dialog_options()

    def test_windows_native(self):
        native, opts = self._opts({}, "win32")
        self.assertTrue(native)
        self.assertNotEqual(opts, QFileDialog.DontUseNativeDialog)

    def test_macos_native(self):
        native, _ = self._opts({}, "darwin")
        self.assertTrue(native)

    def test_linux_kde_native(self):
        native, opts = self._opts({"XDG_CURRENT_DESKTOP": "KDE"}, "linux")
        self.assertTrue(native)
        self.assertNotEqual(opts, QFileDialog.DontUseNativeDialog)

    def test_linux_kde_plasma_colon_native(self):
        native, _ = self._opts({"XDG_CURRENT_DESKTOP": "KDE:plasma"}, "linux")
        self.assertTrue(native)

    def test_linux_kde_full_session_native(self):
        native, _ = self._opts({"KDE_FULL_SESSION": "true"}, "linux")
        self.assertTrue(native)

    def test_linux_gnome_forces_qt(self):
        native, opts = self._opts({"XDG_CURRENT_DESKTOP": "GNOME"}, "linux")
        self.assertFalse(native)
        self.assertEqual(opts, QFileDialog.DontUseNativeDialog)

    def test_linux_unset_forces_qt(self):
        native, opts = self._opts({}, "linux")
        self.assertFalse(native)
        self.assertEqual(opts, QFileDialog.DontUseNativeDialog)


class PortalPlatformThemeTest(unittest.TestCase):
    def _run(self, environ, platform, portal_available):
        with patch.object(fd, "sys") as m_sys, \
             patch.object(fd, "_portal_theme_available", return_value=portal_available), \
             patch.dict(fd.os.environ, environ, clear=True):
            m_sys.platform = platform
            set_it = fd.maybe_set_portal_platformtheme()
            return set_it, fd.os.environ.get("QT_QPA_PLATFORMTHEME")

    def test_kde_unset_sets_portal(self):
        set_it, theme = self._run({"XDG_CURRENT_DESKTOP": "KDE"}, "linux", True)
        self.assertTrue(set_it)
        self.assertEqual(theme, "xdgdesktopportal")

    def test_kde_already_set_is_noop(self):
        set_it, theme = self._run(
            {"XDG_CURRENT_DESKTOP": "KDE", "QT_QPA_PLATFORMTHEME": "kde"}, "linux", True)
        self.assertFalse(set_it)
        self.assertEqual(theme, "kde")   # user/session setting preserved

    def test_kde_without_portal_plugin_is_noop(self):
        set_it, theme = self._run({"XDG_CURRENT_DESKTOP": "KDE"}, "linux", False)
        self.assertFalse(set_it)
        self.assertIsNone(theme)

    def test_gnome_is_noop(self):
        set_it, theme = self._run({"XDG_CURRENT_DESKTOP": "GNOME"}, "linux", True)
        self.assertFalse(set_it)
        self.assertIsNone(theme)

    def test_windows_is_noop(self):
        set_it, theme = self._run({}, "win32", True)
        self.assertFalse(set_it)
        self.assertIsNone(theme)


class DefaultDirectoryTest(unittest.TestCase):
    def test_empty_uses_downloads(self):
        with patch.object(fd, "downloads_dir", return_value="/home/u/Downloads"):
            self.assertEqual(fd._default_directory(""), "/home/u/Downloads")

    def test_bare_filename_goes_into_downloads(self):
        with patch.object(fd, "downloads_dir", return_value="/home/u/Downloads"):
            self.assertEqual(fd._default_directory("pack.plyf"),
                             "/home/u/Downloads/pack.plyf")

    def test_path_with_dir_is_untouched(self):
        with patch.object(fd, "downloads_dir", return_value="/home/u/Downloads"):
            self.assertEqual(fd._default_directory("/tmp/x.bin"), "/tmp/x.bin")


if __name__ == "__main__":
    unittest.main()
