# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Context Reporter for DaVinci Resolve.

Tells the local PolyKybdHost which page DaVinci Resolve shows (Media, Cut,
Edit, Fusion, Color, Fairlight, Deliver), so the keycaps show that page's
shortcuts. See README.md next to this file.

Two ways to run it:

* **From Resolve's menu** (free and Studio): copy this file to Resolve's
  ``Fusion/Scripts/Utility`` folder and choose Workspace > Scripts >
  polykybd_context_reporter. It starts a reporter thread and returns. Run it
  again to stop that reporter.
* **As an external process** (Studio only, Preferences > System > General >
  "External scripting using" set to Local): ``python polykybd_context_reporter.py``
  with Resolve's scripting module on PYTHONPATH. It waits for Resolve and keeps
  running until Ctrl+C.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "resolve", "url": "resolve://edit", "focused": true,
     "pid": 4242, "token": "<only if one is configured>"}

No project, timeline, clip or file name. ``GetCurrentPage()`` is the only
Resolve call. The functions above ``run()`` do not touch Resolve and are
unit-tested by the PolyKybdHost suite (tests/resolve_plugin/).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request

APP = "resolve"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# Overrides without editing this file (an edited copy is no longer updated by
# PolyKybdHost): set these in the environment Resolve starts with.
PORT_ENV = "POLYKYBD_PORT"
TOKEN_ENV = "POLYKYBD_TOKEN"
# The host drops a report older than 8 s (browser_url.DEFAULT_MAX_AGE_S), and
# the script cannot see whether Resolve has OS focus, so it repeats its report
# well inside that window: two lost keep-alives still leave it fresh.
KEEPALIVE_S = 3.0
# Resolve's API has no page-change event, so the page is polled. One
# GetCurrentPage() call every 0.5 s.
POLL_S = 0.5
HTTP_TIMEOUT_S = 0.5
# Consecutive failed GetCurrentPage() calls before the reporter decides Resolve
# has gone (an external process outliving Resolve).
MAX_FAILURES = 6

# The page names GetCurrentPage() returns (README.txt of the scripting API).
PAGES = ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver")

# Shared between runs of this script inside one Resolve process, so a second
# run from the menu stops the first instead of starting a second reporter.
_REGISTRY_KEY = "_polykybd_resolve_reporter"


def page_url(page) -> str | None:
    """``resolve://<page>`` for a known page, else None (no page, the Project
    Manager, or a name a future Resolve adds: sent as nothing rather than
    guessed)."""
    p = str(page or "").strip().lower()
    return f"resolve://{p}" if p in PAGES else None


def payload(url, token="", pid=None, focused=True) -> bytes:
    """One report. ``focused=False`` with no URL withdraws the page, so the
    keyboard leaves that page's overlay when the reporter stops."""
    body = {"app": APP, "url": url, "focused": bool(focused)}
    if pid is not None:
        body["pid"] = int(pid)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


class SendPolicy:
    """Send on a change of page, plus a keep-alive while nothing changes.
    A page of None is sent once, as a withdrawal, after a page was sent."""

    def __init__(self, keepalive_s=KEEPALIVE_S):
        self.keepalive_s = keepalive_s
        self.last_url = None
        self.last_sent = None

    def due(self, url, now) -> bool:
        if url is None:
            return self.last_url is not None
        if url != self.last_url or self.last_sent is None:
            return True
        return now - self.last_sent >= self.keepalive_s

    def sent(self, url, now):
        self.last_url = url
        self.last_sent = now


def settings(env=None):
    """(port, token) from the environment, with the defaults."""
    env = os.environ if env is None else env
    try:
        port = int(env.get(PORT_ENV, "") or DEFAULT_PORT)
    except ValueError:
        port = DEFAULT_PORT
    if not 0 < port < 65536:
        port = DEFAULT_PORT
    return port, env.get(TOKEN_ENV, "") or ""


def http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never go through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()


class Reporter:
    """Polls ``get_page()`` and POSTs a report on a change and as a keep-alive.

    ``get_page`` is ``resolve.GetCurrentPage``; ``post``, ``clock`` and
    ``sleep`` are injectable for tests. Delivery errors are printed once each
    (to Resolve's Console) and otherwise ignored: the next keep-alive retries."""

    def __init__(self, get_page, port=DEFAULT_PORT, token="", pid=None,
                 post=http_post, clock=time.monotonic, sleep=None):
        self.get_page = get_page
        self.port = port
        self.token = token
        self.pid = os.getpid() if pid is None else pid
        self.post = post
        self.clock = clock
        self.stop_event = threading.Event()
        self.sleep = sleep or self.stop_event.wait
        self.policy = SendPolicy()
        self.failures = 0
        self._seen = set()

    def _send(self, url, focused=True):
        try:
            self.post(self.port, payload(url, self.token, self.pid, focused))
        except Exception as e:  # noqa: BLE001 -- a report must never stop the loop
            key = (type(e).__name__, str(e))
            if key not in self._seen:
                self._seen.add(key)
                print(f"PolyKybd: report not delivered: {key[0]}: {key[1]}",
                      file=sys.stderr)

    def step(self) -> bool:
        """One poll. Returns False when Resolve stopped answering."""
        try:
            url = page_url(self.get_page())
            self.failures = 0
        except Exception:  # noqa: BLE001 -- Resolve closed or busy
            self.failures += 1
            if self.failures >= MAX_FAILURES:
                return False
            return True
        now = self.clock()
        if self.policy.due(url, now):
            self._send(url, focused=url is not None)
            self.policy.sent(url, now)
        return True

    def withdraw(self):
        """Send ``url: null, focused: false`` once, if a page was sent."""
        if self.policy.last_url is not None:
            self._send(None, focused=False)
            self.policy = SendPolicy()

    def run(self):
        try:
            while not self.stop_event.is_set():
                if not self.step():
                    break
                self.sleep(POLL_S)
        finally:
            self.withdraw()

    def stop(self):
        self.stop_event.set()


# --- Resolve glue (not unit-tested: needs Resolve) -------------------------

def _find_resolve(namespace):
    """The Resolve object: the ``resolve`` name Resolve gives a menu script,
    then ``bmd.scriptapp``, then the external scripting module (Studio)."""
    r = namespace.get("resolve")
    if r is not None:
        return r
    for name in ("fusion", "fu", "app"):
        # The Fusion object of a menu script; GetResolve() returns Resolve.
        get = getattr(namespace.get(name), "GetResolve", None)
        if callable(get):
            try:
                r = get()
            except Exception:  # noqa: BLE001
                r = None
            if r is not None:
                return r
    bmd = namespace.get("bmd")
    if bmd is not None:
        try:
            r = bmd.scriptapp("Resolve")
        except Exception:  # noqa: BLE001
            r = None
        if r is not None:
            return r
    try:
        import DaVinciResolveScript as dvr  # noqa: N813 -- Resolve's module name
    except ImportError:
        return None
    return dvr.scriptapp("Resolve")


def _registry():
    reg = getattr(sys, _REGISTRY_KEY, None)
    if reg is None:
        reg = {}
        setattr(sys, _REGISTRY_KEY, reg)
    return reg


def _start_in_resolve(res):
    """Menu run: start the reporter thread, or stop the running one."""
    reg = _registry()
    old = reg.get("reporter")
    if old is not None and not old.stop_event.is_set():
        old.stop()
        reg.pop("reporter", None)
        print("PolyKybd: page reporting stopped.")
        return
    port, token = settings()
    rep = Reporter(res.GetCurrentPage, port, token)
    reg["reporter"] = rep
    # Not a daemon thread: if Resolve runs menu scripts in a separate process,
    # a daemon thread would end with this script.
    threading.Thread(target=rep.run, name="polykybd-resolve-reporter").start()
    print(f"PolyKybd: reporting the current page to 127.0.0.1:{port}. "
          "Run this script again to stop.")


def _run_external():
    """External process (Studio): wait for Resolve, report until Ctrl+C."""
    port, token = settings()
    print(f"PolyKybd: reporting DaVinci Resolve's page to 127.0.0.1:{port}. Ctrl+C stops.")
    while True:
        res = _find_resolve({})
        if res is None:
            time.sleep(5)
            continue
        rep = Reporter(res.GetCurrentPage, port, token)
        try:
            rep.run()
        except KeyboardInterrupt:
            rep.stop()
            return
        time.sleep(5)          # Resolve went away: wait for it again


# Names Resolve defines for a script started from its menu or Console.
_IN_RESOLVE_NAMES = {"resolve", "bmd", "fusion", "fu", "app"}


def main(namespace):
    res = _find_resolve(namespace)
    if res is not None and _IN_RESOLVE_NAMES & set(namespace):
        _start_in_resolve(res)
        return
    try:
        _run_external()
    except KeyboardInterrupt:
        # Ctrl+C is how the external process is stopped: end without a traceback.
        pass


# Resolve may run a menu script under another __name__; its injected names
# tell. A test importing this file has neither.
if __name__ == "__main__" or _IN_RESOLVE_NAMES & set(globals()):
    main(globals())
