"""The no-balloon fallback: who gets a tray balloon, and what carries a pending
update for everyone who does not.

Qt-free on purpose — the decision is a path test plus two string builders, and
a GUI harness would only make it slower to run. The WIRING (the menu row, the
tooltip's two writers, the once-per-version prompt) is pinned from the real
app in `host_client_test._smoke_default`.
"""
import unittest

from polyhost.gui.tray_notify import (balloons_are_delivered, updates_menu_title,
                                      updates_tooltip)


class TestBalloonsAreDelivered(unittest.TestCase):

    def test_windows_and_linux_deliver(self):
        for plat in ("win32", "linux", "freebsd13"):
            self.assertTrue(balloons_are_delivered(plat, "/usr/bin/python3"), plat)

    def test_macos_unbundled_does_not(self):
        """What we actually ship: the LaunchAgent runs a shell wrapper that runs
        `python -m polyhost`, so NSBundle.mainBundle is the Python framework and
        NSUserNotificationCenter drops the notification."""
        self.assertFalse(balloons_are_delivered(
            "darwin", "/Users/t/PolyKybdHost/.venv/bin/python"))

    def test_macos_inside_a_real_bundle_does(self):
        """The check is the rule NSBundle applies, not `platform == darwin`, so
        a properly bundled build needs no change here to start working."""
        self.assertTrue(balloons_are_delivered(
            "darwin", "/Applications/PolyHost.app/Contents/MacOS/PolyHost"))

    def test_the_bundle_shim_we_write_today_is_not_one(self):
        """`~/Applications/PolyHost.app/Contents/MacOS/PolyHost` is a /bin/sh
        shim that execs the wrapper — the PROCESS that ends up running is the
        venv python, and that is the path this is asked about."""
        self.assertFalse(balloons_are_delivered(
            "darwin", "/Users/t/Library/Application Support/PolyHost/.venv/bin/python"))

    def test_a_directory_merely_named_macos_is_not_a_bundle(self):
        self.assertFalse(balloons_are_delivered("darwin", "/opt/MacOS/python"))
        self.assertFalse(balloons_are_delivered("darwin", "/opt/x/Contents/MacOS/py"))

    def test_a_missing_executable_path_is_not_a_crash(self):
        self.assertFalse(balloons_are_delivered("darwin", None))


class TestUpdatesMarker(unittest.TestCase):

    def test_nothing_pending_leaves_the_row_alone(self):
        self.assertEqual(updates_menu_title(), "Updates")
        self.assertEqual(updates_menu_title(None, None), "Updates")
        self.assertEqual(updates_tooltip(), "")

    def test_the_row_names_the_version(self):
        """The row that used to be the only signal ("Update to vX available")
        is one submenu deeper, which is where a user who saw no balloon will
        not look — so the version has to be here, not a bare "1 update"."""
        self.assertEqual(updates_menu_title("1.1.6"),
                         "Updates — host v1.1.6 available")
        self.assertEqual(updates_menu_title(None, "2.4.0"),
                         "Updates — firmware v2.4.0 available")
        self.assertEqual(updates_menu_title("1.1.6", "2.4.0"),
                         "Updates — host v1.1.6, firmware v2.4.0 available")

    def test_the_tooltip_says_which_app_it_is_about(self):
        """Two tray icons can share a notification area (the forwarder's F
        mark), so the tooltip names PolyKybd where the menu row cannot."""
        self.assertEqual(updates_tooltip("1.1.6"),
                         "PolyKybd — host v1.1.6 available")
        self.assertEqual(updates_tooltip("1.1.6", "2.4.0"),
                         "PolyKybd — host v1.1.6, firmware v2.4.0 available")


if __name__ == "__main__":
    unittest.main()
