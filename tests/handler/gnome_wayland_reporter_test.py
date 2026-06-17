"""GNOME/Wayland reporter output parsing (headless-core H4c, untested-on-hw).

The live D-Bus call to the Window Calls extension can only be validated on real
GNOME-Wayland hardware, but the gdbus-output parsing and the
missing-extension/no-focus degradation are pure and unit-tested here. The module
imports no pywinctl/Qt, so this runs headless.
"""
import subprocess
import unittest
from unittest import mock

from polyhost.handler import gnome_wayland_reporter as gw


def _proc(stdout="", returncode=0, stderr=""):
    return mock.Mock(stdout=stdout, returncode=returncode, stderr=stderr)


def _list_out(payload):
    # gdbus prints a single string return wrapped as  ('payload',)
    return f"('{payload}',)\n"


class TestGnomeWaylandReporter(unittest.TestCase):
    def setUp(self):
        gw._warned = False  # reset the once-only warning latch between tests
        # Reset the lazily-imported pywinctl fallback cache between tests.
        gw._pywinctl = None
        gw._pywinctl_tried = False

    def test_focused_window_with_title_in_list(self):
        payload = ('[{"id": 100, "wm_class": "Gnome-terminal", "focus": false, "title": "Term"},'
                   ' {"id": 200, "wm_class": "firefox", "focus": true, "title": "Mozilla Firefox"}]')
        with mock.patch.object(subprocess, "run", return_value=_proc(_list_out(payload))):
            win = gw.getActiveWindow()
        self.assertIsNotNone(win)
        self.assertEqual(win.getHandle(), 200)
        self.assertEqual(win.getAppName(), "firefox")
        self.assertEqual(win.title, "Mozilla Firefox")

    def test_title_fetched_on_demand_when_list_omits_it(self):
        # Base "Window Calls" List omits title -> a second GetTitle call fills it.
        list_payload = '[{"id": 7, "wm_class": "Code", "focus": true}]'
        outs = [_proc(_list_out(list_payload)), _proc("('main.py - VS Code',)\n")]
        with mock.patch.object(subprocess, "run", side_effect=outs):
            win = gw.getActiveWindow()
        self.assertEqual(win.getHandle(), 7)
        self.assertEqual(win.title, "main.py - VS Code")

    def test_no_focused_window_returns_none(self):
        payload = '[{"id": 1, "wm_class": "x", "focus": false}]'
        with mock.patch.object(subprocess, "run", return_value=_proc(_list_out(payload))):
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
        payload = '[{"id": 1, "wm_class": "x", "focus": false}]'
        with mock.patch.object(subprocess, "run", return_value=_proc(_list_out(payload))), \
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
