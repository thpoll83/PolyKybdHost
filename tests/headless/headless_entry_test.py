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
        # makes it return (and tear down) promptly. Guards against a slow-quit
        # regression — e.g. the remote-window listener's accept() timeout, which
        # `close()` waits out on the join (see remote_window.RECV_ACCEPT_TIMEOUT).
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

    def test_relay_is_spawned_detached(self):
        """The daemon runs with no console of its own, so a plain Popen makes
        Windows allocate a NEW console window for the relay — which the daemon it
        restarts then inherits and dies with when that window is closed."""
        import subprocess
        from unittest import mock
        from polyhost.headless import HeadlessHost
        from polyhost.services import updater
        host = HeadlessHost(_quiet())
        self.addCleanup(host.stop)
        host._restart_after_stop = True
        host._relay_path = "/tmp/relay.py"
        with mock.patch.object(updater.sys, "platform", "win32"), \
             mock.patch.object(subprocess, "Popen") as popen:
            host._restart_if_requested()
        popen.assert_called_once()
        flags = popen.call_args.kwargs["creationflags"]
        self.assertTrue(flags & updater.WIN_DETACHED_PROCESS)
        self.assertTrue(flags & updater.WIN_CREATE_NEW_PROCESS_GROUP)


class TestWindowReportWiring(unittest.TestCase):
    """The network window-report listener (H4d) is opt-in: HeadlessHost starts
    it only when window_report_network_enabled is set, fed by the core's
    report_window (never the full control registry)."""

    def setUp(self):
        self._addr = os.path.join(tempfile.mkdtemp(prefix="poly_wr_"), "p.sock")
        self._patches = [
            mock.patch.object(protocol, "endpoint_address", return_value=self._addr),
            mock.patch.object(protocol, "load_or_create_authkey", return_value=b"k"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_disabled_by_default(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        self.addCleanup(host.stop)
        with mock.patch.object(host.core, "settings_get", return_value=False):
            host._maybe_start_window_report_server()
        self.assertIsNone(host._winreport_server)

    def test_started_when_enabled_with_report_callback(self):
        import polyhost.server.window_report_server as wrs
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        self.addCleanup(host.stop)
        with mock.patch.object(host.core, "settings_get", return_value=True), \
             mock.patch.object(wrs, "WindowReportServer") as MockSrv:
            host._maybe_start_window_report_server()
        MockSrv.assert_called_once()
        # The server is fed the core's report_window — the only seam it can reach.
        self.assertEqual(MockSrv.call_args.args[0], host.core.report_window)
        MockSrv.return_value.start.assert_called_once()
        # And it is torn down with the host.
        host.stop()
        MockSrv.return_value.stop.assert_called_once()


class TestHeadlessStartOrder(unittest.TestCase):
    """The control endpoint is claimed and bound before the device stack runs."""

    def setUp(self):
        self._addr = os.path.join(tempfile.mkdtemp(prefix="poly_ord_"), "p.sock")
        self._key = b"orderkey"
        self._patches = [
            mock.patch.object(protocol, "endpoint_address", return_value=self._addr),
            mock.patch.object(protocol, "load_or_create_authkey", return_value=self._key),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_control_server_binds_before_the_hid_worker_starts(self):
        from polyhost.headless import HeadlessHost

        host = HeadlessHost(_quiet())
        order = []
        real_cs_start = host.control_server.start
        real_worker_start = host.core.worker.start

        def cs_start():
            order.append("control_server")
            real_cs_start()

        def worker_start():
            order.append("worker")
            real_worker_start()

        # The fixture binds the methods, so patch.object on the classes would
        # not reach them — override on the instances.
        host.control_server.start = cs_start
        host.core.worker.start = worker_start
        host.start()
        try:
            self.assertEqual(order[:2], ["control_server", "worker"])
        finally:
            host.stop()


class TestHeadlessStandsDownWhenTheEndpointIsTaken(unittest.TestCase):
    """The loser of a daemon race must stand down BEFORE it touches the device.

    `PolyCore.__init__` opens the keyboard, so the old ordering — construct the
    host, then fail to bind — meant the losing daemon took the device away from
    the winner on its way out. On macOS the HID open is exclusive, so the winner
    then got `kIOReturnExclusiveAccess` on every reconnect and the board stayed
    unreachable until the user replugged it 50 minutes later (field,
    2026-09-19). It also crashed: `OSError: [Errno 48] Address already in use`,
    unhandled, in crash_log.txt.
    """

    def test_run_headless_never_builds_the_host_when_the_lock_is_held(self):
        from polyhost.headless import run_headless
        from polyhost.server.instance import claim_instance

        class _ExplodingHost:
            def __init__(self, *a, **kw):
                raise AssertionError(
                    "HeadlessHost was constructed despite the endpoint being taken "
                    "— PolyCore.__init__ would have opened the keyboard here")

        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()
        keeb = logging.getLogger("PolyKybdConsole")
        saved_keeb = keeb.handlers[:]
        keeb.handlers.clear()

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="poly_busy_")
        addr = os.path.join(tmp, "p.sock")
        try:
            os.chdir(tmp)
            with mock.patch.object(protocol, "endpoint_address", return_value=addr), \
                 mock.patch.object(protocol, "load_or_create_authkey", return_value=b"k"):
                claim = claim_instance()
                try:
                    with mock.patch("polyhost.headless.HeadlessHost", _ExplodingHost):
                        # Returns instead of raising: standing down is a normal
                        # outcome, not a crash.
                        run_headless(logging.INFO)
                finally:
                    claim.release()
        finally:
            os.chdir(cwd)
            for lg, saved in ((root, saved_handlers), (keeb, saved_keeb)):
                for h in lg.handlers:
                    try:
                        h.close()
                    except Exception:
                        # Best-effort: the temp dir these handlers write into
                        # is removed just below, so a handler that refuses to
                        # close changes nothing — and must not replace the
                        # test's own result with a teardown error.
                        pass
                lg.handlers[:] = saved
            root.setLevel(saved_level)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_passed_in_claim_is_not_released_by_run_headless(self):
        """main_app takes the claim before any device code runs and owns it —
        run_headless must not drop someone else's lock on the way out."""
        from polyhost.headless import run_headless
        from polyhost.server.instance import claim_instance, EndpointBusy

        class _StubHost:
            def __init__(self, *a, **kw):
                pass

            def run(self):
                pass

        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()
        keeb = logging.getLogger("PolyKybdConsole")
        saved_keeb = keeb.handlers[:]
        keeb.handlers.clear()

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="poly_claim_")
        addr = os.path.join(tmp, "p.sock")
        try:
            os.chdir(tmp)
            with mock.patch.object(protocol, "endpoint_address", return_value=addr), \
                 mock.patch.object(protocol, "load_or_create_authkey", return_value=b"k"):
                claim = claim_instance()
                try:
                    with mock.patch("polyhost.headless.HeadlessHost", _StubHost):
                        run_headless(logging.INFO, claim=claim)
                    # Still held: a second claimant is still refused.
                    with self.assertRaises(EndpointBusy):
                        claim_instance()
                finally:
                    claim.release()
        finally:
            os.chdir(cwd)
            for lg, saved in ((root, saved_handlers), (keeb, saved_keeb)):
                for h in lg.handlers:
                    try:
                        h.close()
                    except Exception:
                        # Best-effort: the temp dir these handlers write into
                        # is removed just below, so a handler that refuses to
                        # close changes nothing — and must not replace the
                        # test's own result with a teardown error.
                        pass
                lg.handlers[:] = saved
            root.setLevel(saved_level)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestRunHeadlessLogging(unittest.TestCase):
    """run_headless must write a rotating daemon_log.txt — a GUI-spawned daemon
    runs detached with stdio at DEVNULL, so without the file its logs vanish."""

    def test_run_headless_creates_daemon_log_file(self):
        from polyhost.headless import run_headless

        # Isolate the root logger so basicConfig actually attaches our handlers
        # regardless of what earlier tests configured (and restore after).
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()
        # run_headless also configures the PolyKybdConsole logger — snapshot it
        # so we don't leak a handler pointing at a deleted temp file.
        keeb = logging.getLogger("PolyKybdConsole")
        saved_keeb = keeb.handlers[:]
        keeb.handlers.clear()

        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="poly_dlog_")

        class _StubHost:
            def __init__(self, log, ignore_version=False, allow_key_injection=False):
                log.info("stub daemon up")

            def run(self):
                pass  # don't block

        try:
            os.chdir(tmp)
            # run_headless claims the instance lock; point it at a private
            # endpoint so the test never touches the real config dir.
            addr = os.path.join(tmp, "p.sock")
            with mock.patch("polyhost.headless.HeadlessHost", _StubHost), \
                 mock.patch.object(protocol, "endpoint_address", return_value=addr), \
                 mock.patch.object(protocol, "load_or_create_authkey", return_value=b"k"):
                run_headless(logging.INFO)
            # Flush handlers so the file content is on disk before we read it.
            for h in root.handlers:
                h.flush()
            log_path = os.path.join(tmp, "daemon_log.txt")
            self.assertTrue(os.path.exists(log_path), "daemon_log.txt not created")
            with open(log_path, encoding="utf-8") as f:
                self.assertIn("running headless", f.read())
            # The keyboard-console log file is set up too (mirrors the GUI).
            self.assertTrue(os.path.exists(os.path.join(tmp, "polykybd_console.txt")))
        finally:
            os.chdir(cwd)
            for lg, saved in ((root, saved_handlers), (keeb, saved_keeb)):
                for h in lg.handlers:
                    try:
                        h.close()
                    except Exception:
                        # Best-effort: the temp dir these handlers write into
                        # is removed just below, so a handler that refuses to
                        # close changes nothing — and must not replace the
                        # test's own result with a teardown error.
                        pass
                lg.handlers[:] = saved
            root.setLevel(saved_level)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_console_event_routed_to_keeb_log(self):
        from polyhost.headless import HeadlessHost
        host = HeadlessHost(_quiet())
        self.addCleanup(host.stop)
        seen = []
        cap = logging.Handler()
        cap.emit = lambda r: seen.append(r.getMessage())
        host.keeb_log.addHandler(cap)
        try:
            host._on_console_event("console", ("", "Stop idle."))
            self.assertIn("Stop idle.", seen)
            seen.clear()
            host._on_console_event("status_changed", {"connected": True})
            self.assertEqual(seen, [])   # non-console events ignored
        finally:
            host.keeb_log.removeHandler(cap)


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
