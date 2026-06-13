"""Headless mode (M2): HeadlessHost runs the core + control socket with no
Qt, and polyctl drives it end-to-end. Plus a subprocess guard that
`--headless` (via main_app) imports zero Qt.
"""
import io
import logging
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout

from polyhost.server import protocol
from polyhost.server.instance import probe_existing, LIVE, STALE


def _quiet():
    lg = logging.getLogger("test.headless")
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


class TestHeadlessHost(unittest.TestCase):
    """Build a HeadlessHost on a private endpoint and drive it with polyctl."""

    def setUp(self):
        # Private control endpoint so the test never touches a real socket.
        self._addr = os.path.join(tempfile.mkdtemp(prefix="poly_hl_"), "p.sock")
        self._key = b"headlesskey"
        self._patches = [
            mock.patch.object(protocol, "endpoint_address", return_value=self._addr),
            mock.patch.object(protocol, "load_or_create_authkey", return_value=self._key),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_lifecycle_and_polyctl_status(self):
        from polyhost.headless import HeadlessHost
        from polyhost.cli import polyctl

        host = HeadlessHost(_quiet(), ignore_version=False)
        host.start()
        try:
            self.assertEqual(probe_existing(self._addr, self._key), LIVE)
            # polyctl talks the real socket end-to-end (no device attached).
            out = io.StringIO()
            with redirect_stdout(out):
                rc = polyctl.main(["status"])
            self.assertEqual(rc, 0)
            self.assertIn("connected:", out.getvalue())
        finally:
            host.stop()
        self.assertEqual(probe_existing(self._addr, self._key), STALE)

    def test_request_stop_via_shutdown_callback(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        host.start()
        try:
            host.request_stop()
            self.assertTrue(host._stop.is_set())
        finally:
            host.stop()

    def test_run_loop_exits_on_request_stop(self):
        # Drive the real run() wait-loop on a thread and confirm request_stop
        # makes it return (and tear down) promptly.
        import threading
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        t = threading.Thread(target=host.run, daemon=True)
        t.start()
        try:
            import time
            time.sleep(0.2)            # let run() enter its wait-loop
            self.assertTrue(t.is_alive())
            host.request_stop()
            t.join(timeout=5)
            self.assertFalse(t.is_alive())   # run() returned
            self.assertTrue(host._stopped)   # stop() ran in finally
        finally:
            host.stop()  # idempotent — safe even though run() already stopped

    def test_stop_is_idempotent(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        host.start()
        host.stop()
        host.stop()  # second call must be a no-op, not raise
        self.assertTrue(host._stopped)

    def test_update_finished_flags_restart_and_requests_stop(self):
        # A core-driven self-update must make the headless host re-exec: the
        # event flags the restart and trips the stop so run()'s finally runs it.
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        host._on_update_event("update_finished_ok", {"version": "0.9.0"})
        self.assertTrue(host._restart_after_stop)
        self.assertTrue(host._stop.is_set())
        self.assertIsNone(host._relay_path)

    def test_relay_needed_flags_restart_with_path(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        host._on_update_event("update_relay_needed", {"relay_path": "/tmp/relay.py"})
        self.assertTrue(host._restart_after_stop)
        self.assertEqual(host._relay_path, "/tmp/relay.py")


class TestHeadlessImportsNoQt(unittest.TestCase):
    def test_headless_entry_imports_without_qt(self):
        code = (
            "import sys\n"
            "class P:\n"
            " def find_module(self,n,p=None):\n"
            "  return self if (n=='PyQt5' or n.startswith('PyQt5.')) else None\n"
            " def load_module(self,n):\n"
            "  raise ImportError('Qt in headless: '+n)\n"
            "sys.meta_path.insert(0,P())\n"
            "import polyhost.main_app, polyhost.headless\n"
            "print('NOQT_OK')\n"
        )
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOQT_OK", proc.stdout)


if __name__ == "__main__":
    import unittest.mock  # noqa
    unittest.main()
