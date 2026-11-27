"""Names for the split72's keys: `L:X.Y` and `R:X.Y` (docs/mcp-server-plan.md).

The firmware addresses a key by matrix row and column, which means nothing to a
user or an AI assistant. The names come from the key's place on the PCB and are a
frozen table, `res/key_positions.yaml`, so a later board revision does not rename a
key. Qt-free and stdlib plus PyYAML: the MCP server uses it.

A key reference, as the MCP tools take it, is one of:

* a name, `"L:1.1"`, or an alias that counts across the middle (`"L:9.4"` is
  `"R:8.4"`);
* `{"base": "KC_Q"}`, the one key that sends that keycode on layer 0;
* `{"row": 2, "col": 3}`, a matrix position.

Every reference resolves to exactly one key or raises `KeyRefError`. The resolver
never guesses: a `base` keycode on two keys is an error that lists both.
"""
from __future__ import annotations

import pathlib
import re

TABLE_FILE = pathlib.Path(__file__).resolve().parent.parent / "res" / "key_positions.yaml"

# Columns per half. An X from 9 to 16 names the other half's column 17 - X.
COLUMNS_PER_HALF = 8

_NAME_RE = re.compile(r"\s*([LR]):(\d{1,2})\.(\d)\s*", re.IGNORECASE)


class KeyRefError(ValueError):
    """A key reference that names no key, or more than one."""


class KeyTable:
    """The frozen name table of one keyboard variant."""

    def __init__(self, keys: dict[str, tuple[int, int]], no_display=(), thumb=()):
        self.by_name = dict(keys)
        self.by_pos = {pos: name for name, pos in self.by_name.items()}
        if len(self.by_pos) != len(self.by_name):
            raise ValueError("two key names share one matrix position")
        self.no_display = frozenset(no_display)
        self.thumb = frozenset(thumb)

    # -- names ---------------------------------------------------------------

    def canonical(self, text: str) -> str:
        """The canonical name for a name or an alias. Raises KeyRefError."""
        m = _NAME_RE.fullmatch(text) if isinstance(text, str) else None
        if not m:
            raise KeyRefError(f"{text!r} is not a key name; write it as L:X.Y or R:X.Y, "
                              "for example L:1.1")
        half, x, y = m.group(1).upper(), int(m.group(2)), int(m.group(3))
        if COLUMNS_PER_HALF < x <= 2 * COLUMNS_PER_HALF:
            half, x = ("R" if half == "L" else "L"), 2 * COLUMNS_PER_HALF + 1 - x
        name = f"{half}:{x}.{y}"
        if name not in self.by_name:
            if name != f"{m.group(1).upper()}:{m.group(2)}.{m.group(3)}":
                raise KeyRefError(f"{text.strip()} is {name}, and there is no key there")
            raise KeyRefError(f"there is no key {name}")
        return name

    def position(self, name: str) -> tuple[int, int]:
        return self.by_name[self.canonical(name)]

    def name_at(self, row: int, col: int) -> str | None:
        return self.by_pos.get((row, col))

    def names(self) -> list[str]:
        """Every name, the left half first, row by row from the outer column."""
        return sorted(self.by_name, key=_sort_key)

    # -- references ----------------------------------------------------------

    def resolve(self, ref, base_keycodes=None, parse_keycode=None) -> str:
        """The canonical name `ref` refers to. Raises KeyRefError.

        `base_keycodes` maps (row, col) to the layer-0 keycode and `parse_keycode`
        turns a keycode name into its value; both are needed only for a `base`
        reference."""
        if isinstance(ref, str):
            return self.canonical(ref)
        if not isinstance(ref, dict) or not ref:
            raise KeyRefError("a key is a name like \"L:1.1\", {\"base\": \"KC_Q\"} "
                              "or {\"row\": 2, \"col\": 3}")
        if set(ref) == {"row", "col"}:
            row, col = ref["row"], ref["col"]
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (row, col)):
                raise KeyRefError("row and col must be integers")
            name = self.name_at(row, col)
            if name is None:
                raise KeyRefError(f"there is no key at row {row}, col {col}")
            return name
        if set(ref) == {"base"}:
            if base_keycodes is None or parse_keycode is None:
                raise KeyRefError("a base reference needs the keyboard's layer 0")
            try:
                wanted = parse_keycode(str(ref["base"]))
            except ValueError as exc:
                raise KeyRefError(str(exc)) from None
            hits = sorted((self.by_pos[pos] for pos, code in base_keycodes.items()
                           if code == wanted and pos in self.by_pos), key=_sort_key)
            if not hits:
                raise KeyRefError(f"no key sends {ref['base']} on layer 0")
            if len(hits) > 1:
                raise KeyRefError(f"{ref['base']} is on {len(hits)} keys on layer 0: "
                                  f"{', '.join(hits)}. Name one of them.")
            return hits[0]
        raise KeyRefError(f"unknown key reference fields: {sorted(ref)}")

    # -- drawing -------------------------------------------------------------

    def grid(self, cell_text) -> str:
        """The two halves as they sit on the desk, one cell per key.

        `cell_text(name)` gives the text of a cell. A place with no key is `.`. The
        left half's X runs 1..8 from the left edge, the right half's 8..1."""
        rows = sorted({int(n.split(".")[1]) for n in self.by_name})
        texts = {n: str(cell_text(n)) for n in self.by_name}
        left = [f"L:{x}" for x in range(1, COLUMNS_PER_HALF + 1)]
        right = [f"R:{x}" for x in range(COLUMNS_PER_HALF, 0, -1)]
        # Each column as wide as its widest cell, so one long name widens one column.
        width = {c: max([len(c)] + [len(texts.get(f"{c}.{y}", ".")) for y in rows])
                 for c in left + right}

        def line(cols, cell):
            return " ".join(cell(c).center(width[c]) for c in cols)

        header = f" Y | {line(left, str)} | {line(right, str)}"
        lines = [header, "-" * len(header)]
        for y in rows:
            def at(c, y=y):
                return texts.get(f"{c}.{y}", ".")
            lines.append(f" {y} | {line(left, at)} | {line(right, at)}")
        return "\n".join(lines)


def _sort_key(name: str):
    half, rest = name.split(":")
    x, y = rest.split(".")
    return (half != "L", int(y), int(x))


_TABLES: dict[str, KeyTable] = {}


def load_table(variant: str = "split72", path: pathlib.Path | None = None) -> KeyTable:
    """The frozen table of `variant`. Raises KeyError for a variant it has none for."""
    if path is None and variant in _TABLES:
        return _TABLES[variant]
    import yaml
    with open(path or TABLE_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entry = data[variant]
    table = KeyTable({name: tuple(pos) for name, pos in entry["keys"].items()},
                     entry.get("no_display", ()), entry.get("thumb", ()))
    if path is None:
        _TABLES[variant] = table
    return table
