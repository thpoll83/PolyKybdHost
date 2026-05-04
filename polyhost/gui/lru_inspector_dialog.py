import os

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
    QWidget, QGridLayout, QLabel, QPushButton, QFrame,
)

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayLRUCache, _slot_to_keycode


_MODIFIER_NAMES = ["NO_MOD", "CTRL", "SHIFT", "CTRL+SH", "ALT", "CTRL+ALT", "ALT+SH"]
_NUM_MODIFIER_VARIANTS = 7
_NUM_KEYCODE_SLOTS = 90
_IMG_SCALE = 2
_IMG_W = 72 * _IMG_SCALE
_IMG_H = 40 * _IMG_SCALE


def _keycode_slot_name(slot: int) -> str:
    kc_int = _slot_to_keycode(slot)
    try:
        return KeyCode(kc_int).name.replace("KC_", "")
    except ValueError:
        return f"0x{kc_int:02x}"


def _load_overlay_pixmap(full_path: str, modifier_value: int, keycode: int,
                         device_settings: DeviceSettings) -> QPixmap | None:
    try:
        converter = ImageConverter(device_settings)
        if not converter.open(full_path):
            return None
        overlay_map = converter.extract_overlays(Modifier(modifier_value))
        if keycode not in overlay_map:
            return None
        all_bytes = overlay_map[keycode].all_bytes
        bits = np.unpackbits(np.frombuffer(all_bytes, dtype=np.uint8))
        img_array = (bits[:40 * 72].reshape(40, 72) * 255).astype(np.uint8)
        qimg = QImage(img_array.tobytes(), 72, 40, 72, QImage.Format_Grayscale8)
        return QPixmap.fromImage(qimg).scaled(_IMG_W, _IMG_H, Qt.KeepAspectRatio)
    except Exception:
        return None


def _rank_color(rank: int, total: int) -> str:
    """Background colour for the cell: red→yellow→green from oldest to newest."""
    if total <= 1:
        return "#1e3a1e"
    frac = (rank - 1) / (total - 1)  # 0.0 = LRU (oldest), 1.0 = MRU (newest)
    r = int(180 * (1 - frac))
    g = int(180 * frac)
    return f"rgb({r},{g},30)"


class LRUInspectorDialog(QDialog):
    def __init__(self, cache: OverlayLRUCache, device_settings: DeviceSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"LRU Overlay Cache Inspector  —  {len(cache._cache)}/{cache.capacity} slots used")
        self.resize(1150, 720)

        self._cache = cache
        self._device_settings = device_settings

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        # Refresh + close buttons
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll)

        self._build_grid()

    def _build_grid(self):
        lru_info = self._cache.get_lru_info()
        total_entries = len(lru_info)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

        # Column headers (modifier names)
        corner = QLabel("")
        corner.setFixedWidth(60)
        grid.addWidget(corner, 0, 0)
        for col, mod_name in enumerate(_MODIFIER_NAMES):
            hdr = QLabel(mod_name)
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet("font-weight: bold; color: #aaa;")
            hdr.setFixedWidth(_IMG_W + 4)
            grid.addWidget(hdr, 0, col + 1)

        for row in range(_NUM_KEYCODE_SLOTS):
            # Row label
            row_lbl = QLabel(_keycode_slot_name(row))
            row_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_lbl.setStyleSheet("color: #888; font-size: 8pt;")
            row_lbl.setFixedWidth(60)
            grid.addWidget(row_lbl, row + 1, 0)

            for col in range(_NUM_MODIFIER_VARIANTS):
                pool_slot = row + _NUM_KEYCODE_SLOTS * col
                info = lru_info.get(pool_slot)
                cell = self._build_cell(pool_slot, info, total_entries)
                grid.addWidget(cell, row + 1, col + 1)

        self._scroll.setWidget(container)

    def _build_cell(self, pool_slot: int, info: tuple | None, total: int) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(_IMG_W + 4)
        vbox = QVBoxLayout(frame)
        vbox.setSpacing(1)
        vbox.setContentsMargins(2, 2, 2, 2)

        img_lbl = QLabel()
        img_lbl.setFixedSize(_IMG_W, _IMG_H)
        img_lbl.setAlignment(Qt.AlignCenter)

        if info:
            full_path, mod_val, kc, rank = info
            pixmap = _load_overlay_pixmap(full_path, mod_val, kc, self._device_settings)
            if pixmap:
                img_lbl.setPixmap(pixmap)
            else:
                img_lbl.setText("?")
                img_lbl.setStyleSheet(f"background: {_rank_color(rank, total)}; color: #fff;")

            frame.setStyleSheet(f"QFrame {{ background: {_rank_color(rank, total)}; }}")

            basename = os.path.basename(full_path)
            if len(basename) > 18:
                basename = basename[:16] + "…"
            mod_name = _MODIFIER_NAMES[mod_val] if mod_val < len(_MODIFIER_NAMES) else str(mod_val)
            try:
                kc_name = KeyCode(kc).name.replace("KC_", "")
            except ValueError:
                kc_name = f"0x{kc:02x}"

            info_lbl = QLabel(f"{basename}\n{kc_name} · {mod_name}\n#{rank}/{total}")
            info_lbl.setStyleSheet("font-size: 7pt; color: #ddd;")
        else:
            img_lbl.setStyleSheet("background: #1a1a1a;")
            frame.setStyleSheet("QFrame { background: #111; }")
            slot_lbl = QLabel(f"{pool_slot}")
            slot_lbl.setStyleSheet("font-size: 7pt; color: #333;")
            slot_lbl.setAlignment(Qt.AlignCenter)
            info_lbl = slot_lbl

        vbox.addWidget(img_lbl)
        vbox.addWidget(info_lbl)
        return frame

    def _refresh(self):
        self.setWindowTitle(f"LRU Overlay Cache Inspector  —  {len(self._cache._cache)}/{self._cache.capacity} slots used")
        self._build_grid()
