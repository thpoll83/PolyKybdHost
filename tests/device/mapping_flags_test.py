"""Protocol v21: prepare and enable ride on cmd 33 as flag bits.

`send_overlays_mru` against a fake keyboard. On v21 a warm switch must be its
mapping reports alone, with the reset flag on the first and the show flag on the
last; a cold switch must still send the prepare step before its first image,
and nothing may carry a flag below v21.
"""
import unittest

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.command_ids import Cmd
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import (MAPPING_FLAG_RESET, MAPPING_FLAG_SHOW,
                                       MAPPING_FLAGS_MIN_PROTOCOL, PolyKybd,
                                       protocol_supports)
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings

DS = DeviceSettings()
KEYS = [KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value]
FLAGS_ON = Cmd.OVERLAY_FLAGS_ON.value
MAPPING_W = Cmd.SEND_OVERLAY_MAPPING_W.value
IMAGE_CMDS = {Cmd.SEND_PRC_OVERLAY.value, Cmd.FILL_POOL_FROM_ICON.value, 10, 16, 17, 18, 19}


def _masks(kind="upload"):
    """Three distinct images that take one send path each: a sparse grid too big
    for a PRC record ("upload"), a small box that fits one ("prc"), or exact
    icon-library glyphs ("fill")."""
    if kind == "fill":
        _, index = PolyKybd._shipped_icon_library()
        return [np.unpackbits(np.frombuffer(f, dtype=np.uint8)).reshape(40, 72).astype(bool)
                for f in sorted(index, key=index.get)[:3]]
    out = []
    for i in range(3):
        m = np.zeros((40, 72), dtype=bool)
        if kind == "prc":
            m[10:16 + i, 45:51 + i] = True
        else:
            m[5 + i:25 + i:3, 38:66:2 + i] = True
        out.append(m)
    return out


def _keeb(protocol_21=True):
    keeb = PolyKybd(DeviceSettings(), StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True)
    keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: protocol_21 or f != "mapping_flags"
    version, _ = PolyKybd._shipped_icon_library()
    keeb.fontpack_bundle_versions = {8: version}
    return keeb, dev


def _send(keeb, cache, kind="upload"):
    conv = syn.SyntheticConverter({Modifier.NO_MOD: {
        kc: OverlayData(DS, m) for kc, m in zip(KEYS, _masks(kind))}})
    return keeb.send_overlays_mru(["syn"], cache, synthetic={"syn": conv})


def _reports(dev):
    return [bytes(p) for p in dev.payloads() if p and p[0] == 0x50]


class MappingFlagsTest(unittest.TestCase):

    def test_the_gate_is_protocol_21(self):
        self.assertEqual(MAPPING_FLAGS_MIN_PROTOCOL, 21)
        self.assertTrue(protocol_supports(21, "mapping_flags"))
        self.assertFalse(protocol_supports(20, "mapping_flags"))

    def test_a_WARM_v21_switch_is_its_mapping_reports_alone(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        dev.writes.clear()
        self.assertTrue(_send(keeb, cache))            # every image is a pool hit now
        reports = _reports(dev)
        self.assertEqual({r[1] for r in reports}, {MAPPING_W}, reports)
        self.assertTrue(reports[0][2] & MAPPING_FLAG_RESET, "reset on the first mapping report")
        self.assertTrue(reports[-1][2] & MAPPING_FLAG_SHOW, "show on the last mapping report")

    def test_a_COLD_v21_switch_prepares_before_its_first_image(self):
        for kind, cmd in (("upload", None), ("prc", Cmd.SEND_PRC_OVERLAY.value),
                          ("fill", Cmd.FILL_POOL_FROM_ICON.value)):
            with self.subTest(kind=kind):
                self._cold(kind, cmd)

    def _cold(self, kind, expect_cmd):
        keeb, dev = _keeb()
        self.assertTrue(_send(keeb, OverlayMRUCache(600), kind))
        reports = _reports(dev)
        first_image = next(i for i, r in enumerate(reports) if r[1] in IMAGE_CMDS)
        if expect_cmd is not None:
            self.assertEqual(reports[first_image][1], expect_cmd, "the path under test")
        prepares = [i for i, r in enumerate(reports) if r[1] == FLAGS_ON]
        self.assertEqual(len(prepares), 1, "one prepare, and no separate enable")
        self.assertLess(prepares[0], first_image)
        maps = [r for r in reports if r[1] == MAPPING_W]
        self.assertFalse(maps[0][2] & MAPPING_FLAG_RESET, "already prepared: no second reset")
        self.assertTrue(maps[-1][2] & MAPPING_FLAG_SHOW)
        self.assertEqual(reports[-1][1], MAPPING_W, "the flagged mapping is the last report")

    def test_below_v21_the_sequence_is_unchanged(self):
        keeb, dev = _keeb(protocol_21=False)
        cache = OverlayMRUCache(600)
        for _ in range(2):                             # cold, then warm
            dev.writes.clear()
            self.assertTrue(_send(keeb, cache))
            reports = _reports(dev)
            self.assertEqual(reports[0][1], FLAGS_ON)
            self.assertEqual(reports[-1][1], FLAGS_ON)
            for r in reports:
                if r[1] == MAPPING_W:
                    self.assertFalse(r[2] & (MAPPING_FLAG_RESET | MAPPING_FLAG_SHOW), r)

    def test_flags_are_refused_below_v21_and_without_pairs(self):
        keeb, dev = _keeb(protocol_21=False)
        ok, _ = keeb.send_overlay_mapping({0: 1}, show=True)
        self.assertFalse(ok)
        keeb, dev = _keeb()
        ok, _ = keeb.send_overlay_mapping({}, reset=True)
        self.assertFalse(ok)
        self.assertEqual(_reports(dev), [])


if __name__ == "__main__":
    unittest.main()
