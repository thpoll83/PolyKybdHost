# SPDX-License-Identifier: GPL-3.0-or-later
"""FreeCAD-free half of the PolyKybd context reporter (unit-tested by the host suite).

Everything here runs without FreeCAD or Qt: turning the workbench name into the
pseudo-URL, deciding when to send, and the sender thread.
`polykybd_freecad_gui.py` is the thin FreeCAD glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "freecad", "url": "freecad://sketcher", "focused": true,
     "pid": 4242, "input_age": 0.0, "token": "<only if one is configured>"}

The URL names the active workbench, as one token of a closed list
(`WORKBENCHES`). A workbench that is not on the list (an add-on workbench) is
sent as `freecad://other`, so no add-on name leaves FreeCAD. No file name,
document or object name, no window title.

`input_age` is 0 while FreeCAD is the active application, else the seconds
since it stopped being active. With several FreeCADs open, the host follows
the one with the most recent input, which is then the one in front.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

APP = "freecad"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than its freshness window (8 s), so the
# add-on re-sends its context on a keep-alive well inside that window.
KEEPALIVE_S = 3.0
POLL_S = 0.5                  # how often the Qt timer looks for a change
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; FreeCAD's UI never waits

# FreeCAD 1.1's built-in workbenches: the name `Gui.activeWorkbench().name()`
# and the main window's `workbenchActivated` signal give (the class name the
# workbench is registered under) -> the token sent. Tokens are lower case and
# stable; the host routes on them.
WORKBENCHES = {
    "AssemblyWorkbench": "assembly",
    "BIMWorkbench": "bim",
    "CAMWorkbench": "cam",
    "CloudWorkbench": "cloud",
    "DraftWorkbench": "draft",
    "FemWorkbench": "fem",
    "InspectionWorkbench": "inspection",
    "MaterialWorkbench": "material",
    "MeshWorkbench": "mesh",
    "MeshPartWorkbench": "meshpart",
    "NoneWorkbench": "none",
    "OpenSCADWorkbench": "openscad",
    "PartDesignWorkbench": "partdesign",
    "PartWorkbench": "part",
    "PointsWorkbench": "points",
    "ReverseEngineeringWorkbench": "reverseengineering",
    "RobotWorkbench": "robot",
    "SketcherWorkbench": "sketcher",
    "SpreadsheetWorkbench": "spreadsheet",
    "SurfaceWorkbench": "surface",
    "TechDrawWorkbench": "techdraw",
    "TestWorkbench": "test",
}
OTHER = "other"


def context_url(workbench) -> str | None:
    """`freecad://<token>` for a workbench name, or None when there is none."""
    name = str(workbench or "").strip()
    if not name:
        return None
    return f"freecad://{WORKBENCHES.get(name, OTHER)}"


class SendPolicy:
    """Send on a change of URL or focus, plus a keep-alive while nothing changes."""

    def __init__(self, keepalive_s=KEEPALIVE_S):
        self.keepalive_s = keepalive_s
        self.last = None
        self.last_sent = None

    def due(self, url, focused, now) -> bool:
        if url is None:
            return False
        if (url, bool(focused)) != self.last or self.last_sent is None:
            return True
        return now - self.last_sent >= self.keepalive_s

    def sent(self, url, focused, now):
        self.last = (url, bool(focused))
        self.last_sent = now


def payload(url, token="", pid=None, input_age=None, focused=True) -> bytes:
    """One report. ``focused=False`` with no URL withdraws this instance's
    context, so the host stops showing its workbench at once."""
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

    `submit()` only stores and signals, so the caller -- FreeCAD's GUI thread --
    never touches the network. Failures are silent apart from one line per
    distinct error: the next change or keep-alive retries."""

    def __init__(self, post=None, log=None):
        self._post = post or http_post
        self._log = log or (lambda msg: print(msg, file=sys.stderr))
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
        """Stop the thread after it delivers the report still pending, if any.
        ``wait_s`` > 0 waits that long for it (at exit, so the withdrawal is
        sent before the process ends)."""
        self._stop = True
        self._wake.set()
        if wait_s > 0:
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
                        self._log(f"PolyKybd: report not delivered: {type(e).__name__}: {e}")


def http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never be routed through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()
