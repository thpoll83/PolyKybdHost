# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd context reporter for IDA Pro, IDA Home and IDA Free.

Tells the local PolyKybdHost which kind of IDA widget has the focus
(disassembly text or graph, pseudocode, hex view, local types, a list, ...), so
the keyboard's keycaps show the shortcuts of that view. See README.md.

What is sent, and nothing else::

    POST http://127.0.0.1:<port>/report      Content-Type: application/json
    {"app": "ida", "url": "ida://pseudocode", "focused": true,
     "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}

The URL is built from the widget TYPE only (``get_widget_type``). No address,
function name, file name, database content or window title is read or sent.

The top half of this file needs no IDA (the host's test suite imports it);
the IDA glue is defined only when ``ida_idaapi`` can be imported.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.request

APP = "ida"
DEFAULT_PORT = 50164          # PolyKybdHost `browser_report_port`
# The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S)
# and this plugin cannot tell the host that IDA lost OS focus, so it sends its
# view again on a keep-alive well inside that window.
KEEPALIVE_S = 3.0
POLL_MS = 250                 # how often the timer looks for a change (cheap)
HTTP_TIMEOUT_S = 0.5          # on the SENDER thread; IDA's UI never waits
CONFIG_NAME = "polykybd.json"  # optional, in the IDA user directory

# Views whose keys differ (the host routes these), then groups of the rest.
VIEW_DISASM = "disasm"
VIEW_PSEUDOCODE = "pseudocode"
VIEW_HEX = "hex"
VIEW_TYPES = "types"
VIEW_LIST = "list"
VIEW_OUTPUT = "output"
VIEW_CLI = "cli"
VIEW_OTHER = "other"

# Sub-token of the disassembly view, from get_view_renderer_type().
RENDER_TEXT = "text"
RENDER_GRAPH = "graph"
RENDER_PROXIMITY = "proximity"

# BWN_* constant names (ida_kernwin) -> view. Read with getattr: IDA 9 removed
# BWN_STRUCTS and BWN_ENUMS (both are part of Local types there) and added
# BWN_TICSR; a name the running IDA does not have is skipped.
BWN_VIEWS = {
    "BWN_DISASM": VIEW_DISASM,
    "BWN_PSEUDOCODE": VIEW_PSEUDOCODE,
    "BWN_HEXVIEW": VIEW_HEX,
    "BWN_TICSR": VIEW_TYPES,
    "BWN_TILVIEW": VIEW_TYPES,
    "BWN_LOCTYPS": VIEW_TYPES,
    "BWN_TIL_VIEW": VIEW_TYPES,
    "BWN_STRUCTS": VIEW_TYPES,      # IDA 8 and older
    "BWN_ENUMS": VIEW_TYPES,        # IDA 8 and older
    "BWN_OUTPUT": VIEW_OUTPUT,
    "BWN_CLI": VIEW_CLI,
}
for _name in ("BWN_CHOOSER", "BWN_FUNCS", "BWN_NAMES", "BWN_STRINGS", "BWN_SEGS",
              "BWN_SEGREGS", "BWN_SELS", "BWN_SIGNS", "BWN_TILS", "BWN_IMPORTS",
              "BWN_EXPORTS", "BWN_XREFS", "BWN_CALLS", "BWN_CALLS_CALLERS",
              "BWN_CALLS_CALLEES", "BWN_BPTS", "BWN_THREADS", "BWN_MODULES",
              "BWN_TRACE", "BWN_CALL_STACK", "BWN_PROBS", "BWN_BOOKMARKS",
              "BWN_SEARCH", "BWN_TILIST", "BWN_LOCALS", "BWN_WATCH", "BWN_ADDRWATCH",
              "BWN_UNDOHIST", "BWN_SNIPPETS"):
    BWN_VIEWS[_name] = VIEW_LIST
del _name

_VIEWS = frozenset({VIEW_DISASM, VIEW_PSEUDOCODE, VIEW_HEX, VIEW_TYPES, VIEW_LIST,
                    VIEW_OUTPUT, VIEW_CLI, VIEW_OTHER})
_RENDERS = frozenset({RENDER_TEXT, RENDER_GRAPH, RENDER_PROXIMITY})


def type_table(module) -> dict:
    """``{widget type value: view}`` for the BWN_* constants ``module`` has."""
    table = {}
    for name, view in BWN_VIEWS.items():
        value = getattr(module, name, None)
        if isinstance(value, int) and value not in table:
            table[value] = view
    return table


def view_for(widget_type, table) -> str | None:
    """The view token for a widget type; None when there is no widget."""
    if widget_type is None:
        return None
    return table.get(widget_type, VIEW_OTHER)


def context_url(view, render=None) -> str | None:
    """``ida://<view>[/<render>]``, or None when no widget has the focus.

    ``render`` (text, graph, proximity) is appended for the disassembly view
    only. Anything not in the fixed token sets is dropped, never sent."""
    if view not in _VIEWS:
        return None
    url = f"ida://{view}"
    if view == VIEW_DISASM and render in _RENDERS:
        url += f"/{render}"
    return url


def render_token(renderer_type, module) -> str | None:
    """text / graph / proximity for a TCCRT_* value of ``module``."""
    for name, token in (("TCCRT_FLAT", RENDER_TEXT), ("TCCRT_GRAPH", RENDER_GRAPH),
                        ("TCCRT_PROXIMITY", RENDER_PROXIMITY)):
        value = getattr(module, name, None)
        if value is not None and renderer_type == value:
            return token
    return None


def read_settings(user_dir=None, env=None) -> dict:
    """``{"enabled", "port", "token"}``. Defaults, then ``polykybd.json`` in
    the IDA user directory, then the environment variables
    POLYKYBD_REPORT_PORT / POLYKYBD_REPORT_TOKEN / POLYKYBD_REPORT_DISABLED.
    A bad value keeps the default; never raises."""
    env = os.environ if env is None else env
    s = {"enabled": True, "port": DEFAULT_PORT, "token": ""}
    if user_dir:
        try:
            with open(os.path.join(user_dir, CONFIG_NAME), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            if isinstance(data.get("enabled"), bool):
                s["enabled"] = data["enabled"]
            if isinstance(data.get("port"), int) and 0 < data["port"] < 65536:
                s["port"] = data["port"]
            if isinstance(data.get("token"), str):
                s["token"] = data["token"]
    port = env.get("POLYKYBD_REPORT_PORT", "")
    if port.isdigit() and 0 < int(port) < 65536:
        s["port"] = int(port)
    if env.get("POLYKYBD_REPORT_TOKEN"):
        s["token"] = env["POLYKYBD_REPORT_TOKEN"]
    if env.get("POLYKYBD_REPORT_DISABLED", "") not in ("", "0"):
        s["enabled"] = False
    return s


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
    view, so the host leaves its overlay at once."""
    body = {"app": APP, "url": url, "focused": bool(focused)}
    if pid is not None:
        body["pid"] = int(pid)
    if input_age is not None:
        body["input_age"] = round(max(0.0, float(input_age)), 1)
    if token:
        body["token"] = token
    return json.dumps(body).encode("utf-8")


def _http_post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    # No proxy: a loopback report must never be routed through HTTP(S)_PROXY.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=HTTP_TIMEOUT_S) as r:
        r.read()


class Sender:
    """One daemon thread POSTing the LATEST report; older pending ones are
    dropped. ``submit()`` only stores and signals, so IDA's main thread never
    touches the network. Failures are printed once per distinct error and
    otherwise ignored: the next change or keep-alive retries."""

    def __init__(self, post=None):
        self._post = post or _http_post
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._stop = False
        self._seen = set()
        self._thread = threading.Thread(target=self._run, name="polykybd-ida-reporter",
                                        daemon=True)
        self._thread.start()

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        with self._lock:
            self._pending = (int(port), payload(url, token, pid, input_age, focused))
        self._wake.set()

    def stop(self, wait_s=0.0):
        """Stop the thread after it delivers the report still pending (the
        withdrawal). ``wait_s`` > 0 waits that long for it, so a last report
        sent while IDA exits is not lost with the process."""
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
                        print(f"PolyKybd: report not delivered: {type(e).__name__}: {e}",
                              file=sys.stderr)


class Reporter:
    """The state machine the IDA glue drives: ``tick(url)`` from the timer,
    ``input()`` from the UI hooks, ``withdraw()`` on unload. No IDA here."""

    def __init__(self, settings, sender, clock=time.monotonic, pid=None):
        self.settings = settings
        self.sender = sender
        self.clock = clock
        self.pid = os.getpid() if pid is None else pid
        self.policy = SendPolicy()
        self.last_input = None
        self.reported = False

    def input(self):
        self.last_input = self.clock()

    def tick(self, url):
        if not self.settings["enabled"]:
            return
        now = self.clock()
        if self.policy.due(url, now):
            age = None if self.last_input is None else now - self.last_input
            self.sender.submit(self.settings["port"], url, self.settings["token"],
                               pid=self.pid, input_age=age)
            self.policy.sent(url, now)
            self.reported = True

    def withdraw(self):
        """One last report ``url: null, focused: false``, once."""
        if not self.reported:
            return
        self.sender.submit(self.settings["port"], None, self.settings["token"],
                           pid=self.pid, focused=False)
        self.reported = False
        self.policy = SendPolicy()


# --------------------------------------------------------------------------
# IDA glue
# --------------------------------------------------------------------------

try:
    import ida_idaapi
    import ida_kernwin
except ImportError:          # imported by the host's tests, outside IDA
    ida_idaapi = ida_kernwin = None


def _ida_url(table):
    """The URL of the widget that has the focus in IDA, or None."""
    w = ida_kernwin.get_current_widget()
    if not w:
        return None
    view = view_for(ida_kernwin.get_widget_type(w), table)
    render = None
    if view == VIEW_DISASM:
        render = render_token(ida_kernwin.get_view_renderer_type(w), ida_kernwin)
    return context_url(view, render)


if ida_idaapi is not None:

    class _UiHooks(ida_kernwin.UI_Hooks):
        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        def current_widget_changed(self, widget, prev_widget):
            self.owner.on_input()

        def screen_ea_changed(self, ea, prev_ea):
            self.owner.on_input()

        def database_closed(self):
            self.owner.withdraw()

    class _ViewHooks(ida_kernwin.View_Hooks):
        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        def view_keydown(self, view, key, state):
            self.owner.on_input()

        def view_click(self, view, event):
            self.owner.on_input()

        def view_curpos(self, view):
            self.owner.on_input()

    class PolyKybdReporterMod(ida_idaapi.plugmod_t):
        """One per database (PLUGIN_MULTI): starts with the database, stops
        and withdraws its view when the database closes or IDA exits."""

        def __init__(self):
            super().__init__()
            user_dir = None
            try:
                import ida_diskio
                user_dir = ida_diskio.get_user_idadir()
            except Exception:  # noqa: BLE001 -- the defaults still work
                pass
            self.table = type_table(ida_kernwin)
            self.sender = Sender()
            self.reporter = Reporter(read_settings(user_dir), self.sender)
            self.ui_hooks = _UiHooks(self)
            self.view_hooks = _ViewHooks(self)
            self.ui_hooks.hook()
            self.view_hooks.hook()
            self.timer = ida_kernwin.register_timer(POLL_MS, self._tick)
            self.errors = set()

        def on_input(self):
            self.reporter.input()

        def _tick(self):
            try:
                self.reporter.tick(_ida_url(self.table))
            except Exception as e:  # noqa: BLE001 -- never let a report break IDA
                key = (type(e).__name__, str(e))
                if key not in self.errors:
                    self.errors.add(key)
                    print(f"PolyKybd: {type(e).__name__}: {e}")
            return POLL_MS

        def withdraw(self):
            self.reporter.withdraw()

        def run(self, arg):
            return True

        def shutdown(self):
            """Remove the timer and hooks, send the last report and stop the sender."""
            if getattr(self, "timer", None) is not None:
                ida_kernwin.unregister_timer(self.timer)
                self.timer = None
            for hooks in (getattr(self, "ui_hooks", None), getattr(self, "view_hooks", None)):
                if hooks is not None:
                    hooks.unhook()
            self.reporter.withdraw()
            self.sender.stop(wait_s=HTTP_TIMEOUT_S)

        def __del__(self):
            # IDA unloads a plugmod_t by dropping its last reference.
            self.shutdown()

    class PolyKybdReporterPlugin(ida_idaapi.plugin_t):
        flags = ida_idaapi.PLUGIN_MULTI | ida_idaapi.PLUGIN_HIDE
        comment = "Tells PolyKybdHost which IDA view has the focus"
        help = "Sends ida://<view> to 127.0.0.1; see the PolyKybdHost ida-plugin README"
        wanted_name = "PolyKybd context reporter"
        wanted_hotkey = ""

        def init(self):
            return PolyKybdReporterMod()

    def PLUGIN_ENTRY():
        return PolyKybdReporterPlugin()
