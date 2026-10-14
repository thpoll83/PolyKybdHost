# SPDX-License-Identifier: GPL-3.0-or-later
"""bpy-free half of the PolyKybd Context Reporter (unit-tested by the host suite).

Everything here runs without Blender: building the pseudo-URL, finding the area
under the mouse from plain rectangles, deciding when to send, and the sender
thread. `__init__.py` is the thin bpy glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "blender", "url": "blender://EDIT_MESH/VIEW_3D", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

`pid` and `input_age` (seconds since this Blender last saw a mouse or key
event) let the host tell several running Blenders apart: it uses the instance
with the most recent input, so a background instance's keep-alive cannot
overwrite the one being worked in.

The URL names the interaction mode (`context.mode`) and the editor type under
the mouse (`area.type`, plus `area.ui_type` where Blender has several editors in
one type: UV vs Image, Timeline vs Dope Sheet, Shader vs Geometry nodes). No
file name, object name or scene data -- keep it that way; the host routes on
these tokens alone.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

APP = "blender"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than its freshness window (browser_url.py
# DEFAULT_MAX_AGE_S = 8 s), and the add-on cannot tell the host it lost OS
# focus, so it re-sends its context on a keep-alive well inside that window:
# two lost keep-alives still leave the report fresh.
KEEPALIVE_S = 3.0
POLL_S = 0.2                  # how often the timer looks for a change (cheap)
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; Blender's UI never waits

# Characters allowed in a URL token. Blender's own enums are upper-case
# identifiers; ui_type for a node editor is a tree idname (`ShaderNodeTree`) and
# can come from an add-on, so anything outside this set is dropped rather than
# sent.
_TOKEN_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")


def _token(value) -> str:
    s = str(value or "")
    return s if s and len(s) <= 64 and set(s) <= _TOKEN_OK else ""


def context_url(mode, area_type, ui_type=None) -> str | None:
    """`blender://<mode>/<area_type>[/<ui_type>]`, or None when the editor is unknown.

    `ui_type` is appended only when it says more than `area_type` (for most
    editors the two are equal)."""
    m, a, u = _token(mode), _token(area_type), _token(ui_type)
    if not m or not a:
        return None
    url = f"blender://{m}/{a}"
    if u and u != a:
        url += f"/{u}"
    return url


def area_at(areas, x, y):
    """The first area whose rectangle contains window coordinate (x, y).

    `areas` yields objects with `x, y, width, height` (Blender's `Area`), in
    window pixels with the origin bottom-left -- the same space as an event's
    `mouse_x` / `mouse_y`."""
    if x is None or y is None:
        return None
    for a in areas:
        if a.x <= x < a.x + a.width and a.y <= y < a.y + a.height:
            return a
    return None


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

    `submit()` only stores and signals, so the caller -- Blender's main thread --
    never touches the network. A host that is down refuses the loopback connect
    at once; a hung one costs this thread at most `HTTP_TIMEOUT_S` per attempt.
    Failures are silent: the next change or keep-alive retries."""

    def __init__(self, post=None):
        self._post = post or _http_post
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._stop = False
        self._seen = set()        # (type, message) of delivery errors already printed
        self._thread = threading.Thread(target=self._run, name="polykybd-reporter",
                                        daemon=True)
        self._thread.start()

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        with self._lock:
            self._pending = (int(port), payload(url, token, pid, input_age, focused))
        self._wake.set()

    def stop(self):
        """Stop the thread after it delivers the report still pending, if any
        (the withdrawal sent on unregister). Does not wait for it."""
        self._stop = True
        self._wake.set()

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
                    # Printed once per distinct error to Blender's system
                    # console, so a wrong port or token (HTTP 403) is
                    # diagnosable without a line every keep-alive.
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
