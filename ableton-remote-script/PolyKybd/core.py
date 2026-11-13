# SPDX-License-Identifier: GPL-3.0-or-later
"""Live-free half of the PolyKybd remote script (unit-tested by the host suite).

Everything here runs without Ableton Live: building the pseudo-URL, deciding
when to send, the settings file, and a NON-BLOCKING HTTP sender that the
script drives from Live's ~100 ms `update_display()` tick. `__init__.py` and
`reporter.py` are the thin Live glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "ableton", "url": "ableton://session/clip", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

The URL names the main view (`session` or `arrangement`, from
`Application.View.focused_document_view`) and, when the detail view is open,
which one it shows (`clip` or `device`). No set name, track, clip or device
name. Keep it that way: the host routes on these tokens alone.

Why no thread: Live's main thread is also its UI thread, and Live's embedded
Python is known to stall when a script starts threads (AbletonOSC, which
uses a non-blocking socket polled from a tick for the same reason). So the
sender never blocks: it opens a non-blocking TCP socket to loopback and moves
one step per tick, with `select()` at timeout 0.
"""
from __future__ import annotations

import errno
import json
import os
import select
import socket

APP = "ableton"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than its freshness window (browser_url.py
# DEFAULT_MAX_AGE_S = 8 s), and the script cannot tell the host that Live lost
# OS focus, so it re-sends its context on a keep-alive well inside that window.
KEEPALIVE_S = 3.0
# One HTTP exchange may take this long (counted over ticks) before it is
# dropped. A loopback connect is refused at once when the host is not running.
EXCHANGE_TIMEOUT_S = 1.0
# How long disconnect() may wait to deliver the last (withdrawing) report.
FLUSH_TIMEOUT_S = 0.25
SETTINGS_FILE = "settings.json"

# focused_document_view -> URL token. The LOM documents only these two values.
_MAIN_VIEWS = {"Session": "session", "Arranger": "arrangement"}


def context_url(document_view, clip_visible=False, device_visible=False):
    """`ableton://<session|arrangement>[/clip|/device]`, or None for a view
    name this script does not know.

    Live shows one detail view at a time (Clip or Device), so at most one of
    the two flags is set; if both are, `clip` is reported."""
    main = _MAIN_VIEWS.get(str(document_view or ""))
    if main is None:
        return None
    url = f"ableton://{main}"
    if clip_visible:
        url += "/clip"
    elif device_visible:
        url += "/device"
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
    context, so the host stops showing the view's set when the script stops."""
    body = {"app": APP, "url": url, "focused": bool(focused)}
    if pid is not None:
        body["pid"] = int(pid)
    if input_age is not None:
        body["input_age"] = round(max(0.0, float(input_age)), 1)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


def http_request(port, body) -> bytes:
    """The complete HTTP/1.1 request for one report."""
    head = (f"POST /report HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{int(port)}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n")
    return head.encode("ascii") + body


def load_settings(folder):
    """(port, token) from the optional ``settings.json`` in the script folder.

    The file is the user's: ``{"port": 50164, "token": "..."}``, both keys
    optional. A missing or unreadable file gives the defaults."""
    port, token = DEFAULT_PORT, ""
    try:
        with open(os.path.join(folder, SETTINGS_FILE), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return port, token
    if isinstance(data, dict):
        p = data.get("port")
        if isinstance(p, int) and not isinstance(p, bool) and 0 < p < 65536:
            port = p
        t = data.get("token")
        if isinstance(t, str):
            token = t
    return port, token


# connect_ex() answers on a non-blocking socket: "in progress" on POSIX,
# WSAEWOULDBLOCK (10035) on Windows.
_IN_PROGRESS = {0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EAGAIN, 10035}


class Sender:
    """Delivers the LATEST report over a non-blocking socket, one step per
    `pump()`; an older pending report is replaced, never queued.

    `submit()` only stores. `pump(now)` is called from Live's tick and never
    waits: connect, send, read the status line, close, each when `select()`
    with timeout 0 says the socket is ready. Failures are silent apart from
    one log line per distinct error; the next change or keep-alive retries."""

    def __init__(self, log=None, sock_factory=None, select_fn=None,
                 timeout_s=EXCHANGE_TIMEOUT_S):
        self._log = log or (lambda _msg: None)
        self._sock_factory = sock_factory or (lambda: socket.socket(socket.AF_INET,
                                                                     socket.SOCK_STREAM))
        self._select = select_fn or select.select
        self._timeout_s = timeout_s
        self._pending = None      # (port, request bytes)
        self._job = None          # the exchange in progress
        self._seen = set()
        self.delivered = 0        # exchanges that got a 2xx (for tests and logs)

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        self._pending = (int(port), http_request(port, payload(url, token, pid,
                                                               input_age, focused)))

    @property
    def busy(self) -> bool:
        return self._job is not None or self._pending is not None

    def pump(self, now):
        """Advance the current exchange by at most one step; start the
        pending one when none is running. Never raises, never blocks."""
        try:
            if self._job is None:
                if self._pending is None:
                    return
                port, data = self._pending
                self._pending = None
                self._start(port, data, now)
                return
            if now - self._job["t0"] > self._timeout_s:
                self._fail("timed out")
                return
            self._step()
        except Exception as e:  # noqa: BLE001 -- a report must never break Live
            self._fail(f"{type(e).__name__}: {e}")

    def flush(self, clock, timeout_s=FLUSH_TIMEOUT_S, wait=None):
        """Drive the exchange to its end, for at most `timeout_s`. Only for
        disconnect(), where Live is closing the script anyway: the last
        report withdraws the view, and a loopback exchange takes milliseconds.
        `wait(seconds)` sleeps between steps (default: select on nothing)."""
        wait = wait or (lambda s: self._select([], [], [], s))
        end = clock() + timeout_s
        while self.busy and clock() < end:
            self.pump(clock())
            if self.busy:
                wait(0.005)
        if self._job is not None:
            self._close()

    # --- the exchange ---------------------------------------------------

    def _start(self, port, data, now):
        sock = self._sock_factory()
        sock.setblocking(False)
        self._job = {"sock": sock, "data": data, "sent": 0, "reply": b"",
                     "connected": False, "t0": now}
        rc = sock.connect_ex(("127.0.0.1", port))
        if rc not in _IN_PROGRESS:
            self._fail(f"connect: {os.strerror(rc) if isinstance(rc, int) else rc}")

    def _step(self):
        job = self._job
        sock = job["sock"]
        if job["sent"] < len(job["data"]):
            _r, w, x = self._select([], [sock], [sock], 0)
            if x:
                self._fail("connect failed")
                return
            if not w:
                return
            if not job["connected"]:
                err = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if err:
                    self._fail(f"connect: {os.strerror(err)}")
                    return
                job["connected"] = True
            try:
                job["sent"] += sock.send(job["data"][job["sent"]:])
            except (BlockingIOError, InterruptedError):
                # The socket buffer is full: send the rest on the next tick.
                pass
            return
        r, _w, _x = self._select([sock], [], [], 0)
        if not r:
            return
        try:
            chunk = sock.recv(4096)
        except (BlockingIOError, InterruptedError):
            return
        job["reply"] += chunk
        if b"\r\n" in job["reply"] or not chunk:
            self._finish(job["reply"])

    def _finish(self, reply):
        status = reply.split(b"\r\n", 1)[0].split(b" ")
        if len(status) >= 2 and status[1][:1] == b"2":
            self.delivered += 1
            self._close()
        else:
            self._fail("HTTP " + b" ".join(status[1:]).decode("latin-1", "replace")
                       if len(status) >= 2 else "no reply")

    def _fail(self, why):
        if why not in self._seen:
            self._seen.add(why)
            self._log(f"PolyKybd: report not delivered: {why}")
        self._close()

    def _close(self):
        job, self._job = self._job, None
        if job is not None:
            try:
                job["sock"].close()
            except OSError:
                # The socket is already closed or broken; nothing to release.
                pass
