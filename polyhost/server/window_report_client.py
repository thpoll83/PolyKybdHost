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

    def report(self, handle, name, title, os=None, url=None):
        """Send one window report; raise WindowReportError on failure/timeout.

        ``os`` (optional, an OsType value int) lets the forwarder forward its host
        OS; omitted from the params when None so the field is simply absent for
        forwarders that do not forward their OS."""
        req_id = self._next_id
        self._next_id += 1
        params = {"handle": str(handle), "name": str(name), "title": str(title)}
        if os is not None:
            params["os"] = int(os)
        # Optional in both directions: an older daemon ignores unknown params,
        # and a newer one reads None when an older forwarder omits it.
        if url is not None:
            params["url"] = str(url)
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


class WindowReportSession:
    """A reconnecting window-report connection whose target may move.

    The forwarder re-resolves its target for *every* report — with
    ``--host-file`` the file is read each time and may be rewritten mid-session
    — so a cached connection is only reusable while it still points at the host
    that was just resolved. Remembering the connected host here is what makes a
    changed address take effect on the next report instead of whenever the old
    connection happens to break: the caller cannot notice on its own, because a
    connection to the *previous* host keeps accepting reports quite happily.

    A failed report closes the connection, so the next one reconnects.
    """

    def __init__(self, port=None, authkey=None, timeout=3.0, connect_fn=None):
        self._port = port
        self._authkey = authkey
        self._timeout = timeout
        self._connect = connect_fn if connect_fn is not None else connect
        self._client = None
        self._host = None

    @property
    def host(self):
        """The host the open connection points at, or None when not connected."""
        return self._host

    def report(self, host, handle, name, title, os=None, url=None):
        """Send one report to ``host``, (re)connecting as needed.

        Raises whatever the connect or the report raised, having closed the
        connection first — the caller logs it and the next call reconnects.
        """
        if self._client is not None and host != self._host:
            self.close()
        try:
            if self._client is None:
                self._client = self._connect(
                    host, self._port, self._authkey, self._timeout)
                self._host = host
            return self._client.report(handle, name, title, os=os, url=url)
        except Exception:
            self.close()
            raise

    def close(self):
        """Drop any open connection. Idempotent; never raises."""
        client, self._client, self._host = self._client, None, None
        if client is not None:
            client.close()


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
