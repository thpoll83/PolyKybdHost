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
    Capacity is sourced from DeviceSettings.OVERLAY_MAPPING_CAPACITY: 600, the
    firmware's NUM_OVERLAY_SLOTS, which is not tied to keycode slots x variants.

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
        # Slots that have held an image since the pool was last cleared. A new
        # cache stands for a cleared pool (the connect path clears it, and a
        # reboot empties it), so this starts empty. See slot_is_clean.
        self._written: set[int] = set()

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
                        bytes_data: bytes | None = None) -> tuple[int | None, bool]:
        """
        Return (pool_slot, is_hit), or (None, False) when the pool is full of
        the current batch's own images.
        Hit: content_key already known, OR bytes_data identical to an existing slot.
        Miss: a new slot is allocated. When the pool is full, the slot evicted
        is taken from the oldest batch other than the current one.

        ⚠️ A batch NEVER evicts its own slots. Every slot it holds is still
        mapped to a key in the same program switch, so evicting one put a later
        image on an earlier key: measured over the emulated keyboard, 650
        distinct images in one switch showed 600 correct keys and 50 WRONG ones,
        while the send reported success (2026-10-09). The pool size is therefore
        a hard limit per switch, and the caller leaves the refused key blank.
        Nothing is changed on a refusal.
        bytes_data enables cross-key dedup: identical images share one pool slot.
        full_path is stored for the visual inspector (optional for tests).
        """
        if not self._in_batch:
            self._current_batch += 1

        # Exact key hit, unless the image under that name has changed
        slot = self._key_hit(content_key, bytes_data)
        if slot is not None:
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
            if slot is None:
                return None, False

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

    def claim(self, content_key: tuple, bytes_data: bytes | None = None) -> bool:
        """Mark an image this switch will show as part of the current batch, if
        the pool already holds it. Allocates nothing; returns whether it held it.

        ⚠️ Called for EVERY image of a switch before the first
        ``get_or_allocate``. Images arrive one at a time, so without it a new
        image could evict an old slot that a LATER key of the same switch would
        have hit, and that key then uploads its image again: measured with the
        pool full, a switch reusing 300 images and adding 300 sent 491 uploads
        in mixed order and 600 with the new ones first, instead of 300
        (2026-10-09). A claimed slot belongs to the current batch, so
        ``_evict_oldest_slot`` never picks it. Same hit rules as
        ``get_or_allocate``: the content key, then the bytes."""
        slot = self._key_hit(content_key, bytes_data)
        if slot is None and bytes_data is not None:
            slot = self._bytes_to_slot.get(bytes_data)
        if slot is None:
            return False
        if self._slot_batch.get(slot) != self._current_batch:
            self._slot_batch[slot] = self._current_batch
            self._version += 1
        return True

    def _key_hit(self, content_key: tuple, bytes_data: bytes | None) -> int | None:
        """The slot ``content_key`` names, or None. ⚠️ A key whose image has
        CHANGED is not a hit: a file edited under the same name keeps its key,
        and the slot still holds the old pixels (review, CodeRabbit). The stale
        alias is dropped, so the bytes decide from there."""
        slot = self._cache.get(content_key)
        if slot is None:
            return None
        held = self._slot_to_bytes.get(slot)
        if bytes_data is not None and held is not None and held != bytes_data:
            del self._cache[content_key]
            self._version += 1
            return None
        return slot

    def slot_is_clean(self, slot: int) -> bool:
        """True while ``slot`` has never been written since the pool was cleared.

        ⚠️ A REUSED slot still holds the image it was evicted from, and two of
        the older encodings write only part of a frame: an ROI upload writes its
        rectangle (``copy_rectangle_to_overlay_xy``) and a plain upload skips
        all-zero segments. Into a reused slot they leave the old image around the
        new one, so the sender keeps them for clean slots only. ``forget`` does
        not make a slot clean again: an upload that failed may have written part
        of it."""
        return slot not in self._written

    def mark_written(self, slot: int) -> None:
        """Record that an upload into ``slot`` has started."""
        self._written.add(slot)

    def forget(self, content_key: tuple) -> None:
        """Undo a just-recorded allocation whose image never reached the device.

        ``get_or_allocate`` records the slot *before* the caller uploads the
        image. If that upload fails (or is otherwise not committed), the entry
        must be removed — otherwise it becomes a permanent stale MRU *hit*: the
        host thinks the image is in the pool, never re-sends it, and the keycap
        shows whatever actually occupies that slot. Idempotent; a no-op for an
        unknown key or one that is only a dedup alias of a still-valid slot."""
        slot = self._cache.pop(content_key, None)
        if slot is None:
            return
        self._version += 1
        # If another content_key still maps to this slot (byte-dedup alias),
        # the slot is still valid — only this alias goes away.
        if slot in self._cache.values():
            return
        self._slot_batch.pop(slot, None)
        b = self._slot_to_bytes.pop(slot, None)
        if b is not None:
            self._bytes_to_slot.pop(b, None)
        self._slot_to_info.pop(slot, None)
        # Reclaim the index if it was the most recent fresh allocation, so the
        # pool doesn't leak a slot on every failure.
        if slot == self._next_free - 1:
            self._next_free -= 1

    def forget_slot(self, slot: int) -> None:
        """Forget EVERY key that maps to ``slot``: the image queued for it never
        reached the device.

        ``forget`` alone is not enough for an upload that is queued rather than
        sent at once (a PRC-coded image waiting for its report to fill): a
        later key with the same bytes dedups onto the slot in the meantime, and
        forgetting only the first key would leave that alias as a stale hit."""
        for key in [k for k, s in self._cache.items() if s == slot]:
            self.forget(key)

    def _evict_oldest_slot(self) -> int | None:
        """Pick a victim slot from the oldest batch that is not the current one,
        or None when every occupied slot belongs to the current batch (see
        `get_or_allocate`)."""
        candidates = {s: b for s, b in self._slot_batch.items()
                      if b != self._current_batch}
        if not candidates:
            return None
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
        self._written.clear()
        self._next_free = 0
        self._current_batch = 0
        self._in_batch = False
        self._version += 1
