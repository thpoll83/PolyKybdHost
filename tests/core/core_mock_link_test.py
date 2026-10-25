"""The fast link end to end: a real `PolyCore` with the mock as its keyboard
(`dev_mock_primary`), whose emulated firmware has the bulk pipe (mock_pipe.py).

tests/core/poly_core_transport_test.py pins the core's decisions against a
MagicMock keyboard. Here nothing below the core is replaced: the fresh connect
runs the real probe (PING plus the rate measurement), the snapshot and the
status carry what it measured, and a firmware update and a font-pack flash
stream their chunks over the emulated pipe -- or over HID when the pipe is
absent or `dev_force_hid_link` is set.
"""
import os
import struct
import tempfile
import threading
import unittest
import unittest.mock as mock

from polyhost.core.poly_core import PolyCore
from polyhost.device import bulk_pipe, hid_fontpack, hid_fw_up
from polyhost.device.mock_pipe import PIPE_MIN_PROTOCOL, RIG_RATE_MBPS
from polyhost.services.fontpack_bundle import load_bundle_manifest
from polyhost.settings import PolySettings


def _firmware_image(n=12000):
    boot2 = bytes(252)
    head = (boot2 + struct.pack("<I", hid_fw_up._crc32_rp2040(boot2))
            + struct.pack("<II", 0x20010000, 0x10000101) + "PolyKybd".encode("utf-16-le"))
    return head + bytes((i * 13 + 5) & 0xFF for i in range(n - len(head)))


def _hid_reports(fw, cmd):
    return sum(1 for w in fw.writes if len(w) > 1 and w[1] == cmd)


class MockLinkTest(unittest.TestCase):

    def _core(self, **overrides):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                  "dev_force_hid_link": False, **overrides}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        patches = [mock.patch.object(PolySettings, "get", get),
                   mock.patch.object(PolySettings, "save", lambda *a, **k: True),
                   mock.patch.object(PolyCore, "_compute_daylight_value", lambda self: 20),
                   mock.patch.object(hid_fw_up, "CONFIRM_POLL_INTERVAL_S", 0)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        core = PolyCore(mock.MagicMock(), start_worker=False)
        core.worker.start()
        self.addCleanup(core.shutdown)
        self.events = []
        core.subscribe(lambda name, payload: self.events.append((name, payload)))
        snapshot = core._reconnect_probe(threading.Event())
        core.apply_reconnect(snapshot)
        self._settle(core)
        self.assertTrue(core.connected)
        return core, snapshot

    def _settle(self, core):
        # At the back of the queue: run_sync would go ahead of a queued flash job.
        job = core.worker.submit("barrier", lambda cancel: None)
        self.assertTrue(job.done.wait(60), "the worker did not reach the barrier")

    def _event(self, name):
        found = [p for n, p in self.events if n == name]
        self.assertTrue(found, f"no {name} event")
        return found[-1]

    def _firmware_file(self):
        fd, path = tempfile.mkstemp(suffix=".bin")
        os.write(fd, _firmware_image())
        os.close(fd)
        self.addCleanup(os.remove, path)
        return path

    # -- the probe ----------------------------------------------------------

    def test_a_fresh_connect_measures_the_link_and_the_status_names_it(self):
        core, snapshot = self._core()
        self.assertEqual(snapshot["transport"], bulk_pipe.TRANSPORT_PIPE)
        self.assertAlmostEqual(snapshot["link_rate_mbps"], RIG_RATE_MBPS, delta=0.01)
        status = core.get_status()
        self.assertEqual(status["transport"], bulk_pipe.TRANSPORT_PIPE)
        self.assertEqual(status["pipe"]["port"], core.keeb.firmware.pipe.port_name)
        self.assertEqual(core.pipe_port_for_update(), core.keeb.firmware.pipe.port_name)

    def test_firmware_older_than_the_pipe_connects_hid_only(self):
        core, snapshot = self._core(dev_mock_protocol=PIPE_MIN_PROTOCOL - 1)
        self.assertEqual(snapshot["transport"], bulk_pipe.TRANSPORT_HID)
        self.assertIsNone(core.pipe_port_for_update())

    def test_a_forced_hid_link_never_opens_the_port(self):
        core, snapshot = self._core(dev_force_hid_link=True)
        self.assertEqual(snapshot["transport"], bulk_pipe.TRANSPORT_HID)
        self.assertEqual(core.keeb.firmware.pipe.opens, 0)
        self.assertIsNone(core.pipe_port_for_update())

    # -- the flashes ----------------------------------------------------------

    def test_a_firmware_update_streams_over_the_pipe_and_applies(self):
        core, _ = self._core()
        fw = core.keeb.firmware
        ok, _ = core.flash_firmware(self._firmware_file(), apply=True)
        self.assertTrue(ok)
        self._settle(core)
        self.assertTrue(self._event("fw_flash_done")["ok"], self._event("fw_flash_done"))
        self.assertTrue(self._event("fw_apply_done")["ok"], self._event("fw_apply_done"))
        self.assertEqual(_hid_reports(fw, hid_fw_up.CMD_FW_UP_CHUNK), 0)
        self.assertGreater(fw.pipe.fw_chunk_frames, 0)
        self.assertEqual(fw.running_image, _firmware_image())

    def test_a_firmware_update_with_the_link_forced_off_uses_hid(self):
        core, _ = self._core(dev_force_hid_link=True)
        fw = core.keeb.firmware
        core.flash_firmware(self._firmware_file())
        self._settle(core)
        self.assertTrue(self._event("fw_flash_done")["ok"], self._event("fw_flash_done"))
        self.assertEqual(fw.pipe.fw_chunk_frames, 0)
        self.assertGreater(_hid_reports(fw, hid_fw_up.CMD_FW_UP_CHUNK), 0)

    def test_a_font_pack_streams_over_the_pipe(self):
        bundle = next(b for b in load_bundle_manifest()["bundles"] if b["index"] == 0)
        with open(bundle["path"], "rb") as f:
            data = f.read()
        core, _ = self._core()
        fw = core.keeb.firmware
        ok, _ = core.flash_fontpack(bundle["path"], bundle_id=0)
        self.assertTrue(ok)
        self._settle(core)
        self.assertEqual(fw.bundle_data[0], data)
        self.assertEqual(_hid_reports(fw, hid_fontpack.CMD_FONTPACK_CHUNK), 0)
        self.assertGreater(fw.pipe.fw_chunk_frames, 0)


if __name__ == "__main__":
    unittest.main()
