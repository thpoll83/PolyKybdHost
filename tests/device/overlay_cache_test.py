import unittest

from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayLRUCache


class TestOverlayLRUCacheBasics(unittest.TestCase):

    def test_first_put_returns_slot_zero_and_miss(self):
        cache = OverlayLRUCache(10)
        slot, hit = cache.get_or_allocate(("copy.png", Modifier.NO_MOD.value))
        self.assertEqual(slot, 0)
        self.assertFalse(hit)

    def test_hit_returns_same_slot(self):
        cache = OverlayLRUCache(10)
        key = ("copy.png", Modifier.NO_MOD.value)
        slot_first, _ = cache.get_or_allocate(key)
        slot_second, hit = cache.get_or_allocate(key)
        self.assertEqual(slot_first, slot_second)
        self.assertTrue(hit)

    def test_fills_pool_sequentially(self):
        cache = OverlayLRUCache(5)
        for i in range(5):
            slot, hit = cache.get_or_allocate((f"img{i}.png", 0))
            self.assertEqual(slot, i)
            self.assertFalse(hit)

    def test_lru_eviction_overwrites_oldest(self):
        cache = OverlayLRUCache(3)
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

    def test_lru_hit_protects_from_eviction(self):
        cache = OverlayLRUCache(2)
        k0 = ("a.png", 0)
        k1 = ("b.png", 0)
        cache.get_or_allocate(k0)
        cache.get_or_allocate(k1)
        # touch k0 so k1 becomes the LRU
        cache.get_or_allocate(k0)
        k2 = ("c.png", 0)
        slot2, _ = cache.get_or_allocate(k2)
        # k1 should be evicted (slot 1), k0 still cached
        _, hit0 = cache.get_or_allocate(k0)
        self.assertTrue(hit0)
        _, hit1 = cache.get_or_allocate(k1)
        self.assertFalse(hit1)  # k1 was evicted

    def test_reset_clears_cache(self):
        cache = OverlayLRUCache(10)
        key = ("copy.png", 0)
        cache.get_or_allocate(key)
        cache.reset()
        slot, hit = cache.get_or_allocate(key)
        self.assertFalse(hit)
        self.assertEqual(slot, 0)


class TestPoolSlotToFirmwareAddress(unittest.TestCase):

    def test_slot_0_is_kc_a_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(0)
        self.assertEqual(kc, KeyCode.KC_A.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_90_is_kc_a_ctrl(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(90)
        self.assertEqual(kc, KeyCode.KC_A.value)
        self.assertEqual(mod, Modifier.CTRL)

    def test_slot_79_is_kc_num_lock_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(79)
        self.assertEqual(kc, KeyCode.KC_NUM_LOCK.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_80_is_kc_nonus_backslash_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(80)
        self.assertEqual(kc, KeyCode.KC_NONUS_BACKSLASH.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_81_is_kc_application_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(81)
        self.assertEqual(kc, KeyCode.KC_APPLICATION.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_82_is_kc_left_ctrl_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(82)
        self.assertEqual(kc, KeyCode.KC_LEFT_CTRL.value)
        self.assertEqual(mod, Modifier.NO_MOD)

    def test_slot_89_is_kc_right_gui_no_mod(self):
        cache = OverlayLRUCache(200)
        kc, mod = cache.pool_slot_to_firmware_address(89)
        self.assertEqual(kc, KeyCode.KC_RIGHT_GUI.value)
        self.assertEqual(mod, Modifier.NO_MOD)


class TestDisplayFlatIdx(unittest.TestCase):

    def test_kc_a_no_mod_is_zero(self):
        idx = OverlayLRUCache.display_flat_idx(KeyCode.KC_A.value, Modifier.NO_MOD)
        self.assertEqual(idx, 0)

    def test_kc_a_ctrl_is_90(self):
        idx = OverlayLRUCache.display_flat_idx(KeyCode.KC_A.value, Modifier.CTRL)
        self.assertEqual(idx, 90)

    def test_kc_num_lock_no_mod_is_79(self):
        idx = OverlayLRUCache.display_flat_idx(KeyCode.KC_NUM_LOCK.value, Modifier.NO_MOD)
        self.assertEqual(idx, 79)

    def test_kc_nonus_backslash_no_mod_is_80(self):
        idx = OverlayLRUCache.display_flat_idx(KeyCode.KC_NONUS_BACKSLASH.value, Modifier.NO_MOD)
        self.assertEqual(idx, 80)

    def test_kc_left_ctrl_no_mod_is_82(self):
        idx = OverlayLRUCache.display_flat_idx(KeyCode.KC_LEFT_CTRL.value, Modifier.NO_MOD)
        self.assertEqual(idx, 82)

    def test_round_trip_pool_slot_to_display_flat_idx(self):
        """Pool slot i and display_flat_idx for the same (kc, mod) must match across all modifier layers."""
        cache = OverlayLRUCache(630)
        for pool_slot in range(cache.capacity):
            kc, mod = cache.pool_slot_to_firmware_address(pool_slot)
            flat = OverlayLRUCache.display_flat_idx(kc, mod)
            self.assertEqual(flat, pool_slot,
                             f"pool_slot={pool_slot} kc=0x{kc:02x} mod={mod} → flat={flat}")


if __name__ == '__main__':
    unittest.main()
