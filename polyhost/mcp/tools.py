"""The MCP server's tools, and the allow-list of control methods they reach.

Plan and security model: docs/mcp-server-plan.md. Every tool calls the running
host through the control socket with the local authkey, the same way polyctl
does, so it can do only what polyctl can do for this user, and less:

* `TOOL_METHODS` is the allow-list. `HostLink.call()` refuses every method that is
  not on it before anything is sent. tests/mcp/tools_test.py freezes it.
* `settings.get` is allowed for the keys in `READABLE_SETTINGS` only.
* Every result is built field by field from `RESULT_FIELDS`, never by passing a
  host reply through, so a field added to `status.get` later is not returned.
"""
from __future__ import annotations

import json
import pathlib

from polyhost.device.command_ids import GlyphScript, IdleStyle  # stdlib Enum, no Qt
from polyhost.server import protocol as p
from polyhost.services.keycode_text import keycode_text, parse_keycode
from polyhost.services.key_names import KeyRefError, load_table

MATRIX_ROWS = 10
MATRIX_COLUMNS = 8
BRIGHTNESS_MAX = 50  # PolyKybd.set_brightness clamps to 0..50

MAPPING_FILE = (pathlib.Path(__file__).resolve().parent.parent
                / "res" / "overlay-mapping.poly.yaml")

DAYLIGHT_SETTING = "brightness_set_daylight_dependent"
READABLE_SETTINGS = frozenset({DAYLIGHT_SETTING})

# Lowercase names for the enum values. A closed list here even for GlyphScript,
# whose wire range is open: the firmware ACKs an unknown script without drawing it.
IDLE_STYLES = {s.name.lower(): s.value for s in IdleStyle}
GLYPH_SCRIPTS = {s.name.lower(): s.value for s in GlyphScript}

NOT_RUNNING = "PolyKybdHost is not running. Start it, then try again."


class ToolError(Exception):
    """A tool failed in a way the assistant should read: shown with isError true."""


class HostUnavailable(ToolError):
    def __init__(self):
        super().__init__(NOT_RUNNING)


class MethodNotAllowed(ToolError):
    pass


# ---------------------------------------------------------------------------
# The connection to the host
# ---------------------------------------------------------------------------

class HostLink:
    """A lazily opened control-socket client that sends allowed methods only.

    `connect` returns an object with `call(method, params)` and `close()`
    (polyctl's RpcClient). A host that is not running, or one that went away,
    raises HostUnavailable; the next call tries to connect again."""

    def __init__(self, connect=None):
        self._connect = connect or _default_connect
        self._client = None

    def call(self, method, params=None):
        params = params or {}
        if method not in ALLOWED_METHODS:
            raise MethodNotAllowed(f"the MCP server does not use {method}")
        if method == p.M_SETTINGS_GET and params.get("key") not in READABLE_SETTINGS:
            raise MethodNotAllowed(f"the MCP server does not read the setting {params.get('key')!r}")
        from polyhost.cli.polyctl import RpcError
        for attempt in (0, 1):
            client = self._open()
            try:
                return client.call(method, params)
            except RpcError as exc:
                raise ToolError(exc.message) from None
            except (EOFError, OSError):
                # The host restarted since the last call: reconnect once.
                self.close()
                if attempt:
                    raise HostUnavailable() from None
        raise HostUnavailable()

    def _open(self):
        if self._client is None:
            from polyhost.cli.polyctl import RpcError
            try:
                self._client = self._connect()
            except RpcError as exc:
                # A host of another control-protocol version: say so, not "not running".
                raise ToolError(exc.message) from None
            except (EOFError, OSError):
                raise HostUnavailable() from None
        return self._client

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None


def _default_connect():
    from polyhost.cli.polyctl import connect
    return connect()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _layer_arg(args, key="layer", default=0):
    layer = args.get(key, default)
    if not isinstance(layer, int) or isinstance(layer, bool) or layer < 0:
        raise ToolError(f"'{key}' must be a layer number, 0 or more")
    return layer


def _keymap(link, layer):
    """(layer_count, buffer) with `layer` checked against the keyboard's count."""
    count = link.call(p.M_KEYMAP_LAYER_COUNT)
    if layer >= count:
        raise ToolError(f"the keyboard has layers 0 to {count - 1}, not {layer}")
    buffer = link.call(p.M_KEYMAP_BUFFER)
    if len(buffer) < count * MATRIX_ROWS * MATRIX_COLUMNS:
        raise ToolError("the keyboard sent a short keymap; try again")
    return count, buffer


def _code_at(buffer, layer, row, col):
    return buffer[(layer * MATRIX_ROWS + row) * MATRIX_COLUMNS + col]


def _name(code):
    return keycode_text(code, empty="KC_NO")


_SHORT = None


def _short_name(code):
    """The shortest QMK name of a keycode (KC_ESC, not KC_ESCAPE), without the KC_
    prefix, for the drawing. A composite keycode such as MO(1) as keycode_text()
    writes it. Names of underscores or X only (_______, XXXXXXX) are skipped."""
    global _SHORT
    if _SHORT is None:
        from polyhost.services.keycode_text import keycode_tables
        _SHORT = {}
        for name, value in keycode_tables()[0].items():
            if name.strip("_X") and (value not in _SHORT or len(name) < len(_SHORT[value])):
                _SHORT[value] = name
    name = _name(code)
    if not any(c in name for c in "()") and code in _SHORT:
        name = _SHORT[code]
    return name[3:] if name.startswith("KC_") else name


def _table(link):
    """The key table, or an error on a keyboard that has none (split42)."""
    status = link.call(p.M_STATUS_GET)
    name = str(status.get("name") or "")
    if "split42" in name.lower():
        raise ToolError(f"the key tools support the split72 only, and this keyboard is "
                        f"{name}")
    return load_table("split72")


def _choice(value, choices, what):
    if not isinstance(value, str) or value.lower() not in choices:
        raise ToolError(f"unknown {what} {value!r}; use one of: {', '.join(choices)}")
    return choices[value.lower()]


def _app_names(path=MAPPING_FILE):
    import yaml
    try:
        with open(path, encoding="utf-8") as f:
            mapping = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ToolError(f"cannot read the overlay mapping file: {exc}") from None
    names = set()
    for key in mapping if isinstance(mapping, dict) else ():
        names.update(n.strip() for n in str(key).split(",") if n.strip())
    return sorted(names)


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

def get_status(link, args):
    s = link.call(p.M_STATUS_GET)
    return {
        "connected": bool(s.get("connected")),
        "device_present": bool(s.get("device_present")),
        "paused": bool(s.get("paused")),
        "keyboard": s.get("name"),
        "fw_version": s.get("fw_version"),
        "protocol": s.get("protocol"),
        "hw_version": s.get("hw_version"),
        "current_language": s.get("current_lang"),
        "host_version": s.get("host_version"),
        "safe_mode": bool(s.get("safe_mode")),
    }


def list_languages(link, args):
    return {"languages": [str(code) for code in link.call(p.M_LANG_LIST)]}


def get_keymap(link, args):
    layer = _layer_arg(args)
    table = _table(link)
    count, buffer = _keymap(link, layer)
    return {
        "layer": layer,
        "layer_count": count,
        "keys": {name: _name(_code_at(buffer, layer, *table.by_name[name]))
                 for name in table.names()},
    }


def list_app_overlays(link, args):
    return {"apps": _app_names()}


def set_language(link, args):
    lang = args.get("lang")
    known = [str(c) for c in link.call(p.M_LANG_LIST)]
    if lang not in known:
        raise ToolError(f"unknown language {lang!r}; the keyboard has: {', '.join(known)}")
    link.call(p.M_LANG_SET, {"lang": lang})
    return {"language": lang}


def set_brightness(link, args):
    value = args.get("value")
    if value == "default":
        daylight = bool(link.call(p.M_SETTINGS_GET, {"key": DAYLIGHT_SETTING}))
        link.call(p.M_DAYLIGHT_REFRESH)
        return {"mode": "daylight" if daylight else "keyboard"}
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= BRIGHTNESS_MAX:
        raise ToolError(f"brightness is a number from 0 to {BRIGHTNESS_MAX}, or \"default\"")
    link.call(p.M_BRIGHTNESS_SET, {"value": value})
    return {"brightness": value}


def set_idle_style(link, args):
    value = _choice(args.get("style"), IDLE_STYLES, "idle style")
    link.call(p.M_IDLE_STYLE_SET, {"value": value})
    return {"idle_style": args["style"].lower()}


def set_glyph_script(link, args):
    value = _choice(args.get("script"), GLYPH_SCRIPTS, "glyph script")
    link.call(p.M_GLYPH_SCRIPT_SET, {"value": value})
    return {"glyph_script": args["script"].lower()}


def list_keys(link, args):
    layer = _layer_arg(args)
    table = _table(link)
    _count, buffer = _keymap(link, layer)
    keys = []
    for name in table.names():
        row, col = table.by_name[name]
        keys.append({
            "key": name,
            "row": row,
            "col": col,
            "thumb": name in table.thumb,
            "has_display": name not in table.no_display,
            "keycode": _name(_code_at(buffer, layer, row, col)),
            "base": _name(_code_at(buffer, 0, row, col)),
        })
    return {"layer": layer, "keys": keys}


def show_layout(link, args):
    layer = _layer_arg(args)
    table = _table(link)
    _count, buffer = _keymap(link, layer)

    def cell(name):
        return _short_name(_code_at(buffer, layer, *table.by_name[name]))

    return {
        "layer": layer,
        "layout": (f"Layer {layer}, keycodes as their shortest QMK names without KC_ "
                   f"(ESC is KC_ESC). Column headers are L:X and R:X, "
                   f"rows are Y, so a key's name is <header>.<Y>.\n" + table.grid(cell)),
    }


def set_key(link, args):
    layer = _layer_arg(args)
    table = _table(link)
    try:
        code = parse_keycode(str(args.get("keycode", "")))
    except ValueError as exc:
        raise ToolError(str(exc)) from None
    _count, buffer = _keymap(link, layer)
    base = {pos: _code_at(buffer, 0, *pos) for pos in table.by_pos}
    try:
        name = table.resolve(args.get("key"), base, parse_keycode)
    except KeyRefError as exc:
        raise ToolError(str(exc)) from None
    row, col = table.by_name[name]
    previous = _code_at(buffer, layer, row, col)
    link.call(p.M_KEYMAP_SET, {"layer": layer, "row": row, "col": col, "keycode": code})
    return {
        "key": name,
        "layer": layer,
        "keycode": _name(code),
        "previous": _name(previous),
        "note": ("previous is the keycode read just before the write. The keyboard "
                 "stores the change at once. To undo it, set previous again."),
    }


def set_overlays(link, args):
    enabled = args.get("enabled")
    if not isinstance(enabled, bool):
        raise ToolError("'enabled' must be true or false")
    link.call(p.M_OVERLAY_ENABLE if enabled else p.M_OVERLAY_DISABLE)
    return {"overlays": enabled}


# ---------------------------------------------------------------------------
# Definitions, the allow-list and the result fields
# ---------------------------------------------------------------------------

_READ = {"readOnlyHint": True, "openWorldHint": False}
_SET = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
        "openWorldHint": False}
_LAYER = {"type": "integer", "minimum": 0, "default": 0,
          "description": "Keymap layer. 0 is the base layer."}
_KEY_REF = {
    "description": ("The key: a name like \"L:1.1\" (see list_keys or show_layout), "
                    "{\"base\": \"KC_Q\"} for the one key that sends Q on layer 0, or "
                    "{\"row\": 2, \"col\": 3}."),
    "oneOf": [
        {"type": "string"},
        {"type": "object", "properties": {"base": {"type": "string"}},
         "required": ["base"], "additionalProperties": False},
        {"type": "object", "properties": {"row": {"type": "integer"}, "col": {"type": "integer"}},
         "required": ["row", "col"], "additionalProperties": False},
    ],
}


def _schema(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required),
            "additionalProperties": False}


# name -> (handler, description, input schema, annotations)
TOOLS = {
    "get_status": (get_status,
                   "Whether the PolyKybd keyboard is connected, its firmware version and "
                   "its current language.", _schema(), _READ),
    "list_languages": (list_languages,
                       "The language codes the keyboard can show on its keycaps.",
                       _schema(), _READ),
    "get_keymap": (get_keymap,
                   "The keycode of every key on one layer, by key name.",
                   _schema({"layer": _LAYER}), _READ),
    "list_app_overlays": (list_app_overlays,
                          "The applications PolyKybdHost has keycap overlays for.",
                          _schema(), _READ),
    "list_keys": (list_keys,
                  "Every key with its name (L:X.Y or R:X.Y: half, column from the outer "
                  "edge, row from the top), matrix position, whether it is a thumb key or "
                  "has a display, its keycode on the layer and on layer 0.",
                  _schema({"layer": _LAYER}), _READ),
    "show_layout": (show_layout,
                    "A drawing of both halves with each key's keycode in its place. Use it "
                    "to find keys by position, for example the keys left of the space bar.",
                    _schema({"layer": _LAYER}), _READ),
    "set_language": (set_language,
                     "Switch the keycap language. Use a code from list_languages.",
                     _schema({"lang": {"type": "string"}}, ["lang"]), _SET),
    "set_brightness": (set_brightness,
                       "Set the keycap display brightness from 0 to 50, or \"default\" to "
                       "return to the brightness mode the user configured.",
                       _schema({"value": {"oneOf": [
                           {"type": "integer", "minimum": 0, "maximum": BRIGHTNESS_MAX},
                           {"type": "string", "enum": ["default"]}]}}, ["value"]), _SET),
    "set_idle_style": (set_idle_style,
                       "Set what the keycaps show while the keyboard is idle.",
                       _schema({"style": {"type": "string", "enum": list(IDLE_STYLES)}},
                               ["style"]), _SET),
    "set_glyph_script": (set_glyph_script,
                         "Draw the letter and digit legends in another script, or "
                         "\"standard\" for the normal legends.",
                         _schema({"script": {"type": "string", "enum": list(GLYPH_SCRIPTS)}},
                                 ["script"]), _SET),
    "set_key": (set_key,
                "Change the keycode of one key on one layer. The keyboard stores it at "
                "once. Returns the previous keycode, so the change can be undone.",
                _schema({"layer": _LAYER, "key": _KEY_REF,
                         "keycode": {"type": "string",
                                     "description": "A QMK keycode name such as KC_MUTE, "
                                                    "MO(1) or LCTL(KC_C)."}},
                        ["key", "keycode"]),
                {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True,
                 "openWorldHint": False}),
    "set_overlays": (set_overlays,
                     "Turn the per-application keycap overlays on or off.",
                     _schema({"enabled": {"type": "boolean"}}, ["enabled"]), _SET),
}

# The control methods each tool may reach. Frozen by tests/mcp/tools_test.py.
TOOL_METHODS = {
    "get_status": {p.M_STATUS_GET},
    "list_languages": {p.M_LANG_LIST},
    "get_keymap": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER},
    "list_app_overlays": set(),
    "list_keys": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER},
    "show_layout": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER},
    "set_language": {p.M_LANG_LIST, p.M_LANG_SET},
    "set_brightness": {p.M_BRIGHTNESS_SET, p.M_SETTINGS_GET, p.M_DAYLIGHT_REFRESH},
    "set_idle_style": {p.M_IDLE_STYLE_SET},
    "set_glyph_script": {p.M_GLYPH_SCRIPT_SET},
    "set_key": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER, p.M_KEYMAP_SET},
    "set_overlays": {p.M_OVERLAY_ENABLE, p.M_OVERLAY_DISABLE},
}
ALLOWED_METHODS = frozenset().union(*TOOL_METHODS.values())

# The fields each tool's result may have. Checked by tests/mcp/tools_test.py.
RESULT_FIELDS = {
    "get_status": {"connected", "device_present", "paused", "keyboard", "fw_version",
                   "protocol", "hw_version", "current_language", "host_version", "safe_mode"},
    "list_languages": {"languages"},
    "get_keymap": {"layer", "layer_count", "keys"},
    "list_app_overlays": {"apps"},
    "list_keys": {"layer", "keys"},
    "show_layout": {"layer", "layout"},
    "set_language": {"language"},
    "set_brightness": {"brightness", "mode"},
    "set_idle_style": {"idle_style"},
    "set_glyph_script": {"glyph_script"},
    "set_key": {"key", "layer", "keycode", "previous", "note"},
    "set_overlays": {"overlays"},
}
LIST_KEYS_FIELDS = {"key", "row", "col", "thumb", "has_display", "keycode", "base"}


def tool_list():
    """The `tools/list` result entries."""
    return [{"name": name, "description": desc, "inputSchema": schema, "annotations": ann}
            for name, (_fn, desc, schema, ann) in TOOLS.items()]


def call_tool(link, name, arguments):
    """Run one tool. Returns (result dict, None) or (None, error text)."""
    handler = TOOLS[name][0]
    if not isinstance(arguments, dict):
        return None, "arguments must be an object"
    try:
        return handler(link, arguments), None
    except ToolError as exc:
        return None, str(exc)


def result_text(result):
    """The text content of a result: the layout drawing as is, everything else JSON."""
    if set(result) == {"layer", "layout"}:
        return result["layout"]
    return json.dumps(result, ensure_ascii=False, indent=1)
