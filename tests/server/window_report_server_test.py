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
        self.last_os = None
        self.last_url = None
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

    def _on_report(self, handle, name, title, os=None, url=None):
        self.reports.append((handle, name, title))
        self.last_os = os
        self.last_url = url
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
        self.assertIsNone(self.last_os)  # no os field -> callback gets None

    def test_report_forwards_the_url_over_the_socket(self):
        # End-to-end over a real AF_INET connection: the optional url param
        # survives the framing and reaches the injected callback.
        c = self._client()
        c.report(9, "chrome", "A board", url="https://miro.com/app/board/x")
        self.assertEqual(self.last_url, "https://miro.com/app/board/x")

    def test_a_report_without_a_url_arrives_as_none(self):
        # Back-compatibility with a forwarder that does not send one.
        c = self._client()
        c.report(9, "code", "main.py")
        self.assertIsNone(self.last_url)

    def test_report_forwards_os(self):
        c = self._client()
        c.report(1, "term", "bash", os=2)  # 2 == OsType.MACOS
        self.assertEqual(self.last_os, 2)

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


class WindowReportAiTest(unittest.TestCase):
    """The AI key across the network endpoint, in both directions.

    Push (`ai.state`) is a method; the press comes back on the REPLY to a window
    report, because the forwarder is a client with no listener of its own. Both are
    tested over a real socket so the framing is exercised, not just the dispatch.
    """

    def setUp(self):
        self.reports = []
        self.states = []
        self.state_result = (True, None)
        self.relay = {"raise_seq": 3, "active": True}
        self.relay_error = None
        self.authkey = b"winreport-testkey"
        self.port = _free_port()
        self.server = WindowReportServer(
            self._on_report, "0.8.31", _NullLog(),
            bind_host="127.0.0.1", port=self.port, authkey=self.authkey,
            on_ai_state=self._on_ai_state, ai_relay=self._on_relay)
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

    def _on_report(self, handle, name, title, os=None, url=None):
        self.reports.append((handle, name, title))
        return (True, {"reported": True})

    def _on_ai_state(self, value):
        self.states.append(value)
        return self.state_result

    def _on_relay(self):
        if self.relay_error is not None:
            raise self.relay_error
        return self.relay

    def _client(self):
        c = wrc.connect("127.0.0.1", self.port, authkey=self.authkey)
        self._clients.append(c)
        return c

    # ------------------------------------------------------------------
    def test_a_state_push_reaches_the_callback(self):
        c = self._client()
        c.ai_state("working")
        self.assertEqual(self.states, ["working"])

    def test_a_refused_state_surfaces_as_an_error(self):
        # This is how the remote end learns the far machine has the AI key off,
        # rather than being told the push succeeded.
        self.state_result = (False, "The AI key is off.")
        c = self._client()
        with self.assertRaises(wrc.WindowReportError) as ctx:
            c.ai_state("working")
        self.assertIn("AI key is off", str(ctx.exception))

    def test_the_press_relay_rides_the_window_report_reply(self):
        c = self._client()
        result = c.report(1, "code", "main.py")
        self.assertEqual(result.get("ai"), {"raise_seq": 3, "active": True})

    def test_a_relay_fault_does_not_fail_the_window_report(self):
        # Window tracking is the endpoint's actual job; an AI extra that raises
        # must not cost the forwarder its report (and a reconnect with it).
        self.relay_error = RuntimeError("boom")
        c = self._client()
        result = c.report(1, "code", "main.py")
        self.assertTrue(result.get("ok"))
        self.assertNotIn("ai", result)
        self.assertEqual(len(self.reports), 1)

    def test_still_nothing_else_is_served(self):
        # The surface grew by one named method, not into a registry.
        c = self._client()
        p.send_message(c._conn, p.make_request(99, p.M_BRIGHTNESS_SET, {"value": 50}))
        self.assertTrue(c._conn.poll(3.0))
        msg = p.recv_message(c._conn)
        self.assertEqual(msg["error"]["code"], p.ERR_METHOD_NOT_FOUND)


class WindowReportWithoutAiTest(unittest.TestCase):
    """With no AI callbacks injected the endpoint is EXACTLY what it was before.

    An embedder that wants only the window feed must not silently gain a method,
    and a reply must not grow a field older forwarders would have to skip.
    """

    def setUp(self):
        self.authkey = b"winreport-testkey"
        self.port = _free_port()
        self.server = WindowReportServer(
            lambda handle, name, title, os=None, url=None: (True, None),
            "0.8.31", _NullLog(),
            bind_host="127.0.0.1", port=self.port, authkey=self.authkey)
        self.server.start()

    def tearDown(self):
        try:
            self.server.stop()
        except Exception:
            pass

    def test_ai_state_is_method_not_found(self):
        c = wrc.connect("127.0.0.1", self.port, authkey=self.authkey)
        try:
            with self.assertRaises(wrc.WindowReportError):
                c.ai_state("working")
        finally:
            c.close()

    def test_the_reply_carries_no_ai_block(self):
        c = wrc.connect("127.0.0.1", self.port, authkey=self.authkey)
        try:
            self.assertEqual(c.report(1, "code", "main.py"), {"ok": True})
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
