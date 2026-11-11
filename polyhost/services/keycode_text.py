"""Keycodes as text and back, for polyctl and the combo / tap-dance editor.

Qt-free. The names come from the shipped `res/keycodes.h` (via qmk_keycode_helper,
which imports only the i18n marker), so polyctl and the GUI accept the same spellings.

Accepted input: a number (0x hex or decimal), a QMK name with or without `KC_`
(`KC_J`, `esc`), `MO(n)` / `TO(n)` / `TG(n)` / `TD(n)`, and a modifier wrapper around
a basic keycode such as `S(KC_9)` or `LCTL(KC_C)`. QMK's shorthands like `KC_LPRN` are
not in keycodes.h: write `S(KC_9)`.
"""

from __future__ import annotations

import re

LAYER_FNS = {"TO": 0x5200, "MO": 0x5220, "TG": 0x5260, "TD": 0x5700}

MOD_FNS = {"LCTL": 0x0100, "C": 0x0100, "LSFT": 0x0200, "S": 0x0200, "LALT": 0x0400,
           "A": 0x0400, "LGUI": 0x0800, "G": 0x0800, "RCTL": 0x1100, "RSFT": 0x1200,
           "RALT": 0x1400, "RGUI": 0x1800}

_TABLES = None


def keycode_tables():
    """(name -> value, value -> preferred name) from the shipped keycodes.h."""
    global _TABLES
    if _TABLES is None:
        from polyhost.gui.layout_dialog.qmk_keycode_helper import HEADER_FILE, parse_qmk_keycodes
        try:
            by_name = parse_qmk_keycodes(HEADER_FILE)
        except OSError:
            by_name = {}
        by_value = {}
        for name, value in by_name.items():
            # Prefer the long KC_ name over aliases for display.
            if value not in by_value or (name.startswith("KC_") and len(name) > len(by_value[value])):
                by_value[value] = name
        _TABLES = (by_name, by_value)
    return _TABLES


def parse_keycode(text: str) -> int:
    """The keycode `text` names. Raises ValueError for anything it cannot read."""
    t = text.strip()
    m = re.fullmatch(r"([A-Z]+)\((.+)\)", t, re.IGNORECASE)
    if m and m.group(1).upper() in MOD_FNS:
        inner = parse_keycode(m.group(2))
        if inner > 0xFF:
            raise ValueError(f"{t}: a modifier wraps a basic keycode only")
        return MOD_FNS[m.group(1).upper()] | inner
    m = re.fullmatch(r"(TO|MO|TG|TD)\((\d+)\)", t, re.IGNORECASE)
    if m:
        n = int(m.group(2))
        limit = 0xFF if m.group(1).upper() == "TD" else 0x1F
        if n > limit:
            raise ValueError(f"{t}: layer/slot out of range")
        return LAYER_FNS[m.group(1).upper()] + n
    try:
        value = int(t, 0)
    except ValueError:
        by_name, _unused = keycode_tables()
        key = t.upper() if t.upper() in by_name else ("KC_" + t.upper())
        if key not in by_name:
            raise ValueError(f"unknown keycode {t!r}") from None
        value = by_name[key]
    if not 0 <= value <= 0xFFFF:
        raise ValueError(f"keycode {t!r} out of range")
    return value


def keycode_text(value: int, empty: str = "-") -> str:
    """The spelling parse_keycode() reads back to `value`; `empty` for 0."""
    if value == 0:
        return empty
    if 0x0100 <= value <= 0x1FFF:
        mods = {v: k for k, v in MOD_FNS.items() if len(k) > 1}
        if (value & 0x1F00) in mods:
            return f"{mods[value & 0x1F00]}({keycode_text(value & 0xFF)})"
    for fn, base in LAYER_FNS.items():
        if base <= value < base + (0x100 if fn == "TD" else 0x20):
            return f"{fn}({value - base})"
    _unused, by_value = keycode_tables()
    return by_value.get(value, f"0x{value:04X}")
