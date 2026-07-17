"""Loopback HTTP receiver for browser active-tab reports (Qt-free, stdlib-only).

The browser extension (`browser-extension/`) can't speak the bespoke
``multiprocessing.connection`` framing the control / window-report sockets use —
a WebExtension can only ``fetch()``. So this is a tiny **loopback-only** HTTP
endpoint the extension POSTs its active-tab ``{browser, url, title, focused}`` to
on every tab switch / focus change; the report is handed to a callback (wired to
:class:`polyhost.handler.browser_url.BrowserUrlProvider`).

Security posture — deliberately minimal surface:

* Binds **127.0.0.1 only** (never ``0.0.0.0``), so it is unreachable off the
  machine. This is the key difference from ``WindowReportServer`` (a *network*
  endpoint, hence auth-gated + opt-in): a loopback receiver of low-sensitivity
  window titles is a much smaller risk, so it can default on and needs no
  handshake the extension would struggle to perform.
* Holds **no reference to PolyCore** — only an injected ``on_report`` callback —
  so, like the window-report server, it can never reach device control / flash /
  bootloader.
* Optional shared ``token``: if set, a report must present the same token
  (constant-time compared). Off by default (a local process could at worst pick
  which overlay shows); set it for defence-in-depth against other local apps.

Endpoints: ``POST /report`` (the report), ``GET /ping`` (health probe the
extension uses to detect a running host). Bodies are size-capped; malformed
input is rejected, never raised.
"""
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_BROWSER_REPORT_PORT = 50164
_MAX_BODY_BYTES = 16 * 1024


class _Handler(BaseHTTPRequestHandler):
    # server carries: on_report, token, log (set on the ThreadingHTTPServer).
    protocol_version = "HTTP/1.1"

    # --- CORS: extensions with host_permissions don't need it, but the options
    # page's test fetch might; harmless to always allow a loopback caller. ---
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def do_OPTIONS(self):  # noqa: N802 — stdlib handler naming
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if self.path.split("?", 1)[0] == "/ping":
            self._json(200, {"ok": True, "app": "PolyKybdHost"})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?", 1)[0] != "/report":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._json(400, {"ok": False, "error": "bad length"})
            return
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "bad json"})
            return

        token = getattr(self.server, "token", "")
        if token and not hmac.compare_digest(str(data.get("token", "")), str(token)):
            self._json(403, {"ok": False, "error": "bad token"})
            return

        try:
            self.server.on_report(
                browser=data.get("browser"),
                url=data.get("url"),
                title=data.get("title"),
                focused=data.get("focused", True),
            )
        except Exception as e:  # noqa: BLE001 — never let a report crash the server
            log = getattr(self.server, "log", None)
            if log is not None:
                log.warning("browser report handler failed: %s", e)
            self._json(500, {"ok": False, "error": "handler failed"})
            return
        self._json(200, {"ok": True})

    def log_message(self, fmt, *args):
        # Route stdlib's stderr access log to our logger at debug (silent by default).
        log = getattr(self.server, "log", None)
        if log is not None:
            log.debug_detailed("browser-report http: " + fmt, *args)


class BrowserReportServer:
    """Serve the loopback ``/report`` + ``/ping`` endpoints on a daemon thread."""

    def __init__(self, on_report, log, *, host="127.0.0.1",
                 port=DEFAULT_BROWSER_REPORT_PORT, token=""):
        self._on_report = on_report
        self.log = log
        self.host = host
        self.port = port
        self.token = token or ""
        self._httpd = None
        self._thread = None

    def start(self):
        # ThreadingHTTPServer so a slow/hung client can't block the next report.
        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.on_report = self._on_report
        self._httpd.token = self.token
        self._httpd.log = self.log
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="browser-report-http", daemon=True)
        self._thread.start()
        self.log.info(
            "Browser-report loopback listener on http://%s:%d (/report, /ping)%s",
            self.host, self.port, " [token]" if self.token else "")

    def stop(self):
        """Best-effort shutdown; never raises."""
        httpd = self._httpd
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
            try:
                httpd.server_close()
            except Exception:
                pass
        self._httpd = None
        self._thread = None
