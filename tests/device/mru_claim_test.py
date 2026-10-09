"""A switch claims the images the pool already holds before it allocates any.

Images arrive one at a time, so without the claim a new image could evict an old
slot that a LATER key of the same switch would have hit, and that key uploaded
its image again. Measured with the pool full, a switch reusing 300 images and
adding 300 sent 491 uploads in mixed order and 600 with the new ones first,
instead of 300 (2026-10-09). See `OverlayMRUCache.claim`.
"""
import random
import threading
import unittest
import unittest.mock as mock

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd_mock import PolyKybdMock
from tests.device.pool_overflow_test import _image


class ClaimTest(unittest.TestCase):

    def test_a_claim_allocates_nothing(self):
        cache = OverlayMRUCache(4)
        with cache.batch():
            self.assertFalse(cache.claim(("f", 0, 1), b"a"))
        self.assertEqual(cache.used_slots(), 0)

    def test_a_claim_hits_by_key_and_by_bytes(self):
        cache = OverlayMRUCache(4)
        with cache.batch():
            cache.get_or_allocate(("f", 0, 1), "f", b"a")
        with cache.batch():
            self.assertTrue(cache.claim(("f", 0, 1)))
            self.assertTrue(cache.claim(("g", 0, 9), b"a"))

    def test_a_claimed_slot_is_never_evicted_by_its_own_switch(self):
        """The point of claiming: with the pool full of the last switch, the new
        image takes the slot this switch did NOT claim."""
        cache = OverlayMRUCache(2)
        with cache.batch():
            a, _ = cache.get_or_allocate(("f", 0, 1), "f", b"a")
            b, _ = cache.get_or_allocate(("f", 0, 2), "f", b"b")
        with cache.batch():
            cache.claim(("g", 0, 2), b"b")
            slot, hit = cache.get_or_allocate(("g", 0, 1), "g", b"new")
            self.assertEqual((slot, hit), (a, False))
            self.assertEqual(cache.get_or_allocate(("g", 0, 2), "g", b"b"), (b, True))


class SwitchReusingAFullPoolTest(unittest.TestCase):
    """End to end over the emulated keyboard: the pool holds 20 images of app
    A, and app B needs 10 of them plus 10 new ones."""

    CAPACITY = 20

    def switch(self, kb, cache, name, images, keys):
        ds = DeviceSettings()
        by_mod = {Modifier.NO_MOD: {k: OverlayData(ds, _image(i)) for k, i in zip(keys, images)}}
        misses = []
        real = cache.get_or_allocate

        def counting(content_key, full_path="", bytes_data=None):
            slot, hit = real(content_key, full_path, bytes_data)
            if slot is not None and not hit:
                misses.append(content_key)
            return slot, hit

        cache.get_or_allocate = counting
        try:
            with mock.patch("time.sleep", lambda s: None):
                ok = kb.send_overlays_mru([name], cache, threading.Event(),
                                          synthetic={name: syn.SyntheticConverter(by_mod)})
        finally:
            del cache.get_or_allocate
        self.assertTrue(ok)
        for k, i in zip(keys, images):
            self.assertEqual(bytes(kb.get_display_bitmap(k, Modifier.NO_MOD)),
                             bytes(OverlayData(ds, _image(i)).all_bytes))
        return len(misses)

    def run_order(self, order):
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        cache = OverlayMRUCache(self.CAPACITY)
        keys = [k.value for k in KeyCode if 0x04 <= k.value <= 0x43][:self.CAPACITY]
        self.assertEqual(self.switch(kb, cache, "@a", list(range(20)), keys), 20)
        reused, new = list(range(10)), list(range(100, 110))
        if order == "reused_first":
            images = reused + new
        elif order == "new_first":
            images = new + reused
        else:
            images = reused + new
            random.Random(7).shuffle(images)
        return self.switch(kb, cache, "@b", images, keys)

    def test_each_new_image_is_uploaded_ONCE_whatever_the_order(self):
        for order in ("reused_first", "new_first", "shuffled"):
            with self.subTest(order=order):
                self.assertEqual(self.run_order(order), 10)


if __name__ == "__main__":
    unittest.main()
