# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd context reporter -- Houdini glue.

Reports the type of the pane under the mouse pointer and the network type it
shows (`houdini://network/sop`) to the local PolyKybdHost, so the keycaps show
the hotkeys of that pane. See ../../../README.md; the wire format is in core.py.

`start()` is called from `uiready.py` (the package's pythonX.Ylibs folders).
It registers one `hou.ui.addEventLoopCallback` callback, which polls at most
every `core.POLL_S` seconds:

* `hou.ui.paneTabUnderCursor()` -> the pane tab, `.type().name()`;
* `pane.pwd().childTypeCategory().name()` for a pane that shows a network;
* the mouse position from Qt, only to tell how long ago the user was active.

The callback never does network I/O; `core.Sender` does, on its own thread.
"""
from __future__ import annotations

import atexit
import os
import time
import traceback

from . import core

_state = {
    "started": False,
    "sender": None,
    "policy": None,
    "clock": None,
    "next_poll": 0.0,
    "url": None,          # the last pane URL; kept while the pointer is outside every pane
    "errors": set(),
    "port": core.DEFAULT_PORT,
    "token": "",
    "reported": False,
}


def _print_once(e):
    key = (type(e).__name__, str(e))
    if key not in _state["errors"]:
        _state["errors"].add(key)
        traceback.print_exc()


def _cursor_pos():
    """The mouse position on screen, or None without Qt."""
    try:
        try:
            from PySide6 import QtGui
        except ImportError:
            from PySide2 import QtGui
        p = QtGui.QCursor.pos()
        return (p.x(), p.y())
    except Exception:      # noqa: BLE001 -- input age is optional
        return None


def _pane_url(hou):
    """The URL of the pane tab under the mouse pointer, or None."""
    pane = hou.ui.paneTabUnderCursor()
    if pane is None:
        return None
    category = None
    pwd = getattr(pane, "pwd", None)      # only path-based panes show a network
    if pwd is not None:
        try:
            node = pwd()
            if node is not None:
                category = node.childTypeCategory().name()
        except Exception:  # noqa: BLE001 -- e.g. a node deleted mid-poll
            category = None
    return core.context_url(pane.type().name(), category)


def _tick():
    now = time.monotonic()
    if now < _state["next_poll"]:
        return
    _state["next_poll"] = now + core.POLL_S
    try:
        import hou
        url = _pane_url(hou)
        changed = url is not None and url != _state["url"]
        if url is not None:
            _state["url"] = url
        clock = _state["clock"]
        clock.feed(_cursor_pos(), now, changed)
        url = _state["url"]
        if _state["policy"].due(url, now):
            _state["sender"].submit(_state["port"], url, _state["token"], pid=os.getpid(),
                                    input_age=clock.age(now))
            _state["policy"].sent(url, now)
            _state["reported"] = True
    except Exception as e:  # noqa: BLE001 -- never let a report break Houdini
        _print_once(e)


def start():
    """Start reporting, once per session. Does nothing without a UI (hython,
    hbatch) or with POLYKYBD_REPORT=0."""
    if _state["started"]:
        return
    try:
        import hou
        if not hou.isUIAvailable():
            return
        enabled, port, token = core.settings(os.environ)
        if not enabled:
            return
        _state.update(port=port, token=token, sender=core.Sender(),
                      policy=core.SendPolicy(), clock=core.InputClock(), started=True)
        hou.ui.addEventLoopCallback(_tick)
        atexit.register(stop)
    except Exception as e:  # noqa: BLE001
        _print_once(e)


def stop():
    """Stop reporting and tell the host this Houdini has no pane any more, so
    the keyboard leaves its keys at once. Called on exit; can also be called
    from the Python Shell."""
    if not _state["started"]:
        return
    _state["started"] = False
    try:
        import hou
        hou.ui.removeEventLoopCallback(_tick)
    except Exception:  # noqa: BLE001 -- not registered, or Houdini is shutting down
        pass
    sender = _state["sender"]
    _state["sender"] = None
    if sender is not None:
        sender.stop()
    if _state["reported"]:
        _state["reported"] = False
        try:
            # Directly, not through the sender thread: at exit a daemon thread
            # may never run again.
            core.http_post(_state["port"], core.payload(None, _state["token"],
                                                        pid=os.getpid(), focused=False))
        except Exception:  # noqa: BLE001 -- the host may be gone; the report expires in 8 s
            pass
