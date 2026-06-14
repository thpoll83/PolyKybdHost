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
        self.addCleanup(host.stop)   # shut the core down so its listeners don't leak
        host._on_update_event("update_finished_ok", {"version": "0.9.0"})
        self.assertTrue(host._restart_after_stop)
        self.assertTrue(host._stop.is_set())
        self.assertIsNone(host._relay_path)

    def test_relay_needed_flags_restart_with_path(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        self.addCleanup(host.stop)   # shut the core down so its listeners don't leak
        host._on_update_event("update_relay_needed", {"relay_path": "/tmp/relay.py"})
        self.assertTrue(host._restart_after_stop)
        self.assertEqual(host._relay_path, "/tmp/relay.py")


class TestRunHeadlessLogging(unittest.TestCase):
    """run_headless must write a rotating daemon_log.txt — a GUI-spawned daemon
    runs detached with stdio at DEVNULL, so without the file its logs vanish."""

    def test_run_headless_creates_daemon_log_file(self):
        import polyhost.headless as headless

        # Isolate the root logger so basicConfig actually attaches our handlers
        # regardless of what earlier tests configured (and restore after).
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="poly_dlog_")

        class _StubHost:
            def __init__(self, log, ignore_version=False):
                log.info("stub daemon up")

            def run(self):
                pass  # don't block

        try:
            os.chdir(tmp)
            with mock.patch.object(headless, "HeadlessHost", _StubHost):
                headless.run_headless(logging.INFO)
            # Flush handlers so the file content is on disk before we read it.
            for h in root.handlers:
                h.flush()
            log_path = os.path.join(tmp, "daemon_log.txt")
            self.assertTrue(os.path.exists(log_path), "daemon_log.txt not created")
            with open(log_path, encoding="utf-8") as f:
                self.assertIn("running headless", f.read())
        finally:
            os.chdir(cwd)
            for h in root.handlers:
                try:
                    h.close()
                except Exception:
                    pass
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


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
