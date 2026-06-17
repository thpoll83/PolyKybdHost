"""WindowReportServer + WindowReportClient over a real AF_INET socket (H4d).

No Qt, no device — an injected callback stands in for PolyCore.report_window.
The whole point of this endpoint is the security boundary, so the tests assert
both the happy path (a report reaches the callback) AND that nothing but
`window.report` is reachable and that a wrong authkey can't connect at all.

Threads get short timeouts and the server is stopped in tearDown so a hung test
can't wedge the suite.
"""
import socket
import threading
import unittest

from multiprocessing.connection import AuthenticationError

from polyhost.server import protocol as p
from polyhost.server.window_report_server import WindowReportServer
from polyhost.server import window_report_client as wrc


class _NullLog:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def exception(self, *a, **k): pass


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class WindowReportServerTest(unittest.TestCase):
    def setUp(self):
        self.reports = []
        self.report_result = (True, {"reported": True})
        self.authkey = b"winreport-testkey"
        self.port = _free_port()
        self.server = WindowReportServer(
            self._on_report, "0.8.31", _NullLog(),
            bind_host="127.0.0.1", port=self.port, authkey=self.authkey)
        self.server.start()
        self._clients = []

    def tearDown(self):
        for c in self._clients:
            try:
                c.close()
            except Exception:
                pass
        try:
            self.server.stop()
        except Exception:
            pass

    def _on_report(self, handle, name, title):
        self.reports.append((handle, name, title))
        return self.report_result

    def _client(self, authkey=None):
        c = wrc.connect("127.0.0.1", self.port,
                        authkey=authkey if authkey is not None else self.authkey)
        self._clients.append(c)
        return c

    # ------------------------------------------------------------------
    def test_report_reaches_callback(self):
        c = self._client()
        result = c.report(1234, "code.exe", "main.py - VS Code")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.reports, [("1234", "code.exe", "main.py - VS Code")])

    def test_callback_failure_surfaces_as_error(self):
        self.report_result = (False, "no remote mapping active")
        c = self._client()
        with self.assertRaises(wrc.WindowReportError) as ctx:
            c.report(1, "x", "y")
        self.assertIn("no remote mapping", str(ctx.exception))

    def test_only_window_report_is_served(self):
        # Reach past the client helper and send an arbitrary other method — it
        # must be rejected. This is the security boundary: no device control.
        c = self._client()
        p.send_message(c._conn, p.make_request(99, p.M_BRIGHTNESS_SET, {"value": 50}))
        self.assertTrue(c._conn.poll(3.0))
        msg = p.recv_message(c._conn)
        self.assertIn("error", msg)
        self.assertEqual(msg["error"]["code"], p.ERR_METHOD_NOT_FOUND)
        self.assertEqual(self.reports, [])  # callback never ran

    def test_wrong_authkey_cannot_connect(self):
        # answer_challenge() raises AuthenticationError specifically on a key
        # mismatch — assert that exact type so an unrelated socket failure
        # can't make this pass.
        with self.assertRaises(AuthenticationError):
            self._client(authkey=b"the-wrong-key")
        self.assertEqual(self.reports, [])

    def test_multiple_reports_on_one_connection(self):
        c = self._client()
        c.report(1, "a.exe", "one")
        c.report(2, "b.exe", "two")
        self.assertEqual(self.reports,
                         [("1", "a.exe", "one"), ("2", "b.exe", "two")])

    def test_concurrent_clients(self):
        def worker(i, out):
            try:
                c = wrc.connect("127.0.0.1", self.port, authkey=self.authkey)
                c.report(i, f"app{i}", f"title{i}")
                c.close()
                out.append(True)
            except Exception:
                out.append(False)

        out = []
        threads = [threading.Thread(target=worker, args=(i, out)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(out, [True] * 5)
        self.assertEqual(len(self.reports), 5)


if __name__ == "__main__":
    unittest.main()
