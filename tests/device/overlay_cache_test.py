import unittest

from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache


class TestOverlayMRUCacheBasics(unittest.TestCase):

    def test_first_put_returns_slot_zero_and_miss(self):
        cache = OverlayMRUCache(10)
        slot, hit = cache.get_or_allocate(("copy.png", Modifier.NO_MOD.value))
        self.assertEqual(slot, 0)
        self.assertFalse(hit)

    def test_hit_returns_same_slot(self):
        cache = OverlayMRUCache(10)
        key = ("copy.png", Modifier.NO_MOD.value)
        slot_first, _ = cache.get_or_allocate(key)
        slot_second, hit = cache.get_or_allocate(key)
        self.assertEqual(slot_first, slot_second)
        self.assertTrue(hit)

    def test_fills_pool_sequentially(self):
        cache = OverlayMRUCache(5)
        for i in range(5):
            slot, hit = cache.get_or_allocate((f"img{i}.png", 0))
            self.assertEqual(slot, i)
            self.assertFalse(hit)

    def test_mru_eviction_overwrites_oldest(self):
        cache = OverlayMRUCache(3)
        k0 = ("a.png", 0)
        k1 = ("b.png", 0)
        k2 = ("c.png", 0)
        slot0, _ = cache.get_or_allocate(k0)
        slot1, _ = cache.get_or_allocate(k1)
        slot2, _ = cache.get_or_allocate(k2)
        # pool full; adding a fourth entry evicts k0 (oldest)
        k3 = ("d.png", 0)
        slot3, hit = cache.get_or_allocate(k3)
        self.assertFalse(hit)
        self.assertEqual(slot3, slot0)  # k0's slot is recycled

    def test_mru_hit_protects_from_eviction(self):
        cache = OverlayMRUCache(2)
        k0 = ("a.png", 0)
        k1 = ("b.png", 0)
        cache.get_or_allocate(k0)
        cache.get_or_allocate(k1)
        # touch k0 so k1 becomes the least-recently-used
        cache.get_or_allocate(k0)
        k2 = ("c.png", 0)
        slot2, _ = cache.get_or_allocate(k2)
        # k1 should be evicted (slot 1), k0 still cached
        _, hit0 = cache.get_or_allocate(k0)
        self.assertTrue(hit0)
        _, hit1 = cache.get_or_allocate(k1)
        self.assertFalse(hit1)  # k1 was evicted

    def test_reset_clears_cache(self):
        cache = OverlayMRUCache(10)
        key = ("copy.png", 0)
        cache.get_or_allocate(key)
        cache.reset()
        slot, hit = cache.get_or_allocate(key)
        self.assertFalse(hit)
        self.assertEqual(slot, 0)

    def test_get_occupied_slots_empty(self):
        cache = OverlayMRUCache(10)
        self.assertEqual(cache.get_occupied_slots(), set())

    def test_get_occupied_slots_after_allocations(self):
        cache = OverlayMRUCache(10)
        slot0, _ = cache.get_or_allocate(("a.png", 0))
        slot1, _ = cache.get_or_allocate(("b.png", 0))
        slot2, _ = cache.get_or_allocate(("c.png", 0))
        self.assertEqual(cache.get_occupied_slots(), {slot0, slot1, slot2})

    def test_get_occupied_slots_after_eviction(self):
        cache = OverlayMRUCache(2)
        slot0, _ = cache.get_or_allocate(("a.png", 0))
        slot1, _ = cache.get_or_allocate(("b.png", 0))
        # evict k0 by adding k2
        slot2, _ = cache.get_or_allocate(("c.png", 0))
        # slot2 reuses slot0's index; only two entries remain
        self.assertEqual(len(cache.get_occupied_slots()), 2)
        self.assertIn(slot1, cache.get_occupied_slots())
        self.assertIn(slot2, cache.get_occupied_slots())

    def test_get_occupied_slots_clears_after_reset(self):
        cache = OverlayMRUCache(10)
        cache.get_or_allocate(("a.png", 0))
        cache.reset()
        self.assertEqual(cache.get_occupied_slots(), set())


class TestPoolSlotToFirmwareAddress(unittest.TestCase):

    def test_slot_0_is_kc_a_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(0)
        self.assertEqual(kc, KeyCode.KC_A.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_90_is_kc_a_ctrl(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(90)
        self.assertEqual(kc, KeyCode.KC_A.value)
        self.assertEqual(mod, Modifier.CTRL)

    def test_slot_79_is_kc_num_lock_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(79)
        self.assertEqual(kc, KeyCode.KC_NUM_LOCK.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_80_is_kc_nonus_backslash_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(80)
        self.assertEqual(kc, KeyCode.KC_NONUS_BACKSLASH.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_81_is_kc_application_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(81)
        self.assertEqual(kc, KeyCode.KC_APPLICATION.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_82_is_kc_left_ctrl_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(82)
        self.assertEqual(kc, KeyCode.KC_LEFT_CTRL.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_89_is_kc_right_gui_no_mod(self):
        cache = OverlayMRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(89)
        self.assertEqual(kc, KeyCode.KC_RIGHT_GUI.value)
        self.assertEqual(mod, Modifier.NO_MOD)


class TestDisplayFlatIdx(unittest.TestCase):

    def test_kc_a_no_mod_is_zero(self):
        idx = OverlayMRUCache.display_flat_idx(KeyCode.KC_A.value, Modifier.NO_MOD)
        self.assertEqual(idx, 0)

    def test_kc_a_ctrl_is_90(self):
        idx = OverlayMRUCache.display_flat_idx(KeyCode.KC_A.value, Modifier.CTRL)
        self.assertEqual(idx, 90)

    def test_kc_num_lock_no_mod_is_79(self):
        idx = OverlayMRUCache.display_flat_idx(KeyCode.KC_NUM_LOCK.value, Modifier.NO_MOD)
        self.assertEqual(idx, 79)

    def test_kc_nonus_backslash_no_mod_is_80(self):
        idx = OverlayMRUCache.display_flat_idx(KeyCode.KC_NONUS_BACKSLASH.value, Modifier.NO_MOD)
        self.assertEqual(idx, 80)

    def test_kc_left_ctrl_no_mod_is_82(self):
        idx = OverlayMRUCache.display_flat_idx(KeyCode.KC_LEFT_CTRL.value, Modifier.NO_MOD)
        self.assertEqual(idx, 82)

    def test_round_trip_pool_slot_to_display_flat_idx(self):
        """Pool slot i and display_flat_idx for the same (kc, mod) must match across all modifier layers."""
        cache = OverlayMRUCache(630)
        for pool_slot in range(cache.capacity):
            kc, mod = cache.pool_slot_to_firmware_address(pool_slot)
            flat = OverlayMRUCache.display_flat_idx(kc, mod)
            self.assertEqual(flat, pool_slot,
                             f"pool_slot={pool_slot} kc=0x{kc:02x} mod={mod} → flat={flat}")


class TestBytesDedup(unittest.TestCase):

    _BYTES_A = bytes(i % 256 for i in range(360))
    _BYTES_B = bytes((255 - i % 256) for i in range(360))

    def test_same_bytes_different_key_is_hit_same_slot(self):
        cache = OverlayMRUCache(10)
        k1 = ("img.png", 0, 0x04)  # KC_A
        k2 = ("img.png", 0, 0x05)  # KC_B — different key, same bytes
        slot1, hit1 = cache.get_or_allocate(k1, bytes_data=self._BYTES_A)
        slot2, hit2 = cache.get_or_allocate(k2, bytes_data=self._BYTES_A)
        self.assertFalse(hit1)
        self.assertTrue(hit2)
        self.assertEqual(slot1, slot2)

    def test_different_bytes_get_separate_slots(self):
        cache = OverlayMRUCache(10)
        k1 = ("img.png", 0, 0x04)
        k2 = ("img.png", 0, 0x05)
        slot1, _ = cache.get_or_allocate(k1, bytes_data=self._BYTES_A)
        slot2, _ = cache.get_or_allocate(k2, bytes_data=self._BYTES_B)
        self.assertNotEqual(slot1, slot2)

    def test_dedup_without_bytes_data_is_still_a_miss(self):
        cache = OverlayMRUCache(10)
        k1 = ("img.png", 0, 0x04)
        k2 = ("img.png", 0, 0x05)
        cache.get_or_allocate(k1, bytes_data=self._BYTES_A)
        # Same bytes exist but we don't pass bytes_data → treated as unrelated key
        _, hit = cache.get_or_allocate(k2)
        self.assertFalse(hit)

    def test_eviction_removes_byte_dedup_alias(self):
        cache = OverlayMRUCache(2)
        k1 = ("a.png", 0, 1)
        k2 = ("a.png", 0, 2)  # alias of k1 (same bytes)
        k3 = ("b.png", 0, 3)
        k4 = ("c.png", 0, 4)
        slot1, _ = cache.get_or_allocate(k1, bytes_data=self._BYTES_A)
        slot2, _ = cache.get_or_allocate(k2, bytes_data=self._BYTES_A)  # alias → slot1
        self.assertEqual(slot1, slot2)
        # Pool is at capacity (2 unique slots: slot1 shared by k1+k2, slot2 by k3)
        cache.get_or_allocate(k3, bytes_data=self._BYTES_B)
        # Evicting the least-recently-used entry (k1) should also purge alias k2 since they share a slot
        _, hit_k4 = cache.get_or_allocate(k4, bytes_data=bytes(360))
        # k2 should now be a miss (its slot was freed along with k1)
        _, hit_k2 = cache.get_or_allocate(k2, bytes_data=self._BYTES_A)
        self.assertFalse(hit_k2)

    def test_reset_clears_bytes_index(self):
        cache = OverlayMRUCache(10)
        k1 = ("img.png", 0, 0x04)
        k2 = ("img.png", 0, 0x05)
        cache.get_or_allocate(k1, bytes_data=self._BYTES_A)
        cache.reset()
        _, hit = cache.get_or_allocate(k2, bytes_data=self._BYTES_A)
        self.assertFalse(hit)  # bytes index was cleared


if __name__ == '__main__':
    unittest.main()
