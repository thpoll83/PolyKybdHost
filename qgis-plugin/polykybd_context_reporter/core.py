# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free half of the PolyKybd Context Reporter for QGIS (unit-tested by the host suite).

Everything here runs without QGIS: building the pseudo-URL, deciding when to
send, and the sender thread. `plugin.py` is the thin QGIS glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "qgis", "url": "qgis://map/digitize/cad/edit", "focused": true,
     "pid": 4242, "input_age": 0.0, "token": "<only if one is configured>"}

The URL names the window kind (main window, print layout designer, a dialog),
the map tool group, whether the current layer is in edit mode and whether the
Advanced Digitizing tools are on. No layer name, file name, project content or
window title. Keep it that way: the host routes on these tokens alone.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

APP = "qgis"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than its freshness window (browser_url.py
# DEFAULT_MAX_AGE_S = 8 s), so the plugin re-sends its context well inside it.
KEEPALIVE_S = 3.0
POLL_S = 0.2                  # how often the timer looks for a change (cheap)
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; the QGIS UI never waits

# Window kinds.
MAP = "map"                   # the main window (map canvas, panels)
LAYOUT = "layout"             # a print layout or report designer window
DIALOG = "dialog"             # any other QGIS window (attribute table, a dialog)
WINDOWS = frozenset({MAP, LAYOUT, DIALOG})

# Map tool groups (main window only).
PAN = "pan"                   # pan and the zoom tools
SELECT = "select"             # the select tools
IDENTIFY = "identify"
MEASURE = "measure"           # measure line, area, angle
DIGITIZE = "digitize"         # a capture tool: add feature, add part/ring, reshape, split
VERTEX = "vertex"             # the vertex tool (all layers or the current layer)
OTHER = "other"               # any other tool, or no tool
TOOLS = frozenset({PAN, SELECT, IDENTIFY, MEASURE, DIGITIZE, VERTEX, OTHER})
# The Advanced Digitizing keys work only while one of these tools is active.
CAD_TOOLS = frozenset({DIGITIZE, VERTEX})


def context_url(window, tool=None, editing=False, cad=False) -> str | None:
    """`qgis://map/<tool>[/cad][/edit]`, `qgis://layout` or `qgis://dialog`.

    `/edit`: the current layer is a vector layer in edit mode. `/cad`: the
    Advanced Digitizing tools are on, which matters only for a digitize or
    vertex tool, so it is added only then. None for an unknown window kind."""
    if window not in WINDOWS:
        return None
    if window != MAP:
        return f"qgis://{window}"
    t = tool if tool in TOOLS else OTHER
    url = f"qgis://map/{t}"
    if cad and t in CAD_TOOLS:
        url += "/cad"
    if editing:
        url += "/edit"
    return url


class SendPolicy:
    """Send on change, plus a keep-alive while nothing changes."""

    def __init__(self, keepalive_s=KEEPALIVE_S):
        self.keepalive_s = keepalive_s
        self.last_url = None
        self.last_sent = None

    def due(self, url, now) -> bool:
        if url is None:
            return False
        if url != self.last_url or self.last_sent is None:
            return True
        return now - self.last_sent >= self.keepalive_s

    def sent(self, url, now):
        self.last_url = url
        self.last_sent = now


def payload(url, token="", pid=None, input_age=None, focused=True) -> bytes:
    """One report. ``focused=False`` with no URL withdraws this instance's
    context, so the host stops showing its mode when reporting is turned off."""
    body = {"app": APP, "url": url, "focused": bool(focused)}
    if pid is not None:
        body["pid"] = int(pid)
    if input_age is not None:
        body["input_age"] = round(max(0.0, float(input_age)), 1)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


class Sender:
    """One daemon thread POSTing the LATEST report; older pending ones are dropped.

    `submit()` only stores and signals, so the caller (the QGIS main thread)
    never touches the network. Failures are silent: the next change or
    keep-alive retries. A distinct error is printed once."""

    def __init__(self, post=None):
        self._post = post or _http_post
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._stop = False
        self._seen = set()
        self._thread = threading.Thread(target=self._run, name="polykybd-reporter",
                                        daemon=True)
        self._thread.start()

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        with self._lock:
            self._pending = (int(port), payload(url, token, pid, input_age, focused))
        self._wake.set()

    def stop(self):
        """Stop the thread after it delivers the report still pending, if any
        (the withdrawal sent on unload). Does not wait for it."""
        self._stop = True
        self._wake.set()

    def join(self, timeout=None):
        self._thread.join(timeout)

    def _run(self):
        while True:
            if not self._stop:
                self._wake.wait()
            self._wake.clear()
            with self._lock:
                job, self._pending = self._pending, None
            if job is None and self._stop:
                return
            if job is not None:
                try:
                    self._post(*job)
                except Exception as e:   # noqa: BLE001 -- the thread must survive; retry later
                    key = (type(e).__name__, str(e))
                    if key not in self._seen:
                        self._seen.add(key)
                        print(f"PolyKybd Context Reporter: report not delivered: "
                              f"{type(e).__name__}: {e}", file=sys.stderr)


def _http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never be routed through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()
