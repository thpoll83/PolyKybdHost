"""Keycode names, a Qt-key translation table, and a readable rendering of a step list.

Qt-free on purpose, like every other half of the macro editor: the translation table is
the part with a real chance of being wrong, and a table that can only be exercised
through a widget is a table nobody exercises. `qt_key_to_keycode` takes the Qt key as a
plain int (which is all `Qt::Key` ever was), so the whole recorder can be tested without
a display.

⚠️ **Recording reads the CHARACTER the key produced, not the physical key.** Qt reports
`Qt::Key_Z` for whatever key the OS says types a `z`, so on a German layout the key in
the QWERTY `y` position records as `KC_Z` -- the keycode that types `z` on that machine,
which is what the person pressing it meant. It is the wrong answer only if the macro
will be replayed on a machine with a different OS layout, and the step list names every
keycode it stored so that case is visible and fixable rather than silent. The physical
alternative (`nativeScanCode`) is exact on X11 and needs a per-platform table on Windows
and macOS, so it buys correctness in the rarer case at the cost of two tables that
cannot be tested here.
"""

from __future__ import annotations

from polyhost.services import macro_body

# Qt::Key values. Spelled out rather than imported so this module never touches Qt --
# they are ABI-stable constants, not an implementation detail.
_K_ESCAPE = 0x01000000
_K_TAB = 0x01000001
_K_BACKTAB = 0x01000002
_K_BACKSPACE = 0x01000003
_K_RETURN = 0x01000004
_K_ENTER = 0x01000005
_K_INSERT = 0x01000006
_K_DELETE = 0x01000007
_K_PAUSE = 0x01000008
_K_PRINT = 0x01000009
_K_HOME = 0x01000010
_K_END = 0x01000011
_K_LEFT = 0x01000012
_K_UP = 0x01000013
_K_RIGHT = 0x01000014
_K_DOWN = 0x01000015
_K_PAGEUP = 0x01000016
_K_PAGEDOWN = 0x01000017
_K_SHIFT = 0x01000020
_K_CONTROL = 0x01000021
_K_META = 0x01000022
_K_ALT = 0x01000023
_K_CAPSLOCK = 0x01000024
_K_NUMLOCK = 0x01000025
_K_SCROLLLOCK = 0x01000026
_K_F1 = 0x01000030
_K_MENU = 0x01000055
_K_ALTGR = 0x01001103

# The named keys, as KC_* names resolved against the shipped keycodes.h. Names rather
# than numbers so a wrong entry reads as wrong.
_NAMED_KEYS: dict[int, str] = {
    _K_ESCAPE: "KC_ESCAPE",
    _K_TAB: "KC_TAB",
    _K_BACKTAB: "KC_TAB",          # shift+tab arrives as its own key
    _K_BACKSPACE: "KC_BACKSPACE",
    _K_RETURN: "KC_ENTER",
    _K_ENTER: "KC_KP_ENTER",       # the keypad one; Qt distinguishes them
    _K_INSERT: "KC_INSERT",
    _K_DELETE: "KC_DELETE",
    _K_PAUSE: "KC_PAUSE",
    _K_PRINT: "KC_PRINT_SCREEN",
    _K_HOME: "KC_HOME",
    _K_END: "KC_END",
    _K_LEFT: "KC_LEFT",
    _K_UP: "KC_UP",
    _K_RIGHT: "KC_RIGHT",
    _K_DOWN: "KC_DOWN",
    _K_PAGEUP: "KC_PAGE_UP",
    _K_PAGEDOWN: "KC_PAGE_DOWN",
    _K_SHIFT: "KC_LEFT_SHIFT",
    _K_CONTROL: "KC_LEFT_CTRL",
    _K_META: "KC_LEFT_GUI",
    _K_ALT: "KC_LEFT_ALT",
    _K_ALTGR: "KC_RIGHT_ALT",
    _K_CAPSLOCK: "KC_CAPS_LOCK",
    _K_NUMLOCK: "KC_NUM_LOCK",
    _K_SCROLLLOCK: "KC_SCROLL_LOCK",
    _K_MENU: "KC_APPLICATION",
    0x20: "KC_SPACE",
}
# F1..F24 are contiguous in both worlds.
for _i in range(24):
    _NAMED_KEYS[_K_F1 + _i] = f"KC_F{_i + 1}"

# One US key produces two characters, and Qt reports whichever one the shift state made,
# so BOTH have to land on the same keycode -- otherwise recording `_` stores nothing
# while `-` works, which reads as the recorder dropping keys at random.
_PUNCTUATION: dict[str, str] = {
    "-_": "KC_MINUS",
    "=+": "KC_EQUAL",
    "[{": "KC_LEFT_BRACKET",
    "]}": "KC_RIGHT_BRACKET",
    "\\|": "KC_BACKSLASH",
    ";:": "KC_SEMICOLON",
    "'\"": "KC_QUOTE",
    "`~": "KC_GRAVE",
    ",<": "KC_COMMA",
    ".>": "KC_DOT",
    "/?": "KC_SLASH",
    "1!": "KC_1",
    "2@": "KC_2",
    "3#": "KC_3",
    "4$": "KC_4",
    "5%": "KC_5",
    "6^": "KC_6",
    "7&": "KC_7",
    "8*": "KC_8",
    "9(": "KC_9",
    "0)": "KC_0",
}

_MOD_SYMBOL = {
    0xE0: "Ctrl", 0xE1: "Shift", 0xE2: "Alt", 0xE3: "Gui",
    0xE4: "RCtrl", 0xE5: "RShift", 0xE6: "RAlt", 0xE7: "RGui",
}

# KC_NO and KC_TRANSPARENT. Keymap placeholders, not keys -- see `_load`.
PLACEHOLDER_VALUES = frozenset((0x00, 0x01))

_keycodes: dict[str, int] | None = None
_by_value: dict[int, str] | None = None
_qt_map: dict[int, int] | None = None


def _load() -> dict[str, int]:
    """The basic (one-byte) QMK keycodes, by name.

    Read from the same `res/keycodes.h` the keycode browser parses, so the names in a
    macro are the names everywhere else in the app -- and a QMK update moves both at
    once. Keycodes above 0xFF cannot ride a macro body at all (the wire format stores
    one byte), and the two keymap placeholders are meaningless in a macro.

    ⚠️ The placeholders are excluded BY VALUE, not by name. QMK spells each of them
    three ways -- `KC_NO`/`XXXXXXX` and `KC_TRANSPARENT`/`KC_TRNS`/`_______` -- and the
    alias pass brings every spelling along, so a name blocklist leaks whichever one it
    forgot. Excluding 0x00 and 0x01 cannot miss a spelling that has not been invented
    yet.
    """
    global _keycodes, _by_value
    if _keycodes is None:
        from polyhost.gui.layout_dialog.qmk_keycode_helper import (
            HEADER_FILE, parse_qmk_keycodes,
        )
        try:
            table = parse_qmk_keycodes(HEADER_FILE)
        except Exception:
            table = {}
        _keycodes = {n: v for n, v in table.items()
                     if v not in PLACEHOLDER_VALUES and 0 <= v <= 0xFF}
        # `setdefault`, so the FIRST name wins if a value ever gains two. Measured
        # today: no value in this header has two enum names -- QMK's short aliases are
        # `#define`s, which the enum parser never sees -- so the tie-break is inert and
        # the choice cannot be verified by behaviour. It is written this way because
        # the header lists the canonical long form first, so first-wins is the rule
        # that would give KC_ENTER rather than a short alias if one ever appeared.
        # `macro_keys_test.KeycodeTableTest` pins the measured fact, so the day that
        # changes it is a failing test rather than a silently renamed key.
        _by_value = {}
        for name, value in _keycodes.items():
            _by_value.setdefault(value, name)
    return _keycodes


def keycodes() -> dict[str, int]:
    """Name -> value for every keycode a macro step can hold."""
    return dict(_load())


def name_for(code: int) -> str:
    """The KC_* name for a value, or a bare hex number when it has none.

    A macro can carry any byte -- the firmware plays what it is given -- so an unnamed
    one is displayed rather than refused.
    """
    _load()
    return (_by_value or {}).get(int(code), f"0x{int(code):02X}")


def value_for(name: str) -> int | None:
    """The value for a KC_* name, or a bare hex/decimal number. None when unparseable."""
    table = _load()
    text = (name or "").strip()
    if not text:
        return None
    if text.upper() in table:
        return table[text.upper()]
    try:
        value = int(text, 0)
    except ValueError:
        return None
    return value if 0 <= value <= 0xFF else None


def qt_key_to_keycode(qt_key: int, text: str = "") -> int | None:
    """Translate one Qt key value into a basic keycode, or None when there is none.

    `text` is the event's `text()` and is consulted only as a fallback, for a layout
    that produces a character Qt has no `Key_*` constant for.
    """
    global _qt_map
    table = _load()
    if _qt_map is None:
        built: dict[int, int] = {}
        for key, name in _NAMED_KEYS.items():
            if name in table:
                built[key] = table[name]
        for pair, name in _PUNCTUATION.items():
            if name in table:
                for ch in pair:
                    built[ord(ch)] = table[name]
        for i in range(26):
            name = f"KC_{chr(ord('A') + i)}"
            if name in table:
                built[ord("A") + i] = table[name]   # Qt::Key_A is 'A', not 'a'
        _qt_map = built

    hit = _qt_map.get(int(qt_key))
    if hit is not None:
        return hit
    if text:
        ch = text[0]
        alt = _qt_map.get(ord(ch.upper()))
        if alt is not None:
            return alt
    return None


def describe(steps: list[macro_body.Step]) -> str:
    """One line naming what a step list does, for a summary field.

    Runs of characters collapse into a quoted string and a held chord collapses into
    `Ctrl+Shift+P`, because the raw list -- down, down, tap, up, up -- is exactly what
    the user was trying not to have to read.
    """
    if not steps:
        return ""
    parts: list[str] = []
    text = ""
    held: list[int] = []
    pending = False          # something is held that has not been reported yet

    def flush_text():
        nonlocal text
        if text:
            parts.append(f'"{text}"')
            text = ""

    def chord(mods: list[int], key: int) -> str:
        prefix = "+".join(_short(c) for c in mods)
        return f"{prefix}+{_short(key)}" if prefix else _short(key)

    for step in steps:
        if step.kind == "char":
            text += chr(step.code)
            continue
        flush_text()
        if step.kind == "down":
            held.append(step.code)
            pending = True
        elif step.kind == "tap":
            parts.append(chord(held, step.code))
            pending = False
        elif step.kind == "up":
            # The RELEASE is what completes a recorded chord. A recorder emits
            # down/down/up/up and never a tap, so without this a captured Ctrl+A
            # renders as nothing at all -- which is precisely the macro someone just
            # pressed the keys for.
            if pending and held:
                parts.append(chord(held[:-1], held[-1]))
                pending = False
            if step.code in held:
                held.remove(step.code)
        elif step.kind == "delay":
            parts.append(f"{step.ms} ms")
    flush_text()
    # A chord left holding at the end is a real thing to express (a macro that arms a
    # modifier), so name it rather than dropping it.
    if pending and held:
        parts.append(f"hold {chord(held[:-1], held[-1])}")
    return "  ·  ".join(parts)


def _short(code: int) -> str:
    """A keycode's name without the KC_ prefix, for a summary line."""
    if code in _MOD_SYMBOL:
        return _MOD_SYMBOL[code]
    name = name_for(code)
    return name[3:] if name.startswith("KC_") else name
