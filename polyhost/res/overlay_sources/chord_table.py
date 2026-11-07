"""Write an overlay spec's `bindings:` list from a table of key combinations.

Used by the `gen_specs.py` of the lab and engineering sets (labview, comsol,
simulink, origin). Each set keeps its table and spec header in its own folder;
this module only turns a row into binding lines.

A key combination is written as modifier letters, "+", and a key name:
C Ctrl (Control on a Mac), A Alt (Option on a Mac), S Shift, M Cmd (GUI).
"+F5" is F5 with no modifier. None means the action has no key on that
platform. Key names are the generator's tokens (`N`, `F5`, `KC_PAGE_UP`), plus
the short names in KEYS below.

A row is (icon, label, keys), where `keys` maps a platform ("windows", "linux",
"macos") to a key combination or None. A platform missing from `keys` has no
binding. Rows whose key combination is the same on several platforms are
written once, with an `only:` list, so the generated file stays short.
"""
from __future__ import annotations

from pathlib import Path

MODS = {"C": "CTRL", "A": "ALT", "S": "SHIFT", "M": "GUI"}
KEYS = {"Enter": "ENTER", "Up": "UP", "Down": "DOWN", "Left": "LEFT",
        "Right": "RIGHT", "Home": "HOME", "End": "END", ",": "COMMA",
        ".": "DOT", "/": "SLASH", "-": "MINUS", "=": "EQUAL", "[": "LBRACKET",
        "]": "RBRACKET", "'": "KC_QUOTE", "`": "KC_GRAVE", "Tab": "KC_TAB",
        "Space": "KC_SPACE", "Del": "KC_DELETE", "Bksp": "KC_BACKSPACE",
        "Pause": "KC_PAUSE"}
PLATFORMS = ("windows", "linux", "macos")


def parse(chord: str) -> tuple[str, list[str]]:
    """("C+S") -> ('"S"', ["CTRL"])."""
    mods, key = chord.split("+", 1)
    key = KEYS.get(key, key)
    return f'"{key}"', [MODS[m] for m in mods]


def lines(icon: str | None, label: str, keys: dict[str, str | None],
          not_shared: set[str], platforms=PLATFORMS) -> list[str]:
    """The binding lines of one table row, grouped by identical key combination."""
    groups: dict[str, list[str]] = {}
    for plat in platforms:
        chord = keys.get(plat)
        if chord:
            groups.setdefault(chord, []).append(plat)
    out = []
    for chord, plats in groups.items():
        key, mods = parse(chord)
        parts = [f"key: {key}", f"mods: [{', '.join(mods)}]"]
        if icon:
            parts.append(f"icon: {icon}.png")
        parts.append(f'label: "{label}"')
        if label in not_shared:
            parts.append("shared: false")
        if len(plats) < len(platforms):
            parts.append(f"only: [{', '.join(plats)}]")
        out.append("  - { " + ", ".join(parts) + " }")
    return out


def write(path: Path, header: str, rows, not_shared: set[str],
          platforms=PLATFORMS) -> int:
    """Write header + every row's binding lines to `path`; return the line count."""
    out = [header]
    for row in rows:
        if isinstance(row, str):  # a section comment
            out.append(f"  # --- {row} ---")
            continue
        icon, label, keys = row
        out.extend(lines(icon, label, keys, not_shared, platforms))
    text = "\n".join(out) + "\n"
    path.write_text(text, encoding="utf-8")
    n = text.count("\n  - {")
    print(f"{path.name}: {n} bindings")
    return n
