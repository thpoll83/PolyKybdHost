"""Tutorial scripts: one YAML file per topic (docs/tutorials-plan.md).

Shipped scripts are in ``polyhost/res/tutorials/``; a user puts more in
``<config dir>/tutorials/``, beside ``settings.yaml``. A user script with the same
``id`` as a shipped one replaces it. A script never runs code: every field is data,
and a field this loader does not know is an error, so a typo cannot make a step wait
for ever.

Qt-free. The texts stay ``{language code: text}`` dicts; the GUI picks one with
``pick_text()``.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml

from polyhost.services.keycode_text import parse_keycode

SHIPPED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "res", "tutorials")
USER_DIRNAME = "tutorials"

CATEGORIES = ("layers", "languages", "light", "emoji", "editor", "other")
SOURCE_LANGUAGE = "en"
# Key attention (cmd 47 op 0) is the oldest device feature a tutorial uses.
BASE_PROTOCOL = 32

_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
_SCRIPT_KEYS = {"id", "category", "title", "summary", "min_protocol", "steps"}
_STEP_KEYS = {"say", "text", "point", "guide_to_layer", "wait"}
_POINT_KINDS = {"keycode", "layer_key", "key"}
_WAIT_KINDS = {"seconds", "layer", "press", "keycode"}


class ScriptError(ValueError):
    """A script that cannot be used; the message names the field."""


@dataclass(frozen=True)
class Point:
    """Which key the ring points at. `kind` is "keycode" (value: int), "layer_key"
    (value: a layer name from cmd 35; the key that moves to that layer) or "key"
    (value: (row, col))."""
    kind: str
    value: object


@dataclass(frozen=True)
class Wait:
    """How a step ends. "next": the user presses Next. "seconds": after `value`
    seconds. "layer" / "press" / "keycode": a keyboard event; these need firmware
    events (cmd 49) and end with Next until then."""
    kind: str
    value: object = None


@dataclass(frozen=True)
class Step:
    say: tuple = ()
    text: dict = field(default_factory=dict)
    point: Point | None = None
    guide_to_layer: str | None = None
    wait: Wait = Wait("next")


@dataclass(frozen=True)
class Tutorial:
    id: str
    category: str
    title: dict
    summary: dict
    min_protocol: int
    steps: tuple
    path: str = ""
    user: bool = False

    def to_dict(self) -> dict:
        """The JSON-serializable listing entry (control socket, dialog)."""
        return {"id": self.id, "category": self.category, "title": self.title,
                "summary": self.summary, "min_protocol": self.min_protocol,
                "steps": len(self.steps), "user": self.user, "path": self.path}


def pick_text(texts: dict, code: str | None) -> str:
    """The text for UI language `code` ("de", "pt-BR"), else its base language
    ("pt"), else English, else any."""
    if not texts:
        return ""
    if code:
        if code in texts:
            return texts[code]
        base = code.split("-")[0]
        if base in texts:
            return texts[base]
    return texts.get(SOURCE_LANGUAGE) or next(iter(texts.values()))


def _texts(value, where: str) -> dict:
    if isinstance(value, str):
        return {SOURCE_LANGUAGE: value}
    if isinstance(value, dict) and value and all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        return dict(value)
    raise ScriptError(f"{where}: a text, or a map of language code to text")


def _say(value, where: str) -> tuple:
    lines = [value] if isinstance(value, str) else value
    if not isinstance(lines, list) or not 1 <= len(lines) <= 2 or not all(
            isinstance(s, str) for s in lines):
        raise ScriptError(f"{where}: one or two lines of text")
    for line in lines:
        # The status OLED's face covers 0x20..0x7E only (firmware STATUS_OLED.md).
        if any(not 0x20 <= ord(ch) <= 0x7E for ch in line):
            raise ScriptError(f"{where}: {line!r} has a character the status display "
                              f"cannot show (ASCII 0x20..0x7E only)")
    return tuple(lines)


_CUSTOM = None
LEGENDS_FILE = os.path.join(os.path.dirname(SHIPPED_DIR), "preview", "legends.json")


def custom_keycodes() -> dict:
    """PolyKybd's own keycode names (KC_DAUTO, KC_BASE, ...) -> value, from the
    shipped legends.json. QMK's keycodes.h does not have them."""
    global _CUSTOM
    if _CUSTOM is None:
        import json
        try:
            with open(LEGENDS_FILE, encoding="utf-8") as f:
                table = json.load(f).get("custom", {})
            _CUSTOM = {str(name).upper(): int(value) for value, name in table.items()}
        except (OSError, ValueError, AttributeError):
            _CUSTOM = {}
    return _CUSTOM


def _keycode(value, where: str) -> int:
    if isinstance(value, bool):
        raise ScriptError(f"{where}: a keycode name or number")
    if isinstance(value, int):
        if not 0 <= value <= 0xFFFF:
            raise ScriptError(f"{where}: keycode out of range")
        return value
    if not isinstance(value, str):
        raise ScriptError(f"{where}: a keycode name or number")
    custom = custom_keycodes().get(value.strip().upper())
    if custom is not None:
        return custom
    try:
        return parse_keycode(value)
    except ValueError as e:
        raise ScriptError(f"{where}: {e}") from None


def _layer_name(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScriptError(f"{where}: a layer name, as the keyboard names it (MIDI, Fn, ...)")
    return value.strip()


def _point(value, where: str) -> Point:
    if not isinstance(value, dict) or len(value) != 1 or next(iter(value)) not in _POINT_KINDS:
        raise ScriptError(f"{where}: one of {{keycode: ...}}, {{layer_key: ...}}, "
                          f"{{key: [row, col]}}")
    kind, v = next(iter(value.items()))
    if kind == "keycode":
        return Point(kind, _keycode(v, f"{where}.keycode"))
    if kind == "layer_key":
        return Point(kind, _layer_name(v, f"{where}.layer_key"))
    if (not isinstance(v, list) or len(v) != 2
            or not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in v)):
        raise ScriptError(f"{where}.key: [row, col], two numbers from 0")
    return Point(kind, (v[0], v[1]))


def _wait(value, where: str) -> Wait:
    if value == "next":
        return Wait("next")
    if not isinstance(value, dict) or len(value) != 1 or next(iter(value)) not in _WAIT_KINDS:
        raise ScriptError(f"{where}: next, or one of {{seconds: N}}, {{layer: NAME}}, "
                          f"{{press: KEYCODE}}, {{keycode: KEYCODE}}")
    kind, v = next(iter(value.items()))
    if kind == "seconds":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ScriptError(f"{where}.seconds: a number above 0")
        return Wait(kind, float(v))
    if kind == "layer":
        return Wait(kind, _layer_name(v, f"{where}.layer"))
    return Wait(kind, _keycode(v, f"{where}.{kind}"))


def _step(raw, where: str) -> Step:
    if not isinstance(raw, dict):
        raise ScriptError(f"{where}: a map of step fields")
    unknown = set(raw) - _STEP_KEYS
    if unknown:
        raise ScriptError(f"{where}: unknown field(s) {', '.join(sorted(unknown))}")
    if "point" in raw and "guide_to_layer" in raw:
        raise ScriptError(f"{where}: point and guide_to_layer both ring; give one")
    return Step(
        say=_say(raw["say"], f"{where}.say") if "say" in raw else (),
        text=_texts(raw["text"], f"{where}.text") if "text" in raw else {},
        point=_point(raw["point"], f"{where}.point") if "point" in raw else None,
        guide_to_layer=(_layer_name(raw["guide_to_layer"], f"{where}.guide_to_layer")
                        if "guide_to_layer" in raw else None),
        wait=_wait(raw["wait"], f"{where}.wait") if "wait" in raw else Wait("next"))


def parse_script(raw, path: str = "", user: bool = False) -> Tutorial:
    """A Tutorial from the parsed YAML `raw`. Raises ScriptError."""
    if not isinstance(raw, dict):
        raise ScriptError("the file is not a map of script fields")
    unknown = set(raw) - _SCRIPT_KEYS
    if unknown:
        raise ScriptError(f"unknown field(s) {', '.join(sorted(unknown))}")
    for key in ("id", "category", "title", "steps"):
        if key not in raw:
            raise ScriptError(f"{key}: missing")
    tid = raw["id"]
    if not isinstance(tid, str) or not _ID.fullmatch(tid):
        raise ScriptError("id: lower-case letters, digits and '-'")
    if raw["category"] not in CATEGORIES:
        raise ScriptError(f"category: one of {', '.join(CATEGORIES)}")
    min_protocol = raw.get("min_protocol", BASE_PROTOCOL)
    if isinstance(min_protocol, bool) or not isinstance(min_protocol, int):
        raise ScriptError("min_protocol: a number")
    steps = raw["steps"]
    if not isinstance(steps, list) or not steps:
        raise ScriptError("steps: a list of at least one step")
    parsed = tuple(_step(s, f"steps[{i}]") for i, s in enumerate(steps))
    return Tutorial(
        id=tid, category=raw["category"], title=_texts(raw["title"], "title"),
        summary=_texts(raw["summary"], "summary") if "summary" in raw else {},
        min_protocol=max(BASE_PROTOCOL, min_protocol), steps=parsed,
        path=path, user=user)


def load_file(path: str, user: bool = False) -> Tutorial:
    """Read and parse one script. Raises ScriptError, with the reason."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except OSError as e:
        raise ScriptError(f"cannot read: {e}") from None
    except yaml.YAMLError as e:
        raise ScriptError(f"not valid YAML: {e}") from None
    return parse_script(raw, path, user)


def user_dir() -> str:
    """``<config dir>/tutorials``, beside settings.yaml."""
    from polyhost.settings import settings_path
    return os.path.join(os.path.dirname(settings_path()), USER_DIRNAME)


def _yaml_files(directory: str) -> list:
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    return [os.path.join(directory, n) for n in names
            if n.endswith((".yaml", ".yml")) and not n.startswith(".")]


def load_all(shipped_dir: str = SHIPPED_DIR, user_directory: str | None = None):
    """(tutorials by id, errors). Each error is ``{"path", "error"}``. A user
    script replaces a shipped one with the same id; two files with the same id in
    one folder are an error for the second."""
    found, errors = {}, []
    for directory, user in ((shipped_dir, False), (user_directory, True)):
        if not directory:
            continue
        seen_here = set()
        for path in _yaml_files(directory):
            try:
                t = load_file(path, user)
            except ScriptError as e:
                errors.append({"path": path, "error": str(e)})
                continue
            if t.id in seen_here:
                errors.append({"path": path, "error": f"id {t.id!r} is used by "
                                                      f"{found[t.id].path} too"})
                continue
            seen_here.add(t.id)
            found[t.id] = t
    return found, errors
