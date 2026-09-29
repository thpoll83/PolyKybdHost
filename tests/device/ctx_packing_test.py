"""Tests for polyhost/device/ctx_packing.py: filling cmd 41 reports."""
import unittest

import numpy as np

from polyhost.device.ctx_packing import CtxReportPacker, ctx_record
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.util import ctx_codec

CAP = 62


def _overlay(y0, y1, x0, x1):
    img = np.zeros((40, 72), dtype=bool)
    img[y0:y1, x0:x1] = True
    return OverlayData(DeviceSettings(), img)


def _rec(n):
    return bytes([4]) + bytes(5) + bytes([1] * (n - 6))


class RecordForOverlayTest(unittest.TestCase):
    def test_record_carries_the_roi_box_and_decodes_to_the_image(self):
        ov = _overlay(5, 12, 20, 31)
        rec = ctx_record(ov, 0x07, 3, CAP)
        (kc, mod, top, left, h, w, payload), = ctx_codec.parse_records(rec)
        self.assertEqual((kc, mod, top, left, h, w), (0x07, 3, 5, 20, 7, 11))
        self.assertTrue(ctx_codec.decode(payload, h, w).all())

    def test_too_big_for_the_report_is_none(self):
        rng = np.random.default_rng(1)
        ov = OverlayData(DeviceSettings(), rng.random((40, 72)) < 0.5)
        self.assertIsNone(ctx_record(ov, 4, 0, CAP))

    def test_capacity_is_the_limit(self):
        ov = _overlay(0, 10, 0, 10)
        size = len(ctx_record(ov, 4, 0, CAP))
        self.assertIsNotNone(ctx_record(ov, 4, 0, size))
        self.assertIsNone(ctx_record(ov, 4, 0, size - 1))


class PackerTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.ok = True

    def _send(self, payload):
        self.sent.append(payload)
        return self.ok

    def test_records_share_a_report_until_the_next_does_not_fit(self):
        p = CtxReportPacker(self._send, CAP)
        self.assertEqual(p.add(_rec(30), 0), 0)
        self.assertEqual(p.add(_rec(32), 1), 0)      # 62: exactly full
        self.assertEqual(p.add(_rec(10), 2), 1)      # 72 > 62: the first report goes
        self.assertEqual(self.sent, [_rec(30) + _rec(32)])
        self.assertEqual(p.flush(), 1)
        self.assertEqual(p.flush(), 0)
        self.assertEqual(self.sent[1], _rec(10))
        self.assertEqual((p.reports, p.images), (2, 3))

    def test_holds_tracks_only_the_queue(self):
        p = CtxReportPacker(self._send, CAP)
        p.add(_rec(10), 7)
        self.assertTrue(p.holds(7))
        p.flush()
        self.assertFalse(p.holds(7))

    def test_failed_send_discards_and_forgets_the_queued_slots_and_their_aliases(self):
        cache = OverlayMRUCache(20)
        s0, _ = cache.get_or_allocate(("t", 0, 4), "t", b"a")
        s1, _ = cache.get_or_allocate(("t", 0, 5), "t", b"b")
        alias, hit = cache.get_or_allocate(("u", 0, 6), "u", b"a")   # dedups onto s0
        self.assertTrue(hit)
        self.assertEqual(alias, s0)
        p = CtxReportPacker(self._send, CAP, cache)
        p.add(_rec(30), s0)
        p.add(_rec(30), s1)
        self.ok = False
        self.assertEqual(p.add(_rec(30), 9), -1)
        self.assertFalse(p.pending)
        # Probe by key only: passing the bytes would re-populate the dedup table.
        for key in (("t", 0, 4), ("t", 0, 5), ("u", 0, 6)):
            self.assertFalse(cache.get_or_allocate(key)[1], key)

    def test_discard_reclaims_the_slot_indices(self):
        cache = OverlayMRUCache(20)
        slots = [cache.get_or_allocate(("t", 0, k), "t", bytes([k]))[0] for k in (4, 5, 6)]
        p = CtxReportPacker(self._send, CAP, cache)
        for s in slots:
            p.add(_rec(8), s)
        p.discard()
        self.assertEqual(cache.get_or_allocate(("t", 0, 9), "t", b"z")[0], 0)
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
