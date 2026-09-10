"""Dedicated network listener for active-window reports (headless-core H4d).

The cross-machine forwarder historically relayed the active window over a
**bespoke, unauthenticated** plaintext TCP socket (port 50162, see
``polyhost/handler/remote_window.py``). This is the H4d "safe first slice": a
real control-protocol listener that is **authenticated** (HMAC authkey) and
**version-gated** (the same ``hello`` handshake as the local control socket),
but whose method registry is a **hand-listed pair**: ``window.report`` and
``ai.state``.

The security boundary is the whole point, and it is the SHAPE of the surface
rather than its size. This server holds **no reference to PolyCore** — only
injected callbacks (``on_report(handle, name, title)`` and
``on_ai_state(value)``) — so by construction it cannot reach brightness /
language / firmware-flash / bootloader or any other device control. Binding the
full control registry to the network would expose all of that; this exposes a
window report and one integer. The device-control surface stays on the
local-only UDS / named-pipe endpoint served by
:class:`polyhost.server.control_server.ControlServer`.

⚠️ ``ai.state`` was added (not a second listener on a second port) deliberately:
a sibling server would double the network surface to serve the same LAN peer
that has already authenticated with this endpoint's own authkey. What must not
change is the discipline — injected callback, no PolyCore, no method that names
a file, a device or a window. ``ai.state`` is additionally refused unless the
``ai_key_enabled`` setting is on, so the feature's own off-by-default flag gates
the network method too, not merely the local one.

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
    """Serve ``window.report`` and ``ai.state`` over an authenticated AF_INET socket."""

    def __init__(self, on_report, host_version, log, *,
                 bind_host="0.0.0.0", port=None, authkey=None,
                 on_ai_state=None, ai_relay=None):
        self._on_report = on_report
        # Both optional so an embedder that wants only the window feed gets exactly
        # the old surface: with no on_ai_state, `ai.state` is method-not-found, and
        # with no ai_relay the reply carries no AI fields at all.
        self._on_ai_state = on_ai_state
        self._ai_relay = ai_relay
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
        served = ", ".join(self._served())
        self.log.info(
            "Window-report network listener on %s:%d (auth-gated, %s only)",
            self.address[0], self.port, served)

    def _served(self):
        """The methods this instance actually answers, in a stable order.

        Derived from which callbacks were injected rather than hardcoded, so the
        startup line cannot claim a surface the dispatch does not serve — the same
        reason the release gate derives its job name instead of listing it.
        """
        names = [f"'{p.M_WINDOW_REPORT}'"]
        if self._on_ai_state is not None:
            names.append(f"'{p.M_AI_STATE}'")
        return names

    def dispatch(self, conn, req_id, method, params):
        if method == p.M_WINDOW_REPORT:
            return self._dispatch_window_report(req_id, params)
        if method == p.M_AI_STATE and self._on_ai_state is not None:
            return self._dispatch_ai_state(req_id, params)
        # The entire security model rests on nothing else being reachable.
        return p.make_error(
            req_id, p.ERR_METHOD_NOT_FOUND,
            f"only {', '.join(self._served())} are served on the network endpoint")

    def _dispatch_window_report(self, req_id, params):
        ret = self._on_report(params["handle"], params["name"],
                              params.get("title", ""), os=params.get("os"),
                              url=params.get("url"))
        # report_window returns the (ok, payload) contract; surface failure.
        if isinstance(ret, tuple) and len(ret) == 2 and not ret[0]:
            return p.make_error(req_id, p.ERR_DEVICE, str(ret[1]))
        result = {"ok": True}
        # The AI relay rides the REPLY. The forwarder has no listener, so this is
        # the only direction that needs no inbound port on its machine; and it
        # costs nothing, because the forwarder is sending these anyway.
        if self._ai_relay is not None:
            try:
                relay = self._ai_relay() or {}
            except Exception:  # noqa: BLE001 — a relay fault must not fail the report
                self.log.warning("AI relay state failed", exc_info=True)
                relay = {}
            if relay:
                result["ai"] = relay
        return p.make_response(req_id, result)

    def _dispatch_ai_state(self, req_id, params):
        ret = self._on_ai_state(params.get("value"))
        if isinstance(ret, tuple) and len(ret) == 2 and not ret[0]:
            return p.make_error(req_id, p.ERR_DEVICE, str(ret[1]))
        return p.make_response(req_id, {"ok": True})
