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


if __name__ == "__main__":
    unittest.main()
