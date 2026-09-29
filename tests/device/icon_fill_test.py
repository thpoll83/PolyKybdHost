"""Icon library fills (cmd 42, protocol v20) through the real send path.

`send_overlays_mru` runs against a fake HID device. An image whose exact pixels
are a library icon must go out as a (pool slot, icon id) pair and nothing else;
anything the keyboard refuses must still reach it as an upload; and a keyboard
that cannot fill -- too old, or holding a different icon bundle -- must see
exactly the uploads it saw before.
"""
import unittest

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.bit_packing import pairs_per_report
from polyhost.device.command_ids import Cmd
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import PolyKybd
from polyhost.services import icon_library
from tests.device.fake_hid import FakeHidDevice, make_hid_helper, pad
from tests.device.poly_kybd_cancel_test import StubPolySettings

DS = DeviceSettings()
KEYS = [KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value]


def _library():
    version, index = PolyKybd._shipped_icon_library()
    frames = sorted(index, key=index.get)[:3]
    return version, [(f, index[f]) for f in frames]


def _mask(frame: bytes):
    return np.unpackbits(np.frombuffer(frame, dtype=np.uint8)).reshape(40, 72).astype(bool)


def _not_an_icon():
    m = np.zeros((40, 72), dtype=bool)
    m[3:30:2, 40:70:3] = True                 # a sparse grid no template draws
    return m


def _keeb(device_version, supports=True):
    keeb = PolyKybd(DeviceSettings(), StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True)
    keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: supports if f == "overlay_icons" else True
    keeb.fontpack_bundle_versions = {icon_library.BUNDLE_ID: device_version}
    return keeb, dev


def _send(keeb, masks):
    conv = syn.SyntheticConverter({Modifier.NO_MOD: {
        kc: OverlayData(DS, m) for kc, m in zip(KEYS, masks)}})
    ok = keeb.send_overlays_mru(["syn"], OverlayMRUCache(600), synthetic={"syn": conv})
    return ok


def _cmds(dev):
    return [p[1] for p in dev.payloads() if p and p[0] == 0x50]


IMAGE_CMDS = {Cmd.SEND_PRC_OVERLAY.value, 10, 16, 17, 18, 19}


class IconFillTest(unittest.TestCase):

    def setUp(self):
        self.version, self.icons = _library()
        if len(self.icons) < 3:
            self.skipTest("no icon library shipped")
        self.masks = [_mask(f) for f, _ in self.icons]

    def test_library_icons_go_out_as_ONE_fill_report_and_no_upload(self):
        keeb, dev = _keeb(self.version)
        self.assertTrue(_send(keeb, self.masks))
        cmds = _cmds(dev)
        self.assertEqual(cmds.count(Cmd.FILL_POOL_FROM_ICON.value), 1)
        self.assertFalse(IMAGE_CMDS & set(cmds), cmds)
        self.assertEqual(keeb.stat_chosen["fill"], 3)

    def test_the_stats_count_fill_reports_and_their_alternatives(self):
        """Field log, 2026-09-29: a cold Word switch of 24 fills + 5 PRC images
        logged `image reports sent 8` and `if plain: 0` -- only the older
        encodings were counted."""
        keeb, dev = _keeb(self.version)
        _send(keeb, self.masks)
        self.assertEqual(keeb.stat_best, 1, "one fill report")
        self.assertGreater(keeb.stat_plain, keeb.stat_best)
        self.assertGreater(keeb.stat_croi, 0)

    def test_the_pairs_name_the_icon_ids(self):
        keeb, dev = _keeb(self.version)
        _send(keeb, self.masks)
        report = next(p for p in dev.payloads() if p[1] == Cmd.FILL_POOL_FROM_ICON.value)
        width = report[2]
        bits = int.from_bytes(bytes(report[3:3 + 61]), "little")
        n = pairs_per_report(61, width)
        pairs = {((bits >> (2 * i * width)) & ((1 << width) - 1),
                  (bits >> ((2 * i + 1) * width)) & ((1 << width) - 1)) for i in range(n)}
        self.assertEqual({icon for _, icon in pairs}, {i for _, i in self.icons})

    def test_an_image_that_is_not_an_icon_is_still_uploaded(self):
        keeb, dev = _keeb(self.version)
        _send(keeb, self.masks[:2] + [_not_an_icon()])
        cmds = _cmds(dev)
        self.assertEqual(cmds.count(Cmd.FILL_POOL_FROM_ICON.value), 1)
        self.assertTrue(IMAGE_CMDS & set(cmds))
        self.assertEqual(keeb.stat_chosen["fill"], 2)

    def test_a_REFUSED_pair_and_everything_after_it_are_uploaded(self):
        keeb, dev = _keeb(self.version)
        read = dev.read

        def refuse_at_1(size, timeout=0):
            last = dev.last_payload()
            if last[:2] == bytes([0x50, Cmd.FILL_POOL_FROM_ICON.value]):
                return pad(b"P" + bytes([Cmd.FILL_POOL_FROM_ICON.value]) + b"!" + bytes([1]))
            return read(size, timeout)
        dev.read = refuse_at_1
        self.assertTrue(_send(keeb, self.masks))
        self.assertEqual(keeb.stat_chosen["fill"], 1)
        self.assertTrue(IMAGE_CMDS & set(_cmds(dev)), "the refused two must be uploaded")

    def test_a_FAILED_fallback_upload_forgets_the_slots_it_never_sent(self):
        """CodeRabbit on #291: a refused pair whose fallback upload then fails
        left its slot in the MRU cache, a stale hit the next switch never
        re-sends."""
        keeb, dev = _keeb(self.version)
        read, write = dev.read, dev.write

        def refuse_at_1(size, timeout=0):
            if dev.last_payload()[:2] == bytes([0x50, Cmd.FILL_POOL_FROM_ICON.value]):
                return pad(b"P" + bytes([Cmd.FILL_POOL_FROM_ICON.value]) + b"!" + bytes([1]))
            return read(size, timeout)

        def image_writes_fail(report):
            if report[1] == 0x50 and report[2] in IMAGE_CMDS:
                raise OSError("unplugged mid-send")
            return write(report)
        dev.read, dev.write = refuse_at_1, image_writes_fail
        cache = OverlayMRUCache(600)
        conv = syn.SyntheticConverter({Modifier.NO_MOD: {
            kc: OverlayData(DS, m) for kc, m in zip(KEYS, self.masks)}})
        self.assertFalse(keeb.send_overlays_mru(["syn"], cache, synthetic={"syn": conv}))
        self.assertEqual(len(cache.get_occupied_slots()), 1,
                         "only the one applied fill may stay cached")

    def test_NO_REPLY_uploads_the_whole_report(self):
        """A frozen keyboard (DOOM) drops cmd 42 without answering."""
        keeb, dev = _keeb(self.version)
        read = dev.read

        def silent(size, timeout=0):
            if dev.last_payload()[:2] == bytes([0x50, Cmd.FILL_POOL_FROM_ICON.value]):
                return b""
            return read(size, timeout)
        dev.read = silent
        self.assertTrue(_send(keeb, self.masks))
        self.assertEqual(keeb.stat_chosen["fill"], 0)

    def test_a_DIFFERENT_icon_bundle_on_the_keyboard_means_no_fills(self):
        """An id names a glyph only within one bundle version."""
        keeb, dev = _keeb(self.version + 1)
        _send(keeb, self.masks)
        self.assertNotIn(Cmd.FILL_POOL_FROM_ICON.value, _cmds(dev))

    def test_firmware_before_protocol_20_gets_only_uploads(self):
        keeb, dev = _keeb(self.version, supports=False)
        _send(keeb, self.masks)
        cmds = _cmds(dev)
        self.assertNotIn(Cmd.FILL_POOL_FROM_ICON.value, cmds)
        self.assertTrue(IMAGE_CMDS & set(cmds))


class StaleBundleSlotTest(unittest.TestCase):
    """⚠️ A keyboard before protocol 20 has no slot 8: flashing icons.plyi there is
    refused, and the autocheck would retry it on every connect."""

    def test_a_slot_the_device_does_not_list_is_never_flashed(self):
        from polyhost.device.hid_fontpack import decide_stale_bundles
        shipped = [{"index": 0, "content_version": 3},
                   {"index": 8, "content_version": 1, "kind": "icons"}]
        v19 = {i: 3 for i in range(8)}
        self.assertEqual(decide_stale_bundles(v19, shipped), [])
        v20 = {**v19, 8: 0}
        self.assertEqual([b["index"] for b in decide_stale_bundles(v20, shipped)], [8])

    def test_pre_v6_firmware_still_gets_fonts_but_never_icons(self):
        from polyhost.device.hid_fontpack import decide_stale_bundles
        shipped = [{"index": 0, "content_version": 3},
                   {"index": 8, "content_version": 1, "kind": "icons"}]
        self.assertEqual([b["index"] for b in decide_stale_bundles({}, shipped)], [0])


if __name__ == "__main__":
    unittest.main()
