import os
from collections import OrderedDict

from polyhost.device.keys import KeyCode, Modifier


def _slot_to_keycode(keycode_slot: int) -> int:
    """Inverse of keycode_to_mapping_idx: slot index (0-89) → raw keycode int."""
    if keycode_slot <= 79:
        return keycode_slot + KeyCode.KC_A.value
    elif keycode_slot <= 81:
        return keycode_slot - 80 + KeyCode.KC_NONUS_BACKSLASH.value
    else:
        return keycode_slot - 82 + KeyCode.KC_LEFT_CTRL.value


class OverlayMRUCache:
    """
    Tracks which overlay images occupy which pool slots in the keyboard firmware.

    The pool is a contiguous range of firmware overlay slots (0..capacity-1).
    Each slot is addressed by a (keycode, modifier) pair derived from its flat index.
    Capacity is sourced from DeviceSettings.OVERLAY_MRU_POOL_CAPACITY (90 × 7 = 630).

    Content key: (os.path.basename(filename), modifier.value, keycode)
    — uniquely identifies one overlay image (one key+modifier combo from one file).

    Eviction policy is least-recently-used: when the pool is full, the slot whose
    content was touched longest ago is reused. The class is named MRU because it
    *contains* the most-recently-used overlays — that is the property surfaced to
    callers and to the inspector dialog.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: OrderedDict[tuple, int] = OrderedDict()
        self._next_free: int = 0
        self._slot_to_info: dict[int, tuple[str, int, int]] = {}
        self._bytes_to_slot: dict[bytes, int] = {}   # bytes_data → pool_slot
        self._slot_to_bytes: dict[int, bytes] = {}   # pool_slot → bytes_data

    def get_or_allocate(self, content_key: tuple, full_path: str = "",
                        bytes_data: bytes | None = None) -> tuple[int, bool]:
        """
        Return (pool_slot, is_hit).
        Hit: content_key already known, OR bytes_data identical to an existing slot.
        Miss: a new slot is allocated (evicting the least-recently-used entry if full).
        bytes_data enables cross-key dedup: identical images share one pool slot.
        full_path is stored for the visual inspector (optional for tests).
        """
        # Exact key hit
        if content_key in self._cache:
            self._cache.move_to_end(content_key)
            return self._cache[content_key], True

        # Byte-level dedup: identical image already lives at another slot
        if bytes_data is not None and bytes_data in self._bytes_to_slot:
            slot = self._bytes_to_slot[bytes_data]
            self._cache[content_key] = slot
            self._cache.move_to_end(content_key)
            return slot, True

        # True miss: allocate or evict
        if self._next_free < self.capacity:
            slot = self._next_free
            self._next_free += 1
        else:
            _, evicted_slot = self._cache.popitem(last=False)
            slot = evicted_slot
            # Remove all alias entries pointing to the same slot — they are now stale
            for k in [k for k, v in self._cache.items() if v == slot]:
                del self._cache[k]
            # Clean bytes index for this slot
            if slot in self._slot_to_bytes:
                self._bytes_to_slot.pop(self._slot_to_bytes.pop(slot), None)

        self._cache[content_key] = slot
        if bytes_data is not None:
            self._bytes_to_slot[bytes_data] = slot
            self._slot_to_bytes[slot] = bytes_data
        if full_path:
            modifier_value = content_key[1] if len(content_key) > 1 else 0
            keycode = content_key[2] if len(content_key) > 2 else 0
            self._slot_to_info[slot] = (full_path, modifier_value, keycode)
        return slot, False

    def used_slots(self) -> int:
        """Number of pool slots currently occupied."""
        return len(self._cache)

    def get_occupied_slots(self) -> set:
        """Set of pool slot indices currently holding a cached image."""
        return set(self._cache.values())

    def get_mru_info(self) -> dict[int, tuple]:
        """
        Returns {pool_slot: (full_path, modifier_value, keycode, mru_rank)} for all
        occupied slots. mru_rank 1 = least-recently-used (next to evict), N = most-recently-used.
        """
        # A single slot can be referenced by multiple OrderedDict keys (byte-dedup
        # aliases), so the raw enumerate index can exceed the number of unique slots.
        # Take each slot's latest position, then re-rank 1..N over unique slots so
        # the inspector's red→green gradient stays normalised.
        last_position: dict[int, int] = {}
        for position, (_key, slot) in enumerate(self._cache.items()):
            last_position[slot] = position

        result = {}
        for rank, (slot, _pos) in enumerate(
            sorted(last_position.items(), key=lambda kv: kv[1]), 1
        ):
            info = self._slot_to_info.get(slot)
            if info:
                full_path, mod_val, kc = info
                result[slot] = (full_path, mod_val, kc, rank)
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
        self._bytes_to_slot.clear()
        self._slot_to_bytes.clear()
        self._next_free = 0
