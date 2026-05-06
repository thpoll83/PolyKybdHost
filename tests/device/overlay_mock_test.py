"""
Tests for OverlayFirmwareSim and PolyKybdMock overlay simulation.

No Qt / no image files required: OverlayData is constructed directly from
numpy arrays, and the mock's HID methods never touch real hardware.
"""
import unittest
import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_data import OverlayData
from polyhost.device.overlay_sim import OverlayFirmwareSim, OVERLAY_BYTES, display_flat_idx
from polyhost.device.poly_kybd_mock import PolyKybdMock


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_image(pattern: str = "rect") -> np.ndarray:
    """Return a 40×72 bool numpy array with a known pixel pattern."""
    img = np.zeros((40, 72), dtype=bool)
    if pattern == "rect":
        img[5:20, 10:60] = True
    elif pattern == "stripe":
        img[::2, :] = True          # every other row
    elif pattern == "dot":
        img[0, 0] = True            # single pixel at top-left
    elif pattern == "full":
        img[:] = True
    return img


def _make_overlay(pattern: str = "rect") -> OverlayData:
    return OverlayData(DeviceSettings(), _make_image(pattern))


def _make_mock() -> PolyKybdMock:
    return PolyKybdMock(DeviceSettings(), "0.7.1")


def _slot(kc_value: int, mod: Modifier) -> int:
    return display_flat_idx(kc_value, mod)


# ── OverlayFirmwareSim unit tests ────────────────────────────────────────────

class TestOverlayFirmwareSimInit(unittest.TestCase):

    def test_initial_state_returns_none_for_any_position(self):
        sim = OverlayFirmwareSim()
        self.assertIsNone(sim.get_display_bitmap(KeyCode.KC_A.value, Modifier.NO_MOD))
        self.assertIsNone(sim.get_display_bitmap(KeyCode.KC_Z.value, Modifier.CTRL))

    def test_get_display_image_returns_none_initially(self):
        sim = OverlayFirmwareSim()
        self.assertIsNone(sim.get_display_image(KeyCode.KC_A.value, Modifier.NO_MOD))


class TestOverlayFirmwareSimWriteAndRead(unittest.TestCase):

    def test_store_image_and_retrieve_via_identity_mapping(self):
        sim = OverlayFirmwareSim()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        bitmap = bytes([i % 256 for i in range(OVERLAY_BYTES)])
        sim.store_image(_slot(kc, mod), bitmap)
        self.assertEqual(sim.get_display_bitmap(kc, mod), bitmap)

    def test_store_image_marks_slot_as_used(self):
        sim = OverlayFirmwareSim()
        slot = _slot(KeyCode.KC_B.value, Modifier.SHIFT)
        sim.store_image(slot, bytes(OVERLAY_BYTES))
        self.assertTrue(sim.is_used(slot))

    def test_store_image_wrong_size_raises(self):
        sim = OverlayFirmwareSim()
        with self.assertRaises(ValueError):
            sim.store_image(0, bytes(100))

    def test_get_display_image_shape(self):
        sim = OverlayFirmwareSim()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        sim.store_image(_slot(kc, mod), bytes([0xFF] * OVERLAY_BYTES))
        img = sim.get_display_image(kc, mod)
        self.assertIsNotNone(img)
        self.assertEqual(img.shape, (40, 72))

    def test_get_display_image_all_white(self):
        sim = OverlayFirmwareSim()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        sim.store_image(_slot(kc, mod), bytes([0xFF] * OVERLAY_BYTES))
        img = sim.get_display_image(kc, mod)
        self.assertTrue(img.all())

    def test_get_display_image_single_pixel_accuracy(self):
        sim = OverlayFirmwareSim()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        # 72 pixels per row = 9 bytes.  Row 0 occupies bytes 0..8 (MSB-first).
        # byte 0 bit7 = pixel (0,0);  byte 8 bit0 = pixel (0,71).
        bitmap = bytearray(OVERLAY_BYTES)
        bitmap[0] = 0x80            # MSB-first: pixel (row=0, col=0)
        bitmap[8] = 0x01            # LSB of byte 8: pixel (row=0, col=71)
        sim.store_image(_slot(kc, mod), bytes(bitmap))
        img = sim.get_display_image(kc, mod)
        self.assertTrue(img[0, 0])
        self.assertTrue(img[0, 71])
        self.assertFalse(img[0, 1])
        self.assertFalse(img[1, 0])

    def test_two_positions_stored_independently(self):
        sim = OverlayFirmwareSim()
        kc_a = KeyCode.KC_A.value
        kc_b = KeyCode.KC_B.value
        mod = Modifier.NO_MOD
        bm_a = bytes([0xAA] * OVERLAY_BYTES)
        bm_b = bytes([0x55] * OVERLAY_BYTES)
        sim.store_image(_slot(kc_a, mod), bm_a)
        sim.store_image(_slot(kc_b, mod), bm_b)
        self.assertEqual(sim.get_display_bitmap(kc_a, mod), bm_a)
        self.assertEqual(sim.get_display_bitmap(kc_b, mod), bm_b)


class TestOverlayFirmwareSimResets(unittest.TestCase):

    def test_reset_usage_makes_image_invisible(self):
        sim = OverlayFirmwareSim()
        kc, mod = KeyCode.KC_A.value, Modifier.NO_MOD
        sim.store_image(_slot(kc, mod), bytes(OVERLAY_BYTES))
        sim.reset_usage()
        self.assertIsNone(sim.get_display_bitmap(kc, mod))

    def test_reset_usage_preserves_image_data(self):
        sim = OverlayFirmwareSim()
        kc, mod = KeyCode.KC_A.value, Modifier.NO_MOD
        slot = _slot(kc, mod)
        bitmap = bytes([0xCC] * OVERLAY_BYTES)
        sim.store_image(slot, bitmap)
        sim.reset_usage()
        # Re-mark via set_mapping (identity)
        sim.set_mapping(slot, slot)
        self.assertEqual(sim.get_display_bitmap(kc, mod), bitmap)

    def test_reset_mapping_restores_identity(self):
        sim = OverlayFirmwareSim()
        kc_a, kc_b = KeyCode.KC_A.value, KeyCode.KC_B.value
        mod = Modifier.NO_MOD
        slot_a = _slot(kc_a, mod)
        slot_b = _slot(kc_b, mod)
        bm_b = bytes([0xFF] * OVERLAY_BYTES)
        sim.store_image(slot_b, bm_b)
        sim.set_mapping(slot_a, slot_b)   # KC_A display → KC_B data
        self.assertEqual(sim.get_display_bitmap(kc_a, mod), bm_b)
        sim.reset_mapping()
        # After reset: KC_A maps to itself (slot_a), which has no data stored
        self.assertIsNone(sim.get_display_bitmap(kc_a, mod))

    def test_reset_all_clears_store_usage_and_mapping(self):
        sim = OverlayFirmwareSim()
        kc, mod = KeyCode.KC_A.value, Modifier.NO_MOD
        slot = _slot(kc, mod)
        sim.store_image(slot, bytes([0xFF] * OVERLAY_BYTES))
        sim.set_mapping(slot, slot)
        sim.reset_all()
        self.assertIsNone(sim.get_display_bitmap(kc, mod))
        self.assertFalse(sim.is_used(slot))
        self.assertEqual(sim._store, {})
        self.assertEqual(sim._mapping, {})


class TestOverlayFirmwareSimMapping(unittest.TestCase):

    def test_set_mapping_redirects_display_to_different_pool_slot(self):
        sim = OverlayFirmwareSim()
        kc_disp = KeyCode.KC_Z.value
        mod_disp = Modifier.CTRL
        display_pos = _slot(kc_disp, mod_disp)

        kc_pool = KeyCode.KC_A.value
        pool_slot = _slot(kc_pool, Modifier.NO_MOD)

        bitmap = bytes([0xAB] * OVERLAY_BYTES)
        sim.store_image(pool_slot, bitmap)
        sim.reset_usage()
        sim.set_mapping(display_pos, pool_slot)

        self.assertEqual(sim.get_display_bitmap(kc_disp, mod_disp), bitmap)

    def test_unmapped_display_position_returns_none_after_apply_mapping(self):
        sim = OverlayFirmwareSim()
        kc_a = KeyCode.KC_A.value
        kc_b = KeyCode.KC_B.value
        mod = Modifier.NO_MOD
        slot_b = _slot(kc_b, mod)
        sim.store_image(slot_b, bytes([0x55] * OVERLAY_BYTES))
        # Only KC_B display position is mapped/marked used
        sim.apply_mapping({slot_b: slot_b})
        # KC_A display position is NOT in usage set → None
        self.assertIsNone(sim.get_display_bitmap(kc_a, mod))
        # KC_B IS in usage set → bitmap returned
        self.assertIsNotNone(sim.get_display_bitmap(kc_b, mod))

    def test_mru_flow_store_reset_remap(self):
        """
        Full MRU app-switch flow:
          1. send_smallest_overlay writes to pool slot (store_image marks pool_slot used)
          2. reset_usage() clears all bits
          3. send_overlay_mapping marks only display positions as used
          4. display query returns image via mapping
        """
        sim = OverlayFirmwareSim()
        display_kc = KeyCode.KC_Z.value
        display_mod = Modifier.SHIFT
        display_pos = _slot(display_kc, display_mod)

        pool_kc = KeyCode.KC_A.value
        pool_slot = _slot(pool_kc, Modifier.NO_MOD)

        bitmap = bytes([0b10101010] * OVERLAY_BYTES)
        sim.store_image(pool_slot, bitmap)   # cache-miss write
        sim.reset_usage()                    # clear pool_slot mark
        sim.apply_mapping({display_pos: pool_slot})  # display → pool

        self.assertEqual(sim.get_display_bitmap(display_kc, display_mod), bitmap)
        self.assertIsNone(sim.get_display_bitmap(pool_kc, Modifier.NO_MOD))  # pool itself not shown

    def test_apply_mapping_updates_last_mapping_wins(self):
        sim = OverlayFirmwareSim()
        kc, mod = KeyCode.KC_A.value, Modifier.NO_MOD
        pos = _slot(kc, mod)
        bm1 = bytes([0x11] * OVERLAY_BYTES)
        bm2 = bytes([0x22] * OVERLAY_BYTES)
        sim.store_image(0, bm1)
        sim.store_image(1, bm2)
        sim.set_mapping(pos, 0)
        sim.set_mapping(pos, 1)   # second call wins
        self.assertEqual(sim.get_display_bitmap(kc, mod), bm2)


# ── PolyKybdMock integration tests ──────────────────────────────────────────

class TestPolyKybdMockSendSmallestOverlay(unittest.TestCase):

    def test_stores_bitmap_at_correct_pool_slot(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        od = _make_overlay("rect")
        mock.send_smallest_overlay(kc, mod, {kc: od})
        self.assertEqual(mock.get_display_bitmap(kc, mod), od.all_bytes)

    def test_returns_smallest_message_count(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        od = _make_overlay("rect")
        count = mock.send_smallest_overlay(kc, Modifier.NO_MOD, {kc: od})
        expected = min(od.all_msgs, od.compressed_msgs, od.roi_msgs, od.compressed_roi_msgs)
        self.assertEqual(count, expected)

    def test_stores_image_for_different_modifiers_independently(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        od_nomod = _make_overlay("rect")
        od_ctrl = _make_overlay("stripe")
        mock.send_smallest_overlay(kc, Modifier.NO_MOD, {kc: od_nomod})
        mock.send_smallest_overlay(kc, Modifier.CTRL, {kc: od_ctrl})
        self.assertEqual(mock.get_display_bitmap(kc, Modifier.NO_MOD), od_nomod.all_bytes)
        self.assertEqual(mock.get_display_bitmap(kc, Modifier.CTRL), od_ctrl.all_bytes)

    def test_get_display_image_matches_original_numpy_array(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        original = _make_image("rect")
        od = OverlayData(DeviceSettings(), original)
        mock.send_smallest_overlay(kc, Modifier.NO_MOD, {kc: od})
        result = mock.get_display_image(kc, Modifier.NO_MOD)
        self.assertIsNotNone(result)
        np.testing.assert_array_equal(result, original)


class TestPolyKybdMockResets(unittest.TestCase):

    def test_reset_overlay_usage_hides_images(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        od = _make_overlay()
        mock.send_smallest_overlay(kc, Modifier.NO_MOD, {kc: od})
        mock.reset_overlay_usage()
        self.assertIsNone(mock.get_display_bitmap(kc, Modifier.NO_MOD))

    def test_reset_overlays_and_usage_clears_everything(self):
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        od = _make_overlay()
        mock.send_smallest_overlay(kc, Modifier.NO_MOD, {kc: od})
        mock.reset_overlays_and_usage()
        self.assertIsNone(mock.get_display_bitmap(kc, Modifier.NO_MOD))
        self.assertEqual(mock._sim._store, {})

    def test_reset_overlay_mapping_restores_identity(self):
        mock = _make_mock()
        kc_a = KeyCode.KC_A.value
        kc_b = KeyCode.KC_B.value
        mod = Modifier.NO_MOD
        od_b = _make_overlay("stripe")
        slot_a = _slot(kc_a, mod)
        slot_b = _slot(kc_b, mod)
        mock._sim.store_image(slot_b, od_b.all_bytes)
        mock._sim.set_mapping(slot_a, slot_b)   # KC_A → KC_B image
        self.assertEqual(mock.get_display_bitmap(kc_a, mod), od_b.all_bytes)
        mock.reset_overlay_mapping()
        self.assertIsNone(mock.get_display_bitmap(kc_a, mod))  # KC_A has no stored image


class TestPolyKybdMockSendOverlayMapping(unittest.TestCase):

    def test_send_overlay_mapping_marks_display_positions_used(self):
        mock = _make_mock()
        kc_disp = KeyCode.KC_Z.value
        mod_disp = Modifier.ALT
        display_pos = _slot(kc_disp, mod_disp)

        kc_pool = KeyCode.KC_A.value
        pool_slot = _slot(kc_pool, Modifier.NO_MOD)

        od = _make_overlay()
        mock._sim.store_image(pool_slot, od.all_bytes)
        mock.reset_overlay_usage()
        mock.send_overlay_mapping({display_pos: pool_slot})
        self.assertEqual(mock.get_display_bitmap(kc_disp, mod_disp), od.all_bytes)

    def test_send_overlay_mapping_increments_counter(self):
        mock = _make_mock()
        self.assertEqual(mock.hid_mapping_sends, 0)
        mock.send_overlay_mapping({0: 0})
        self.assertEqual(mock.hid_mapping_sends, 1)
        mock.send_overlay_mapping({1: 1})
        self.assertEqual(mock.hid_mapping_sends, 2)

    def test_send_overlay_mapping_stores_last_mapping(self):
        mock = _make_mock()
        mapping = {5: 3, 10: 7}
        mock.send_overlay_mapping(mapping)
        self.assertEqual(mock.last_mapping, mapping)


class TestPolyKybdMockMRUFlow(unittest.TestCase):

    def _make_mru_cache(self, capacity: int = 20):
        from polyhost.device.overlay_cache import OverlayMRUCache
        return OverlayMRUCache(capacity)

    def test_send_smallest_overlay_returns_positive_message_count(self):
        # hid_image_sends is only incremented inside send_overlays_mru, not by
        # send_smallest_overlay directly (which is also used in normal mode).
        mock = _make_mock()
        cache = self._make_mru_cache()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        od = _make_overlay()
        pool_slot, _ = cache.get_or_allocate(("test.png", mod.value, kc))
        pool_kc, pool_mod = cache.pool_slot_to_firmware_address(pool_slot)
        count = mock.send_smallest_overlay(pool_kc, pool_mod, {pool_kc: od})
        self.assertGreater(count, 0)

    def test_mru_normal_mode_stores_at_display_address(self):
        mock = _make_mock()
        kc = KeyCode.KC_B.value
        mod = Modifier.SHIFT
        od = _make_overlay("dot")
        mock.send_smallest_overlay(kc, mod, {kc: od})
        # In normal mode: pool_slot == display_pos (identity)
        self.assertEqual(mock.get_display_bitmap(kc, mod), od.all_bytes)

    def test_full_mru_flow_display_shows_correct_image(self):
        """
        Simulate one full MRU app-switch cycle:
          - two keycodes, one modifier each
          - images stored at pool slots (pool_slot_to_firmware_address addresses)
          - after reset_usage + mapping, display shows correct images
        """
        mock = _make_mock()

        display_kc_a = KeyCode.KC_A.value
        display_kc_b = KeyCode.KC_B.value
        mod = Modifier.NO_MOD

        od_a = _make_overlay("rect")
        od_b = _make_overlay("stripe")

        # Pool slots 0 and 1 (first two pool addresses)
        from polyhost.device.overlay_cache import OverlayMRUCache
        pool_kc_0, pool_mod_0 = OverlayMRUCache(20).pool_slot_to_firmware_address(0)
        pool_kc_1, pool_mod_1 = OverlayMRUCache(20).pool_slot_to_firmware_address(1)

        mock.send_smallest_overlay(pool_kc_0, pool_mod_0, {pool_kc_0: od_a})
        mock.send_smallest_overlay(pool_kc_1, pool_mod_1, {pool_kc_1: od_b})

        display_pos_a = display_flat_idx(display_kc_a, mod)
        display_pos_b = display_flat_idx(display_kc_b, mod)
        pool_slot_0 = display_flat_idx(pool_kc_0, pool_mod_0)
        pool_slot_1 = display_flat_idx(pool_kc_1, pool_mod_1)

        mock.reset_overlay_usage()
        mock.send_overlay_mapping({display_pos_a: pool_slot_0, display_pos_b: pool_slot_1})

        np.testing.assert_array_equal(
            mock.get_display_image(display_kc_a, mod),
            _make_image("rect"))
        np.testing.assert_array_equal(
            mock.get_display_image(display_kc_b, mod),
            _make_image("stripe"))

    def test_unmapped_position_returns_none_in_mru_mode(self):
        mock = _make_mock()
        kc_a = KeyCode.KC_A.value
        kc_b = KeyCode.KC_B.value
        mod = Modifier.NO_MOD
        od = _make_overlay()

        mock.send_smallest_overlay(kc_a, mod, {kc_a: od})
        mock.reset_overlay_usage()
        # Only map KC_A; KC_B is not mapped
        display_pos_a = display_flat_idx(kc_a, mod)
        mock.send_overlay_mapping({display_pos_a: display_flat_idx(kc_a, mod)})

        self.assertIsNotNone(mock.get_display_bitmap(kc_a, mod))
        self.assertIsNone(mock.get_display_bitmap(kc_b, mod))


class TestSaveAsPng(unittest.TestCase):

    def test_save_png_returns_false_when_no_image(self):
        import tempfile, os
        mock = _make_mock()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.png")
            result = mock.save_overlay_as_png(KeyCode.KC_A.value, Modifier.NO_MOD, path)
        self.assertFalse(result)

    def test_save_png_produces_valid_file(self):
        import tempfile, os
        mock = _make_mock()
        kc = KeyCode.KC_A.value
        mod = Modifier.NO_MOD
        od = _make_overlay("rect")
        mock.send_smallest_overlay(kc, mod, {kc: od})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.png")
            result = mock.save_overlay_as_png(kc, mod, path)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(path))
            with open(path, "rb") as f:
                sig = f.read(8)
            # PNG magic bytes
            self.assertEqual(sig, b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
