"""The taskbar and desktop are renamed away from File Explorer's keycaps.

The decision is tested with an injected class reader: `window_class()` is a
ctypes call that only runs on Windows.
"""

import sys
import unittest
from pathlib import Path

import yaml

from polyhost.handler.win_shell import (SHELL_APP, SHELL_CLASSES, shell_app_name,
                                        window_class)


def reader(cls):
    return lambda handle: cls


class ShellAppNameTest(unittest.TestCase):

    def test_the_taskbar_and_desktop_become_the_shell(self):
        for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"):
            with self.subTest(cls):
                self.assertEqual(SHELL_APP, shell_app_name("explorer", 1, reader(cls)))

    def test_a_file_explorer_window_stays_explorer(self):
        self.assertEqual("explorer",
                         shell_app_name("explorer", 1, reader("CabinetWClass")))

    def test_the_forwarders_raw_exe_name_is_recognised_too(self):
        """The handler strips `.exe`; the forwarder sends `app_name_for(win)`
        as it is, and the case is whatever Windows reports."""
        self.assertEqual(SHELL_APP,
                         shell_app_name("Explorer.EXE", 1, reader("Shell_TrayWnd")))

    def test_an_unreadable_class_leaves_the_name_alone(self):
        self.assertEqual("explorer", shell_app_name("explorer", 1, reader(None)))

    def test_no_other_app_pays_for_the_class_read(self):
        def boom(handle):
            raise AssertionError("class read for a non-explorer window")
        for name in ("chrome", "code", "explorerpatcher", "", None):
            with self.subTest(name):
                self.assertEqual(name, shell_app_name(name, 1, boom))

    def test_window_class_is_None_off_Windows(self):
        if sys.platform == "win32":
            self.skipTest("only meaningful off Windows")
        self.assertIsNone(window_class(1))

    def test_no_mapping_entry_carries_the_shell_name(self):
        """Nothing drawn is the point. An entry keyed on the shell name would
        bring keycaps back, which should be a deliberate change here too."""
        path = (Path(__file__).resolve().parents[2]
                / "polyhost" / "res" / "overlay-mapping.poly.yaml")
        mapping = yaml.safe_load(path.read_text(encoding="utf-8"))
        names = {n.strip() for key in mapping for n in str(key).split(",")}
        self.assertNotIn(SHELL_APP, names)
        self.assertIn("explorer", names)

    def test_the_class_set_is_exactly_the_shell(self):
        self.assertEqual({"Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                          "Progman", "WorkerW"}, set(SHELL_CLASSES))


if __name__ == "__main__":
    unittest.main()
