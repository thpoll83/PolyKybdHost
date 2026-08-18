"""WindowReportSession — the reconnecting window-report connection (H4d).

The forwarder re-resolves its target for every report (`--host-file` is read
each time), so the interesting behaviour is not "does a report get sent" — the
socket-level test in window_report_server_test.py covers that — but *when the
session is allowed to reuse an existing connection*. Reusing one that points at
the previous host is silent: the old machine keeps accepting reports, so
nothing errors and the keycaps simply follow the wrong computer.

No sockets here: an injected connect_fn stands in for the real connect, which
is what lets a host change be asserted directly.
"""
import unittest

from polyhost.server.window_report_client import WindowReportSession


class _FakeClient:
    """Stands in for WindowReportClient, recording what it was asked to do."""

    def __init__(self, host, fail=False):
        self.host = host
        self.reports = []
        self.closed = False
        self._fail = fail

    def report(self, handle, name, title, os=None, url=None):
        if self._fail:
            raise OSError("boom")
        self.reports.append((handle, name, title, os, url))
        return {"reported": True}

    def close(self):
        self.closed = True


class _FakeConnector:
    """connect_fn double: records every call and hands back a _FakeClient."""

    def __init__(self, fail_hosts=(), fail_report_hosts=()):
        self.calls = []
        self.clients = []
        self._fail_hosts = set(fail_hosts)
        self._fail_report_hosts = set(fail_report_hosts)

    def __call__(self, host, port=None, authkey=None, timeout=3.0):
        self.calls.append((host, port, authkey, timeout))
        if host in self._fail_hosts:
            raise OSError("unreachable")
        client = _FakeClient(host, fail=host in self._fail_report_hosts)
        self.clients.append(client)
        return client

    @property
    def hosts(self):
        return [c[0] for c in self.calls]


class WindowReportSessionTest(unittest.TestCase):
    def setUp(self):
        self.conn = _FakeConnector()
        self.session = WindowReportSession(
            port=50163, authkey=b"k", timeout=1.5, connect_fn=self.conn)

    def test_connects_once_and_reuses_for_the_same_host(self):
        for i in range(3):
            self.session.report("10.0.0.1", i, "app", "title")
        self.assertEqual(self.conn.hosts, ["10.0.0.1"])
        self.assertEqual(len(self.conn.clients), 1)
        self.assertEqual(len(self.conn.clients[0].reports), 3)

    def test_connect_gets_the_configured_port_authkey_and_timeout(self):
        self.session.report("10.0.0.1", 1, "app", "title")
        self.assertEqual(self.conn.calls, [("10.0.0.1", 50163, b"k", 1.5)])

    def test_report_forwards_every_field_including_os(self):
        self.session.report("10.0.0.1", 42, "chrome", "A Title", os=2,
                            url="https://example.com/a")
        self.assertEqual(self.conn.clients[0].reports,
                         [(42, "chrome", "A Title", 2, "https://example.com/a")])

    def test_a_changed_host_reconnects_instead_of_reusing_the_old_link(self):
        # The regression this class exists for: the target moved (a rewritten
        # --host-file), so the open connection must not be reused.
        self.session.report("10.0.0.1", 1, "app", "title")
        self.session.report("10.0.0.2", 2, "app", "title")

        self.assertEqual(self.conn.hosts, ["10.0.0.1", "10.0.0.2"])
        self.assertTrue(self.conn.clients[0].closed,
                        "the connection to the old host must be closed")
        # The second report went to the new host only.
        self.assertEqual(len(self.conn.clients[0].reports), 1)
        self.assertEqual(len(self.conn.clients[1].reports), 1)
        self.assertEqual(self.session.host, "10.0.0.2")

    def test_switching_back_reconnects_again(self):
        for host in ("10.0.0.1", "10.0.0.2", "10.0.0.1"):
            self.session.report(host, 1, "app", "title")
        self.assertEqual(self.conn.hosts, ["10.0.0.1", "10.0.0.2", "10.0.0.1"])

    def test_close_drops_the_connection_and_the_next_report_reconnects(self):
        self.session.report("10.0.0.1", 1, "app", "title")
        self.session.close()

        self.assertTrue(self.conn.clients[0].closed)
        self.assertIsNone(self.session.host)

        self.session.report("10.0.0.1", 2, "app", "title")
        self.assertEqual(self.conn.hosts, ["10.0.0.1", "10.0.0.1"])

    def test_close_is_idempotent_and_safe_before_any_connection(self):
        self.session.close()
        self.session.close()
        self.assertIsNone(self.session.host)
        self.assertEqual(self.conn.calls, [])

    def test_a_failed_report_closes_so_the_next_one_reconnects(self):
        conn = _FakeConnector(fail_report_hosts={"10.0.0.1"})
        session = WindowReportSession(connect_fn=conn)

        with self.assertRaises(OSError):
            session.report("10.0.0.1", 1, "app", "title")
        self.assertTrue(conn.clients[0].closed)
        self.assertIsNone(session.host)

        with self.assertRaises(OSError):
            session.report("10.0.0.1", 2, "app", "title")
        self.assertEqual(conn.hosts, ["10.0.0.1", "10.0.0.1"])

    def test_a_failed_connect_leaves_no_half_open_session(self):
        conn = _FakeConnector(fail_hosts={"10.0.0.9"})
        session = WindowReportSession(connect_fn=conn)

        with self.assertRaises(OSError):
            session.report("10.0.0.9", 1, "app", "title")
        self.assertIsNone(session.host)

    def test_defaults_to_the_real_connect(self):
        # Guards the connect_fn default: it is resolved from the module, and
        # `connect` is defined below the class.
        from polyhost.server import window_report_client as wrc
        self.assertIs(WindowReportSession()._connect, wrc.connect)


if __name__ == "__main__":
    unittest.main()
