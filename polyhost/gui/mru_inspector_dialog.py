import os

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
    QWidget, QGridLayout, QLabel, QPushButton, QFrame, QTabWidget,
)

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache, _slot_to_keycode


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
    """Background colour: dark yellow (rank 1 = least-recently-used / next to evict) → green (rank N = most-recently-used / freshest)."""
    if total <= 1:
        return "rgb(0,180,30)"
    frac = (rank - 1) / (total - 1)
    r = int(150 * (1 - frac))
    g = int(150 + 30 * frac)
    return f"rgb({r},{g},30)"


class MRUInspectorDialog(QDialog):
    _AUTO_REFRESH_MSEC = 2000

    def __init__(self, caches: list[tuple[str, OverlayMRUCache]],
                 device_settings: DeviceSettings, parent=None):
        super().__init__(parent)
        self._caches = caches
        self._device_settings = device_settings
        self._last_versions: dict[str, int] = {}

        self._update_title()
        self.resize(1150, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        self._tabs = QTabWidget()
        outer.addWidget(self._tabs)

        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._build_tabs()
        self._snapshot_versions()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(self._AUTO_REFRESH_MSEC)

    def _update_title(self):
        parts = [f"{label}: {cache.used_slots()}/{cache.capacity}" for label, cache in self._caches]
        self.setWindowTitle("MRU Overlay Cache Inspector  —  " + "  |  ".join(parts))

    def _build_tabs(self):
        self._tabs.clear()
        for label, cache in self._caches:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(self._build_grid(cache))
            self._tabs.addTab(scroll, label)

    def _build_grid(self, cache: OverlayMRUCache) -> QWidget:
        mru_info = cache.get_mru_info()
        max_rank = max((entry[3] for entry in mru_info.values()), default=1)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

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
            row_lbl = QLabel(_keycode_slot_name(row))
            row_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_lbl.setStyleSheet("color: #888; font-size: 8pt;")
            row_lbl.setFixedWidth(60)
            grid.addWidget(row_lbl, row + 1, 0)

            for col in range(_NUM_MODIFIER_VARIANTS):
                pool_slot = row + _NUM_KEYCODE_SLOTS * col
                info = mru_info.get(pool_slot)
                cell = self._build_cell(pool_slot, info, max_rank)
                grid.addWidget(cell, row + 1, col + 1)

        return container

    def _build_cell(self, pool_slot: int, info: tuple | None, max_rank: int) -> QFrame:
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
                img_lbl.setStyleSheet(f"background: {_rank_color(rank, max_rank)}; color: #fff;")

            frame.setStyleSheet(f"QFrame {{ background: {_rank_color(rank, max_rank)}; }}")

            basename = os.path.basename(full_path)
            if len(basename) > 18:
                basename = basename[:16] + "…"
            mod_name = _MODIFIER_NAMES[mod_val] if mod_val < len(_MODIFIER_NAMES) else str(mod_val)
            try:
                kc_name = KeyCode(kc).name.replace("KC_", "")
            except ValueError:
                kc_name = f"0x{kc:02x}"

            info_lbl = QLabel(f"{basename}\n{kc_name} · {mod_name}\nbatch {rank}/{max_rank}")
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

    def _snapshot_versions(self):
        self._last_versions = {label: cache.version for label, cache in self._caches}

    def _auto_refresh(self):
        if all(self._last_versions.get(label) == cache.version
               for label, cache in self._caches):
            return
        active_index = self._tabs.currentIndex()
        self._update_title()
        self._build_tabs()
        if 0 <= active_index < self._tabs.count():
            self._tabs.setCurrentIndex(active_index)
        self._snapshot_versions()
