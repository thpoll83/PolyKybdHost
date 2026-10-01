"""split72's physical keys: where each sits and what it types on the base layer.

Two sources, joined on the matrix position (row, col):

* the KLE (`res/polykybd-split72.json`) for the geometry the layout editor
  draws -- position, size, rotation;
* `res/preview/board.json` for the base-layer keycode, exported from the
  firmware's keymap.c by `scripts/export_preview_data.py`.

Qt-free, so the mock keyboard (which seeds its keymap from it) and the board
view share one reading.
"""
from __future__ import annotations

import json
import pathlib

RES = pathlib.Path(__file__).resolve().parent.parent / "res"
BOARD_JSON = RES / "preview" / "board.json"
KLE_JSON = RES / "polykybd-split72.json"


def load_board(path: pathlib.Path | None = None) -> dict | None:
    """The exported board, or None when this install has no export."""
    try:
        return json.loads((path or BOARD_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def base_keycodes(path: pathlib.Path | None = None) -> dict[tuple[int, int], int]:
    """{(row, col): keycode} for every key whose base-layer keycode resolved."""
    board = load_board(path)
    if not board:
        return {}
    return {tuple(k["matrix"]): k["keycode"] for k in board.get("keys", [])
            if k.get("keycode") is not None}


def physical_keys() -> list[dict]:
    """Every key the KLE draws, with its matrix position and base keycode:
    [{row, col, x, y, w, h, r, rx, ry, keycode, token}]."""
    from polyhost.kle.kle_praser import parse_kle
    _, _, matrix = parse_kle(json.loads(KLE_JSON.read_text(encoding="utf-8")))
    board = load_board() or {}
    by_pos = {tuple(k["matrix"]): k for k in board.get("keys", [])}
    keys = []
    for info in matrix.values():
        entry = by_pos.get((info["row"], info["col"]), {})
        keys.append({**{k: info.get(k, 0) for k in ("row", "col", "x", "y", "w", "h", "r", "rx", "ry")},
                     "keycode": entry.get("keycode"), "token": entry.get("token", "")})
    return keys
