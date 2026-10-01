"""Recovery paths, driven against the emulated keyboard (device/mock_firmware.py).

Each of these used to need a real keyboard misbehaving at the right moment: a
COMMIT ack lost on the split link, a half that did not confirm, the unsigned-
firmware prompt, a chunk resync, the keyboard going deaf after a big transfer.
The unmodified host code -- hid_fontpack, hid_fw_up, PolyCore's probe and
font-pack autocheck -- runs against `MockFirmware` with a `FaultPlan` saying
what goes wrong.
"""
import os
import struct
import tempfile
import threading
import unittest
import unittest.mock as mock

import numpy as np

from polyhost.core.poly_core import PolyCore
from polyhost.device import hid_fontpack, hid_fw_up
from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.mock_firmware import FaultPlan, MockFirmware, MockHidHelper
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.services.fontpack_bundle import load_bundle_manifest
from polyhost.settings import PolySettings


def _symbol_bundle():
    manifest = load_bundle_manifest()
    bundle = next(b for b in manifest["bundles"] if b["index"] == 0)
    with open(bundle["path"], "rb") as f:
        return bundle, f.read()


def _hid(protocol=21, **faults):
    fw = MockFirmware(protocol, faults=FaultPlan(**faults))
    return fw, MockHidHelper(fw)


def _no_sleep():
    return mock.patch("time.sleep", lambda s: None)


class FontPackTransportTest(unittest.TestCase):

    def test_a_clean_flash_lands_the_bundle(self):
        bundle, data = _symbol_bundle()
        fw, hid = _hid()
        ok, msg, status = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0)
        self.assertTrue(ok, msg)
        self.assertEqual(status, hid_fontpack.COMMIT_OK)
        self.assertEqual(fw.bundle_data[0], data)
        self.assertEqual(fw.reported_bundle_versions()[0], bundle["content_version"])

    def test_a_split_link_L_is_retried_not_restreamed(self):
        bundle, _ = _symbol_bundle()
        fw, hid = _hid(fontpack_commit=["L", "."])
        with _no_sleep():
            ok, _, status = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0)
        self.assertTrue(ok)
        self.assertEqual(status, hid_fontpack.COMMIT_OK)
        self.assertEqual(fw.reports[hid_fontpack.CMD_FONTPACK_BEGIN], 1)    # one stream
        self.assertEqual(fw.reports[hid_fontpack.CMD_FONTPACK_COMMIT], 2)   # two COMMITs

    def test_a_rejected_commit_stores_nothing(self):
        bundle, _ = _symbol_bundle()
        fw, hid = _hid(fontpack_commit=["R"])
        ok, _, status = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0)
        self.assertFalse(ok)
        self.assertEqual(status, hid_fontpack.COMMIT_REJECTED)
        self.assertNotIn(0, fw.bundle_data)

    def test_a_chunk_resync_rewinds_and_still_lands_every_byte(self):
        bundle, data = _symbol_bundle()
        size = hid_fontpack.FONTPACK_CHUNK_SIZE
        fw, hid = _hid(chunk_resync={40 * size: 12 * size})
        with _no_sleep():
            ok, msg, _ = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.bundle_data[0], data)

    def test_the_erase_wait_is_polled_through(self):
        bundle, _ = _symbol_bundle()
        fw, hid = _hid(erase_polls=3)
        with _no_sleep():
            ok, msg, _ = hid_fontpack.flash_fontpack(hid, bundle["path"], bundle_id=0)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.reports[hid_fontpack.CMD_FONTPACK_BEGIN], 4)

    def test_a_slot_the_keyboard_lacks_is_refused_at_begin(self):
        # icons.plyi is slot 8, which a v19 keyboard does not have.
        manifest = load_bundle_manifest()
        icons = next(b for b in manifest["bundles"] if b["index"] == 8)
        fw, hid = _hid(protocol=19)
        ok, _, status = hid_fontpack.flash_fontpack(hid, icons["path"], bundle_id=8)
        self.assertFalse(ok)
        self.assertEqual(status, "begin")


class FontPackAutocheckTest(unittest.TestCase):
    """The core's half: a lost COMMIT ack must not leave the bundle forgotten."""

    def _core(self, faults):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                  "fontpack_auto_flash": True}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True),
                  mock.patch("time.sleep", lambda s: None)):
            p.start()
            self.addCleanup(p.stop)
        core = PolyCore(mock.MagicMock(), start_worker=False)
        # Only the symbol bundle is missing; the rest read as current.
        core.keeb.firmware.bundle_versions.pop(0, None)
        core.keeb.firmware.faults.fontpack_commit.extend(faults)
        return core

    def test_a_lost_ack_on_a_bundle_that_landed_is_reported_as_landed(self):
        core = self._core([None, None, None])           # three COMMITs, no reply
        core._fontpack_autocheck_job(threading.Event())
        bundle, _ = _symbol_bundle()
        self.assertEqual(core.keeb.fontpack_bundle_versions[0], bundle["content_version"])
        self.assertNotIn(0, core._fontpack_failed)       # verified, not forgotten

    def test_a_split_link_failure_is_remembered_for_a_retry(self):
        core = self._core(["L", "L", "L"])
        core._fontpack_autocheck_job(threading.Event())
        self.assertIn(0, core._fontpack_failed)
        # Next connect: the version reads current, the retry entry still flashes it.
        begins = core.keeb.firmware.reports[hid_fontpack.CMD_FONTPACK_BEGIN]
        core._fontpack_autocheck_job(threading.Event())
        self.assertEqual(core.keeb.firmware.reports[hid_fontpack.CMD_FONTPACK_BEGIN], begins + 1)
        self.assertNotIn(0, core._fontpack_failed)


def _firmware_image() -> bytes:
    from polyhost.device.hid_fw_up import _crc32_rp2040
    boot2 = bytes(252)
    header = boot2 + struct.pack("<I", _crc32_rp2040(boot2)) + struct.pack("<II", 0x20010000, 0x10000101)
    return header + "PolyKybd".encode("utf-16-le") + bytes(range(256)) * 4


class FirmwareUpdateTransportTest(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".bin")
        os.write(fd, _firmware_image())
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        p = mock.patch.object(hid_fw_up, "CONFIRM_POLL_INTERVAL_S", 0)
        p.start()
        self.addCleanup(p.stop)

    def _sign(self):
        with open(self.path + ".sig", "wb") as f:
            f.write(bytes(range(64)))
        self.addCleanup(os.remove, self.path + ".sig")

    def test_an_unsigned_image_waits_for_the_keypress_and_is_accepted(self):
        fw, hid = _hid(fw_confirm_polls=3, fw_confirm="accept")
        with _no_sleep():
            ok, msg = hid_fw_up.flash_firmware(hid, self.path)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.reports[hid_fw_up.CMD_FW_UP_COMMIT], 4)   # 3x '?' then '.'
        self.assertTrue(fw.fw_staged_valid)

    def test_an_unsigned_image_the_user_rejects_is_reported_as_unsigned(self):
        fw, hid = _hid(fw_confirm="reject")
        with _no_sleep():
            ok, msg = hid_fw_up.flash_firmware(hid, self.path)
        self.assertFalse(ok)
        self.assertIn("not signed", msg)
        self.assertFalse(fw.fw_staged_valid)

    def test_a_signature_that_fails_says_so_rather_than_offering_the_prompt(self):
        self._sign()
        fw, hid = _hid(fw_signature_valid=False)
        with _no_sleep():
            ok, msg = hid_fw_up.flash_firmware(hid, self.path)
        self.assertFalse(ok)
        self.assertIn("signature does not match", msg)

    def test_apply_reboots_onto_the_staged_image(self):
        self._sign()
        fw, hid = _hid()
        with _no_sleep():
            self.assertTrue(hid_fw_up.flash_firmware(hid, self.path)[0])
        fw.pop_fresh_boot()
        ok, msg = hid_fw_up.apply_staged_firmware(hid)
        self.assertTrue(ok, msg)
        self.assertEqual(fw.running_image, _firmware_image())
        self.assertTrue(fw.pop_fresh_boot())
        ok, info = hid_fw_up.get_fw_version(hid)
        self.assertTrue(ok)
        self.assertEqual(info["fw_size"], len(_firmware_image()))

    def test_apply_with_nothing_staged_is_a_plain_refusal(self):
        fw, hid = _hid()
        ok, msg = hid_fw_up.apply_staged_firmware(hid)
        self.assertFalse(ok)
        self.assertIn("not available", msg)


class DeafWindowTest(unittest.TestCase):
    """The keyboard stops answering after a big transfer; the probe's 3-strike
    debounce is what keeps that from flapping the connection."""

    def test_the_probe_rides_out_the_window_and_reconnects_after_it(self):
        now = [1000.0]
        real_get = PolySettings.get

        def get(settings, name):
            return {"dev_mock_primary": True, "dev_mock_protocol": 0}.get(
                name, real_get(settings, name)) if name.startswith("dev_mock") else real_get(settings, name)

        with mock.patch.object(PolySettings, "get", get), \
                mock.patch.object(PolySettings, "save", lambda *a, **k: True):
            core = PolyCore(mock.MagicMock(), start_worker=False)
        keeb = core.keeb
        keeb.firmware.clock = lambda: now[0]
        keeb.faults.deaf_after_images = (2, 5.0)
        core.apply_reconnect(core._reconnect_probe(threading.Event()))
        self.assertTrue(core.connected)

        ds = DeviceSettings()
        images = {}
        for i, kc in enumerate((KeyCode.KC_A, KeyCode.KC_B, KeyCode.KC_C)):
            image = np.zeros((40, 72), dtype=bool)
            image[5 + i:30, 3:60] = np.random.default_rng(i).random((25 - i, 57)) > 0.5
            images[kc.value] = OverlayData(ds, image)
        conv = syn.SyntheticConverter({Modifier.NO_MOD: images})
        self.assertTrue(keeb.send_overlays_mru(["@burst"], OverlayMRUCache(600),
                                               threading.Event(), synthetic={"@burst": conv}))
        self.assertTrue(keeb.firmware.deaf())

        published = [core._reconnect_probe(threading.Event()) for _ in range(3)]
        self.assertIsNone(published[0])
        self.assertIsNone(published[1])
        self.assertFalse(published[2]["connected_now"])    # the third strike publishes

        now[0] += 6.0                                       # the window passes
        snapshot = core._reconnect_probe(threading.Event())
        self.assertTrue(snapshot["connected_now"])


class ApiFaultTest(unittest.TestCase):

    def test_a_failed_enable_is_reported_and_the_next_one_works(self):
        kb = PolyKybdMock(DeviceSettings(), faults=FaultPlan(fail={"enable_overlays": 1}))
        ok, msg = kb.enable_overlays()
        self.assertFalse(ok)
        self.assertIn("injected", msg)
        self.assertFalse(kb.firmware.overlays_enabled)
        self.assertTrue(kb.enable_overlays()[0])
        self.assertTrue(kb.firmware.overlays_enabled)

    def test_a_raising_send_surfaces_as_the_generic_overlay_warning(self):
        kb = PolyKybdMock(DeviceSettings(), faults=FaultPlan(raises={"send_overlays_mru": 1}))
        with self.assertRaises(OSError):
            kb.send_overlays_mru([], OverlayMRUCache(600))

    def test_an_unplugged_device_fails_its_writes(self):
        fw, hid = _hid(disconnected=True)
        ok, msg = hid.send_and_read_validate(bytearray([0x50, 6]))
        self.assertFalse(ok)
        self.assertIn(b"disconnected", bytes(msg))


if __name__ == "__main__":
    unittest.main()
