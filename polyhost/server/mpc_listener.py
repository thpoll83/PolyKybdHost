"""Shared listener half of the two ``multiprocessing.connection`` servers.

:class:`~polyhost.server.control_server.ControlServer` (local UDS / Windows
named pipe, the full ``PolyCore`` registry) and
:class:`~polyhost.server.window_report_server.WindowReportServer` (opt-in
``AF_INET``, exactly one method) are deliberately different *surfaces* — that
separation is the security boundary and must stay. But underneath they are the
same server: bind a ``Listener``, accept on a daemon thread, hand each
connection a reader thread, push the opening ``hello`` frame, read framed
requests, map handler exceptions onto JSON-RPC errors, and tear the whole thing
down without wedging.

Only the **dispatch** differs, so only :meth:`MpcListenerServer.dispatch` is
abstract.

Why this is a base class and not just deduplication: ``stop()`` has to wake a
thread parked in a blocking ``accept()``, and the *wrong* way to do that —
opening an authed ``mpc.Client`` — deadlocks whenever the accept loop has
already noticed ``_running`` is false, because a handshake needs a thread
*inside* ``accept()`` to answer it and there no longer is one. That hung the
test suite intermittently across three sessions while the sibling module in
this same package already carried the bounded-raw-connect remedy *and a comment
explaining it*. A single implementation is what stops the next fix from landing
on only one of them.
"""
import multiprocessing.connection as mpc
import socket
import sys
import threading

from polyhost.server import protocol as p

#: Bound on the raw connect ``stop()`` uses to wake a blocked ``accept()``.
#: Always a local endpoint, so this only ever caps a pathological case.
WAKE_TIMEOUT_S = 1.0


class MpcListenerServer:
    """Accept loop + per-connection plumbing for an ``mpc`` JSON-RPC server.

    Subclasses implement :meth:`dispatch` and may override
    :meth:`on_connection_added` / :meth:`on_connection_dropped` (the control
    server uses those to keep its per-connection write locks and event
    subscriptions in step with the live set).
    """

    def __init__(self, *, address, authkey, host_version, log,
                 family=None, thread_prefix="mpc"):
        self.address = address
        self.authkey = authkey
        self.host_version = host_version
        self.log = log
        self._family = family
        self._thread_prefix = thread_prefix

        self._listener = None
        self._accept_thread = None
        self._running = False
        self._conns = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    def dispatch(self, conn, req_id, method, params):
        """Handle one request; return the message to send back.

        Called on the connection's reader thread with ``req_id`` guaranteed
        non-None (notifications are dropped before this point) and ``params``
        guaranteed to be a dict. Return a ``protocol.make_response`` /
        ``make_error`` mapping. Raising is fine — see :meth:`_dispatch` for how
        exceptions become JSON-RPC errors.
        """
        raise NotImplementedError

    def on_connection_added(self, conn):
        """Called once per accepted connection, before its reader starts."""

    def on_connection_dropped(self, conn):
        """Called once when a connection leaves the live set."""

    def after_dispatch(self, conn, method):
        """Called after a reply has been written. The control server defers its
        shutdown teardown to here so the client sees the ack first."""

    def secure_listener(self):
        """Hook for tightening endpoint permissions right after bind."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        kwargs = {"authkey": self.authkey}
        if self._family is not None:
            kwargs["family"] = self._family
        self._listener = mpc.Listener(self.address, **kwargs)
        self.secure_listener()
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name=f"{self._thread_prefix}-accept", daemon=True)
        self._accept_thread.start()

    def stop(self):
        """Stop accepting and close everything. Best-effort, never raises."""
        self._running = False
        listener = self._listener
        if listener is not None:
            # Wake a blocked accept(), THEN close. Both wrapped — a half-torn-down
            # listener on a racing stop() must not raise.
            self._wake_accept()
            try:
                listener.close()
            except Exception:
                pass
        with self._lock:
            conns = list(self._conns)
            self._conns.clear()
        for conn in conns:
            self.on_connection_dropped(conn)
            _close_quietly(conn)

    def connection_count(self):
        """Number of live connections (test/diagnostic helper)."""
        with self._lock:
            return len(self._conns)

    def wake_address(self):
        """Address :meth:`_wake_accept` dials to unblock ``accept()``.

        Defaults to the bound address, which is right for a UDS path / named
        pipe. A server bound to a wildcard ``AF_INET`` host must override this:
        ``0.0.0.0`` is a valid thing to *bind* and not a valid thing to
        *connect to*, so waking it means dialing loopback instead.
        """
        return self.address

    def _wake_accept(self):
        """Poke the endpoint so a thread parked in ``accept()`` returns.

        A bounded RAW connect, deliberately, rather than an authed
        ``mpc.Client``: ``Client`` completes a two-way authkey handshake that
        only a thread already *inside* ``accept()`` can answer. ``stop()`` clears
        ``_running`` first, so the accept loop may have re-checked the flag and
        left before we get here — and then the handshake has nobody to answer it
        and blocks ``stop()`` forever (a hang in ``answer_challenge`` →
        ``recv_bytes``).

        A raw connect+close wakes the socket and returns within the timeout
        whatever the accept thread is doing; the server-side handshake on it then
        fails fast (EOF) and the loop, seeing ``_running`` false, breaks.
        """
        address = self.wake_address()
        try:
            if isinstance(address, tuple):
                _close_quietly(socket.create_connection(
                    address, timeout=WAKE_TIMEOUT_S))
            elif sys.platform == "win32":
                # Named pipe: opening the path completes the pending
                # ConnectNamedPipe, which is what accept() is waiting on.
                open(address, "rb", buffering=0).close()
            else:
                waker = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                waker.settimeout(WAKE_TIMEOUT_S)
                try:
                    waker.connect(address)
                finally:
                    waker.close()
        except OSError:
            # Endpoint already gone, refusing, or busy — nothing to wake.
            pass

    # ------------------------------------------------------------------
    # Accept loop + per-connection handler
    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self._running:
            try:
                conn = self._listener.accept()
            except Exception:
                # AuthenticationError on a bad key, the listener closed by
                # stop(), or a transport error on one client — keep serving
                # unless we're shutting down.
                if not self._running:
                    break
                continue
            if not self._running:
                _close_quietly(conn)
                break
            with self._lock:
                self._conns.add(conn)
            self.on_connection_added(conn)
            threading.Thread(
                target=self._handle_connection, args=(conn,),
                name=f"{self._thread_prefix}-conn", daemon=True).start()

    def _handle_connection(self, conn):
        # The very first frame is the server's hello notification.
        try:
            self.send(conn, p.make_notification(p.HELLO, p.hello_params(self.host_version)))
        except Exception:
            self._drop(conn)
            return
        try:
            while True:
                try:
                    msg = p.recv_message(conn)
                except (EOFError, OSError):
                    break
                except Exception:
                    # Keep the traceback: a framing/decode failure here is a
                    # protocol bug, and the frame itself is already lost.
                    self.log.exception("%s: malformed frame", type(self).__name__)
                    break
                self._dispatch(conn, msg)
        finally:
            self._drop(conn)

    def _dispatch(self, conn, msg):
        req_id = msg.get("id") if isinstance(msg, dict) else None
        method = msg.get("method") if isinstance(msg, dict) else None
        params = (msg.get("params") if isinstance(msg, dict) else None) or {}
        if req_id is None:
            # A notification. Nothing client->server is expected as one, and
            # answering would desync every following response id — drop it.
            return
        try:
            reply = self.dispatch(conn, req_id, method, params)
        except RpcError as e:
            reply = p.make_error(req_id, e.code, e.message)
        except (KeyError, TypeError, ValueError) as e:
            reply = p.make_error(req_id, p.ERR_INVALID_PARAMS, f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001 — last-resort guard
            self.log.exception("%s: handler for %r failed", type(self).__name__, method)
            reply = p.make_error(req_id, p.ERR_INTERNAL, f"{type(e).__name__}: {e}")
        self._reply(conn, reply)
        self.after_dispatch(conn, method)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def send(self, conn, obj):
        """Write one frame. Overridden by servers that serialize writes."""
        p.send_message(conn, obj)

    def _reply(self, conn, obj):
        try:
            self.send(conn, obj)
        except Exception:
            self._drop(conn)

    def _drop(self, conn):
        with self._lock:
            present = conn in self._conns
            self._conns.discard(conn)
        if present:
            self.on_connection_dropped(conn)
        _close_quietly(conn)


class RpcError(Exception):
    """Raised by a dispatch handler to produce a JSON-RPC error response.

    ``code`` is one of the ``protocol.ERR_*`` constants; ``message`` is a
    human-readable string sent back to the client verbatim.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = str(message)


def _close_quietly(conn):
    try:
        conn.close()
    except Exception:
        pass
