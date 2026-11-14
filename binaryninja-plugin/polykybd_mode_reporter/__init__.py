# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Mode Reporter -- Binary Ninja UI glue.

Reports the view type (linear, graph, hex, ...) and the IL level of the
focused pane to the local PolyKybdHost, so the keycaps show the keys of that
view. See ../README.md; the wire format is in core.py.

- `UIContextNotification.OnViewChange` and `OnILViewTypeChange` read the pane
  at once when the view or the IL level changes.
- A `QTimer` (every 0.5 s, on the UI thread) reads it too: it catches a change
  that has no notification (a click into another pane) and sends the 3 s
  keep-alive. With no view open it keeps a report without a URL fresh on the
  same keep-alive. It only reads two values; the network I/O is on the sender
  thread (`core.Sender`).
"""
import json
import os
import time
import traceback

try:
    import binaryninjaui
    from binaryninja.settings import Settings
    from binaryninjaui import UIContext, UIContextNotification
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:          # headless Binary Ninja: nothing to report
    binaryninjaui = None

from . import core

_KEY_ENABLED = "polykybd.reportContext"
_KEY_PORT = "polykybd.port"
_KEY_TOKEN = "polykybd.token"
# The SendPolicy key while no view is open (the report itself has no URL).
_NO_VIEW = "binaryninja://<none>"

_state = {
    "sender": None,
    "policy": None,
    "reported": False,       # a context was sent since the last withdrawal
    "inactive_since": None,  # time.monotonic() when the app lost focus
    "errors": set(),
}


def _print_once(e):
    key = (type(e).__name__, str(e))
    if key not in _state["errors"]:
        _state["errors"].add(key)
        traceback.print_exc()


def _register_settings():
    s = Settings()
    s.register_group("polykybd", "PolyKybd")
    scopes = ["SettingsProjectScope", "SettingsResourceScope"]
    s.register_setting(_KEY_ENABLED, json.dumps({
        "title": "Report view to PolyKybdHost",
        "type": "boolean", "default": True, "ignore": scopes,
        "description": "Send the view type and IL level of the focused pane to "
                       "PolyKybdHost on this computer (127.0.0.1 only)."}))
    s.register_setting(_KEY_PORT, json.dumps({
        "title": "PolyKybdHost port",
        "type": "number", "default": core.DEFAULT_PORT, "minValue": 1, "maxValue": 65535,
        "ignore": scopes,
        "description": "PolyKybdHost's browser_report_port (default 50164)."}))
    s.register_setting(_KEY_TOKEN, json.dumps({
        "title": "PolyKybdHost token",
        "type": "string", "default": "", "ignore": scopes,
        "description": "Only if PolyKybdHost has browser_report_token set: the same value."}))


def _prefs():
    s = Settings()
    return (s.get_bool(_KEY_ENABLED), s.get_integer(_KEY_PORT) or core.DEFAULT_PORT,
            s.get_string(_KEY_TOKEN) or "")


def _current_url():
    """The pseudo-URL of the focused pane in the active window, or None."""
    ctx = UIContext.activeContext()
    frame = ctx.getCurrentViewFrame() if ctx is not None else None
    if frame is None:
        return None
    view = frame.getCurrentViewInterface()
    il = None
    if view is not None:
        try:
            il = view.getILViewType()
        except Exception:    # noqa: BLE001 -- a view without IL levels
            il = None
    return core.context_url(frame.getCurrentView(), il)


def _input_age(now):
    """0 while Binary Ninja is the active application, else the seconds since
    it lost focus. With several Binary Ninja processes open, the host follows
    the one with the smallest age."""
    since = _state["inactive_since"]
    return 0.0 if since is None else now - since


def _withdraw(port, token):
    """Tell the host this instance stopped reporting, once, so the keyboard
    leaves the view's overlay at once instead of after the 8 s freshness
    window."""
    sender = _state["sender"]
    if not _state["reported"] or sender is None:
        return
    sender.submit(port, None, token, pid=os.getpid(),
                  input_age=_input_age(time.monotonic()), focused=False)
    _state["reported"] = False
    _state["policy"] = core.SendPolicy()


def _tick():
    sender, policy = _state["sender"], _state["policy"]
    if sender is None:
        return
    try:
        enabled, port, token = _prefs()
        if not enabled:
            _withdraw(port, token)
            return
        url = _current_url()
        now = time.monotonic()
        # No view (start screen, last file closed): the report has no URL, and
        # it is kept fresh on the same keep-alive with this instance's input
        # age. One withdrawal expires after the host's 8 s window, and another
        # Binary Ninja process that still reports a view would then answer for
        # this instance's window.
        key = url if url is not None else _NO_VIEW
        if policy.due(key, now):
            sender.submit(port, url, token, pid=os.getpid(),
                          input_age=_input_age(now), focused=url is not None)
            policy.sent(key, now)
            _state["reported"] = True
    except Exception as e:   # noqa: BLE001 -- never let a report break the UI
        _print_once(e)


def _on_state_changed(state):
    try:
        from PySide6.QtCore import Qt
        active = state == Qt.ApplicationState.ApplicationActive
    except Exception:        # noqa: BLE001
        active = True
    if active:
        _state["inactive_since"] = None
    elif _state["inactive_since"] is None:
        _state["inactive_since"] = time.monotonic()


def _on_quit():
    try:
        _, port, token = _prefs()
        _withdraw(port, token)
    except Exception as e:   # noqa: BLE001
        _print_once(e)
    sender = _state["sender"]
    _state["sender"] = None
    if sender is not None:
        sender.stop(wait_s=core.HTTP_TIMEOUT_S)


if binaryninjaui is not None:

    class _Notifications(UIContextNotification):
        def __init__(self):
            UIContextNotification.__init__(self)
            UIContext.registerNotification(self)

        def OnViewChange(self, context, frame, type):  # noqa: A002, N802 -- API name
            _tick()

        def OnILViewTypeChange(self, context, frame, view, viewType):  # noqa: N802, N803
            _tick()

    def _start():
        _register_settings()
        _state["sender"] = core.Sender()
        _state["policy"] = core.SendPolicy()
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(_on_state_changed)
            app.aboutToQuit.connect(_on_quit)
        timer = QTimer()
        timer.setInterval(int(core.POLL_S * 1000))
        timer.timeout.connect(_tick)
        timer.start()
        # Module globals, so Python keeps them alive.
        _state["timer"] = timer
        _state["notifications"] = _Notifications()

    try:
        _start()
    except Exception as e:   # noqa: BLE001 -- a broken plugin must not stop the UI
        _print_once(e)
