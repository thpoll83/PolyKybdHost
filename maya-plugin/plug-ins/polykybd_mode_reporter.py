# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Mode Reporter: a Maya Python plug-in (Maya Python API 2.0).

Tells PolyKybdHost which kind of panel is under the mouse pointer in Maya (or,
when the pointer is over no panel, the panel with focus) and the selection mode
(object / component), so the keyboard shows the keys of the Graph Editor, the
Time Editor, the UV Editor, the Node Editor or the Hypershade while you work in
one of them.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "maya", "url": "maya://graph/object", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

No scene, file, node or object names and no window titles. The host routes on
the URL tokens alone.

The top half of this file (down to "Maya glue") does not import Maya and is
unit-tested by the host's suite (tests/maya_plugin/). The Maya glue imports
``maya.cmds`` and PySide only inside functions, so this file imports without
Maya.

Settings: environment variables read when the plug-in loads.

- ``POLYKYBD_REPORT_PORT``: PolyKybdHost's ``browser_report_port`` (default 50164).
- ``POLYKYBD_REPORT_TOKEN``: only if PolyKybdHost has ``browser_report_token`` set.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.request

APP = "maya"
VERSION = "1.0.0"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S),
# so the plug-in re-sends its context well inside that window.
KEEPALIVE_S = 3.0
POLL_MS = 250                 # how often the main-thread timer looks for a change
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; Maya's UI never waits

# Panel kind tokens. `getPanel(typeOf=...)` names the built-in panel types;
# every editor below that is a scripted panel is named by its scripted panel
# type (`scriptedPanel(q=True, type=True)`).
PANEL_TYPES = {
    "modelPanel": "model",
    "outlinerPanel": "outliner",
}
SCRIPTED_TYPES = {
    "graphEditor": "graph",
    "dopeSheetPanel": "dopesheet",
    "timeEditorPanel": "timeeditor",
    "polyTexturePlacementPanel": "uv",
    "nodeEditorPanel": "node",
    "hyperShadePanel": "hypershade",
    "outlinerPanel": "outliner",
}
OTHER = "other"
SELECT_MODES = ("object", "component", "hierarchy")

_TRAILING_DIGITS = re.compile(r"\d+$")


def panel_kind(panel_type, scripted_type=None, panel_name=None) -> str:
    """The URL token of a panel.

    ``panel_type`` is ``getPanel(typeOf=panel)``, ``scripted_type`` the
    scripted panel type when ``panel_type`` is ``scriptedPanel``. When the
    type is unknown, the panel name without its trailing number is tried
    (Maya names the default panels after their type: ``graphEditor1``)."""
    if panel_type in PANEL_TYPES:
        return PANEL_TYPES[panel_type]
    if panel_type == "scriptedPanel" and scripted_type in SCRIPTED_TYPES:
        return SCRIPTED_TYPES[scripted_type]
    if isinstance(panel_name, str):
        stem = _TRAILING_DIGITS.sub("", panel_name)
        if stem in SCRIPTED_TYPES:
            return SCRIPTED_TYPES[stem]
        if stem in PANEL_TYPES:
            return PANEL_TYPES[stem]
    return OTHER


def select_mode(object_mode, component_mode, hierarchical=False) -> str:
    """The URL token of the selection mode (``selectMode`` queries)."""
    if component_mode:
        return "component"
    if object_mode:
        return "object"
    if hierarchical:
        return "hierarchy"
    return OTHER


def context_url(kind, mode) -> str | None:
    """``maya://<panel kind>/<selection mode>``, or None for an unknown token.

    Only tokens from the closed sets above are sent, so nothing Maya returns
    (a panel name, a user-defined panel type) can reach the report."""
    kinds = set(PANEL_TYPES.values()) | set(SCRIPTED_TYPES.values()) | {OTHER}
    if kind not in kinds or mode not in (*SELECT_MODES, OTHER):
        return None
    return f"maya://{kind}/{mode}"


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
    context, so the host stops showing its mode when the plug-in unloads."""
    body = {"app": APP, "url": url, "focused": bool(focused)}
    if pid is not None:
        body["pid"] = int(pid)
    if input_age is not None:
        body["input_age"] = round(max(0.0, float(input_age)), 1)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


def settings(env=None):
    """(port, token) from the environment; a bad port falls back to the default."""
    env = os.environ if env is None else env
    try:
        port = int(env.get("POLYKYBD_REPORT_PORT", DEFAULT_PORT))
        if not 0 < port < 65536:
            raise ValueError(port)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return port, env.get("POLYKYBD_REPORT_TOKEN", "") or ""


class Sender:
    """One daemon thread POSTing the LATEST report; older pending ones are dropped.

    `submit()` only stores and signals, so Maya's main thread never touches the
    network. Failures are silent: the next change or keep-alive retries. Each
    distinct error is printed once to the Script Editor."""

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

    def stop(self, wait_s=0.0):
        """Stop the thread after it delivers the report still pending (the
        withdrawal sent on unload). Waits up to ``wait_s`` for it."""
        self._stop = True
        self._wake.set()
        if wait_s:
            self._thread.join(wait_s)

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
                        print(f"PolyKybd Mode Reporter: report not delivered: "
                              f"{type(e).__name__}: {e}", file=sys.stderr)


def _http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never go through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()


# --- Maya glue ---------------------------------------------------------------
# Everything below runs inside Maya, on its main thread.

def maya_useNewAPI():   # noqa: N802 -- the name Maya looks for
    """Tells Maya this plug-in uses the Python API 2.0."""


def _qt():
    """(QtCore, QtGui) from the PySide Maya ships: PySide6 since Maya 2025,
    PySide2 before."""
    try:
        from PySide6 import QtCore, QtGui
    except ImportError:
        from PySide2 import QtCore, QtGui
    return QtCore, QtGui


def _current_url(cmds):
    """The context URL from Maya's state, or None if a query fails."""
    try:
        panel = cmds.getPanel(underPointer=True) or cmds.getPanel(withFocus=True)
        kind = OTHER
        if panel:
            ptype = cmds.getPanel(typeOf=panel)
            stype = None
            if ptype == "scriptedPanel":
                stype = cmds.scriptedPanel(panel, query=True, type=True)
            kind = panel_kind(ptype, stype, panel)
        mode = select_mode(cmds.selectMode(query=True, object=True),
                           cmds.selectMode(query=True, component=True),
                           cmds.selectMode(query=True, hierarchical=True))
    except Exception:   # noqa: BLE001 -- a panel can disappear between queries
        return None
    return context_url(kind, mode)


class _Reporter:
    """The timer, the scriptJobs and the sender of one loaded plug-in."""

    def __init__(self):
        import maya.cmds as cmds
        QtCore, QtGui = _qt()
        self._cmds = cmds
        self._QtGui = QtGui
        self._port, self._token = settings()
        self._sender = Sender()
        self._policy = SendPolicy()
        self._last_input = time.monotonic()
        self._last_cursor = None
        self._jobs = [
            cmds.scriptJob(event=["SelectModeChanged", self.tick]),
            cmds.scriptJob(event=["SelectTypeChanged", self.tick]),
            cmds.scriptJob(event=["quitApplication", self.withdraw]),
        ]
        self._timer = QtCore.QTimer()
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.tick)
        self._timer.start()

    def _input_age(self, now):
        # The pointer moving counts as input. A key press with a still
        # pointer is not seen; the context change it causes is (below).
        try:
            pos = self._QtGui.QCursor.pos()
            cur = (pos.x(), pos.y())
        except Exception:   # noqa: BLE001
            cur = None
        if cur != self._last_cursor:
            self._last_cursor = cur
            self._last_input = now
        return now - self._last_input

    def tick(self):
        now = time.monotonic()
        age = self._input_age(now)
        url = _current_url(self._cmds)
        if url is not None and url != self._policy.last_url:
            self._last_input = now
            age = 0.0
        if self._policy.due(url, now):
            self._sender.submit(self._port, url, self._token, os.getpid(), age)
            self._policy.sent(url, now)

    def withdraw(self):
        self._sender.submit(self._port, None, self._token, os.getpid(), None,
                            focused=False)

    def close(self):
        self._timer.stop()
        for job in self._jobs:
            try:
                if self._cmds.scriptJob(exists=job):
                    self._cmds.scriptJob(kill=job, force=True)
            except Exception:   # noqa: BLE001
                pass
        self.withdraw()
        self._sender.stop(wait_s=HTTP_TIMEOUT_S)


_reporter = None


def initializePlugin(plugin):   # noqa: N802 -- Maya entry point
    import maya.api.OpenMaya as om
    om.MFnPlugin(plugin, "PolyKybd", VERSION, "Any")
    global _reporter
    if _reporter is None:
        _reporter = _Reporter()


def uninitializePlugin(plugin):   # noqa: N802 -- Maya entry point
    global _reporter
    if _reporter is not None:
        _reporter.close()
        _reporter = None
