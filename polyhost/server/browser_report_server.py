"""Loopback HTTP receiver for browser active-tab reports (Qt-free, stdlib-only).

The browser extension (`browser-extension/`) can't speak the bespoke
``multiprocessing.connection`` framing the control / window-report sockets use —
a WebExtension can only ``fetch()``. So this is a tiny **loopback-only** HTTP
endpoint the extension POSTs its active-tab ``{browser, url, title, focused}`` to
on every tab switch / focus change; the report is handed to a callback (wired to
:class:`polyhost.handler.browser_url.BrowserUrlProvider`). The Blender add-on
(`blender-addon/`) uses the same endpoint with ``{app, url, focused}``, where
``url`` is a ``blender://<mode>/<editor>`` pseudo-URL; same token, same gates.

Security posture — deliberately minimal surface:

* Binds **127.0.0.1 only** (never ``0.0.0.0``), so it is unreachable off the
  machine. This is the key difference from ``WindowReportServer`` (a *network*
  endpoint, hence auth-gated + opt-in): a loopback receiver of low-sensitivity
  window titles is a much smaller risk, so it can default on and needs no
  handshake the extension would struggle to perform.
* Holds **no reference to PolyCore** — only an injected ``on_report`` callback —
  so, like the window-report server, it can never reach device control / flash /
  bootloader.
* **No cross-origin ``POST /report``**: CORS is granted only for the ``/ping``
  health check, and ``/report`` requires an ``application/json`` body — a
  combination that forces a preflight the report path never answers, so a
  third-party web page cannot POST a spoofed report even with the receiver on
  and no token. The extension has ``host_permissions`` and is exempt from CORS.
* Optional shared ``token``: if set, a report must present the same token
  (constant-time compared). Off by default (a local *process* could at worst
  pick which overlay shows); set it for defence-in-depth against other local
  apps.

Endpoints: ``POST /report`` (the report), ``GET /ping`` (health probe the
extension uses to detect a running host). Bodies are size-capped; malformed
input is rejected, never raised.

The command channel (host → extension), for the agent keys' cloud sessions:
``GET /command`` is held open up to ``COMMAND_WAIT_S`` and answers with the
next command (``{"id", "focus_url"}``) or none; the extension answers each one
with ``POST /command_result`` ``{"id", "found"}``. Both need the header
``X-PolyKybd-Extension: 1``: a custom header forces a CORS preflight, which
these paths never grant, so a web page can neither take a command nor answer
one. The only command is "focus the tab with this exact URL", and the host
sends only a ``https://claude.ai/code/session_…`` address
(``cloud_relay.is_session_url``): the extension never opens anything.
"""
import hmac
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_BROWSER_REPORT_PORT = 50164
_MAX_BODY_BYTES = 16 * 1024
# How long one GET /command is held open. Below the 30 s after which Chrome stops
# an idle extension service worker, so each wait ends before that.
COMMAND_WAIT_S = 20.0
# An extension that polled within this time counts as listening.
LISTENING_S = COMMAND_WAIT_S + 10.0
EXTENSION_HEADER = "X-PolyKybd-Extension"


class TabCommands:
    """The host's queue of commands for the browser extension, and their answers.

    Thread-safe: the extension's request threads wait in ``next()``, the agent
    key press calls ``focus()`` from its own thread."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._cond = threading.Condition()
        self._ids = itertools.count(1)
        self._pending = None          # (id, url) not yet taken
        self._results = {}            # id -> found, for a command still waited on
        self._waiting = set()         # ids whose focus() call still waits
        self._last_poll = None

    def listening(self) -> bool:
        with self._cond:
            return (self._last_poll is not None
                    and self._clock() - self._last_poll < LISTENING_S)

    def next(self, wait_s: float):
        """The next command for an extension, or None after `wait_s`."""
        deadline = self._clock() + wait_s
        with self._cond:
            self._last_poll = self._clock()
            while self._pending is None:
                left = deadline - self._clock()
                if left <= 0:
                    return None
                self._cond.wait(left)
            cid, url = self._pending
            self._pending = None
            self._last_poll = self._clock()
            return {"id": cid, "focus_url": url}

    def answer(self, cid, found) -> bool:
        with self._cond:
            # Only a command still waited on, and only once: a late or repeated
            # answer is refused, so nothing piles up.
            if (not isinstance(cid, int) or isinstance(cid, bool)
                    or cid not in self._waiting or cid in self._results):
                return False
            self._results[cid] = bool(found)
            self._cond.notify_all()
            return True

    def focus(self, url: str, timeout_s: float = 2.0):
        """Ask the extension to focus the tab showing `url`. True: done; False:
        no tab has it; None: no extension listening, or no answer in time."""
        if not self.listening():
            return None
        with self._cond:
            cid = next(self._ids)
            self._pending = (cid, url)      # a newer press replaces an untaken one
            self._waiting.add(cid)
            self._cond.notify_all()
            deadline = self._clock() + timeout_s
            try:
                while cid not in self._results:
                    left = deadline - self._clock()
                    if left <= 0:
                        if self._pending and self._pending[0] == cid:
                            self._pending = None
                        return None
                    self._cond.wait(left)
                return self._results.pop(cid)
            finally:
                self._waiting.discard(cid)


class _Handler(BaseHTTPRequestHandler):
    # server carries: on_report, token, log (set on the ThreadingHTTPServer).
    protocol_version = "HTTP/1.1"

    # --- CORS is granted ONLY for the /ping health check the options page calls
    # cross-origin. /report deliberately gets NO CORS grant: a web page can only
    # skip a preflight with a "simple" request, and combined with the
    # application/json requirement in do_POST that forces a preflight /report
    # never answers — so no third-party page can POST a spoofed report. The
    # extension itself has host_permissions and is exempt from CORS entirely. ---
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, payload, *, cors=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cors:
            self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def do_OPTIONS(self):  # noqa: N802 — stdlib handler naming
        # Honour a preflight only for /ping; /report gets no CORS grant.
        if self.path.split("?", 1)[0] == "/ping":
            self.send_response(204)
            self._cors()
        else:
            self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _from_extension(self) -> bool:
        """The command paths answer only the extension: the custom header makes a
        page's request preflighted, and the token (when set) must match."""
        if self.headers.get(EXTENSION_HEADER) != "1":
            self._json(403, {"ok": False, "error": "extension header missing"})
            return False
        token = getattr(self.server, "token", "")
        if token and not hmac.compare_digest(
                str(self.headers.get("X-PolyKybd-Token", "")), str(token)):
            self._json(403, {"ok": False, "error": "bad token"})
            return False
        return True

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/ping":
            self._json(200, {"ok": True, "app": "PolyKybdHost"}, cors=True)
        elif path == "/command":
            if self._from_extension():
                command = self.server.commands.next(self.server.command_wait_s)
                self._json(200, {"ok": True, "command": command})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def _read_json(self):
        """The request's JSON object, or None after answering the error."""
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._json(415, {"ok": False, "error": "unsupported media type"})
            return None
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._json(400, {"ok": False, "error": "bad length"})
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "bad json"})
            return None
        return data

    def do_POST(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/command_result":
            if not self._from_extension():
                return
            data = self._read_json()
            if data is None:
                return
            ok = self.server.commands.answer(data.get("id"), data.get("found") is True)
            self._json(200 if ok else 400, {"ok": ok})
            return
        if path != "/report":
            self._json(404, {"ok": False, "error": "not found"})
            return
        # Require application/json. A cross-origin page can avoid a CORS preflight
        # only with a "simple" content type (text/plain / form encoding);
        # requiring application/json forces a preflight, which /report does not
        # grant — closing the browser-based spoofing vector without a token.
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._json(415, {"ok": False, "error": "unsupported media type"})
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

        # Text fields pass only as text: a number or an object for `url`
        # would reach urlsplit() in window tracking and raise there, which
        # turns the focused window's overlays off for as long as it is resent.
        report = {key: (data.get(key) if isinstance(data.get(key), str) else None)
                  for key in ("browser", "url", "title")}
        report["focused"] = data.get("focused", True)
        # A context reporter (the Blender add-on, `blender-addon/`) names
        # itself with `app` instead of `browser`. Passed only when present, so
        # a browser report reaches the callback exactly as before.
        if isinstance(data.get("app"), str):
            report["app"] = data.get("app")
            # Optional instance identity (several Blenders open at once):
            # passed only when it is a sane number, never as a raw string.
            pid, age = data.get("pid"), data.get("input_age")
            if isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid < 2**32:
                report["pid"] = pid
            if (isinstance(age, (int, float)) and not isinstance(age, bool)
                    and 0 <= age < 10**7):
                report["input_age"] = float(age)
        try:
            self.server.on_report(**report)
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
        self.commands = TabCommands()
        self.command_wait_s = COMMAND_WAIT_S
        self._httpd = None
        self._thread = None

    def start(self):
        # ThreadingHTTPServer so a slow/hung client can't block the next report.
        self._httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        self._httpd.daemon_threads = True
        self._httpd.on_report = self._on_report
        self._httpd.token = self.token
        self._httpd.log = self.log
        self._httpd.commands = self.commands
        self._httpd.command_wait_s = self.command_wait_s
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
