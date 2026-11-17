"""One running tutorial: which step is shown, what rings, when the step ends.

Qt-free. Every method runs on the device worker, because each one may talk to the
keyboard. The core owns at most one run and emits ``state()`` after each change.

Device features used (docs/tutorials-plan.md):
- ``point``: key attention (cmd 47 op 0, protocol 32).
- ``guide_to_layer``: the layer guide (cmd 47 op 2, protocol 34). On protocol 32..33
  the ring points at the first key of the path instead.
- ``say``, ``spotlight``, ``reveal`` and a ``wait`` on a keyboard event (layer, press)
  need the host tutorial command (cmd 49, protocol 35). Without it ``say`` is shown in
  the host panel only, the spotlight and reveal are left out, and an event wait ends
  with Next (``auto`` is false). The DOOM monolith firmware NACKs cmd 49; a refused
  INFO at start counts as "no cmd 49".
- While cmd 49 is in use, ``poll()`` must run at least every few seconds: the keyboard
  ends the session after HostTutorial.WATCHDOG_S without a cmd 49 report.
"""
from __future__ import annotations

import logging
import time

from polyhost.device.command_ids import HostTutorial
from polyhost.services.midi_guide import (GUIDE_COUNT, GUIDE_PERIOD_MS, find_path,
                                         layer_target, stays_on_layer)
from polyhost.services.tutorials.loader import Point, custom_keycodes, fixed_layers

# A ring that runs out by itself, so a host that stops without a cancel does not
# leave the keyboard ringing for ever: the MIDI guide's 12 ripples, about 30 s.
RING_COUNT = GUIDE_COUNT
RING_PERIOD_MS = GUIDE_PERIOD_MS
# The firmware's custom keycode that goes back to the default layer.
KC_BASE = custom_keycodes().get("KC_BASE", 0x7E08)


def _json_value(value):
    """A wait value as JSON: a Point (a `key` wait) becomes {"kind", "value"}, with
    a [row, col] list for a key position. The control socket encodes state()."""
    if isinstance(value, Point):
        v = list(value.value) if isinstance(value.value, tuple) else value.value
        return {"kind": value.kind, "value": v}
    return value


class TutorialRun:
    def __init__(self, tutorial, keeb, log: logging.Logger | None = None,
                 clock=time.monotonic):
        self.tutorial = tutorial
        self.keeb = keeb
        self.log = log or logging.getLogger("PolyHost")
        self.clock = clock
        self.index = 0
        self.finished = None        # None while running, else "done" / "stopped"
        self._ringing = False
        self._ring = None           # "point" / "guide" / None, for the step shown
        self._ring_error = None
        self._deadline = None
        self._names = None
        self._base = None
        self._buffer = None
        self._cmd49 = False         # the keyboard takes cmd 49 (text, spotlight, events)
        self._armed = False         # the shown step waits for a keyboard event
        self._spot_on = False
        self._step_keys = []        # (row, col) of the key the shown step rings

    # ---- lifecycle -------------------------------------------------------------

    def start(self) -> tuple[bool, str]:
        protocol = getattr(self.keeb, "protocol_version", 0) or 0
        if protocol < self.tutorial.min_protocol:
            return False, (f"The tutorial {self.tutorial.id!r} needs firmware protocol "
                           f"{self.tutorial.min_protocol}; the keyboard has {protocol}.")
        if not self.keeb.supports("key_attention"):
            return False, "The firmware is too old for tutorials (protocol 32)."
        if self.keeb.supports("host_tutorial"):
            ok, info = self.keeb.tutorial_info()
            self._cmd49 = ok
            if not ok:
                self.log.info("Tutorial %s: no cmd 49 (%s); ring only", self.tutorial.id, info)
        self._show(0)
        return True, "started"

    def next(self):
        if self.finished:
            return
        if self.index + 1 >= len(self.tutorial.steps):
            self._finish("done")
        else:
            self._show(self.index + 1)

    def back(self):
        if not self.finished and self.index > 0:
            self._show(self.index - 1)

    def stop(self):
        if not self.finished:
            self._finish("stopped")

    def tick(self) -> bool:
        """Advance a `seconds` step whose time is up. True when the state changed."""
        if self.finished or self._deadline is None or self.clock() < self._deadline:
            return False
        self.next()
        return True

    def poll(self) -> bool:
        """Cmd 49 POLL: keeps the keyboard's session alive and advances a step whose
        keyboard event happened. True when the state changed."""
        if self.finished or not self._cmd49:
            return False
        ok, info = self.keeb.tutorial_poll()
        if not ok:
            return False
        left = self._left_needed_layer(info)
        wait = self.tutorial.steps[self.index].wait
        if self._armed and info["armed"] and info["matched"] & 0x01:
            # A press that leaves the layer (KC_BASE, a layer key) is the step's
            # point. Any other press counts only while the keyboard is on the layer:
            # the same key on the base layer is not what the step asked for.
            if left is None or self._leaves_a_layer(wait):
                self.next()
                return True
        if wait.kind == "leave":
            layer = self._layer_index(wait.value)
            if layer is not None and info.get("layer") != layer:
                self.next()
                return True
        if left is not None:
            name, entry = left
            # The user left the layer this step is about, for example after a
            # one-shot (OSL) key: go back to the step that enters it.
            self.log.info("Tutorial %s step %d: the keyboard left layer %r; back to "
                          "step %d", self.tutorial.id, self.index + 1, name, entry + 1)
            self._show(entry)
            return True
        return False

    # ---- state -------------------------------------------------------------------

    def state(self) -> dict:
        step = self.tutorial.steps[self.index]
        remaining = None
        if self._deadline is not None and not self.finished:
            remaining = max(0.0, round(self._deadline - self.clock(), 1))
        return {
            "id": self.tutorial.id, "title": self.tutorial.title,
            "step": self.index, "steps": len(self.tutorial.steps),
            "say": list(step.say), "text": step.text,
            "wait": {"kind": step.wait.kind, "value": _json_value(step.wait.value)},
            # Whether the step ends by itself; else the panel's Next ends it.
            "auto": (step.wait.kind == "seconds" or self._armed
                     or (step.wait.kind == "leave" and self._cmd49
                         and self._layer_index(step.wait.value) is not None)),
            "keyboard_text": self._cmd49,
            "remaining_s": remaining,
            "ring": self._ring, "ring_error": self._ring_error,
            "finished": self.finished,
        }

    # ---- internals -----------------------------------------------------------------

    def _finish(self, reason: str):
        self._cancel_ring()
        self._deadline = None
        self._armed = False
        if self._cmd49:
            self.keeb.tutorial_end()
        self.finished = reason
        self.log.info("Tutorial %s %s at step %d of %d", self.tutorial.id, reason,
                      self.index + 1, len(self.tutorial.steps))

    def _show(self, index: int):
        self.index = index
        step = self.tutorial.steps[index]
        self._ring, self._ring_error = None, None
        self._deadline = (self.clock() + step.wait.value
                          if step.wait.kind == "seconds" else None)
        self._step_keys = []
        if step.guide_to_layer:
            self._run_guide(step.guide_to_layer)
        elif step.point:
            self._run_point(step.point)
        else:
            self._cancel_ring()
        if self._cmd49:
            self._show_on_keyboard(step)

    def _show_on_keyboard(self, step):
        """Cmd 49 for the step shown: the emoji mode, text, spotlight, reveal, and the
        event it waits for. A refusal is logged; the step still runs with Next."""
        if step.emoji_mode is not None and self.keeb.supports("tutorial_emoji_mode"):
            self._report("emoji mode", self.keeb.tutorial_emoji_mode(step.emoji_mode))
        lines = list(step.say) + ["", ""]
        self._report("text", self.keeb.tutorial_text(lines[0], lines[1]))
        if step.spotlight is not None:
            keys = set(self._step_keys)
            for point in step.spotlight:
                keys |= self._keys_of(point)
            self._report("spotlight", self.keeb.tutorial_spotlight(sorted(keys)))
            self._spot_on = True
        elif step.reveal is None and self._spot_on:
            # No spotlight on this step: every key is lit again. A reveal step keeps
            # the one before, for the wave to end it.
            self._report("spotlight", self.keeb.tutorial_spotlight(None))
            self._spot_on = False
        if step.reveal is not None:
            row, col, why = self._resolve(step.reveal)
            if why:
                self.log.info("Tutorial %s step %d: no reveal, %s", self.tutorial.id,
                              self.index + 1, why)
            else:
                self._report("reveal", self.keeb.tutorial_reveal(row, col))
                self._spot_on = False   # the wave ends the spotlight
        conds = self._conditions(step.wait)
        ok, _msg = self._report("arm", self.keeb.tutorial_arm(conds))
        self._armed = ok and bool(conds)

    def _needed_layer(self, index: int):
        """(layer name, index of the step that entered it) for a step that is about a
        layer, or None. A step is about layer L when an earlier step guided to L with
        `guide_to_layer` and waited for it, the guide's last key stays on L (TO, TG),
        and no step since then waited for a press of KC_BASE or a layer key, or for
        leaving a layer. The step with that press still needs L: its match is read
        first. A layer that is held (MO) or one-shot (OSL) is left on purpose, so it
        is never needed. A step that itself waits for a layer needs none: on the way
        to its layer the keyboard leaves the one before."""
        if self.tutorial.steps[index].wait.kind == "layer":
            return None
        needed = None
        for i, step in enumerate(self.tutorial.steps[:index]):
            if (step.wait.kind == "layer" and step.guide_to_layer == step.wait.value
                    and self._entered_with_a_staying_key(step.wait.value)):
                needed = (step.wait.value, i)
            elif step.wait.kind == "leave" or self._leaves_a_layer(step.wait):
                needed = None
        return needed

    def _entered_with_a_staying_key(self, name: str) -> bool:
        path, _target, why = self._path_to(name)
        if why:
            return False
        _names, _base, buffer = self._keymap()
        row, col, layer = path[-1]
        cols = self.keeb.device_settings.MATRIX_COLUMNS
        per = self.keeb.device_settings.MATRIX_ROWS * cols
        return stays_on_layer(buffer[layer * per + row * cols + col])

    def _left_needed_layer(self, info: dict):
        """(name, entry step) when POLL reports the keyboard off the layer the shown
        step needs, else None."""
        needed = self._needed_layer(self.index)
        if needed is None:
            return None
        layer = self._layer_index(needed[0])
        if layer is None or info.get("layer") == layer:
            return None
        return needed

    @staticmethod
    def _leaves_a_layer(wait) -> bool:
        return wait.kind == "press" and (wait.value == KC_BASE
                                         or layer_target(wait.value) is not None)

    def _report(self, what, result):
        ok, msg = result
        if not ok:
            self.log.info("Tutorial %s step %d: %s refused: %s", self.tutorial.id,
                          self.index + 1, what, msg)
        return ok, msg

    def _conditions(self, wait):
        """The cmd 49 condition for a keyboard-event wait, or []."""
        if wait.kind == "layer":
            layer = self._layer_index(wait.value)
            if layer is None:
                self.log.info("Tutorial %s: the keyboard has no layer %r", self.tutorial.id,
                              wait.value)
                return []
            return [(HostTutorial.COND_LAYER, layer, 0)]
        if wait.kind == "press":
            return [(HostTutorial.COND_KEYCODE, wait.value & 0xFF, wait.value >> 8)]
        if wait.kind == "key":
            row, col, why = self._resolve(wait.value)
            if why:
                self.log.info("Tutorial %s: no key to wait for, %s", self.tutorial.id, why)
                return []
            return [(HostTutorial.COND_KEY, row, col)]
        return []

    def _keys_of(self, point) -> set:
        """The (row, col) keys a spotlight item names; empty when none is found."""
        if point.kind != "layer":
            row, col, why = self._resolve(point)
            return set() if why else {(row, col)}
        layer = self._layer_index(point.value)
        if layer is None:
            return set()
        _names, _base, buffer = self._keymap()
        ds = self.keeb.device_settings
        per = ds.MATRIX_ROWS * ds.MATRIX_COLUMNS
        cells = buffer[layer * per:(layer + 1) * per]
        # 0 is KC_NO, 1 is KC_TRANSPARENT: nothing of this layer's own on that key.
        return {(i // ds.MATRIX_COLUMNS, i % ds.MATRIX_COLUMNS)
                for i, kc in enumerate(cells) if kc > 1}

    def _cancel_ring(self):
        if self._ringing:
            self.keeb.key_attention_cancel()
            self._ringing = False

    def _keymap(self):
        """(layer names, base layer, keymap buffer), read once per run. The layers
        the keyboard does not store (Settings, Language, Intl, Emoji) come from the
        shipped preview export and follow the stored ones, when it is for this
        matrix and the keyboard stores as many layers as the export says."""
        if self._buffer is None:
            ok, names = self.keeb.get_layer_names()
            self._names = list(names) if ok else []
            ok, base = self.keeb.get_default_layer()
            self._base = base if ok else 0
            ok, buffer = self.keeb.get_dynamic_buffer()
            self._buffer = list(buffer) if ok and buffer else []
            self._add_fixed_layers()
        return self._names, self._base, self._buffer

    def _add_fixed_layers(self):
        ds = self.keeb.device_settings
        per = ds.MATRIX_ROWS * ds.MATRIX_COLUMNS
        fixed = fixed_layers(ds.MATRIX_ROWS, ds.MATRIX_COLUMNS)
        if not fixed or not per or len(self._buffer) != fixed["stored"] * per:
            return
        if len(self._names) != fixed["stored"]:
            self._names = (self._names + [""] * fixed["stored"])[:fixed["stored"]]
        for name, cells in fixed["layers"]:
            layer = [0] * per
            for (row, col), kc in cells.items():
                layer[row * ds.MATRIX_COLUMNS + col] = kc
            self._buffer.extend(layer)
            self._names.append(name)

    def _layer_index(self, name: str):
        names, _base, _buffer = self._keymap()
        for i, n in enumerate(names):
            if str(n).strip().lower() == name.lower():
                return i
        return None

    def _path_to(self, name: str):
        target = self._layer_index(name)
        if target is None:
            return None, None, f"the keyboard has no layer {name!r}"
        _names, base, buffer = self._keymap()
        ds = self.keeb.device_settings
        path = find_path(buffer, ds.MATRIX_ROWS, ds.MATRIX_COLUMNS, base, target)
        if not path:
            return None, target, f"no key path from layer {base} to {name!r}"
        return path, target, None

    def _find_keycode(self, keycode: int):
        """(row, col) of the first key with `keycode`, base layer first."""
        _names, base, buffer = self._keymap()
        ds = self.keeb.device_settings
        per = ds.MATRIX_ROWS * ds.MATRIX_COLUMNS
        layers = len(buffer) // per if per else 0
        order = [base] + [n for n in range(layers) if n != base]
        for layer in order:
            start = layer * per
            for i in range(per):
                if buffer[start + i] == keycode:
                    return i // ds.MATRIX_COLUMNS, i % ds.MATRIX_COLUMNS
        return None

    def _resolve(self, point):
        """(row, col, None) or (None, None, why)."""
        if point.kind == "key":
            return point.value[0], point.value[1], None
        if point.kind == "keycode":
            pos = self._find_keycode(point.value)
            if pos is None:
                return None, None, f"no key has keycode 0x{point.value:04X}"
            return pos[0], pos[1], None
        path, _target, why = self._path_to(point.value)
        if why:
            return None, None, why
        row, col, _layer = path[0]
        return row, col, None

    def _ring_key(self, row, col, how: str):
        ok, msg = self.keeb.key_attention(row, col, RING_COUNT, RING_PERIOD_MS)
        self._ringing = ok
        if ok:
            self._ring = how
        else:
            self._ring_error = msg

    def _run_point(self, point):
        row, col, why = self._resolve(point)
        if why:
            self._cancel_ring()
            self._ring_error = why
            self.log.info("Tutorial %s step %d: no ring, %s", self.tutorial.id,
                          self.index + 1, why)
            return
        # A START replaces the running request, so no cancel first.
        self._step_keys = [(row, col)]
        self._ring_key(row, col, "point")

    def _run_guide(self, name: str):
        path, target, why = self._path_to(name)
        if why:
            self._cancel_ring()
            self._ring_error = why
            self.log.info("Tutorial %s step %d: no guide, %s", self.tutorial.id,
                          self.index + 1, why)
            return
        self._step_keys = [(r, c) for r, c, _layer in path]
        if self.keeb.supports("key_guide"):
            ok, msg = self.keeb.key_guide(path, target, RING_COUNT, RING_PERIOD_MS)
            self._ringing = ok
            if ok:
                self._ring = "guide"
            else:
                self._ring_error = msg
            return
        row, col, _layer = path[0]
        self._ring_key(row, col, "point")

