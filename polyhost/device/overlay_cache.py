from contextlib import contextmanager

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
    Capacity is sourced from DeviceSettings.OVERLAY_MAPPING_CAPACITY (90 x 7 = 630).

    Content key: (os.path.basename(filename), modifier.value, keycode)
    — uniquely identifies one overlay image (one key+modifier combo from one file).

    Aging is batch-based: every overlay sent in one program switch shares a
    single age. Eviction targets the oldest batch first, so a complete batch is
    drained before any newer batch is touched. Outside an explicit ``batch()``
    context each ``get_or_allocate`` call is its own batch (the original
    per-call MRU semantic), which keeps unit tests and ad-hoc callers correct.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: dict[tuple, int] = {}
        self._next_free: int = 0
        self._slot_to_info: dict[int, tuple[str, int, int]] = {}
        self._bytes_to_slot: dict[bytes, int] = {}   # bytes_data → pool_slot
        self._slot_to_bytes: dict[int, bytes] = {}   # pool_slot → bytes_data
        self._slot_batch: dict[int, int] = {}        # pool_slot → batch_id
        self._current_batch: int = 0
        self._in_batch: bool = False
        self._version: int = 0                       # bumps on every state change
        self._transferred_mapping: dict[int, int] = {}  # accumulated display_idx → pool_slot

    @property
    def version(self) -> int:
        """Monotonically-increasing counter for change detection (e.g. live UI)."""
        return self._version

    @property
    def transferred_mapping(self) -> dict[int, int]:
        """Accumulated display_idx → pool_slot of every mapping ever sent (later sends override earlier ones)."""
        return self._transferred_mapping

    def record_transferred_mapping(self, mapping: dict[int, int]) -> None:
        """Merge a freshly sent mapping into the accumulated history (for inspector UI)."""
        self._transferred_mapping.update(mapping)
        self._version += 1

    @contextmanager
    def batch(self):
        """Group every ``get_or_allocate`` inside the with-block under one age.
        Eviction during the batch will not touch slots from this batch unless
        every older batch has already been fully drained."""
        self._current_batch += 1
        was_in_batch = self._in_batch
        self._in_batch = True
        try:
            yield
        finally:
            self._in_batch = was_in_batch

    def get_or_allocate(self, content_key: tuple, full_path: str = "",
                        bytes_data: bytes | None = None) -> tuple[int, bool]:
        """
        Return (pool_slot, is_hit).
        Hit: content_key already known, OR bytes_data identical to an existing slot.
        Miss: a new slot is allocated. When the pool is full, the slot evicted
        is taken from the oldest batch (preferring a batch other than the
        currently-active one, so a single program switch never displaces its own
        in-progress entries unless its batch has filled the entire pool).
        bytes_data enables cross-key dedup: identical images share one pool slot.
        full_path is stored for the visual inspector (optional for tests).
        """
        if not self._in_batch:
            self._current_batch += 1

        # Exact key hit
        if content_key in self._cache:
            slot = self._cache[content_key]
            self._slot_batch[slot] = self._current_batch
            self._version += 1
            return slot, True

        # Byte-level dedup: identical image already lives at another slot
        if bytes_data is not None and bytes_data in self._bytes_to_slot:
            slot = self._bytes_to_slot[bytes_data]
            self._cache[content_key] = slot
            self._slot_batch[slot] = self._current_batch
            self._version += 1
            return slot, True

        # True miss: allocate a fresh slot or evict the oldest batch
        if self._next_free < self.capacity:
            slot = self._next_free
            self._next_free += 1
        else:
            slot = self._evict_oldest_slot()

        self._cache[content_key] = slot
        self._slot_batch[slot] = self._current_batch
        if bytes_data is not None:
            self._bytes_to_slot[bytes_data] = slot
            self._slot_to_bytes[slot] = bytes_data
        if full_path:
            modifier_value = content_key[1] if len(content_key) > 1 else 0
            keycode = content_key[2] if len(content_key) > 2 else 0
            self._slot_to_info[slot] = (full_path, modifier_value, keycode)
        self._version += 1
        return slot, False

    def _evict_oldest_slot(self) -> int:
        """Pick a victim slot. Prefer the smallest batch that is not the current
        batch; only fall back to the current batch when nothing older remains."""
        candidates = {s: b for s, b in self._slot_batch.items()
                      if b != self._current_batch}
        if not candidates:
            candidates = self._slot_batch
        victim = min(candidates, key=candidates.get)

        # Drop every alias key pointing at the victim slot
        for k in [k for k, v in self._cache.items() if v == victim]:
            del self._cache[k]
        del self._slot_batch[victim]
        if victim in self._slot_to_bytes:
            self._bytes_to_slot.pop(self._slot_to_bytes.pop(victim), None)
        self._slot_to_info.pop(victim, None)
        return victim

    def used_slots(self) -> int:
        """Number of pool slots currently occupied."""
        return len(self._slot_batch)

    def get_occupied_slots(self) -> set:
        """Set of pool slot indices currently holding a cached image."""
        return set(self._slot_batch.keys())

    def get_mru_info(self) -> dict[int, tuple]:
        """
        Returns {pool_slot: (full_path, modifier_value, keycode, mru_rank)} for
        every occupied slot that has display info. Slots from the same batch
        share a rank; rank 1 = oldest batch (next to evict), N = most-recent
        batch. The number of distinct ranks equals the number of live batches.
        """
        if not self._slot_batch:
            return {}
        sorted_batches = sorted(set(self._slot_batch.values()))
        batch_to_rank = {b: rank for rank, b in enumerate(sorted_batches, 1)}

        result = {}
        for slot, batch_id in self._slot_batch.items():
            info = self._slot_to_info.get(slot)
            if info:
                full_path, mod_val, kc = info
                result[slot] = (full_path, mod_val, kc, batch_to_rank[batch_id])
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
        self._slot_batch.clear()
        self._transferred_mapping.clear()
        self._next_free = 0
        self._current_batch = 0
        self._in_batch = False
        self._version += 1
