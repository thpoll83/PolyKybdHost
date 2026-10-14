# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Context Reporter -- Blender glue.

Reports Blender's interaction mode and the editor under the mouse to the local
PolyKybdHost, so the keyboard's keycaps can show the shortcuts of the context
you are actually in. See README.md; the wire format is in core.py.

Two moving parts:

* a **mouse tracker** -- one modal operator per window that only RECORDS the
  mouse position and passes every event through untouched ({'PASS_THROUGH'}).
  Blender sends keys to the area under the mouse, so that area is the editor
  whose shortcuts apply. Python has no other way to read the mouse position.
* a **timer** (`bpy.app.timers`) that reads `context.mode` and the area under
  the last mouse position, and hands a report to the sender thread on a change
  and as a keep-alive. The timer never does network I/O itself.
"""

bl_info = {  # legacy add-on install (Blender < 4.2); 4.2+ reads blender_manifest.toml
    "name": "PolyKybd Context Reporter",
    "author": "PolyKybd",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Preferences > Add-ons",
    "description": "Tells the local PolyKybdHost which mode and editor you are in",
    "category": "System",
}

import os
import time
import traceback

import bpy

from . import core

_state = {
    "sender": None,
    "policy": None,
    "mouse": {},          # window pointer -> (seq, x, y), window-relative pixels
    "seq": 0,             # bumps on every recorded event: newest window wins
    "tracked": set(),     # window pointers with a running tracker
    "errors": set(),      # (type, message) already printed by _tick
    "last_input": None,   # time.monotonic() of the newest mouse/key event
    "reported": False,    # a context was sent since the last withdrawal
}


def _prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class PolyKybdReporterPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enabled: bpy.props.BoolProperty(
        name="Report context", default=True,
        description="Send the current mode and editor to PolyKybdHost on this computer")
    port: bpy.props.IntProperty(
        name="Port", default=core.DEFAULT_PORT, min=1, max=65535,
        description="PolyKybdHost's browser_report_port (default 50164)")
    token: bpy.props.StringProperty(
        name="Token", default="", subtype='PASSWORD',
        description="Only if PolyKybdHost has browser_report_token set: the same value")

    def draw(self, _context):
        col = self.layout.column()
        col.prop(self, "enabled")
        col.prop(self, "port")
        col.prop(self, "token")
        col.label(text="Sent: interaction mode and editor type only, to 127.0.0.1.")


def _record(win_ptr, event):
    _state["seq"] += 1
    _state["last_input"] = time.monotonic()
    _state["mouse"][win_ptr] = (_state["seq"], event.mouse_x, event.mouse_y)


class POLYKYBD_OT_track_mouse(bpy.types.Operator):
    """Record the mouse position for PolyKybd (passes every event through)"""
    bl_idname = "polykybd.track_mouse"
    bl_label = "PolyKybd: Track Mouse"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        win = context.window
        if win is None:
            return {'CANCELLED'}
        self._win = win.as_pointer()
        _state["tracked"].add(self._win)
        _record(self._win, event)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, _context, event):
        if _state["sender"] is None:          # add-on disabled: step out
            _state["tracked"].discard(self._win)
            return {'CANCELLED'}
        if not event.type.startswith('TIMER'):
            _record(self._win, event)
        return {'PASS_THROUGH'}

    def cancel(self, _context):
        _state["tracked"].discard(getattr(self, "_win", None))


def _ensure_trackers(wm):
    for win in wm.windows:
        ptr = win.as_pointer()
        if ptr in _state["tracked"]:
            continue
        try:
            with bpy.context.temp_override(window=win, screen=win.screen):
                bpy.ops.polykybd.track_mouse('INVOKE_DEFAULT')
        except Exception:     # noqa: BLE001 -- e.g. a window mid-teardown; retry next tick
            pass


def _current_url(wm):
    """The context URL under the mouse in the window that saw the newest event.

    With several Blender windows open each keeps its last mouse position; the
    event loop only feeds the window under the pointer, so the most recently
    updated one is where the keys go."""
    best = None
    for win in wm.windows:
        pos = _state["mouse"].get(win.as_pointer())
        if pos is not None and win.screen is not None and (best is None or pos[0] > best[0][0]):
            best = (pos, win)
    if best is None:
        return None
    (_seq, x, y), win = best
    area = core.area_at(win.screen.areas, x, y)
    if area is None:
        return None
    with bpy.context.temp_override(window=win, screen=win.screen, area=area):
        mode = bpy.context.mode
    return core.context_url(mode, area.type, getattr(area, "ui_type", None))


def _tick():
    sender, policy = _state["sender"], _state["policy"]
    if sender is None:
        return None                            # unregistered: stop the timer
    try:
        prefs = _prefs()
        wm = bpy.context.window_manager
        if prefs is not None and not prefs.enabled:
            _withdraw(prefs)
            return core.POLL_S
        if prefs is None or wm is None:
            return core.POLL_S
        _ensure_trackers(wm)
        url = _current_url(wm)
        now = time.monotonic()
        if policy.due(url, now):
            last = _state["last_input"]
            sender.submit(prefs.port, url, prefs.token, pid=os.getpid(),
                          input_age=None if last is None else now - last)
            policy.sent(url, now)
            _state["reported"] = True
    except Exception as e:     # noqa: BLE001 -- never let a report break Blender
        # Swallowed so a bug here can never break Blender's UI, but printed
        # once per distinct error, so it can be diagnosed from Blender's
        # system console instead of overlays silently stopping to switch.
        key = (type(e).__name__, str(e))
        if key not in _state["errors"]:
            _state["errors"].add(key)
            traceback.print_exc()
    return core.POLL_S


def _withdraw(prefs):
    """Tell the host this instance stopped reporting, once, so the keyboard
    leaves the last mode's overlay instead of keeping it until the window
    changes. The policy is reset, so re-enabling reports again at once."""
    sender = _state["sender"]
    if not _state.get("reported") or sender is None:
        return
    sender.submit(prefs.port, None, prefs.token, pid=os.getpid(), focused=False)
    _state["reported"] = False
    _state["policy"] = core.SendPolicy()


@bpy.app.handlers.persistent
def _on_load_post(*_args):
    # Loading a file ends every modal operator; restart the trackers.
    _state["tracked"].clear()
    _state["mouse"].clear()


_classes = (PolyKybdReporterPreferences, POLYKYBD_OT_track_mouse)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _state["sender"] = core.Sender()
    _state["policy"] = core.SendPolicy()
    bpy.app.handlers.load_post.append(_on_load_post)
    bpy.app.timers.register(_tick, first_interval=core.POLL_S, persistent=True)


def unregister():
    prefs = _prefs()
    if prefs is not None:
        _withdraw(prefs)
    sender = _state["sender"]
    _state["sender"] = None
    if sender is not None:
        sender.stop()
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    _state["tracked"].clear()
    _state["mouse"].clear()
