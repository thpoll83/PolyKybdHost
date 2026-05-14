import struct
import zlib

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier


def _write_png_gray8(path: str, pixels: np.ndarray) -> None:
    """Write an 8-bit grayscale PNG using only stdlib (zlib/struct) + numpy."""
    h, w = pixels.shape
    raw = b"".join(b"\x00" + row.tobytes() for row in pixels)
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)

_OVERLAY_W = 72
_OVERLAY_H = 40
OVERLAY_BYTES = _OVERLAY_W * _OVERLAY_H // 8  # 360


def display_flat_idx(keycode: int, modifier: Modifier) -> int:
    """
    Flat firmware index for a (keycode_int, modifier) pair.
    Mirrors adjust_overlay_idx_to_mod + keycode_to_mapping_idx in fill_overlay.c.
    GUI modifier (value 8) maps to offset 8; others use their enum value directly.
    """
    if keycode > KeyCode.KC_APPLICATION.value:
        slot = keycode - KeyCode.KC_LEFT_CTRL.value + 82
    elif keycode > KeyCode.KC_NUM_LOCK.value:
        slot = keycode - KeyCode.KC_NONUS_BACKSLASH.value + 80
    else:
        slot = keycode - KeyCode.KC_A.value
    return slot + 90 * modifier.value


class OverlayFirmwareSim:
    """
    Simulates the firmware's overlay store, usage bit-array, and mapping table.

    Write path (fill_overlay.c): no mapping lookup — images always land at their
    direct pool address (display_flat_idx(pool_kc, pool_mod)).

    Display path (copy_overlay_to_buffer): compute display_idx, check is_overlay_used
    on display_idx, apply overlay_map to get pool_slot, return stored bitmap.

    reset_overlay_usage(): clears all usage bits; image data is preserved.
    reset_overlay_mapping(): restores identity mapping (clears non-identity entries).
    reset_overlays_and_usage(): clears store, usage, and mapping.
    set_mapping(from, to) + mark from as used: mirrors set_10bit_overlay_mapping.
    """

    def __init__(self) -> None:
        self._store: dict[int, bytes] = {}     # pool_slot → 360-byte bitmap
        self._usage: set[int] = set()          # used positions (display or pool)
        self._mapping: dict[int, int] = {}     # non-identity display_pos → pool_slot
        self._device_settings = DeviceSettings()

    # ── write path ─────────────────────────────────────────────────────────

    def store_image(self, pool_slot: int, bitmap_bytes: bytes | bytearray) -> None:
        """Store a 360-byte bitmap at pool_slot and temporarily mark it as used."""
        if len(bitmap_bytes) != OVERLAY_BYTES:
            raise ValueError(f"Expected {OVERLAY_BYTES} bytes, got {len(bitmap_bytes)}")
        self._store[pool_slot] = bytes(bitmap_bytes)
        self._usage.add(pool_slot)

    # ── reset commands ──────────────────────────────────────────────────────

    def reset_usage(self) -> None:
        """Mirrors reset_overlay_usage(): clears all usage bits; image data preserved."""
        self._usage.clear()

    def set_all_usage(self) -> None:
        """Mirrors reset_overlay_usage(): clears all usage bits; image data preserved."""
        self._usage = set(list(range(self._device_settings.OVERLAY_MAPPING_USAGE_COUNT)))

    def reset_mapping(self) -> None:
        """Mirrors reset_overlay_mapping(): restores identity by clearing non-identity entries."""
        self._mapping.clear()

    def reset_all(self) -> None:
        """Mirrors reset_overlays_and_usage(): clears store, usage, and mapping."""
        self._store.clear()
        self._usage.clear()
        self._mapping.clear()

    # ── mapping command ─────────────────────────────────────────────────────

    def set_mapping(self, display_pos: int, pool_slot: int) -> None:
        """
        Mirrors set_overlay_mapping(from, to) + set_overlay_usage(from) inside
        set_10bit_overlay_mapping: records the redirect and marks display_pos as used.
        """
        self._mapping[display_pos] = pool_slot
        self._usage.add(display_pos)

    def apply_mapping(self, from_to: dict[int, int]) -> None:
        """Apply a display_pos → pool_slot dict (from send_overlay_mapping)."""
        for display_pos, pool_slot in from_to.items():
            self.set_mapping(display_pos, pool_slot)

    # ── display path ────────────────────────────────────────────────────────

    def is_used(self, display_idx: int) -> bool:
        return display_idx in self._usage

    def get_pool_slot_for(self, display_idx: int) -> int:
        """Return overlay_map[display_idx] (identity if not explicitly mapped)."""
        return self._mapping.get(display_idx, display_idx)

    def get_display_bitmap(self, keycode: int, modifier: Modifier) -> bytes | None:
        """
        Full display pipeline mirroring copy_overlay_to_buffer:
          1. compute display_idx
          2. check is_overlay_used(display_idx)
          3. apply mapping to get pool_slot
          4. return stored bitmap, or None if not used / not stored.
        """
        display_idx = display_flat_idx(keycode, modifier)
        if not self.is_used(display_idx):
            return None
        pool_slot = self.get_pool_slot_for(display_idx)
        return self._store.get(pool_slot)

    def get_display_image(self, keycode: int, modifier: Modifier) -> "np.ndarray | None":
        """Return a 72×40 bool numpy array for the display position, or None."""
        bitmap = self.get_display_bitmap(keycode, modifier)
        if bitmap is None:
            return None
        bits = np.unpackbits(np.frombuffer(bitmap, dtype=np.uint8))
        return bits[:_OVERLAY_H * _OVERLAY_W].reshape(_OVERLAY_H, _OVERLAY_W).astype(bool)

    def save_as_png(self, keycode: int, modifier: Modifier, path: str) -> bool:
        """Write the overlay for (keycode, modifier) as a PNG. Returns False if no image."""
        img = self.get_display_image(keycode, modifier)
        if img is None:
            return False
        _write_png_gray8(path, (img * 255).astype(np.uint8))
        return True
