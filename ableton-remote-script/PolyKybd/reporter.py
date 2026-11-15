# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd remote script -- the Live glue around core.py.

Reports which main view Ableton Live shows (Session or Arrangement), which
detail view is open (Clip or Device), the kind of clip in the Clip View (MIDI
or audio) and whether the main view is visible at all, to the local
PolyKybdHost, so the keycaps show that view's shortcuts. See ../README.md.

Live API used (Live Object Model, Application.View; Ableton does not document
the Python side of it, see the README for the sources):

* ``Live.Application.get_application().view``
* ``view.focused_document_view`` -- ``'Session'`` or ``'Arranger'``
* ``view.is_view_visible('Detail/Clip')``, ``('Detail/DeviceChain')``, and
  ``('Session')`` or ``('Arranger')`` for the main view itself
* ``Live.Application.get_application().get_document().view.detail_clip``
  -- the clip in the Clip View, or None; ``.is_midi_clip`` / ``.is_audio_clip``
* listeners, where this Live has them: ``add_focused_document_view_listener``,
  ``add_view_focus_changed_listener``, ``add_is_view_visible_listener(name, cb)``,
  and ``add_detail_clip_listener`` on the song view

The LOM has no property that says which view has the KEYBOARD focus:
``view_focus_changed`` is a listener without a value. So ``/clip`` means the
Clip View is on screen, not that it has the focus (see the README).

Live calls ``update_display()`` on its main thread about every 100 ms. All
work happens there and none of it waits: the state is read (one property and
two calls, plus the detail clip while the Clip View is shown), and
the sender moves its non-blocking socket one step. The
listeners only note the time of the last change, which is sent as
``input_age``. The state itself is read on every tick, so a Live without one
of the listeners still reports every change within 100 ms.
"""
import os
import time

import Live  # noqa: F401 -- provided by Live's embedded Python

from . import core

_DETAIL_CLIP = "Detail/Clip"
_DETAIL_DEVICE = "Detail/DeviceChain"
# focused_document_view -> the name is_view_visible() takes for that view
# (Application.View.available_main_views).
_MAIN_VIEW_NAMES = {"Session": "Session", "Arranger": "Arranger"}


class PolyKybdReporter:
    """A control surface with no MIDI ports: it only reports the view."""

    def __init__(self, c_instance, clock=time.monotonic):
        self._c = c_instance
        self._clock = clock
        folder = os.path.dirname(os.path.abspath(__file__))
        self._port, self._token = core.load_settings(folder)
        self._sender = core.Sender(log=self._log)
        self._policy = core.SendPolicy()
        self._last_change = clock()
        self._reported = False
        self._listeners = []
        self._view = None
        self._song_view = None
        try:
            app = Live.Application.get_application()
            self._view = app.view
            try:
                self._song_view = app.get_document().view
            except Exception as e:  # noqa: BLE001 -- the clip kind is optional
                self._log(f"PolyKybd: cannot read the song view: {type(e).__name__}: {e}")
            self._add_listeners()
        except Exception as e:  # noqa: BLE001 -- never let the script break Live
            self._log(f"PolyKybd: cannot read the view: {type(e).__name__}: {e}")
        self._log(f"PolyKybd: reporting the view to 127.0.0.1:{self._port}")

    # --- Live's control-surface interface ---------------------------------

    def update_display(self):
        """Live's ~100 ms tick on its main thread."""
        now = self._clock()
        try:
            url = self._current_url()
            if self._policy.due(url, now):
                self._sender.submit(self._port, url, self._token, pid=os.getpid(),
                                    input_age=now - self._last_change)
                self._policy.sent(url, now)
                self._reported = True
        except Exception as e:  # noqa: BLE001
            self._log(f"PolyKybd: {type(e).__name__}: {e}")
        self._sender.pump(now)

    def disconnect(self):
        """Live closes, or the control surface was switched off: withdraw the
        view so the keyboard leaves its set at once, then stop."""
        self._remove_listeners()
        if self._reported:
            self._sender.submit(self._port, None, self._token, pid=os.getpid(),
                                focused=False)
            self._sender.flush(self._clock)

    def connect_script_instances(self, _instances):
        pass

    def refresh_state(self):
        self._policy = core.SendPolicy()       # report again on the next tick

    def build_midi_map(self, _midi_map_handle):
        pass

    def receive_midi(self, _midi_bytes):
        pass

    def port_settings_changed(self):
        pass

    def can_lock_to_devices(self):
        return False

    def suggest_input_port(self):
        return ""

    def suggest_output_port(self):
        return ""

    def suggest_map_mode(self, _cc_no, _channel):
        return -1

    # --- view state -------------------------------------------------------

    def _current_url(self):
        view = self._view
        if view is None:
            return None
        document_view = view.focused_document_view
        clip_visible = view.is_view_visible(_DETAIL_CLIP)
        device_visible = False if clip_visible else view.is_view_visible(_DETAIL_DEVICE)
        clip_kind, main_visible = None, True
        if clip_visible:
            clip_kind = self._clip_kind()
            name = _MAIN_VIEW_NAMES.get(str(document_view or ""))
            if name is not None:
                main_visible = bool(view.is_view_visible(name))
        return core.context_url(document_view, clip_visible, device_visible,
                                clip_kind, main_visible)

    def _clip_kind(self):
        """`midi` or `audio` for the clip in the Clip View, else None."""
        song_view = self._song_view
        clip = getattr(song_view, "detail_clip", None) if song_view is not None else None
        if clip is None:
            return None
        if clip.is_midi_clip:
            return "midi"
        if clip.is_audio_clip:
            return "audio"
        return None

    def _changed(self):
        self._last_change = self._clock()

    def _add_listeners(self):
        view = self._view
        adds = [("focused_document_view", None), ("view_focus_changed", None),
                ("is_view_visible", _DETAIL_CLIP), ("is_view_visible", _DETAIL_DEVICE)]
        targets = [(view, name, arg) for name, arg in adds]
        if self._song_view is not None:
            targets.append((self._song_view, "detail_clip", None))
        for target, name, arg in targets:
            add = getattr(target, f"add_{name}_listener", None)
            if add is None:
                continue
            try:
                if arg is None:
                    add(self._changed)
                else:
                    add(arg, self._changed)
                self._listeners.append((target, name, arg))
            except Exception as e:  # noqa: BLE001 -- a listener is optional
                self._log(f"PolyKybd: no {name} listener: {e}")

    def _remove_listeners(self):
        for target, name, arg in self._listeners:
            remove = getattr(target, f"remove_{name}_listener", None)
            try:
                if remove is not None:
                    remove(self._changed) if arg is None else remove(arg, self._changed)
            except Exception:  # noqa: BLE001
                pass
        self._listeners = []

    def _log(self, msg):
        try:
            self._c.log_message(msg)
        except Exception:  # noqa: BLE001
            pass
