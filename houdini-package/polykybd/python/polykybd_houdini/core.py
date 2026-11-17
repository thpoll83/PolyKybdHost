# SPDX-License-Identifier: GPL-3.0-or-later
"""hou-free half of the PolyKybd context reporter for Houdini (unit-tested by
the host suite, tests/houdini_package/reporter_core_test.py).

Everything here runs without Houdini: building the pseudo-URL from the pane
type and the network type category, deciding when to send, and the sender
thread. `__init__.py` is the thin `hou` glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "houdini", "url": "houdini://network/sop", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

The URL names the type of the pane under the mouse pointer (Houdini sends a
hotkey to that pane) and the type category of the network that pane shows
(`hou.NodeTypeCategory.name()`: Object, Sop, Dop, ...). No node path, node
name, file name or scene content -- keep it that way; the host routes on these
tokens alone.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

APP = "houdini"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S),
# so a keep-alive goes out well inside that window: two lost keep-alives still
# leave the report fresh.
KEEPALIVE_S = 3.0
POLL_S = 0.2                  # how often the event-loop callback looks for a change
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; Houdini's UI never waits

# hou.paneTabType value names -> URL token. A pane type not listed here is
# sent as "other": its keys are the global ones.
PANE_TOKENS = {
    "SceneViewer": "scene",
    "NetworkEditor": "network",
    "Parm": "parms",
    "ChannelEditor": "anim",
    "Textport": "textport",
    "PythonShell": "python",
    "TreeView": "tree",
    "DetailsView": "details",
    "MaterialPalette": "material",
    "CompositorViewer": "compositor",
    "ChannelList": "channels",
}
OTHER_PANE = "other"

# hou.NodeTypeCategory names of the network a pane shows -> URL token.
# Cop2 is the old compositing network, Cop the Copernicus one (Houdini 20.5+).
CONTEXT_TOKENS = {
    "Object": "obj",
    "Sop": "sop",
    "Dop": "dop",
    "Vop": "vop",
    "Lop": "lop",
    "Cop": "cop",
    "Cop2": "cop",
    "Chop": "chop",
    "Top": "top",
    "Driver": "rop",
    "Shop": "shop",
    "Manager": "mgr",
}


def context_url(pane_type, category=None) -> str | None:
    """`houdini://<pane>[/<context>]`, or None when no pane is known.

    `pane_type` is the name of a `hou.paneTabType` value (`"NetworkEditor"`),
    `category` the name of the type category of the network the pane shows
    (`"Sop"`), or None for a pane that shows no network."""
    if not pane_type:
        return None
    pane = PANE_TOKENS.get(str(pane_type), OTHER_PANE)
    ctx = CONTEXT_TOKENS.get(str(category or ""))
    return f"houdini://{pane}/{ctx}" if ctx else f"houdini://{pane}"


class InputClock:
    """When this Houdini last saw the user move the mouse or change pane.

    Houdini's Python API has no input event hook, so the glue feeds the mouse
    position on every poll; a move counts as input. Key presses without a
    mouse move are not seen (README)."""

    def __init__(self):
        self.last_pos = None
        self.last_input = None

    def feed(self, pos, now, changed=False):
        if pos is not None and pos != self.last_pos:
            if self.last_pos is not None or self.last_input is None:
                self.last_input = now
            self.last_pos = pos
        if changed:
            self.last_input = now

    def age(self, now):
        return None if self.last_input is None else max(0.0, now - self.last_input)


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
    context, so the host stops showing its pane's keys at once."""
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

    `submit()` only stores and signals, so the caller -- Houdini's UI thread --
    never touches the network. Failures are silent: the next change or
    keep-alive retries. Each distinct error is printed once."""

    def __init__(self, post=None):
        self._post = post or http_post
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
        """Stop the thread after it delivers the report still pending, if any."""
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
                except Exception as e:   # noqa: BLE001 -- the thread must survive
                    key = (type(e).__name__, str(e))
                    if key not in self._seen:
                        self._seen.add(key)
                        print(f"PolyKybd reporter: report not delivered: "
                              f"{type(e).__name__}: {e}", file=sys.stderr)


def http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never be routed through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()


def settings(env):
    """(enabled, port, token) from the environment the package file sets:
    POLYKYBD_REPORT ("0" turns reporting off), POLYKYBD_REPORT_PORT and
    POLYKYBD_REPORT_TOKEN. A port that is not a number in range is the
    default."""
    enabled = str(env.get("POLYKYBD_REPORT", "1")).strip().lower() not in ("0", "false", "off", "no")
    try:
        port = int(env.get("POLYKYBD_REPORT_PORT") or DEFAULT_PORT)
        if not 0 < port < 65536:
            port = DEFAULT_PORT
    except ValueError:
        port = DEFAULT_PORT
    return enabled, port, str(env.get("POLYKYBD_REPORT_TOKEN") or "")
