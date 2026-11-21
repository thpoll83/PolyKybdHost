# SPDX-License-Identifier: GPL-3.0-or-later
"""Jupyter-free half of the server extension (unit-tested by the host suite).

The page posts ``{url, focused, input_age}`` to its own Jupyter server; this
module checks it and forwards ONE report to PolyKybdHost's loopback receiver::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "jupyter", "url": "jupyter://notebook/edit", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

``pid`` is the Jupyter server's process id. Only the six URLs in ``URLS`` pass:
the page cannot make the server send anything else to the host.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request

APP = "jupyter"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; no request handler waits

URLS = frozenset({
    "jupyter://notebook/command",
    "jupyter://notebook/edit",
    "jupyter://editor",
    "jupyter://console",
    "jupyter://terminal",
    "jupyter://other",
})

PORT_ENV = "POLYKYBD_REPORT_PORT"
TOKEN_ENV = "POLYKYBD_REPORT_TOKEN"


def settings(config=None, environ=None):
    """``(port, token)``: the environment first, then the Jupyter config
    (``c.PolyKybdReporter.port`` / ``.token``), then the defaults."""
    environ = os.environ if environ is None else environ
    config = config or {}
    port, token = config.get("port", DEFAULT_PORT), config.get("token", "")
    if environ.get(PORT_ENV):
        port = environ[PORT_ENV]
    if environ.get(TOKEN_ENV):
        token = environ[TOKEN_ENV]
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    if not 0 < port < 65536:
        port = DEFAULT_PORT
    return port, str(token or "")


def payload(data, pid=None, token=""):
    """The report for the host as bytes, or None when ``data`` (the page's
    JSON body) is not a valid report. A report that is not focused withdraws
    this server's context: it is sent with no URL."""
    if not isinstance(data, dict):
        return None
    focused = data.get("focused") is True
    url = data.get("url")
    if focused:
        if not isinstance(url, str) or url not in URLS:
            return None
    else:
        url = None
    body = {"app": APP, "url": url, "focused": focused}
    if pid is not None:
        body["pid"] = int(pid)
    age = data.get("input_age")
    if isinstance(age, (int, float)) and not isinstance(age, bool) and age >= 0:
        body["input_age"] = round(min(float(age), 10**6), 1)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


class Sender:
    """One daemon thread POSTing the LATEST report; older pending ones are
    dropped. ``submit()`` only stores and signals, so the server's event loop
    never waits on the network. Failures are silent: the page's next change
    or keep-alive tries again."""

    def __init__(self, post=None):
        self._post = post or _http_post
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._seen = set()
        self._thread = threading.Thread(target=self._run, name="polykybd-reporter",
                                        daemon=True)
        self._thread.start()

    def submit(self, port, body):
        with self._lock:
            self._pending = (int(port), body)
        self._wake.set()

    def _run(self):
        while True:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                job, self._pending = self._pending, None
            if job is None:
                continue
            try:
                self._post(*job)
            except Exception as e:   # noqa: BLE001 -- the thread must survive
                # Once per distinct error, so a wrong port or token (HTTP 403)
                # shows in the server log without a line every keep-alive.
                key = (type(e).__name__, str(e))
                if key not in self._seen:
                    self._seen.add(key)
                    print(f"polykybd_jupyterlab: report not delivered: "
                          f"{type(e).__name__}: {e}", file=sys.stderr)


def _http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never go through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()
