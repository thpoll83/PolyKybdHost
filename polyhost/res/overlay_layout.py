"""Where a key's image is in a template overlay file.

A template overlay (`res/overlays/<name>.mods.png` and its siblings) is a 10 x 9
grid of 72 x 40 cells, one per key slot, with one modifier variant per RGBA
channel. `scripts/generate_app_overlays.py` writes these files and
`polyhost/services/game_assets` patches cells of a shipped file at runtime, so both read
the layout from here. The loader, `device/im_converter.py`, has its own copy of
the channel assignment; `tests/device/overlay_generator_channels_test.py` keeps
the two equal.
"""
from __future__ import annotations

from polyhost.device.keys import KeyCode, Modifier, keycode_to_mapping_idx

GRID_X, GRID_Y = 10, 9
SLOT_W, SLOT_H = 72, 40
IMG_W, IMG_H = GRID_X * SLOT_W, GRID_Y * SLOT_H

# RGBA channel index in the numpy array we build / save.
CH = {"R": 0, "G": 1, "B": 2, "A": 3}

# modifier -> (file kind, channel).  Mirrors polyhost/device/im_converter.py.
PRIMARY_CH = {Modifier.NO_MOD: "A", Modifier.CTRL: "R", Modifier.ALT: "G", Modifier.SHIFT: "B"}
COMBO_CH = {Modifier.CTRL_SHIFT: "R", Modifier.CTRL_ALT: "G", Modifier.ALT_SHIFT: "B",
            Modifier.GUI_KEY: "A"}
# Third and fourth tiers (protocol v12+). Before v12 the firmware folded every
# GUI+x chord onto the bare-GUI variant, so extra's G/B/A sat reserved and empty;
# the variant is now just the L/R-folded modifier bitmask, giving all 16.
# ⚠️ Channel assignment MUST mirror polyhost/device/im_converter.py exactly -- the
# loader reads these positions by name, so a mismatch here silently addresses the
# wrong variant rather than failing. In particular the least-important variant of
# each tier goes in A, because a 3-channel PNG drops alpha entirely.
EXTRA_CH = {Modifier.CTRL_ALT_SHIFT: "R", Modifier.GUI_SHIFT: "G",
            Modifier.GUI_ALT: "B", Modifier.GUI_CTRL: "A"}
GUI_CH = {Modifier.GUI_CTRL_SHIFT: "R", Modifier.GUI_ALT_SHIFT: "G",
          Modifier.GUI_CTRL_ALT: "B", Modifier.GUI_CTRL_ALT_SHIFT: "A"}


def cell_for(kc: KeyCode) -> tuple[int, int]:
    """(row, column) of the cell holding key `kc`."""
    slot = keycode_to_mapping_idx(kc)
    row, col = divmod(slot, GRID_X)
    return row, col


def region_box(anchor: str, size: tuple[int, int], margin: int) -> tuple[int, int, int, int]:
    """Return (x0, y0, w, h): the sub-rectangle of the 72x40 cell to draw into."""
    bw, bh = min(size[0], SLOT_W), min(size[1], SLOT_H)
    a = anchor.lower()
    if "right" in a:
        x0 = SLOT_W - bw - margin
    elif "left" in a:
        x0 = margin
    else:
        x0 = (SLOT_W - bw) // 2
    if "bottom" in a:
        y0 = SLOT_H - bh - margin
    elif "top" in a:
        y0 = margin
    else:
        y0 = (SLOT_H - bh) // 2
    return max(0, x0), max(0, y0), bw, bh


# --------------------------------------------------------------------------- #
# key-name -> KeyCode (only the 90 keys that actually have an overlay cell)
# --------------------------------------------------------------------------- #
def _build_key_aliases() -> dict[str, KeyCode]:
    a: dict[str, KeyCode] = {}
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        a[c] = KeyCode[f"KC_{c}"]
    for d in "0123456789":
        a[d] = KeyCode[f"KC_{d}"]
    for n in range(1, 13):
        a[f"F{n}"] = KeyCode[f"KC_F{n}"]
    named = {
        "ENTER": "KC_ENTER", "RETURN": "KC_ENTER", "CR": "KC_ENTER",
        "ESC": "KC_ESCAPE", "ESCAPE": "KC_ESCAPE",
        "BACKSPACE": "KC_BACKSPACE", "BKSP": "KC_BACKSPACE", "BSPC": "KC_BACKSPACE",
        "TAB": "KC_TAB", "SPACE": "KC_SPACE", "SPC": "KC_SPACE",
        "MINUS": "KC_MINUS", "-": "KC_MINUS",
        "EQUAL": "KC_EQUAL", "EQUALS": "KC_EQUAL", "=": "KC_EQUAL", "PLUS": "KC_EQUAL",
        "LBRACKET": "KC_LEFT_BRACKET", "[": "KC_LEFT_BRACKET",
        "RBRACKET": "KC_RIGHT_BRACKET", "]": "KC_RIGHT_BRACKET",
        "BACKSLASH": "KC_BACKSLASH", "\\": "KC_BACKSLASH",
        "SEMICOLON": "KC_SEMICOLON", ";": "KC_SEMICOLON",
        "QUOTE": "KC_QUOTE", "'": "KC_QUOTE",
        "GRAVE": "KC_GRAVE", "`": "KC_GRAVE", "TILDE": "KC_GRAVE",
        "COMMA": "KC_COMMA", ",": "KC_COMMA",
        "DOT": "KC_DOT", "PERIOD": "KC_DOT", ".": "KC_DOT",
        "SLASH": "KC_SLASH", "/": "KC_SLASH",
        "CAPS": "KC_CAPS_LOCK", "CAPSLOCK": "KC_CAPS_LOCK",
        "PRINTSCREEN": "KC_PRINT_SCREEN", "PRTSC": "KC_PRINT_SCREEN", "PSCR": "KC_PRINT_SCREEN",
        "SCROLLLOCK": "KC_SCROLL_LOCK", "PAUSE": "KC_PAUSE",
        "INSERT": "KC_INSERT", "INS": "KC_INSERT",
        "HOME": "KC_HOME", "PAGEUP": "KC_PAGE_UP", "PGUP": "KC_PAGE_UP",
        "DELETE": "KC_DELETE", "DEL": "KC_DELETE",
        "END": "KC_END", "PAGEDOWN": "KC_PAGE_DOWN", "PGDN": "KC_PAGE_DOWN",
        "RIGHT": "KC_RIGHT", "LEFT": "KC_LEFT", "DOWN": "KC_DOWN", "UP": "KC_UP",
        "NUMLOCK": "KC_NUM_LOCK", "APP": "KC_APPLICATION", "MENU": "KC_APPLICATION",
    }
    for k, v in named.items():
        a[k] = KeyCode[v]
    return a


KEY_ALIASES = _build_key_aliases()


def resolve_key(token: str) -> KeyCode:
    t = str(token).strip()
    up = t.upper()
    if up in KEY_ALIASES:
        return KEY_ALIASES[up]
    # A bare token is tried as KC_<TOKEN> too, so `PRINT_SCREEN` works like the
    # aliased `DELETE`/`ENTER` rather than reporting "no overlay cell" for a key
    # that has one — the alias table only covers the common spellings.
    name = up if up.startswith("KC_") else f"KC_{up}"
    if name in KeyCode.__members__:
        kc = KeyCode[name]
        # only the mapped 90 keys carry a cell
        if name in {k.name for k in KEY_ALIASES.values()} or _has_cell(kc):
            return kc
        raise ValueError(
            f"key {token!r} has no overlay cell (not one of the 90 grid keys)")
    raise ValueError(f"unknown key {token!r}")


def _has_cell(kc: KeyCode) -> bool:
    v = kc.value
    return (KeyCode.KC_A.value <= v <= KeyCode.KC_NUM_LOCK.value
            or v in (KeyCode.KC_NONUS_BACKSLASH.value, KeyCode.KC_APPLICATION.value)
            or KeyCode.KC_LEFT_CTRL.value <= v <= KeyCode.KC_RIGHT_GUI.value)
