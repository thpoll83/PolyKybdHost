"""One program switch that needs more distinct images than the overlay pool holds.

Measured over the emulated keyboard before this guard (2026-10-09): 650 distinct
images in one switch showed 600 correct keys and 50 WRONG ones, and the send
reported success. Each image past the pool evicted a slot an earlier key of the
same switch still pointed at. The pool size is a hard limit per switch: the
images past it leave their keys blank, never on another key's picture.
"""
import threading
import unittest
import unittest.mock as mock

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd_mock import PolyKybdMock


def _template(overlays):
    """A stand-in for `ImageConverter`, a real file-backed source."""
    converter = mock.MagicMock()
    converter.open.return_value = True
    converter.extract_overlays.side_effect = lambda mod: dict(overlays.get(mod, {})) or None
    del converter.modifier_invariant
    return converter


def _image(i: int) -> np.ndarray:
    """A distinct picture per index: its bits as blocks, never blank."""
    img = np.zeros((40, 72), dtype=bool)
    for b in range(12):
        if (i >> b) & 1:
            r, c = divmod(b, 6)
            img[2 + r * 10: 9 + r * 10, 2 + c * 11: 10 + c * 11] = True
    img[30:38, 2:70] = True
    return img


class CacheRefusesToEvictItsOwnBatchTest(unittest.TestCase):

    def test_a_full_batch_REFUSES_instead_of_evicting_itself(self):
        cache = OverlayMRUCache(3)
        with cache.batch():
            slots = [cache.get_or_allocate(("f", 0, k), "f", bytes([k]))[0] for k in range(3)]
            self.assertEqual(cache.get_or_allocate(("f", 0, 9), "f", bytes([9])), (None, False))
        self.assertEqual(sorted(slots), [0, 1, 2])
        self.assertEqual(cache.used_slots(), 3)

    def test_a_refusal_changes_nothing_and_hits_still_work(self):
        cache = OverlayMRUCache(2)
        with cache.batch():
            a, _ = cache.get_or_allocate(("f", 0, 1), "f", b"a")
            cache.get_or_allocate(("f", 0, 2), "f", b"b")
            version = cache.version
            self.assertIsNone(cache.get_or_allocate(("f", 0, 3), "f", b"c")[0])
            self.assertEqual(cache.version, version)
            self.assertEqual(cache.get_or_allocate(("g", 0, 7), "g", b"a"), (a, True))

    def test_the_NEXT_switch_still_evicts_the_older_one(self):
        cache = OverlayMRUCache(2)
        with cache.batch():
            cache.get_or_allocate(("f", 0, 1), "f", b"a")
            cache.get_or_allocate(("f", 0, 2), "f", b"b")
        with cache.batch():
            slot, hit = cache.get_or_allocate(("g", 0, 1), "g", b"c")
        self.assertIsNotNone(slot)
        self.assertFalse(hit)


class SwitchPastThePoolTest(unittest.TestCase):

    def send(self, n: int, capacity: int):
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        ds = DeviceSettings()
        keys = [k.value for k in KeyCode if 0x04 <= k.value <= 0x43]
        positions = [(m, k) for m in Modifier for k in keys][:n]
        by_mod, want = {}, {}
        for i, (m, k) in enumerate(positions):
            ov = OverlayData(ds, _image(i))
            by_mod.setdefault(m, {})[k] = ov
            want[(m, k)] = bytes(ov.all_bytes)
        with mock.patch("time.sleep", lambda s: None):
            ok = kb.send_overlays_mru(["@many"], OverlayMRUCache(capacity),
                                      threading.Event(),
                                      synthetic={"@many": syn.SyntheticConverter(by_mod)})
        right = wrong = blank = 0
        for (m, k), b in want.items():
            got = kb.get_display_bitmap(k, m)
            if got is None:
                blank += 1
            elif bytes(got) == b:
                right += 1
            else:
                wrong += 1
        return ok, right, wrong, blank

    def test_past_the_pool_keys_go_BLANK_never_WRONG(self):
        ok, right, wrong, blank = self.send(25, capacity=20)
        self.assertTrue(ok)
        self.assertEqual((right, wrong, blank), (20, 0, 5))

    def test_exactly_the_pool_is_all_correct(self):
        self.assertEqual(self.send(20, capacity=20)[1:], (20, 0, 0))

    def test_the_real_pool_size(self):
        """600 is OVERLAY_MAPPING_CAPACITY, the firmware's pool."""
        ok, right, wrong, blank = self.send(650, DeviceSettings().OVERLAY_MAPPING_CAPACITY)
        self.assertTrue(ok)
        self.assertEqual((right, wrong, blank), (600, 0, 50))

    def test_a_refused_LATER_source_blanks_the_key_an_earlier_one_drew(self):
        """Last source wins a key. When the pool refuses the later one's image,
        the earlier one's picture must not stay there in its place (review,
        Greptile): that would show the browser's icon under a website's key."""
        ds = DeviceSettings()
        a_key, b_key, c_key = KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value
        first = _template({Modifier.NO_MOD: {a_key: OverlayData(ds, _image(1)),
                                            b_key: OverlayData(ds, _image(2))}})
        later = _template({Modifier.NO_MOD: {c_key: OverlayData(ds, _image(3)),
                                            a_key: OverlayData(ds, _image(4))}})
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        with mock.patch("time.sleep", lambda s: None), \
                mock.patch("polyhost.device.poly_kybd.ImageConverter") as converter:
            converter.side_effect = [first, later]
            self.assertTrue(kb.send_overlays_mru(["first.png", "later.png"],
                                                 OverlayMRUCache(3), threading.Event()))
        self.assertIsNone(kb.get_display_bitmap(a_key, Modifier.NO_MOD))
        self.assertIsNotNone(kb.get_display_bitmap(b_key, Modifier.NO_MOD))
        self.assertIsNotNone(kb.get_display_bitmap(c_key, Modifier.NO_MOD))


if __name__ == "__main__":
    unittest.main()
