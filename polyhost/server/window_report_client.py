"""Network client for the window-report endpoint (headless-core H4d).

stdlib-only and Qt-free — the forwarder uses it to push the active window to a
remote PolyKybdHost daemon's :class:`WindowReportServer` over an authenticated,
version-gated control connection, replacing the plaintext TCP relay.

The connect is bounded by a socket timeout (the forwarder polls on the Qt main
thread, so a stuck connect must not freeze the tray), and the request/response
wait is bounded with ``conn.poll``.
"""
import socket

from multiprocessing.connection import Connection, answer_challenge, deliver_challenge

from polyhost.server import protocol as p


class WindowReportError(Exception):
    """A failed handshake, RPC error, or timeout talking to the endpoint."""


class WindowReportClient:
    def __init__(self, conn, timeout=3.0):
        self._conn = conn
        self._timeout = timeout
        self._next_id = 1
        self._verify_hello()

    def _verify_hello(self):
        if not self._conn.poll(self._timeout):
            raise WindowReportError("timed out waiting for server hello")
        msg = p.recv_message(self._conn)
        if msg.get("method") != p.HELLO:
            raise WindowReportError("server did not send a hello handshake")
        ok, why = p.check_hello(msg.get("params") or {})
        if not ok:
            raise WindowReportError(why)

    def report(self, handle, name, title, os=None):
        """Send one window report; raise WindowReportError on failure/timeout.

        ``os`` (optional, an OsType value int) lets the forwarder forward its host
        OS; omitted from the params when None so the field is simply absent for
        forwarders that do not forward their OS."""
        req_id = self._next_id
        self._next_id += 1
        params = {"handle": str(handle), "name": str(name), "title": str(title)}
        if os is not None:
            params["os"] = int(os)
        p.send_message(self._conn, p.make_request(
            req_id, p.M_WINDOW_REPORT, params))
        while True:
            if not self._conn.poll(self._timeout):
                raise WindowReportError("timed out waiting for window.report reply")
            msg = p.recv_message(self._conn)
            if msg.get("id") != req_id:
                continue  # stray frame — skip
            if "error" in msg:
                err = msg["error"] or {}
                raise WindowReportError(err.get("message", "unknown error"))
            return msg.get("result")

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def connect(host, port=None, authkey=None, timeout=3.0):
    """Open an authenticated window-report connection to ``host``.

    Mirrors ``multiprocessing.connection.Client`` for AF_INET (connect →
    HMAC challenge/response) but with a bounded connect timeout, so the
    forwarder never blocks indefinitely on an unreachable host."""
    if port is None:
        port = p.WINDOW_REPORT_PORT
    if authkey is None:
        authkey = p.load_or_create_authkey(p.window_report_authkey_path())

    s = socket.create_connection((host, port), timeout=timeout)
    try:
        s.setblocking(True)
        conn = Connection(s.detach())
    except Exception:
        s.close()
        raise
    try:
        # Client side of the multiprocessing auth handshake (answer, then
        # deliver) — same order Client() uses internally.
        answer_challenge(conn, authkey)
        deliver_challenge(conn, authkey)
    except Exception:
        conn.close()
        raise
    return WindowReportClient(conn, timeout=timeout)
