"""PolyCore.flash_firmware / check_update / install_update.

Drives a bare PolyCore (no device construction) with the firmware-flash
(`hid_fw_up`) and self-update (`updater`) engines mocked — pins the gating,
the (ok, payload) contract, the queued worker job, and the JSON event
stream that `polyctl fw flash` / `polyctl update install` consume.
"""
import logging
import threading
import unittest
from unittest import mock

from polyhost.core import poly_core
from polyhost.core.poly_core import PolyCore


def make_core(*, connected=True, device_present=True, paused=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.fw")
    core.connected = connected
    core.device_present = device_present
    core.paused = paused
    core._observers = []
    core._observers_lock = threading.Lock()
    core.worker = mock.MagicMock()
    core.keeb = mock.MagicMock()
    return core


def _events(core):
    seen = []
    core.subscribe(lambda n, p: seen.append((n, p)))
    return seen


class TestFlashFirmware(unittest.TestCase):

    def test_gating_blocks_when_absent_or_paused(self):
        ok, msg = make_core(connected=False, device_present=False).flash_firmware("fw.bin")
        self.assertFalse(ok)
        ok, msg = make_core(paused=True).flash_firmware("fw.bin")
        self.assertFalse(ok)

    def test_unreadable_file_fails_fast(self):
        core = make_core()
        ok, msg = core.flash_firmware("/no/such/file.bin")
        self.assertFalse(ok)
        self.assertIn("Cannot read", msg)
        core.worker.submit.assert_not_called()

    def test_invalid_image_fails_before_queue(self):
        core = make_core()
        with mock.patch("builtins.open", mock.mock_open(read_data=b"junk")), \
             mock.patch.object(poly_core.hid_fw_up, "validate_rp2040_firmware",
                               return_value=(False, "bad boot2")):
            ok, msg = core.flash_firmware("fw.bin")
        self.assertFalse(ok)
        self.assertIn("RP2040", msg)
        core.worker.submit.assert_not_called()

    def test_valid_queues_job_and_streams_events(self):
        core = make_core()
        seen = _events(core)
        with mock.patch("builtins.open", mock.mock_open(read_data=b"img")), \
             mock.patch.object(poly_core.hid_fw_up, "validate_rp2040_firmware",
                               return_value=(True, "")), \
             mock.patch.object(poly_core.hid_fw_up, "validate_polykybd_firmware",
                               return_value=(True, "")), \
             mock.patch.object(poly_core.hid_fw_up, "flash_firmware",
                               return_value=(True, "done")) as m_flash, \
             mock.patch.object(poly_core.hid_fw_up, "apply_staged_firmware",
                               return_value=(True, "applied")) as m_apply:
            ok, payload = core.flash_firmware("fw.bin", apply=True)
            self.assertTrue(ok)
            self.assertEqual(payload, {"queued": True, "apply": True})
            # Run the queued job to drive the event stream.
            self.assertEqual(core.worker.submit.call_args.args[0], "fw_flash")
            job = core.worker.submit.call_args.args[1]
            cancel = mock.MagicMock()
            cancel.is_set.return_value = False
            job(cancel)
        m_flash.assert_called_once()
        m_apply.assert_called_once()
        names = [n for n, _ in seen]
        self.assertIn("fw_flash_done", names)
        self.assertIn("fw_apply_done", names)
        done = dict(seen)["fw_flash_done"]
        self.assertEqual(done, {"ok": True, "msg": "done"})

    def test_no_apply_skips_apply_step(self):
        core = make_core()
        seen = _events(core)
        with mock.patch("builtins.open", mock.mock_open(read_data=b"img")), \
             mock.patch.object(poly_core.hid_fw_up, "validate_rp2040_firmware",
                               return_value=(True, "")), \
             mock.patch.object(poly_core.hid_fw_up, "validate_polykybd_firmware",
                               return_value=(True, "")), \
             mock.patch.object(poly_core.hid_fw_up, "flash_firmware",
                               return_value=(True, "done")), \
             mock.patch.object(poly_core.hid_fw_up, "apply_staged_firmware") as m_apply:
            core.flash_firmware("fw.bin", apply=False)
            core.worker.submit.call_args.args[1](mock.MagicMock(is_set=lambda: False))
        m_apply.assert_not_called()
        self.assertNotIn("fw_apply_done", [n for n, _ in seen])


_REL = mock.MagicMock(version="0.9.0", html_url="http://x/rel", tarball_url="http://x/t")


class TestUpdate(unittest.TestCase):

    def test_check_no_update(self):
        core = make_core()
        with mock.patch("polyhost.services.updater.check_latest", return_value=None):
            ok, payload = core.check_update()
        self.assertTrue(ok)
        self.assertFalse(payload["available"])

    def test_check_available(self):
        core = make_core()
        with mock.patch("polyhost.services.updater.check_latest", return_value=_REL):
            ok, payload = core.check_update()
        self.assertTrue(ok)
        self.assertEqual(payload["available"], True)
        self.assertEqual(payload["version"], "0.9.0")
        self.assertEqual(payload["url"], "http://x/rel")

    def test_check_error_returns_false(self):
        import polyhost.services.updater as up
        core = make_core()
        with mock.patch.object(up, "check_latest", side_effect=up.UpdateCheckError("boom")):
            ok, msg = core.check_update()
        self.assertFalse(ok)
        self.assertIn("boom", msg)

    def test_install_up_to_date(self):
        core = make_core()
        with mock.patch("polyhost.services.updater.check_latest", return_value=None):
            ok, msg = core.install_update()
        self.assertFalse(ok)
        self.assertIn("up to date", msg.lower())

    def test_install_spawns_installer(self):
        core = make_core()
        with mock.patch("polyhost.services.updater.check_latest", return_value=_REL), \
             mock.patch("polyhost.services.updater.UpdateInstaller") as m_inst:
            ok, payload = core.install_update()
        self.assertTrue(ok)
        self.assertEqual(payload, {"queued": True, "version": "0.9.0"})
        m_inst.assert_called_once()
        m_inst.return_value.start.assert_called_once()


class TestDeviceCommands(unittest.TestCase):

    def test_send_overlay_mapping_coerces_json_string_keys(self):
        core = make_core()
        # Drive _device_call's run_sync so the lambda actually hits keeb.
        core.worker.run_sync.side_effect = lambda name, fn, timeout=None: fn(None)
        core.keeb.send_overlay_mapping.return_value = (True, "ok")
        ok, _ = core.send_overlay_mapping({"4": "5", "6": 7})
        self.assertTrue(ok)
        self.assertEqual(core.keeb.send_overlay_mapping.call_args.args[0], {4: 5, 6: 7})

    def test_activate_bootloader_gating_and_submit(self):
        blocked = make_core(device_present=False, connected=False)
        ok, _ = blocked.activate_bootloader()
        self.assertFalse(ok)
        blocked.worker.submit.assert_not_called()

        core = make_core()
        ok, payload = core.activate_bootloader()
        self.assertTrue(ok)
        self.assertEqual(payload, {"queued": True})
        self.assertEqual(core.worker.submit.call_args.args[0], "activate_bootloader")

    def test_set_handedness_submits(self):
        core = make_core()
        ok, _ = core.set_handedness(True)
        self.assertTrue(ok)
        self.assertEqual(core.worker.submit.call_args.args[0], "set_handedness")

    def test_apply_staged_gating(self):
        blocked = make_core(device_present=False, connected=False)
        ok, _ = blocked.apply_staged_firmware()
        self.assertFalse(ok)
        blocked.worker.submit.assert_not_called()

        core = make_core()
        ok, payload = core.apply_staged_firmware()
        self.assertTrue(ok)
        self.assertEqual(payload, {"queued": True})
        self.assertEqual(core.worker.submit.call_args.args[0], "apply_staged_firmware")


if __name__ == "__main__":
    unittest.main()
