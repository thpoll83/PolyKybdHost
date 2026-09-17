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
import base64
import binascii

from polyhost.server import protocol as p
from polyhost.server.mpc_listener import MpcListenerServer

# A real OS icon is a few KB -- the largest on a stock GNOME install measured
# ~16 KB, and base64 inflates by 4/3. 64 KB of base64 leaves ~48 KB of icon,
# generous for anything legitimate and still a bounded read on the one method
# exposed to the network.
# ⚠️ DERIVED from what a shrunk icon can be, not guessed. It was 64 KB on the
# premise that "the largest on a stock GNOME install measured ~16 KB"; a stock
# VS Code icon is 512x512 / ~220 KB, so the endpoint REFUSED a legitimate report
# (measured 2026-09-17, 294276 base64 chars). The sender now bounds the RASTER
# at icon_binarise.TRANSPORT_MAX_PX, so the real ceiling is an incompressible
# PNG of that size: 160x160 RGBA is 102400 raw and measured 102685 encoded,
# i.e. ~136916 base64 chars. 192 KB leaves ~40% headroom for a format we do not
# ship today without becoming a memory lever -- which is the whole point of a
# cap on the ONE method reachable over the network.
MAX_ICON_B64 = 192 * 1024
# The OS offers one display name on Linux and at most a handful on Windows.
MAX_NAMES = 8


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
        try:
            icon = self._decode_icon(params.get("icon"))
        except ValueError as err:
            return p.make_error(req_id, p.ERR_INVALID_PARAMS, str(err))
        names = params.get("names") or ()
        if not isinstance(names, (list, tuple)):
            return p.make_error(req_id, p.ERR_INVALID_PARAMS, "names must be a list")
        ret = self._on_report(params["handle"], params["name"],
                              params.get("title", ""), os=params.get("os"),
                              url=params.get("url"),
                              names=tuple(str(n) for n in names[:MAX_NAMES]),
                              icon_key=params.get("icon_key"), icon=icon)
        # report_window returns the (ok, payload) contract; surface failure.
        if isinstance(ret, tuple) and len(ret) == 2:
            if not ret[0]:
                return p.make_error(req_id, p.ERR_DEVICE, str(ret[1]))
            # ⚠️ Unwrap, or `want_icon` cannot reach the forwarder: the real
            # sink is PolyCore.report_window, which answers a TUPLE, so a
            # dict-only merge here silently discarded every field the payload
            # carried while still replying ok. The feature then looks dead
            # rather than broken.
            ret = ret[1]
        result = {"ok": True}
        # The sink may ask for something back -- today only `want_icon`. Merging
        # rather than replacing keeps `ok` unconditional, so an older forwarder
        # reading only that field is unaffected.
        if isinstance(ret, dict):
            result.update(ret)
        return p.make_response(req_id, result)

    @staticmethod
    def _decode_icon(value):
        """The forwarder's icon bytes, or None. Raises ValueError on junk.

        ⚠️ Bounded on PURPOSE. This is the one method reachable on the NETWORK
        endpoint, so its params are the only attacker-shaped input the daemon
        parses -- an unbounded base64 blob here is a memory-exhaustion lever
        against a process that owns the HID device. The cap is generous next to
        a real icon: the largest on a stock GNOME install measured ~16 KB.
        """
        if not value:
            return None
        if not isinstance(value, str):
            raise ValueError("icon must be base64 text")
        if len(value) > MAX_ICON_B64:
            raise ValueError("icon too large (%d > %d base64 chars)"
                             % (len(value), MAX_ICON_B64))
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as err:
            raise ValueError("icon is not valid base64: %s" % err) from err
