"""Tests for the Qt-free logind sleep listener (headless-core plan H0c)."""

import logging
import subprocess
import sys
import types
import unittest
from unittest import mock

from polyhost.services import sleep_listener
from polyhost.services.sleep_listener import (
    install_sleep_listener,
    should_fire_on_sleep,
)


def _quiet_log():
    log = logging.getLogger("sleep_listener_test")
    log.addHandler(logging.NullHandler())
    return log


def _msg(body):
    """Minimal stand-in for a jeepney Message: only .body is read."""
    return types.SimpleNamespace(body=body)


class ShouldFireOnSleepTest(unittest.TestCase):
    def test_true_means_sleeping(self):
        self.assertTrue(should_fire_on_sleep(_msg((True,))))

    def test_false_means_resuming(self):
        self.assertFalse(should_fire_on_sleep(_msg((False,))))

    def test_empty_body_is_safe(self):
        self.assertFalse(should_fire_on_sleep(_msg(())))
        self.assertFalse(should_fire_on_sleep(_msg(None)))

    def test_dispatch_calls_callback_only_when_true(self):
        # Mirror the loop's dispatch decision against the pure function.
        cb = mock.Mock()
        for body, expected in [((True,), 1), ((False,), 0)]:
            cb.reset_mock()
            if should_fire_on_sleep(_msg(body)):
                cb()
            self.assertEqual(cb.call_count, expected)


class InstallSleepListenerPlatformTest(unittest.TestCase):
    def test_non_linux_returns_none(self):
        cb = mock.Mock()
        with mock.patch.object(sleep_listener.sys, "platform", "darwin"):
            result = install_sleep_listener(cb, _quiet_log())
        self.assertIsNone(result)
        cb.assert_not_called()

    def test_unavailable_system_bus_returns_none(self):
        # This container genuinely has no system D-Bus — exercise the real path.
        # Force the linux branch so the open_dbus_connection attempt runs and
        # fails gracefully to None rather than raising.
        cb = mock.Mock()
        with mock.patch.object(sleep_listener.sys, "platform", "linux"):
            result = install_sleep_listener(cb, _quiet_log())
        self.assertIsNone(result)
        cb.assert_not_called()


class NoQtImportTest(unittest.TestCase):
    def test_module_imports_without_pyqt5(self):
        # Import the module in a fresh subprocess with PyQt5 poisoned so any
        # accidental Qt import would raise. Proves the headless path is Qt-free.
        code = (
            "import sys\n"
            "sys.modules['PyQt5'] = None\n"
            "import polyhost.services.sleep_listener as m\n"
            "assert 'PyQt5' not in [k for k, v in sys.modules.items() if v is not None]\n"
            "print('OK')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
