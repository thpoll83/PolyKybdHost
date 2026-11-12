"""The first-time MIDI guide: the first time a MIDI program is in front, the
keyboard's focus ripple shows how to reach the MIDI layer.

An entry in ``overlay-mapping.poly.yaml`` marks a program (or a web page, through its
``url:`` gate) that takes MIDI input::

    bitwig studio:
      overlay: [...]
      midi: true

The guide is the key path from the active base layer to the MIDI layer, read from the
keymap the keyboard holds, so a user's own remap is followed. On the default split72
keymap it is two steps: Fn (on the base layer), then the key above the right Shift
(on the Fn layer). The keyboard (cmd 47 op 2, firmware protocol 34+) rings the step
whose layer is active and stops on the MIDI layer.

Qt-free; the core calls it on the device worker. Which programs already had the guide
is kept in ``midi_guide_seen.json`` beside ``settings.yaml``, by program name (or web
host), so it runs once per program.
"""
import json
import logging
import os
import threading
from collections import deque
from urllib.parse import urlsplit

SEEN_FILENAME = "midi_guide_seen.json"
MIDI_LAYER_NAME = "MIDI"     # layer_names.c in the firmware
MAX_STEPS = 4                # KEY_GUIDE_MAX_STEPS, the firmware's ATTN_GUIDE_MAX_STEPS
GUIDE_COUNT = 12             # ripples in total, about 30 s at the period below
GUIDE_PERIOD_MS = 2500
# How long a started guide can still be ringing: its ripples, plus the last one's
# 2.2 s run.
GUIDE_SECONDS = GUIDE_COUNT * GUIDE_PERIOD_MS / 1000 + 3


def seen_path() -> str:
    """Beside settings.yaml."""
    from polyhost.settings import settings_path
    return os.path.join(os.path.dirname(settings_path()), SEEN_FILENAME)


# Browsers without Web MIDI: a `midi: true` web page cannot hear the keyboard there.
NO_WEB_MIDI = ("safari",)


def is_midi_entry(entry, app_name=None) -> bool:
    """`midi: true` on the matched entry, except a web page in a browser that has no
    Web MIDI."""
    if not (isinstance(entry, dict) and entry.get("midi") is True):
        return False
    return not (entry.get("url") and str(app_name or "").lower().startswith(NO_WEB_MIDI))


def program_key(app_name, entry, url=None):
    """What 'the first time' counts per: the web host for an entry gated on a URL,
    else the program name. None when neither is known."""
    if isinstance(entry, dict) and entry.get("url") and url:
        host = urlsplit(url).hostname
        if host:
            return "web:" + host.lower().removeprefix("www.")
    return str(app_name).lower() if app_name else None


def layer_target(keycode: int):
    """The layer a layer key moves to, or None. MO, TO, TG, OSL, TT, LT and LM; not
    DF/PDF, which change the base layer itself."""
    if 0x4000 <= keycode <= 0x4FFF:                 # LT(layer, kc)
        return (keycode >> 8) & 0x0F
    if 0x5000 <= keycode <= 0x51FF:                 # LM(layer, mod)
        return (keycode >> 5) & 0x0F
    for base in (0x5200, 0x5220, 0x5260, 0x5280, 0x52C0):   # TO MO TG OSL TT
        if base <= keycode <= base + 0x1F:
            return keycode & 0x1F
    return None


def find_path(buffer, rows: int, cols: int, base_layer: int, target_layer: int,
              max_steps: int = MAX_STEPS):
    """The shortest list of ``(row, col, layer)`` key presses from `base_layer` to
    `target_layer` in a flat ``[layer][row][col]`` keymap, or None.

    Each step goes to a HIGHER layer: the keyboard picks the step by the highest
    active layer, so a path through a lower layer could never advance. Ties go to
    the first key in matrix order."""
    if buffer is None or rows <= 0 or cols <= 0:
        return None
    per_layer = rows * cols
    layers = len(buffer) // per_layer
    if not (0 <= base_layer < layers) or base_layer == target_layer:
        return None
    came = {base_layer: None}
    queue = deque([(base_layer, 0)])
    while queue:
        layer, depth = queue.popleft()
        if depth >= max_steps:
            continue
        start = layer * per_layer
        for i in range(per_layer):
            to = layer_target(buffer[start + i])
            if to is None or to <= layer or to in came:
                continue
            came[to] = (layer, i // cols, i % cols)
            if to == target_layer:
                path, node = [], to
                while came[node] is not None:
                    prev, row, col = came[node]
                    path.append((row, col, prev))
                    node = prev
                return path[::-1]
            if to < layers:      # a layer the keyboard does not store has no keys to read
                queue.append((to, depth + 1))
    return None


class SeenPrograms:
    """The programs that had the guide, in a small JSON list. Called on the worker;
    the lock covers a reset from the control socket."""

    def __init__(self, path: str | None = None, log: logging.Logger | None = None):
        self._path = path
        self.log = log or logging.getLogger("PolyHost")
        self._lock = threading.Lock()
        self._seen = None

    def _load(self):
        if self._seen is not None:
            return
        self._seen = set()
        if not self._path:
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._seen = {str(x) for x in data}
        except FileNotFoundError:
            # No file yet: no program has had the guide, so the empty set stands.
            return
        except (OSError, ValueError) as e:
            self.log.warning("Cannot read %s (%s); the MIDI guide runs again.", self._path, e)

    def has(self, key) -> bool:
        with self._lock:
            self._load()
            return key in self._seen

    def add(self, key):
        with self._lock:
            self._load()
            if key in self._seen:
                return
            self._seen.add(key)
            self._write()

    def clear(self):
        with self._lock:
            self._seen = set()
            self._write()

    def _write(self):
        if not self._path:
            return
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sorted(self._seen), f, indent=0)
            os.replace(tmp, self._path)
        except OSError as e:
            self.log.warning("Cannot write %s: %s", self._path, e)


def midi_layer(names) -> int | None:
    """The index of the layer the keyboard calls MIDI (cmd 35), or None."""
    for i, name in enumerate(names or ()):
        if str(name).strip().upper() == MIDI_LAYER_NAME:
            return i
    return None


def run_guide(keeb, log: logging.Logger | None = None) -> tuple[bool, str]:
    """Read the keymap, find the path to the MIDI layer and start the guide.
    Runs on the device worker."""
    log = log or logging.getLogger("PolyHost")
    if not keeb.supports("key_guide"):
        return False, "The firmware is too old for the MIDI guide (protocol 34)."
    ok, names = keeb.get_layer_names()
    target = midi_layer(names) if ok else None
    if target is None:
        return False, "The keyboard has no MIDI layer."
    ok, base = keeb.get_default_layer()
    if not ok:
        return False, "Cannot read the keyboard's base layer."
    ok, buffer = keeb.get_dynamic_buffer()
    if not ok or not buffer:
        return False, "Cannot read the keymap."
    ds = keeb.device_settings
    path = find_path(buffer, ds.MATRIX_ROWS, ds.MATRIX_COLUMNS, base, target)
    if not path:
        return False, f"No key path from layer {base} to the MIDI layer {target}."
    log.info("MIDI guide: %s to layer %d", path, target)
    return keeb.key_guide(path, target, GUIDE_COUNT, GUIDE_PERIOD_MS)
