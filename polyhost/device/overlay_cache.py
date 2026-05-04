import os
from collections import OrderedDict
from typing import Optional

from polyhost.device.keys import KeyCode, Modifier


def _slot_to_keycode(keycode_slot: int) -> int:
    """Inverse of keycode_to_mapping_idx: slot index (0-89) → raw keycode int."""
    if keycode_slot <= 79:
        return keycode_slot + KeyCode.KC_A.value
    elif keycode_slot <= 81:
        return keycode_slot - 80 + KeyCode.KC_NONUS_BACKSLASH.value
    else:
        return keycode_slot - 82 + KeyCode.KC_LEFT_CTRL.value


class OverlayLRUCache:
    """
    Tracks which overlay images occupy which pool slots in the keyboard firmware.

    The pool is a contiguous range of firmware overlay slots (0..capacity-1).
    Each slot is addressed by a (keycode, modifier) pair derived from its flat index.
    Capacity is sourced from DeviceSettings.OVERLAY_LRU_POOL_CAPACITY (90 × 7 = 630).

    Content key: (os.path.basename(filename), modifier.value, keycode)
    — uniquely identifies one overlay image (one key+modifier combo from one file).
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: OrderedDict[tuple, int] = OrderedDict()
        self._next_free: int = 0
        # pool_slot → (full_path, modifier_value, keycode) for the inspector
        self._slot_to_info: dict[int, tuple[str, int, int]] = {}

    def get_or_allocate(self, content_key: tuple, full_path: str = "") -> tuple[int, bool]:
        """
        Return (pool_slot, is_hit).
        Hit: slot already holds this content; marked as most-recently-used.
        Miss: a slot is allocated (evicting LRU if pool is full) and returned.
        full_path is stored for the visual inspector (optional for tests).
        """
        if content_key in self._cache:
            self._cache.move_to_end(content_key)
            return self._cache[content_key], True

        if self._next_free < self.capacity:
            slot = self._next_free
            self._next_free += 1
        else:
            _, slot = self._cache.popitem(last=False)

        self._cache[content_key] = slot
        if full_path:
            modifier_value = content_key[1] if len(content_key) > 1 else 0
            keycode = content_key[2] if len(content_key) > 2 else 0
            self._slot_to_info[slot] = (full_path, modifier_value, keycode)
        return slot, False

    def get_lru_info(self) -> dict[int, tuple]:
        """
        Returns {pool_slot: (full_path, modifier_value, keycode, lru_rank)} for all
        occupied slots. lru_rank 1 = most-recently-used, N = least-recently-used (next to evict).
        """
        total = len(self._cache)
        result = {}
        for rank_from_lru, (_key, slot) in enumerate(self._cache.items(), 1):
            rank_from_mru = total - rank_from_lru + 1
            info = self._slot_to_info.get(slot)
            if info:
                full_path, mod_val, kc = info
                result[slot] = (full_path, mod_val, kc, rank_from_mru)
        return result

    def pool_slot_to_firmware_address(self, slot: int) -> tuple[int, Modifier]:
        """Convert a flat pool slot index to (keycode_int, Modifier) for HID send."""
        keycode_slot = slot % 90
        modifier_var = slot // 90
        return _slot_to_keycode(keycode_slot), Modifier(modifier_var)

    @staticmethod
    def display_flat_idx(keycode: int, modifier: Modifier) -> int:
        """
        Flat firmware index for a display position (keycode_int, modifier).
        Mirrors keycode_to_mapping_idx but accepts a raw int keycode.
        """
        if keycode > KeyCode.KC_APPLICATION.value:
            slot = keycode - KeyCode.KC_LEFT_CTRL.value + 82
        elif keycode > KeyCode.KC_NUM_LOCK.value:
            slot = keycode - KeyCode.KC_NONUS_BACKSLASH.value + 80
        else:
            slot = keycode - KeyCode.KC_A.value
        return slot + 90 * modifier.value

    def reset(self):
        """Clear all entries (call after device reconnect)."""
        self._cache.clear()
        self._slot_to_info.clear()
        self._next_free = 0
