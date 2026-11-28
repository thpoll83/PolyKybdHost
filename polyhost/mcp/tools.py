"""The MCP server's tools, and the allow-list of control methods they reach.

Plan and security model: docs/mcp-server-plan.md. Every tool calls the running
host through the control socket with the local authkey, the same way polyctl
does, so it can do only what polyctl can do for this user, and less:

* `TOOL_METHODS` is the allow-list. `HostLink.call()` refuses every method that is
  not on it before anything is sent. tests/mcp/tools_test.py freezes it.
* `settings.get` is allowed for the keys in `READABLE_SETTINGS` only.
* The connection names itself with `client.identify`, and the host then refuses
  it while its `mcp_enabled` setting is off, and checks the same allow-list again
  (ControlServer._mcp_refusal). A host that does not know `client.identify` is
  refused (OLD_HOST): it could apply neither check.
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
OLD_HOST = ("The running PolyKybdHost is older than this MCP server and cannot apply "
            "its AI-assistant setting. Update PolyKybdHost, then try again.")


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
                client = self._connect()
            except RpcError as exc:
                # A host of another control-protocol version: say so, not "not running".
                raise ToolError(exc.message) from None
            except (EOFError, OSError):
                raise HostUnavailable() from None
            try:
                # Name this connection, so the host applies its mcp_enabled setting.
                client.call(p.M_CLIENT_IDENTIFY, {"client": "mcp"})
            except RpcError as exc:
                client.close()
                if exc.code == p.ERR_METHOD_NOT_FOUND:
                    # Fail closed: a host older than client.identify cannot apply the
                    # mcp_enabled setting or its own allow-list check.
                    raise ToolError(OLD_HOST) from None
                raise ToolError(exc.message) from None
            except (EOFError, OSError):
                client.close()
                raise HostUnavailable() from None
            self._client = client
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
# Version 2: the user's overlay sets and keys drawn freely
# ---------------------------------------------------------------------------

_PHYSICAL = ("L:", "R:", "l:", "r:")


def _layer0(link):
    """(key table, {(row, col): layer-0 keycode}): one keymap read."""
    table = _table(link)
    _count, buffer = _keymap(link, 0)
    return table, {pos: _code_at(buffer, 0, *pos) for pos in table.by_pos}


def _overlay_key(link, ref, snapshot=None):
    """(keycode name, physical keys that send it on layer 0) for a key reference.

    A physical reference ("L:3.2", {"base": ...}, {"row", "col"}) is turned into its
    layer-0 keycode; anything else is read as a keycode name ("KC_F5", "F5").
    `snapshot` is a `_layer0()` result to reuse."""
    from polyhost.services import user_overlays
    physical = isinstance(ref, dict) or (isinstance(ref, str) and ref.strip().startswith(_PHYSICAL))
    table, base = snapshot or _layer0(link)
    if physical:
        try:
            name = table.resolve(ref, base, parse_keycode)
        except KeyRefError as exc:
            raise ToolError(str(exc)) from None
        code = base[table.by_name[name]]
    else:
        try:
            code = parse_keycode(str(ref))
        except ValueError as exc:
            raise ToolError(str(exc)) from None
    try:
        kc = user_overlays.check_key(_name(code))
    except user_overlays.UserOverlayError as exc:
        raise ToolError(f"{exc}. Images belong to keycodes, and this key sends "
                        f"{_name(code)}.") from None
    shows_on = sorted((table.by_pos[pos] for pos, c in base.items() if c == kc.value),
                      key=table.names().index)
    return kc.name, shows_on


def _app_arg(args):
    from polyhost.services import user_overlays
    try:
        return user_overlays.check_app(args.get("app"))
    except user_overlays.UserOverlayError as exc:
        raise ToolError(str(exc)) from None


def _binding(link, b, snapshot=None):
    """A binding for the host, with its key resolved and its drawing checked here,
    so a bad shape is reported before anything is written."""
    from polyhost.services import key_drawing
    if not isinstance(b, dict):
        raise ToolError("a binding is an object with key, drawing, mods and legend")
    extra = set(b) - {"key", "drawing", "mods", "legend"}
    if extra:
        raise ToolError(f"unknown binding fields: {sorted(extra)}")
    key, shows_on = _overlay_key(link, b.get("key"), snapshot)
    try:
        _mask, notes = key_drawing.render(b.get("drawing"))
    except key_drawing.DrawingError as exc:
        raise ToolError(f"{key}: {exc}") from None
    out = {"key": key, "drawing": b["drawing"], "mods": b.get("mods") or [],
           "legend": b.get("legend", True)}
    return out, shows_on, [f"{key}: {n}" for n in notes]


def find_icons(link, args):
    from polyhost.services import key_drawing
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolError("query is one or more words, for example \"copy\"")
    return {"icons": key_drawing.find_icons(query)}


def list_overlay_keys(link, args):
    from polyhost.device.keys import KeyCode
    from polyhost.res.overlay_layout import _has_cell
    table = _table(link)
    _count, buffer = _keymap(link, 0)
    on_base = {}
    for name in table.names():
        on_base.setdefault(_code_at(buffer, 0, *table.by_name[name]), []).append(name)
    # Every keycode with an overlay slot, also those only other layers use (F5 on Fn).
    return {"keys": [{"keycode": kc.name, "on_layer_0": on_base.get(kc.value, [])}
                     for kc in KeyCode if _has_cell(kc)]}


def list_user_overlays(link, args):
    sets = link.call(p.M_USER_OVERLAY_LIST)
    return {"sets": [{"app": str(s.get("app")), "keys": int(s.get("keys", 0))} for s in sets]}


def create_overlay(link, args):
    app = _app_arg(args)
    bindings = args.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ToolError("bindings is a non-empty list")
    clean, notes = [], []
    snapshot = _layer0(link)        # one keymap read for the whole set
    for b in bindings:
        cb, _shows_on, n = _binding(link, b, snapshot)
        clean.append(cb)
        notes += n
    result = link.call(p.M_USER_OVERLAY_SET, {"app": app, "bindings": clean, "merge": False})
    return {"app": app, "placed": _placed(result), "notes": notes}


def draw_key(link, args):
    app = _app_arg(args)
    follow = args.get("follow", "keycode")
    if follow == "key":
        raise ToolError("follow \"key\" (an image on one physical key) needs firmware "
                        "support that is not released yet; use follow \"keycode\"")
    if follow != "keycode":
        raise ToolError("follow is \"keycode\" or \"key\"")
    binding = {k: args[k] for k in ("key", "drawing", "mods", "legend") if k in args}
    cb, shows_on, notes = _binding(link, binding)
    result = link.call(p.M_USER_OVERLAY_SET, {"app": app, "bindings": [cb], "merge": True})
    from polyhost.services.user_overlays import mod_names, modifier
    want = mod_names(modifier(cb["mods"]))
    placed = [x for x in _placed(result) if x["key"] == cb["key"] and x["mods"] == want]
    return {"app": app, "key": cb["key"], "mods": placed[0]["mods"] if placed else cb["mods"],
            "legend": cb["legend"], "shows_on": shows_on, "notes": notes}


def clear_key(link, args):
    app = _app_arg(args)
    key, _shows_on = _overlay_key(link, args.get("key"))
    result = link.call(p.M_USER_OVERLAY_CLEAR,
                       {"app": app, "key": key, "mods": args.get("mods") or []})
    return {"app": app, "key": key, "removed": bool(result.get("removed"))}


def delete_overlay(link, args):
    app = _app_arg(args)
    result = link.call(p.M_USER_OVERLAY_CLEAR, {"app": app})
    return {"app": app, "removed": bool(result.get("removed"))}


def preview_overlay(link, args):
    app = _app_arg(args)
    mods = args.get("mods") or []
    result = link.call(p.M_USER_OVERLAY_PREVIEW, {"app": app, "mods": mods})
    return {"app": app, "mods": mods, "image": str(result.get("png_base64", ""))}


def _placed(result):
    return [{"key": str(x.get("key")), "mods": list(x.get("mods") or []),
             "legend": bool(x.get("legend", True))} for x in (result or {}).get("placed", [])]


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


_WRITE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True,
          "openWorldHint": False}
_APP = {"type": "string",
        "description": "The app's process name in lowercase (see list_app_overlays), "
                       "or \"*\" for every app."}
DRAWING_HELP = (
    "A drawing is a list of shapes on the 72x40 px key, drawn in order, [0,0] top "
    "left: {\"rect\": [x,y,w,h], \"fill\": bool, \"width\": n}, {\"ellipse\": [x,y,w,h], "
    "...}, {\"line\": [x0,y0,x1,y1], \"width\": n}, {\"polygon\": [[x,y],...]}, "
    "{\"text\": \"F5\", \"at\": [x,y], \"size\": 6-40, \"align\": "
    "\"left|center|right\"} (Latin letters only), {\"icon\": name from find_icons, "
    "\"at\": [x,y]}, {\"bitmap\": [\"#..#\", ...], \"at\": [x,y], \"scale\": 1-4}; "
    "add \"erase\": true to draw black. With legend true the key's legend stays and "
    "the firmware cuts 3 px around the drawing; keep the drawing to one side then. "
    "Call preview_overlay to see the result.")
_BINDING = {
    "type": "object",
    "properties": {
        "key": {"description": "A physical key (\"L:3.2\", {\"base\": \"KC_Q\"}) or a "
                               "keycode name (\"KC_F5\")."},
        "drawing": {"type": "array", "items": {"type": "object"}},
        "mods": {"type": "array", "items": {"type": "string",
                                            "enum": ["CTRL", "SHIFT", "ALT", "GUI"]},
                 "description": "Show the drawing while these modifiers are held."},
        "legend": {"type": "boolean", "default": True,
                   "description": "false: the drawing replaces the key's legend."},
    },
    "required": ["key", "drawing"],
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
    "find_icons": (find_icons,
                   "Search the keyboard's icon library by words (\"copy\", \"play\"). "
                   "Returns icon names for an {\"icon\": name} shape, with their size.",
                   _schema({"query": {"type": "string"}}, ["query"]), _READ),
    "list_overlay_keys": (list_overlay_keys,
                          "The keycodes that can have an image, with the physical keys that "
                          "send each on layer 0. An image belongs to a keycode: it shows on "
                          "every key that sends it.", _schema(), _READ),
    "list_user_overlays": (list_user_overlays,
                           "The overlay sets the user or an assistant made, by app.",
                           _schema(), _READ),
    "create_overlay": (create_overlay,
                       "Make the user's overlay set for an app, replacing the set made "
                       "before. It is laid over the app's shipped icons: the user's keys "
                       "win, the shipped icons stay on the others. " + DRAWING_HELP,
                       _schema({"app": _APP, "bindings": {"type": "array", "items": _BINDING}},
                               ["app", "bindings"]), _WRITE),
    "draw_key": (draw_key,
                 "Draw a picture on one key, for one app or for every app (app \"*\"), "
                 "with or without the key's legend. Replaces an earlier drawing on that "
                 "key and modifiers. " + DRAWING_HELP,
                 _schema({"app": _APP, **_BINDING["properties"],
                          "follow": {"type": "string", "enum": ["keycode", "key"],
                                     "default": "keycode",
                                     "description": "keycode: on every key that sends "
                                                    "this keycode. key: on this physical "
                                                    "key only (needs newer firmware)."}},
                         ["app", "key", "drawing"]), _WRITE),
    "clear_key": (clear_key,
                  "Remove the drawing on one key (and modifiers) from an app's user set.",
                  _schema({"app": _APP, "key": _BINDING["properties"]["key"],
                           "mods": _BINDING["properties"]["mods"]}, ["app", "key"]), _WRITE),
    "delete_overlay": (delete_overlay,
                       "Remove an app's whole user overlay set. Shipped sets stay.",
                       _schema({"app": _APP}, ["app"]), _WRITE),
    "preview_overlay": (preview_overlay,
                        "A picture of both halves with the image each key shows for an app "
                        "(layer 0). Keys show their keycode name in grey where the legend "
                        "stays; the real legend depends on the language.",
                        _schema({"app": _APP, "mods": _BINDING["properties"]["mods"]},
                                ["app"]), _READ),
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
    "find_icons": set(),
    "list_overlay_keys": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER},
    "list_user_overlays": {p.M_USER_OVERLAY_LIST},
    "create_overlay": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER,
                       p.M_USER_OVERLAY_SET},
    "draw_key": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER,
                 p.M_USER_OVERLAY_SET},
    "clear_key": {p.M_STATUS_GET, p.M_KEYMAP_LAYER_COUNT, p.M_KEYMAP_BUFFER,
                  p.M_USER_OVERLAY_CLEAR},
    "delete_overlay": {p.M_USER_OVERLAY_CLEAR},
    "preview_overlay": {p.M_USER_OVERLAY_PREVIEW},
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
    "find_icons": {"icons"},
    "list_overlay_keys": {"keys"},
    "list_user_overlays": {"sets"},
    "create_overlay": {"app", "placed", "notes"},
    "draw_key": {"app", "key", "mods", "legend", "shows_on", "notes"},
    "clear_key": {"app", "key", "removed"},
    "delete_overlay": {"app", "removed"},
    "preview_overlay": {"app", "mods", "image"},
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


def result_content(result):
    """The MCP content items of a result: an "image" field as a PNG image item, the
    layout drawing as plain text, everything else as JSON text."""
    if set(result) == {"layer", "layout"}:
        return [{"type": "text", "text": result["layout"]}]
    items = []
    if "image" in result:
        result = dict(result)
        items.append({"type": "image", "data": result.pop("image"), "mimeType": "image/png"})
    items.append({"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)})
    return items
