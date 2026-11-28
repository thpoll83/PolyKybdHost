"""Overlay images per PHYSICAL key (firmware protocol v40, KEY_OVERLAY_MIN_PROTOCOL).

An ordinary overlay file holds one image per keycode, and the keyboard draws it on
every key that sends that keycode. A `.keys.png` file holds one image per physical
key instead: cell `i` of the 10 x 9 grid (row-major, `i = row * 10 + col`, white on
black, read like any overlay file without `.mods.` in its name) is matrix index `i`
(`matrix_row * 8 + matrix_col`). The send path
maps it to the cmd 33 `from` `KEY_OVERLAY_BASE + i`; the keyboard draws it where the
key's keycode has no image, in every modifier state
(qmk `copy_key_overlay_to_buffer()`, docs/protocol/protocol-history.md v40).

Written by services/user_overlays.py for a `"*"` drawing with `follow: "key"`.
"""
from __future__ import annotations

from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.res.overlay_layout import GRID_X, _has_cell, cell_for

KEY_IMAGE_SUFFIX = ".keys.png"
# Firmware OVERLAY_MAP_KEY_BASE (OVERLAY_MAP_IDX_CNT + 16) and OVERLAY_MAP_KEY_CNT.
KEY_OVERLAY_BASE = 1456
KEY_OVERLAY_COUNT = 80
MATRIX_COLUMNS = 8
# The "modifier" of a physical-key position in the send loop's (modifier, key)
# tuples, so key index 4 never collides with keycode 4 (KC_A).
KEY_POSITION = -1


def is_key_image_file(name) -> bool:
    return str(name).endswith(KEY_IMAGE_SUFFIX)


def matrix_index(row: int, col: int) -> int:
    return row * MATRIX_COLUMNS + col


def mapping_from(index: int) -> int:
    """The cmd 33 `from` of matrix index `index`."""
    if not 0 <= index < KEY_OVERLAY_COUNT:
        raise ValueError(f"matrix index {index} out of range")
    return KEY_OVERLAY_BASE + index


# The loader walks the grid cells in keycode order; this turns its keycode back
# into the cell, which a `.keys.png` uses as the matrix index.
_CELL_OF_KEYCODE = {kc.value: (lambda rc: rc[0] * GRID_X + rc[1])(cell_for(kc))
                    for kc in KeyCode if _has_cell(kc)}


class KeyImageConverter:
    """The send loop's converter for a `.keys.png`: images by matrix index."""

    physical_keys = True
    modifier_invariant = True

    def __init__(self, device_settings):
        self._conv = ImageConverter(device_settings)
        self.no_legend = frozenset()

    def open(self, filename) -> bool:
        if not self._conv.open(filename):
            return False
        # The chunk lists "0:<matrix index>" pairs.
        self.no_legend = frozenset((KEY_POSITION, idx) for mod, idx in self._conv.no_legend
                                   if mod == Modifier.NO_MOD.value)
        return True

    def extract_overlays(self, modifier=Modifier.NO_MOD):
        if modifier != Modifier.NO_MOD:
            return None
        by_keycode = self._conv.extract_overlays(Modifier.NO_MOD) or {}
        out = {}
        for keycode, data in by_keycode.items():
            idx = _CELL_OF_KEYCODE.get(keycode)
            if idx is not None and idx < KEY_OVERLAY_COUNT:
                out[idx] = data
        return out
