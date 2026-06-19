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

try:
    import jeepney  # noqa: F401
    _HAS_JEEPNEY = True
except ImportError:
    # jeepney is a linux-only runtime dep (requirements.txt) imported lazily by
    # sleep_listener; without it the system-bus test can't patch the connection.
    _HAS_JEEPNEY = False


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

    @unittest.skipUnless(_HAS_JEEPNEY, "jeepney not installed")
    def test_unavailable_system_bus_returns_none(self):
        # Force the linux branch AND make the bus connect raise, so the
        # graceful-None fallback is exercised deterministically regardless of
        # whether the host actually exposes a system D-Bus (CI runners may).
        cb = mock.Mock()
        with mock.patch.object(sleep_listener.sys, "platform", "linux"), \
             mock.patch("jeepney.io.blocking.open_dbus_connection",
                        side_effect=OSError("no system bus")):
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
