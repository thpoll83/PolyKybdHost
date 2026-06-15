"""Dedicated network listener for active-window reports (headless-core H4d).

The cross-machine forwarder historically relayed the active window over a
**bespoke, unauthenticated** plaintext TCP socket (port 50162, see
``polyhost/handler/remote_window.py``). This is the H4d "safe first slice": a
real control-protocol listener that is **authenticated** (HMAC authkey) and
**version-gated** (the same ``hello`` handshake as the local control socket),
but whose method registry contains *exactly one* method — ``window.report``.

The security boundary is the whole point. This server holds **no reference to
PolyCore** — only an injected ``on_report(handle, name, title)`` callback — so
by construction it cannot reach brightness / language / firmware-flash /
bootloader or any other device control. Binding the full control registry to
the network would expose all of that; this exposes only the window report. The
device-control surface stays on the local-only UDS / named-pipe endpoint served
by :class:`polyhost.server.control_server.ControlServer`.

Transport is the same stdlib ``multiprocessing.connection`` as the local
socket, here over ``AF_INET``. Its HMAC challenge auth is not strong crypto
(see the stdlib docs) but is vastly better than the plaintext relay it replaces
and is appropriate for a LAN window-title feed. It is **opt-in** — off by
default, since it opens a network port.
"""
import multiprocessing.connection as mpc
import threading

from polyhost.server import protocol as p


class WindowReportServer:
    """Serve only ``window.report`` over an authenticated AF_INET socket."""

    def __init__(self, on_report, host_version, log, *,
                 bind_host="0.0.0.0", port=None, authkey=None):
        self._on_report = on_report
        self.host_version = host_version
        self.log = log
        self.port = port if port is not None else p.WINDOW_REPORT_PORT
        self.address = (bind_host, self.port)
        self.authkey = (authkey if authkey is not None
                        else p.load_or_create_authkey(p.window_report_authkey_path()))

        self._listener = None
        self._accept_thread = None
        self._running = False
        self._conns = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._listener = mpc.Listener(self.address, family="AF_INET", authkey=self.authkey)
        self._running = True
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="winreport-accept", daemon=True)
        self._accept_thread.start()
        self.log.info(
            "Window-report network listener on %s:%d (auth-gated, '%s' only)",
            self.address[0], self.port, p.M_WINDOW_REPORT)

    def stop(self):
        """Stop accepting and close everything. Best-effort, never raises."""
        self._running = False
        listener = self._listener
        if listener is not None:
            # Unblock the blocking accept() with a throwaway local connection,
            # then close the listener.
            try:
                throwaway = mpc.Client(("127.0.0.1", self.port),
                                       family="AF_INET", authkey=self.authkey)
                try:
                    throwaway.close()
                except Exception:
                    pass
            except Exception:
                pass
            try:
                listener.close()
            except Exception:
                pass
        with self._lock:
            conns = list(self._conns)
            self._conns.clear()
        for conn in conns:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Accept loop + per-connection handler
    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self._running:
            try:
                conn = self._listener.accept()
            except Exception:
                # AuthenticationError on a bad key, the listener closed on
                # stop(), or a transport error on one client — keep serving
                # unless we're shutting down.
                if not self._running:
                    break
                continue
            if not self._running:
                try:
                    conn.close()
                except Exception:
                    pass
                break
            with self._lock:
                self._conns.add(conn)
            t = threading.Thread(target=self._handle_connection, args=(conn,),
                                 name="winreport-conn", daemon=True)
            t.start()

    def _handle_connection(self, conn):
        # The very first frame is the server's hello notification.
        try:
            p.send_message(conn, p.make_notification(
                p.HELLO, p.hello_params(self.host_version)))
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
                    self.log.warning("Window-report listener: malformed frame")
                    break
                self._dispatch(conn, msg)
        finally:
            self._drop(conn)

    def _dispatch(self, conn, msg):
        req_id = msg.get("id") if isinstance(msg, dict) else None
        method = msg.get("method") if isinstance(msg, dict) else None
        params = (msg.get("params") if isinstance(msg, dict) else None) or {}
        if req_id is None:
            return  # notification — nothing client->server is expected
        if method != p.M_WINDOW_REPORT:
            # The entire security model rests on nothing else being reachable.
            self._reply(conn, p.make_error(
                req_id, p.ERR_METHOD_NOT_FOUND,
                f"only '{p.M_WINDOW_REPORT}' is served on the network endpoint"))
            return
        try:
            ret = self._on_report(params["handle"], params["name"],
                                  params.get("title", ""))
            # report_window returns the (ok, payload) contract; surface failure.
            if isinstance(ret, tuple) and len(ret) == 2 and not ret[0]:
                reply = p.make_error(req_id, p.ERR_DEVICE, str(ret[1]))
            else:
                reply = p.make_response(req_id, {"ok": True})
        except (KeyError, TypeError, ValueError) as e:
            reply = p.make_error(req_id, p.ERR_INVALID_PARAMS, f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001 — last-resort guard
            self.log.exception("Window-report handler failed")
            reply = p.make_error(req_id, p.ERR_INTERNAL, f"{type(e).__name__}: {e}")
        self._reply(conn, reply)

    def _reply(self, conn, obj):
        try:
            p.send_message(conn, obj)
        except Exception:
            self._drop(conn)

    def _drop(self, conn):
        with self._lock:
            self._conns.discard(conn)
        try:
            conn.close()
        except Exception:
            pass
