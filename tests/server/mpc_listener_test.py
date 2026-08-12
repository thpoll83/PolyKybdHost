"""MpcListenerServer — the accept/connection/teardown half both mpc servers share.

``ControlServer`` (local UDS / named pipe, full PolyCore registry) and
``WindowReportServer`` (opt-in AF_INET, one method) had two hand-written copies
of the same listener: bind, an accept loop, a per-connection reader thread, the
opening ``hello`` frame, the JSON-RPC error mapping, and a ``stop()`` that has
to wake a thread parked in a blocking ``accept()``.

That last one is why this base exists rather than being a tidiness exercise.
``WindowReportServer.stop()`` carried the bounded-raw-connect wake *and a
paragraph explaining it*, while ``ControlServer.stop()`` used an authed
``mpc.Client`` and deadlocked the whole test suite intermittently for ~3
sessions (CLAUDE.md: "the deadlock was diagnosed from a stack trace across
three sessions while a sibling module in the same package carried the remedy").
One implementation is the fix for the class, not just that instance.

These tests drive the base directly over a real socket, so they pin the
behaviour independently of either subclass.
"""
import os
import socket
import sys
import tempfile
import threading
import time
import unittest

from multiprocessing.connection import AuthenticationError, Client

from polyhost.server import protocol as p
from polyhost.server.mpc_listener import MpcListenerServer


class _NullLog:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
    def exception(self, *a, **k): pass


class _CountingLog(_NullLog):
    """Counts warning/exception lines so a retry loop's visibility is testable."""

    def __init__(self):
        self.count = 0

    def warning(self, *a, **k):
        self.count += 1

    def exception(self, *a, **k):
        self.count += 1


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class EchoServer(MpcListenerServer):
    """Minimal concrete server: one method, plus hooks the tests observe."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.dispatched = []

    def dispatch(self, conn, req_id, method, params):
        self.dispatched.append((method, params))
        if method == "echo":
            return p.make_response(req_id, {"said": params["text"]})
        if method == "boom":
            raise RuntimeError("handler exploded")
        if method == "needs_param":
            return p.make_response(req_id, {"v": params["missing"]})
        return p.make_error(req_id, p.ERR_METHOD_NOT_FOUND, f"unknown '{method}'")


class _InetServerCase(unittest.TestCase):
    """Runs the base over AF_INET so it works identically on POSIX and Windows."""

    AUTHKEY = b"test-authkey"

    def setUp(self):
        self.port = _free_port()
        self.server = EchoServer(
            address=("127.0.0.1", self.port), family="AF_INET",
            authkey=self.AUTHKEY, host_version="1.2.3", log=_NullLog(),
            thread_prefix="test")
        self.server.start()
        self.addCleanup(self.server.stop)

    def _client(self, authkey=None):
        conn = Client(("127.0.0.1", self.port),
                      authkey=self.AUTHKEY if authkey is None else authkey)
        self.addCleanup(lambda: self._quiet_close(conn))
        return conn

    @staticmethod
    def _quiet_close(conn):
        try:
            conn.close()
        except Exception:
            pass

    def _handshake(self, conn):
        msg = p.recv_message(conn)
        self.assertEqual(msg.get("method"), p.HELLO)
        return msg

    def _call(self, conn, method, params=None, req_id=1):
        p.send_message(conn, p.make_request(req_id, method, params))
        return p.recv_message(conn)


class TestHandshakeAndAuth(_InetServerCase):

    def test_server_pushes_hello_first(self):
        conn = self._client()
        msg = self._handshake(conn)
        self.assertEqual(msg["params"]["host_version"], "1.2.3")

    def test_wrong_authkey_cannot_connect(self):
        with self.assertRaises(AuthenticationError):
            Client(("127.0.0.1", self.port), authkey=b"wrong")

    def test_server_keeps_serving_after_a_rejected_client(self):
        """A bad key must not take the accept loop down with it."""
        with self.assertRaises(AuthenticationError):
            Client(("127.0.0.1", self.port), authkey=b"wrong")
        conn = self._client()
        self._handshake(conn)
        self.assertEqual(self._call(conn, "echo", {"text": "hi"})["result"],
                         {"said": "hi"})


class TestDispatch(_InetServerCase):

    def test_request_reaches_dispatch_and_the_result_comes_back(self):
        conn = self._client()
        self._handshake(conn)
        reply = self._call(conn, "echo", {"text": "hello"})
        self.assertEqual(reply["id"], 1)
        self.assertEqual(reply["result"], {"said": "hello"})
        self.assertEqual(self.server.dispatched, [("echo", {"text": "hello"})])

    def test_missing_params_default_to_an_empty_dict(self):
        conn = self._client()
        self._handshake(conn)
        p.send_message(conn, {"id": 5, "method": "echo"})
        reply = p.recv_message(conn)
        self.assertEqual(self.server.dispatched, [("echo", {})])
        self.assertEqual(reply["error"]["code"], p.ERR_INVALID_PARAMS)

    def test_notifications_without_an_id_are_ignored(self):
        """Nothing client->server is expected as a notification; it must not
        produce a reply (which would desync every subsequent response id)."""
        conn = self._client()
        self._handshake(conn)
        p.send_message(conn, p.make_notification("echo", {"text": "x"}))
        reply = self._call(conn, "echo", {"text": "after"}, req_id=9)
        self.assertEqual(reply["id"], 9)
        self.assertEqual(self.server.dispatched, [("echo", {"text": "after"})])

    def test_a_bad_param_becomes_ERR_INVALID_PARAMS(self):
        conn = self._client()
        self._handshake(conn)
        reply = self._call(conn, "needs_param", {})
        self.assertEqual(reply["error"]["code"], p.ERR_INVALID_PARAMS)
        self.assertIn("KeyError", reply["error"]["message"])

    def test_an_exploding_handler_becomes_ERR_INTERNAL_and_keeps_the_conn(self):
        conn = self._client()
        self._handshake(conn)
        reply = self._call(conn, "boom")
        self.assertEqual(reply["error"]["code"], p.ERR_INTERNAL)
        self.assertIn("RuntimeError", reply["error"]["message"])
        # The connection survives — one bad call is not a disconnect.
        self.assertEqual(self._call(conn, "echo", {"text": "ok"}, req_id=2)["result"],
                         {"said": "ok"})

    def test_unknown_method_is_the_subclass_decision(self):
        conn = self._client()
        self._handshake(conn)
        reply = self._call(conn, "nope")
        self.assertEqual(reply["error"]["code"], p.ERR_METHOD_NOT_FOUND)

    def test_several_clients_are_served_concurrently(self):
        a, b = self._client(), self._client()
        self._handshake(a)
        self._handshake(b)
        self.assertEqual(self._call(a, "echo", {"text": "A"})["result"], {"said": "A"})
        self.assertEqual(self._call(b, "echo", {"text": "B"})["result"], {"said": "B"})


class TestConnectionTracking(_InetServerCase):

    def test_live_connections_are_tracked_and_released(self):
        conn = self._client()
        self._handshake(conn)
        self.assertEqual(self.server.connection_count(), 1)
        conn.close()
        deadline = time.time() + 5
        while self.server.connection_count() and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(self.server.connection_count(), 0)

    def test_stop_closes_live_connections(self):
        conn = self._client()
        self._handshake(conn)
        self.server.stop()
        self.assertEqual(self.server.connection_count(), 0)


class TestStopDoesNotDeadlock(_InetServerCase):
    """The regression this base exists for (see the module docstring)."""

    def test_stop_returns_promptly(self):
        done = threading.Event()
        threading.Thread(target=lambda: (self.server.stop(), done.set()),
                         daemon=True).start()
        self.assertTrue(done.wait(timeout=10), "stop() blocked — accept() wake failed")

    def test_stop_returns_even_if_the_accept_thread_already_exited(self):
        """The exact race: stop() clears _running first, so the accept loop can
        leave before the wake lands and nothing is left to answer a handshake.
        A bounded RAW connect wakes the socket regardless of the thread state —
        an authed mpc.Client here is what hung the suite."""
        self.server._running = False
        self._quiet_close(socket.create_connection(("127.0.0.1", self.port), timeout=2))
        deadline = time.time() + 5
        while self.server._accept_thread.is_alive() and time.time() < deadline:
            time.sleep(0.02)
        self.assertFalse(self.server._accept_thread.is_alive(),
                         "accept thread did not exit")
        done = threading.Event()
        threading.Thread(target=lambda: (self.server.stop(), done.set()),
                         daemon=True).start()
        self.assertTrue(done.wait(timeout=10), "stop() deadlocked on a dead accept loop")

    def test_stop_is_idempotent(self):
        self.server.stop()
        self.server.stop()

    def test_stop_never_raises_on_a_half_torn_down_listener(self):
        self.server._listener.close()
        self.server.stop()


class _RaisingListener:
    """A listener whose accept() always fails immediately."""

    def __init__(self):
        self.calls = 0

    def accept(self):
        self.calls += 1
        raise OSError("listener is dead")

    def close(self):
        pass


class TestAcceptRetryIsBounded(unittest.TestCase):
    """A permanently-failing accept() must not spin the thread at 100% CPU.

    Reported by CodeRabbit on #162, and inherited from BOTH pre-refactor
    servers: the retry branch did a bare `continue`, so an accept() that fails
    *immediately* (rather than blocking) re-entered with no delay and no log for
    as long as `_running` stayed true.

    Driven through an injected listener stub rather than a real closed socket,
    deliberately: closing a listener does NOT wake a thread already parked in
    accept() on Linux — that is the very reason `_wake_accept` exists — so the
    real-socket version of this test measures nothing. What is being pinned here
    is the loop's retry POLICY, which is ours; the OS socket semantics are not.
    """

    def _run_loop_briefly(self, seconds=0.25):
        log = _CountingLog()
        server = EchoServer(address=("127.0.0.1", _free_port()), family="AF_INET",
                            authkey=b"k", host_version="1.0.0", log=log,
                            thread_prefix="spin")
        listener = _RaisingListener()
        server._listener = listener
        server._running = True
        thread = threading.Thread(target=server._accept_loop, daemon=True)
        thread.start()
        time.sleep(seconds)
        server._running = False
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive(), "accept loop did not exit on _running=False")
        return listener, log

    def test_retries_are_rate_limited_not_a_busy_spin(self):
        listener, _log = self._run_loop_briefly(0.25)
        self.assertGreater(listener.calls, 1, "the loop gave up instead of retrying")
        # ~0.25s / ACCEPT_RETRY_DELAY_S turns, with generous slack for a loaded
        # box. An unbounded `continue` lands in the tens of thousands here.
        self.assertLess(listener.calls, 60,
                        f"accept() is spinning: {listener.calls} retries in 0.25s")

    def test_the_failure_is_logged_so_a_dead_listener_is_visible(self):
        _listener, log = self._run_loop_briefly(0.15)
        self.assertGreater(log.count, 0, "a permanently failing accept() logged nothing")

    def test_logging_is_throttled_rather_than_per_iteration(self):
        """First failure, then every Nth — a broken listener must not flood."""
        listener, log = self._run_loop_briefly(0.25)
        self.assertLess(log.count, listener.calls,
                        "every retry logged — this would flood the log")


@unittest.skipIf(sys.platform == "win32", "AF_UNIX-specific wake path")
class TestUnixSocketWake(unittest.TestCase):
    """ControlServer's real transport: an AF_UNIX path, not a TCP port."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(lambda: self._rmtree(self.dir))
        self.address = os.path.join(self.dir, "sock")
        self.server = EchoServer(address=self.address, family=None,
                                 authkey=b"k", host_version="1.0.0",
                                 log=_NullLog(), thread_prefix="unix")
        self.server.start()
        self.addCleanup(self.server.stop)

    @staticmethod
    def _rmtree(path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def test_round_trip_over_a_unix_socket(self):
        conn = Client(self.address, authkey=b"k")
        self.addCleanup(conn.close)
        self.assertEqual(p.recv_message(conn).get("method"), p.HELLO)
        p.send_message(conn, p.make_request(1, "echo", {"text": "unix"}))
        self.assertEqual(p.recv_message(conn)["result"], {"said": "unix"})

    def test_stop_returns_promptly(self):
        done = threading.Event()
        threading.Thread(target=lambda: (self.server.stop(), done.set()),
                         daemon=True).start()
        self.assertTrue(done.wait(timeout=10), "stop() blocked on AF_UNIX")

    def test_stop_survives_an_already_unlinked_endpoint(self):
        os.unlink(self.address)
        self.server.stop()


if __name__ == "__main__":
    unittest.main()
