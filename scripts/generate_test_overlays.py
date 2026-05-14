#!/usr/bin/env python3
"""Generate test overlay PNGs for PolyKybdHost.

The PolyKybd overlay PNG format is a 10x9 grid of 72x40 px keycap overlays
(720x360 total). Each colour channel of an RGBA PNG carries one modifier
variation; a "combo" PNG covers the remaining modifiers. The test PNGs this
script writes encode the per-(slot, channel) index as a centred number, so
each channel rendered alone shows distinct numbers and the channels are
preserved bit-for-bit even where alpha=0.

Run via the project venv (numpy + PyQt5 are required, both already present):

    .venv/bin/python scripts/generate_test_overlays.py
    .venv/bin/python scripts/generate_test_overlays.py --start-number 360 \
        --kind combo --out polyhost/res/test_overlays/test_overlay.combo.mods.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QImage, QPainter, QColor
from PyQt5.QtWidgets import QApplication

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from polyhost.device.keys import KeyCode, Modifier  # noqa: E402

GRID_X = 10
GRID_Y = 9
SLOT_W = 72
SLOT_H = 40
IMG_W = GRID_X * SLOT_W
IMG_H = GRID_Y * SLOT_H
NUM_SLOTS = GRID_X * GRID_Y
NUM_CHANNELS = 4

# Channel-to-modifier mapping mirrors polyhost/device/im_converter.py.
# Channel order in the numpy array is R, G, B, A (after the BGRA→RGBA swap
# we apply on save, see _save_png).
CHANNELS_PRIMARY = [
    ("R", Modifier.CTRL),
    ("G", Modifier.ALT),
    ("B", Modifier.SHIFT),
    ("A", Modifier.NO_MOD),
]
CHANNELS_COMBO = [
    ("R", Modifier.CTRL_SHIFT),
    ("G", Modifier.CTRL_ALT),
    ("B", Modifier.ALT_SHIFT),
    ("A", Modifier.GUI_KEY),
]


def slot_to_keycode(slot: int) -> int:
    """Map a 0..89 slot index to its raw keycode, matching the iteration in
    ImageConverter.extract_overlays (which jumps over keypad and media ranges)."""
    if slot <= 79:
        return KeyCode.KC_A.value + slot
    if slot <= 81:
        return KeyCode.KC_NONUS_BACKSLASH.value + (slot - 80)
    return KeyCode.KC_LEFT_CTRL.value + (slot - 82)


def keycode_name(keycode: int) -> str:
    try:
        return KeyCode(keycode).name
    except ValueError:
        return f"0x{keycode:04x}"


def render_text_mask(text: str, font: QFont) -> np.ndarray:
    """Rasterise `text` centred in a 72x40 region, return a bool mask of lit pixels."""
    img = QImage(SLOT_W, SLOT_H, QImage.Format_Grayscale8)
    img.fill(0)
    painter = QPainter(img)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    painter.drawText(0, 0, SLOT_W, SLOT_H, Qt.AlignCenter, text)
    painter.end()
    buf = img.constBits()
    buf.setsize(SLOT_W * SLOT_H)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(SLOT_H, SLOT_W).copy()
    return arr > 127


def build_overlay(start_number: int, channels: list[tuple[str, Modifier]],
                  font: QFont) -> tuple[np.ndarray, list[tuple[int, int, int, str, int]]]:
    """Return rgba_array.

    rgba_array: (IMG_H, IMG_W, 4) uint8 in R,G,B,A channel order.
    """
    rgba = np.zeros((IMG_H, IMG_W, 4), dtype=np.uint8)

    rgba_channel_index = {"R": 0, "G": 1, "B": 2, "A": 3}

    for ch_idx, (ch_name, modifier) in enumerate(channels):
        ch_axis = rgba_channel_index[ch_name]
        for slot in range(NUM_SLOTS):
            number = start_number + ch_idx * NUM_SLOTS + slot
            mask = render_text_mask(str(number), font)

            row, col = divmod(slot, GRID_X)
            y0 = row * SLOT_H
            x0 = col * SLOT_W
            block = rgba[y0:y0 + SLOT_H, x0:x0 + SLOT_W, ch_axis]
            block[mask] = 255

    return rgba


def save_png(rgba: np.ndarray, path: Path) -> None:
    """Save an (H, W, 4) RGBA uint8 array as PNG, preserving RGB bytes where A=0.

    QImage.Format_RGBA8888 is straight (non-premultiplied) RGBA; the PNG writer
    keeps every byte as-is so transparent pixels still carry data on R/G/B/A.
    """
    h, w, _ = rgba.shape
    contiguous = np.ascontiguousarray(rgba)
    img = QImage(contiguous.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
    if not img.save(str(path), "PNG"):
        raise RuntimeError(f"QImage.save() failed for {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path,
                        default=REPO_ROOT / "polyhost" / "res" / "test_overlays",
                        help="Where to write the PNGs (default: polyhost/res/test_overlays/).")
    parser.add_argument("--start-number", type=int, default=0,
                        help="Numbering offset for the primary image (default 0).")
    parser.add_argument("--combo-start", type=int, default=None,
                        help="Numbering offset for the combo image. "
                             "Defaults to start-number + 360 so the two images don't overlap.")
    parser.add_argument("--font", default="DejaVu Sans Bold",
                        help="Family name passed to QFont (default: 'DejaVu Sans Bold').")
    parser.add_argument("--font-size", type=int, default=14,
                        help="Pixel size of the rendered numbers.")
    parser.add_argument("--only", choices=("primary", "combo", "both"), default="both")
    args = parser.parse_args()

    combo_start = args.combo_start if args.combo_start is not None else args.start_number + NUM_CHANNELS * NUM_SLOTS

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # QApplication required for QPainter font metrics on some Qt builds.
    app = QApplication.instance() or QApplication(sys.argv)
    _ = app  # keep alive

    font = QFont(args.font)
    font.setPixelSize(args.font_size)
    font.setBold(True)

    if args.only in ("primary", "both"):
        rgba = build_overlay(args.start_number, CHANNELS_PRIMARY, font)
        out = args.out_dir / "test_overlay.mods.png"
        save_png(rgba, out)
        print(f"Wrote {out}  (numbers {args.start_number}..{args.start_number + 359})")
    if args.only in ("combo", "both"):
        rgba = build_overlay(combo_start, CHANNELS_COMBO, font)
        out = args.out_dir / "test_overlay.combo.mods.png"
        save_png(rgba, out)
        print(f"Wrote {out}  (numbers {combo_start}..{combo_start + 359})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
