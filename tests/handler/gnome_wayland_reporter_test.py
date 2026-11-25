"""GNOME/Wayland reporter output parsing (headless-core H4c, untested-on-hw).

The live D-Bus call to the PolyKybd Window Reporter extension can only be
validated on real GNOME-Wayland hardware, but the gdbus-output parsing and the
missing-extension/no-focus degradation are pure and unit-tested here. The module
imports no pywinctl/Qt, so this runs headless.
"""
import subprocess
import unittest
from unittest import mock

from polyhost.handler import gnome_wayland_reporter as gw


def _proc(stdout="", returncode=0, stderr=""):
    return mock.Mock(stdout=stdout, returncode=returncode, stderr=stderr)


def _gdbus_out(payload):
    # gdbus prints a single string return wrapped as  ('payload',)
    return f"('{payload}',)\n"


class TestGnomeWaylandReporter(unittest.TestCase):
    def setUp(self):
        gw._warned = False  # reset the once-only warning latch between tests
        gw._warned_payload = False
        # Reset the lazily-imported pywinctl fallback cache between tests.
        gw._pywinctl = None
        gw._pywinctl_tried = False

    def test_focused_window(self):
        # GetFocusedWindow returns the focused window (incl. title) in one call.
        payload = ('{"id": 200, "wm_class": "firefox", '
                   '"wm_class_instance": "Navigator", "title": "Mozilla Firefox"}')
        with mock.patch.object(subprocess, "run", return_value=_proc(_gdbus_out(payload))):
            win = gw.getActiveWindow()
        self.assertIsNotNone(win)
        self.assertEqual(win.getHandle(), 200)
        self.assertEqual(win.getAppName(), "firefox")
        self.assertEqual(win.title, "Mozilla Firefox")

    def test_a_reply_that_is_not_a_json_object_is_unavailable_not_a_crash(self):
        # 2026-11-25: the extension answered with a JSON string while GNOME Shell reloaded
        # it, `GnomeWin("...")` raised AttributeError, and the forwarder died.
        for payload in ('"oops"', '[1, 2]', '42', 'true', '""'):
            gw._warned_payload = False
            with mock.patch.object(subprocess, "run",
                                   return_value=_proc(_gdbus_out(payload))), \
                    mock.patch.object(gw, "_pywinctl_fallback", return_value=None):
                self.assertIsNone(gw.getActiveWindow(), payload)   # fell back, no raise

    def test_a_non_object_reply_falls_back_to_pywinctl(self):
        pwc = mock.Mock()
        pwc.getActiveWindow.return_value = "x11-window"
        with mock.patch.object(subprocess, "run", return_value=_proc(_gdbus_out('"oops"'))), \
                mock.patch.object(gw, "_pywinctl_fallback", return_value=pwc):
            self.assertEqual(gw.getActiveWindow(), "x11-window")

    def test_a_non_object_reply_warns_once_with_the_type_and_not_the_content(self):
        with mock.patch.object(subprocess, "run",
                               return_value=_proc(_gdbus_out('"secret title"'))), \
                mock.patch.object(gw, "_pywinctl_fallback", return_value=None), \
                self.assertLogs("PolyHost", "WARNING") as logs:
            gw.getActiveWindow()
            gw.getActiveWindow()
        self.assertEqual(len(logs.records), 1)
        self.assertIn("JSON str", logs.output[0])
        self.assertNotIn("secret title", logs.output[0])

    def test_null_payload_returns_none(self):
        # Extension is up but nothing is focused -> the JSON literal 'null'.
        with mock.patch.object(subprocess, "run", return_value=_proc(_gdbus_out("null"))):
            self.assertIsNone(gw.getActiveWindow())

    def test_missing_extension_warns_and_falls_back(self):
        # Extension absent + no pywinctl fallback available -> None, warned once.
        with mock.patch.object(subprocess, "run", return_value=_proc("", returncode=1, stderr="no such name")), \
             mock.patch.object(gw, "_pywinctl_fallback", return_value=None):
            self.assertIsNone(gw.getActiveWindow())
        self.assertTrue(gw._warned)

    def test_gdbus_not_installed_falls_back(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError("gdbus")), \
             mock.patch.object(gw, "_pywinctl_fallback", return_value=None):
            self.assertIsNone(gw.getActiveWindow())
        self.assertTrue(gw._warned)

    def test_falls_back_to_pywinctl_when_extension_unavailable(self):
        # When the extension is missing, the X11/XWayland (pywinctl) fallback is
        # used so X11-backed apps stay tracked under a Wayland session.
        fake_win = object()
        fake_pwc = mock.Mock()
        fake_pwc.getActiveWindow.return_value = fake_win
        with mock.patch.object(subprocess, "run", return_value=_proc("", returncode=1)), \
             mock.patch.object(gw, "_pywinctl_fallback", return_value=fake_pwc):
            self.assertIs(gw.getActiveWindow(), fake_win)
        fake_pwc.getActiveWindow.assert_called_once()

    def test_no_focus_does_not_fall_back(self):
        # Extension is up and reports nothing focused -> None, WITHOUT consulting
        # the fallback (else a stale XWayland window would mask "nothing focused").
        with mock.patch.object(subprocess, "run", return_value=_proc(_gdbus_out("null"))), \
             mock.patch.object(gw, "_pywinctl_fallback") as fb:
            self.assertIsNone(gw.getActiveWindow())
        fb.assert_not_called()

    def test_fallback_import_guarded_against_sysexit(self):
        # pymonctl can sys.exit() with no X server; the fallback must swallow it
        # (return None) rather than killing the process.
        gw._pywinctl = None
        gw._pywinctl_tried = False
        with mock.patch("builtins.__import__", side_effect=SystemExit(1)):
            self.assertIsNone(gw._pywinctl_fallback())

    def test_eq_against_none_and_other(self):
        win = gw.GnomeWin({"id": 5, "wm_class": "a", "title": "t"})
        self.assertNotEqual(win, None)
        other = gw.GnomeWin({"id": 5, "wm_class": "b", "title": "u"})
        self.assertEqual(win, other)   # equality is by handle


if __name__ == "__main__":
    unittest.main()
