# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt-free half of the PolyKybd Mode Reporter for Binary Ninja (unit-tested by
the host suite).

Everything here runs without Binary Ninja: building the pseudo-URL from the
view type and the IL level, deciding when to send, and the sender thread.
`__init__.py` is the thin `binaryninjaui` glue around it.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "binaryninja", "url": "binaryninja://graph/hlil", "focused": true,
     "pid": 4242, "input_age": 0.0, "token": "<only if one is configured>"}

The URL is ``binaryninja://<view>[/<il>]``:

- ``<view>`` is the view type of the focused pane: ``linear``, ``graph``,
  ``hex``, ``bytes`` or ``triage``. Every other view type (a plugin's own
  view, the types view, ...) is sent as ``other``, so a plugin's view name is
  never sent.
- ``<il>`` is the IL level, only for ``linear`` and ``graph``: ``disasm``,
  ``llil``, ``lifted``, ``llil_ssa``, ``mlil``, ``mlil_ssa``, ``mapped_mlil``,
  ``mapped_mlil_ssa``, ``hlil``, ``hlil_ssa``, or ``pseudo_c`` /
  ``pseudo_rust`` / ``pseudo_python`` (``pseudo`` for another language).

No file name, address, function name or window title. Keep it that way: the
host routes on these tokens alone.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

APP = "binaryninja"
SCHEME = "binaryninja://"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than its freshness window (browser_url.py
# DEFAULT_MAX_AGE_S = 8 s), so the plugin re-sends its context on a keep-alive
# well inside that window: two lost keep-alives still leave the report fresh.
KEEPALIVE_S = 3.0
POLL_S = 0.5                  # the timer that reads the focused pane
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; the UI never waits

# The first part of ViewFrame.getCurrentView() ("Linear:ELF", "Hex:Raw").
_VIEWS = {"linear": "linear", "graph": "graph", "hex": "hex", "bytes": "bytes",
          "triage": "triage"}
# Views that show code at an IL level.
IL_VIEWS = frozenset({"linear", "graph"})

# BNFunctionGraphType (binaryninjacore.h) by value and by enum name.
_IL_BY_VALUE = {
    0: "disasm", 1: "llil", 2: "lifted", 3: "llil_ssa", 4: "mlil", 5: "mlil_ssa",
    6: "mapped_mlil", 7: "mapped_mlil_ssa", 8: "hlil", 9: "hlil_ssa", 10: "pseudo",
}
_IL_BY_NAME = {
    "NormalFunctionGraph": 0, "LowLevelILFunctionGraph": 1, "LiftedILFunctionGraph": 2,
    "LowLevelILSSAFormFunctionGraph": 3, "MediumLevelILFunctionGraph": 4,
    "MediumLevelILSSAFormFunctionGraph": 5, "MappedMediumLevelILFunctionGraph": 6,
    "MappedMediumLevelILSSAFormFunctionGraph": 7, "HighLevelILFunctionGraph": 8,
    "HighLevelILSSAFormFunctionGraph": 9, "HighLevelLanguageRepresentationFunctionGraph": 10,
}
# The language names Binary Ninja ships for the decompiler output.
_PSEUDO = {"pseudo c": "pseudo_c", "pseudo rust": "pseudo_rust",
           "pseudo python": "pseudo_python"}


def view_token(view_name) -> str | None:
    """``linear``, ``graph``, ``hex``, ``bytes``, ``triage`` or ``other`` for a
    ``getCurrentView()`` string, None when there is no view."""
    if not isinstance(view_name, str) or not view_name.strip():
        return None
    head = view_name.split(":", 1)[0].strip().lower()
    return _VIEWS.get(head, "other")


def _graph_type_value(value):
    """The BNFunctionGraphType number of an enum member, an int or a name."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    name = getattr(value, "name", None)
    if isinstance(name, str) and name in _IL_BY_NAME:
        return _IL_BY_NAME[name]
    if isinstance(value, str):
        return _IL_BY_NAME.get(value.split(".")[-1])
    inner = getattr(value, "value", None)
    if isinstance(inner, int) and not isinstance(inner, bool):
        return inner
    return None


def il_token(il) -> str | None:
    """The IL level token of what ``View.getILViewType()`` returns, or None.

    Accepts the Python ``FunctionViewType`` (``view_type`` + ``name``), the
    core struct shape (``type`` + ``name``), a ``FunctionGraphType`` member or
    a plain int."""
    if il is None:
        return None
    lang = None
    if hasattr(il, "view_type"):
        lang, il = getattr(il, "name", None), il.view_type
    elif hasattr(il, "type") and not isinstance(il, (int, str)):
        lang, il = getattr(il, "name", None), il.type
    value = _graph_type_value(il)
    token = _IL_BY_VALUE.get(value)
    if token == "pseudo":
        if isinstance(lang, bytes):
            lang = lang.decode("utf-8", "replace")
        key = lang.strip().lower() if isinstance(lang, str) else "pseudo c"
        return _PSEUDO.get(key, "pseudo")
    return token


def context_url(view_name, il=None) -> str | None:
    """``binaryninja://<view>[/<il>]``, or None when no view is shown."""
    view = view_token(view_name)
    if view is None:
        return None
    url = SCHEME + view
    level = il_token(il) if view in IL_VIEWS else None
    if level:
        url += "/" + level
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
    context, so the host stops showing its view's overlay at once."""
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

    `submit()` only stores and signals, so the caller (the Qt main thread)
    never touches the network. Failures are silent apart from one line per
    distinct error: the next change or keep-alive retries."""

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
        """Stop the thread after it delivers the report still pending, if any
        (the withdrawal sent at exit). Waits at most ``wait_s`` for it."""
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
    # No proxy: a loopback report must never be routed through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()
