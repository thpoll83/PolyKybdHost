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
