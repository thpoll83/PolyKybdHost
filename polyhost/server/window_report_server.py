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

The listener plumbing (accept loop, per-connection reader, hello frame, the
non-deadlocking ``stop()``) is shared with the control server via
:class:`polyhost.server.mpc_listener.MpcListenerServer`; only :meth:`dispatch`
is local, which is exactly where the surface difference belongs.

Transport is the same stdlib ``multiprocessing.connection`` as the local
socket, here over ``AF_INET``. Its HMAC challenge auth is not strong crypto
(see the stdlib docs) but is vastly better than the plaintext relay it replaces
and is appropriate for a LAN window-title feed. It is **opt-in** — off by
default, since it opens a network port.
"""
from polyhost.server import protocol as p
from polyhost.server.mpc_listener import MpcListenerServer


class WindowReportServer(MpcListenerServer):
    """Serve only ``window.report`` over an authenticated AF_INET socket."""

    def __init__(self, on_report, host_version, log, *,
                 bind_host="0.0.0.0", port=None, authkey=None):
        self._on_report = on_report
        port = port if port is not None else p.WINDOW_REPORT_PORT
        super().__init__(
            address=(bind_host, port),
            family="AF_INET",
            authkey=(authkey if authkey is not None
                     else p.load_or_create_authkey(p.window_report_authkey_path())),
            host_version=host_version,
            log=log,
            thread_prefix="winreport")
        self.port = port

    def wake_address(self):
        """Dial loopback rather than the bound host: this server binds a
        wildcard (``0.0.0.0``) by design, and a wildcard is bindable but not
        connectable — ``stop()`` would never wake ``accept()``."""
        host = self.address[0]
        if host in ("", "0.0.0.0"):
            return ("127.0.0.1", self.port)
        return self.address

    def start(self):
        super().start()
        self.log.info(
            "Window-report network listener on %s:%d (auth-gated, '%s' only)",
            self.address[0], self.port, p.M_WINDOW_REPORT)

    def dispatch(self, conn, req_id, method, params):
        if method != p.M_WINDOW_REPORT:
            # The entire security model rests on nothing else being reachable.
            return p.make_error(
                req_id, p.ERR_METHOD_NOT_FOUND,
                f"only '{p.M_WINDOW_REPORT}' is served on the network endpoint")
        ret = self._on_report(params["handle"], params["name"],
                              params.get("title", ""), os=params.get("os"),
                              url=params.get("url"))
        # report_window returns the (ok, payload) contract; surface failure.
        if isinstance(ret, tuple) and len(ret) == 2 and not ret[0]:
            return p.make_error(req_id, p.ERR_DEVICE, str(ret[1]))
        return p.make_response(req_id, {"ok": True})
