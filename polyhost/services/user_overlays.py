"""Overlay sets the user, or an AI assistant on the user's request, made
(docs/mcp-server-plan.md, version 2). Qt-free.

Each set is a folder in `user_overlays/` in the config directory:

    user_overlays/<slug>/set.yaml          {"app", "source", "bindings": [...]}
    user_overlays/<slug>/user_<slug>.mods.png        (and .combo / .extra / .gui)

A binding is {"key": "KC_F5", "mods": ["CTRL"], "drawing": [shapes], "legend": true}.
`key` is a keycode name with an overlay slot: an overlay belongs to a keycode, not
to a physical key. The drawing format is services/key_drawing.py.

Since firmware protocol v40 a binding of the "*" set can instead follow one
PHYSICAL key: {"key": "L:1.1", "follow": "key", "drawing": [...], "legend": ...}, no
mods. Those go into `user__all.keys.png` (device/key_images.py), cell = matrix index,
and the keyboard draws them where the key's keycode has no image.

How the sets reach the keyboard (PolyCore):

* An app's set is LAID OVER the shipped entry for that app: `merged_mapping()`
  appends its files after every `overlay` list in the entry, and the send keeps
  the last image per key and modifier, so the user's keys win and the shipped
  icons stay on every other key. An app with no shipped entry gets a new one.
* The set for app "*" (folder `_all`) goes in front of every overlay send
  (`star_files()`), so every app image wins over it and it fills the keys the
  focused app leaves empty.
"""
from __future__ import annotations

import copy
import os
import re
import shutil

import numpy as np

from polyhost.device.keys import KeyCode, Modifier
from polyhost.res.overlay_layout import (CH, COMBO_CH, EXTRA_CH, GUI_CH, IMG_H, IMG_W,
                                         PRIMARY_CH, SLOT_H, SLOT_W, _has_cell, cell_for)
from polyhost.services import key_drawing

ALL_APPS = "*"
SET_FILE = "set.yaml"
MAX_BINDINGS = 400           # one set: 90 keys x a few modifiers is the useful range
MAX_SETS = 100
_APP_RE = re.compile(r"[a-z0-9][a-z0-9 ._+-]{0,63}")

# The file of each tier: the generator's suffixes (scripts/generate_app_overlays.py).
TIERS = (("primary", ".mods.png", PRIMARY_CH), ("combo", ".combo.mods.png", COMBO_CH),
         ("extra", ".extra.mods.png", EXTRA_CH), ("gui", ".gui.mods.png", GUI_CH))
_MOD_BITS = {"CTRL": 1, "CONTROL": 1, "SHIFT": 2, "ALT": 4, "OPTION": 4,
             "GUI": 8, "WIN": 8, "CMD": 8, "SUPER": 8, "META": 8}


class UserOverlayError(ValueError):
    """A request the store refuses, with the reason in plain words."""


def root_dir() -> str:
    from polyhost.server.protocol import _config_dir
    return os.path.join(_config_dir(), "user_overlays")


# -- names ----------------------------------------------------------------------

def check_app(app) -> str:
    """The app name as the window matcher sees it (lowercase), or UserOverlayError."""
    if app == ALL_APPS:
        return app
    if not isinstance(app, str):
        raise UserOverlayError("app must be a string")
    name = app.strip().lower()
    if not _APP_RE.fullmatch(name):
        raise UserOverlayError(
            f"{app!r} is not an app name: use the process name in lowercase "
            "(letters, digits, space, '.', '_', '+', '-'), or \"*\" for every app")
    return name


def slug(app: str) -> str:
    if app == ALL_APPS:
        return "_all"
    return re.sub(r"[^a-z0-9_-]", "-", app)


def set_dir(app: str, root: str | None = None) -> str:
    return os.path.join(root or root_dir(), slug(check_app(app)))


def check_key(name) -> KeyCode:
    """The KeyCode of a keycode name that has an overlay slot."""
    kc = None
    if isinstance(name, str) and name in KeyCode.__members__:
        kc = KeyCode[name]
    elif isinstance(name, str):
        from polyhost.services.keycode_text import parse_keycode
        try:
            kc = KeyCode(parse_keycode(name))
        except ValueError:
            kc = None
    if kc is None:
        raise UserOverlayError(f"{name!r} is not a keycode name such as KC_F5")
    if not _has_cell(kc):
        raise UserOverlayError(f"{name} has no overlay slot; only letters, digits, F1-F12, "
                               "navigation, editing, punctuation and modifier keys have one")
    return kc


def modifier(mods) -> Modifier:
    if mods is None:
        mods = []
    if not isinstance(mods, list) or not all(isinstance(m, str) for m in mods):
        raise UserOverlayError("mods is a list such as [\"CTRL\", \"SHIFT\"]")
    bits = 0
    for m in mods:
        bit = _MOD_BITS.get(m.strip().upper())
        if bit is None:
            raise UserOverlayError(f"unknown modifier {m!r}; use CTRL, SHIFT, ALT or GUI")
        bits |= bit
    return Modifier(bits)


def mod_names(mod: Modifier) -> list[str]:
    return [n for n, b in (("CTRL", 1), ("SHIFT", 2), ("ALT", 4), ("GUI", 8)) if mod.value & b]


FOLLOW_KEYCODE = "keycode"
FOLLOW_KEY = "key"


def physical_key(name) -> tuple[str, int]:
    """(canonical key name, matrix index) of a physical key name such as "L:1.1"."""
    from polyhost.device.key_images import matrix_index
    from polyhost.services.key_names import KeyRefError, load_table
    table = load_table("split72")
    try:
        canonical = table.canonical(name)
    except KeyRefError as exc:
        raise UserOverlayError(str(exc)) from None
    return canonical, matrix_index(*table.by_name[canonical])


def check_binding(b, app=None) -> dict:
    """A clean copy of binding `b`, with its drawing checked. Raises UserOverlayError."""
    if not isinstance(b, dict):
        raise UserOverlayError("a binding is an object with key, mods, drawing and legend")
    extra = set(b) - {"key", "mods", "drawing", "legend", "follow"}
    if extra:
        raise UserOverlayError(f"unknown binding fields: {sorted(extra)}")
    follow = b.get("follow", FOLLOW_KEYCODE)
    if follow not in (FOLLOW_KEYCODE, FOLLOW_KEY):
        raise UserOverlayError('follow is "keycode" or "key"')
    legend = b.get("legend", True)
    if not isinstance(legend, bool):
        raise UserOverlayError("legend must be true or false")
    if follow == FOLLOW_KEY:
        if app is not None and app != ALL_APPS:
            raise UserOverlayError('only the set for every app ("*") can follow a physical key')
        if b.get("mods"):
            raise UserOverlayError("a drawing on a physical key shows with every modifier; "
                                   "leave mods empty")
        name, _idx = physical_key(b.get("key"))
        label, out = name, {"key": name, "follow": FOLLOW_KEY}
    else:
        kc = check_key(b.get("key"))
        label, out = kc.name, {"key": kc.name, "mods": mod_names(modifier(b.get("mods")))}
    try:
        key_drawing.render(b.get("drawing"))
    except key_drawing.DrawingError as exc:
        raise UserOverlayError(f"{label}: {exc}") from None
    out.update({"drawing": b["drawing"], "legend": legend})
    return out


def binding_place(b) -> tuple:
    """What a binding occupies: a later binding with the same place replaces it."""
    if b.get("follow") == FOLLOW_KEY:
        return (FOLLOW_KEY, b["key"])
    return (FOLLOW_KEYCODE, b["key"], tuple(b.get("mods") or ()))


def remove_binding(app: str, key, mods=None, root: str | None = None) -> bool:
    """Remove the binding of `app`'s set on `key` (a keycode name with `mods`, or a
    physical key name for a follow-"key" binding). Returns whether one was removed."""
    data = load_set(app, root)
    if not data:
        return False
    if isinstance(key, str) and key.strip()[:2].upper() in ("L:", "R:"):
        place = (FOLLOW_KEY, physical_key(key)[0])
    else:
        place = (FOLLOW_KEYCODE, check_key(key).name, tuple(mod_names(modifier(mods))))
    old = data.get("bindings") or []
    keep = [b for b in old if binding_place(b) != place]
    if len(keep) == len(old):
        return False
    save_set(app, keep, root)
    return True


# -- the store ------------------------------------------------------------------

def load_set(app: str, root: str | None = None) -> dict | None:
    import yaml
    path = os.path.join(set_dir(app, root), SET_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return None
    except (OSError, yaml.YAMLError) as exc:
        raise UserOverlayError(f"cannot read {path}: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("bindings"), list):
        raise UserOverlayError(f"{path} is not an overlay set")
    return data


def list_sets(root: str | None = None) -> list[dict]:
    """[{app, keys: n}] for every readable set, "*" first, then by app name."""
    root = root or root_dir()
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    for name in names:
        path = os.path.join(root, name, SET_FILE)
        if not os.path.isfile(path):
            continue
        import yaml
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            app = check_app(data.get("app"))
        except (OSError, yaml.YAMLError, UserOverlayError):
            continue
        if slug(app) != name:
            continue
        out.append({"app": app, "keys": len(data.get("bindings") or [])})
    out.sort(key=lambda s: (s["app"] != ALL_APPS, s["app"]))
    return out


def save_set(app: str, bindings: list, root: str | None = None) -> dict:
    """Write `bindings` as the whole set for `app` and draw its files.

    Returns {"placed": [...], "files": [...]}. An empty list removes the set."""
    app = check_app(app)
    if not isinstance(bindings, list):
        raise UserOverlayError("bindings must be a list")
    if len(bindings) > MAX_BINDINGS:
        raise UserOverlayError(f"a set has at most {MAX_BINDINGS} bindings")
    clean, seen = [], {}
    for b in bindings:
        cb = check_binding(b, app)
        where = binding_place(cb)
        if where in seen:
            clean[seen[where]] = cb      # the later binding for a key wins
        else:
            seen[where] = len(clean)
            clean.append(cb)
    if not clean:
        remove_set(app, root)
        return {"placed": [], "files": []}
    root = root or root_dir()
    if not os.path.isdir(set_dir(app, root)) and len(list_sets(root)) >= MAX_SETS:
        raise UserOverlayError(f"there are already {MAX_SETS} user overlay sets")
    folder = set_dir(app, root)
    os.makedirs(folder, exist_ok=True)
    import yaml
    tmp = os.path.join(folder, SET_FILE + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump({"app": app, "source": "mcp", "bindings": clean}, f,
                       allow_unicode=True, sort_keys=False)
    os.replace(tmp, os.path.join(folder, SET_FILE))
    files = _write_files(app, clean, folder)
    return {"placed": [{"key": b["key"], "mods": b.get("mods", []), "legend": b["legend"],
                        "follow": b.get("follow", FOLLOW_KEYCODE)} for b in clean],
            "files": files}


def remove_set(app: str, root: str | None = None) -> bool:
    folder = set_dir(app, root)
    if not os.path.isdir(folder):
        return False
    shutil.rmtree(folder)
    return True


def files_for(app: str, root: str | None = None) -> list[str]:
    """The drawn files of `app`'s set, absolute, in tier order, the physical-key
    file last. [] for no set."""
    from polyhost.device.key_images import KEY_IMAGE_SUFFIX
    folder = set_dir(app, root)
    stem = "user_" + slug(check_app(app))
    suffixes = [suffix for _t, suffix, _c in TIERS] + [KEY_IMAGE_SUFFIX]
    return [p for p in (os.path.join(folder, stem + suffix) for suffix in suffixes)
            if os.path.isfile(p)]


def star_files(root: str | None = None) -> list[str]:
    return files_for(ALL_APPS, root)


def _write_files(app, bindings, folder) -> list[str]:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    from polyhost.device.im_converter import NO_LEGEND_CHUNK
    from polyhost.device.key_images import KEY_IMAGE_SUFFIX
    from polyhost.res.overlay_layout import GRID_X
    arrays = {t: np.zeros((IMG_H, IMG_W, 4), dtype=np.uint8) for t, _s, _c in TIERS}
    no_legend = {t: set() for t, _s, _c in TIERS}
    keys = np.zeros((IMG_H, IMG_W, 4), dtype=np.uint8)
    keys_no_legend = set()
    for b in bindings:
        if b.get("follow") == FOLLOW_KEY:
            # Cell = matrix index, white on black (device/key_images.py): the loader
            # reads a file without ".mods." in its name as one grayscale image.
            _name, idx = physical_key(b["key"])
            mask, _notes = key_drawing.render(b["drawing"])
            row, col = divmod(idx, GRID_X)
            block = keys[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W, :3]
            block[:] = 0
            block[mask] = 255
            if not b["legend"]:
                keys_no_legend.add((Modifier.NO_MOD.value, idx))
            continue
        kc, mod = KeyCode[b["key"]], modifier(b["mods"])
        tier, channel = next((t, chans[mod]) for t, _s, chans in TIERS if mod in chans)
        mask, _notes = key_drawing.render(b["drawing"])
        row, col = cell_for(kc)
        block = arrays[tier][row * SLOT_H:(row + 1) * SLOT_H,
                             col * SLOT_W:(col + 1) * SLOT_W, CH[channel]]
        block[:] = 0
        block[mask] = 255
        if not b["legend"]:
            no_legend[tier].add((mod.value, kc.value))
    stem = "user_" + slug(app)
    written = []
    outputs = [(suffix, arrays[tier], no_legend[tier]) for tier, suffix, _c in TIERS]
    if keys.any():
        keys[..., CH["A"]] = 255         # opaque: the grayscale read uses RGB
    outputs.append((KEY_IMAGE_SUFFIX, keys, keys_no_legend))
    for suffix, array, flagged in outputs:
        path = os.path.join(folder, stem + suffix)
        if not array.any():
            if os.path.exists(path):
                os.remove(path)
            continue
        info = None
        if flagged:
            info = PngInfo()
            info.add_text(NO_LEGEND_CHUNK, " ".join(f"{m}:{k}" for m, k in sorted(flagged)))
        tmp = path + ".tmp"
        Image.fromarray(array, mode="RGBA").save(tmp, format="PNG", pnginfo=info)
        os.replace(tmp, path)
        written.append(path)
    return written


# -- the mapping ------------------------------------------------------------------

def merged_mapping(shipped: dict, root: str | None = None, log=None) -> dict:
    """The shipped mapping with every user set (except "*") laid over it.

    The shipped dict is not changed. An entry the user's set covers is copied and
    the set's files are appended to each of its `overlay` lists, so the user's keys
    win in every route of the entry (titles, URLs, OS branches)."""
    from polyhost.handler.common import mapping_key
    merged = dict(shipped)
    # The YAML keys are comma-separated name lists ("chrome,google chrome,...");
    # the matcher splits them, so the lookup here does too.
    by_name = {}
    for raw in shipped:
        for name in str(raw).split(","):
            by_name.setdefault(name.strip(), raw)
    for s in list_sets(root):
        app = s["app"]
        if app == ALL_APPS:
            continue
        files = files_for(app, root)
        if not files:
            continue
        name = mapping_key(app, by_name)
        key = by_name[name] if name is not None else None
        if key is None:
            merged[app] = {"overlay": list(files)}
            continue
        entry = copy.deepcopy(merged[key])
        _append_overlays(entry, files)
        if "overlay" not in entry:
            entry["overlay"] = list(files)
        merged[key] = entry
        if log is not None:
            log.info("User overlay set for %s is laid over the shipped entry %r", app, key)
    return merged


def _append_overlays(node, files):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "overlay":
                node[k] = ([v] if isinstance(v, str) else list(v or [])) + list(files)
            else:
                _append_overlays(v, files)
    elif isinstance(node, list):
        for v in node:
            _append_overlays(v, files)
