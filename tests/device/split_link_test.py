"""The "USB half answers, other half silent" classification (device/split_link.py).

Driven against the emulated keyboard: ``erase_polls`` makes BEGIN answer '~'
forever, which is what a firmware does while it waits on a half that never ACKs
its erase. A fake clock walks past the 90 s deadline without waiting for it.
"""
import itertools
import os
import tempfile
import threading
import unittest
import unittest.mock as mock

from polyhost.core.poly_core import PolyCore
from polyhost.device import hid_fontpack, hid_fw_up
from polyhost.device.mock_firmware import FaultPlan, MockFirmware, MockHidHelper
from polyhost.device.split_link import (SPLIT_LINK_MARK, is_split_link_failure,
                                        split_link_timeout_message)
from polyhost.services.fontpack_bundle import load_bundle_manifest
from polyhost.settings import PolySettings

from tests.device.mock_fault_test import _firmware_image

FOREVER = 10 ** 9


def _hid(**faults):
    fw = MockFirmware(21, faults=FaultPlan(**faults))
    return fw, MockHidHelper(fw)


def _fast_clock(test):
    """time.monotonic() advances 5 s per call; time.sleep() returns at once."""
    ticks = itertools.count(0, 5)
    for p in (mock.patch("time.monotonic", lambda: float(next(ticks))),
              mock.patch("time.sleep", lambda s: None)):
        p.start()
        test.addCleanup(p.stop)


class MessageTest(unittest.TestCase):

    def test_the_message_carries_the_mark(self):
        msg = split_link_timeout_message("BEGIN timed out", "font pack region")
        self.assertIn(SPLIT_LINK_MARK, msg)
        self.assertTrue(is_split_link_failure(msg))

    def test_other_failures_and_non_strings_are_not_flagged(self):
        self.assertFalse(is_split_link_failure(
            "FW_UP_BEGIN timed out — keyboard did not finish erasing within 90 s."))
        self.assertFalse(is_split_link_failure(None))
        self.assertFalse(is_split_link_failure({"msg": SPLIT_LINK_MARK}))


class FontPackBeginTest(unittest.TestCase):

    def setUp(self):
        _fast_clock(self)
        bundle = next(b for b in load_bundle_manifest()["bundles"] if b["index"] == 0)
        self.path = bundle["path"]

    def test_endless_erase_polls_are_a_split_link_failure(self):
        _, hid = _hid(erase_polls=FOREVER)
        ok, msg, status = hid_fontpack.flash_fontpack(hid, self.path, bundle_id=0)
        self.assertFalse(ok)
        self.assertEqual(status, hid_fontpack.STATUS_SPLIT_LINK)
        self.assertTrue(is_split_link_failure(msg), msg)

    def test_a_keyboard_that_stops_answering_is_not_one(self):
        # No reply at all is a USB problem, not the other half: the old message.
        _, hid = _hid(disconnected=True)
        ok, msg, status = hid_fontpack.flash_fontpack(hid, self.path, bundle_id=0)
        self.assertFalse(ok)
        self.assertNotEqual(status, hid_fontpack.STATUS_SPLIT_LINK)
        self.assertFalse(is_split_link_failure(msg), msg)


class FirmwareBeginTest(unittest.TestCase):

    def setUp(self):
        _fast_clock(self)
        fd, self.path = tempfile.mkstemp(suffix=".bin")
        os.write(fd, _firmware_image())
        os.close(fd)
        self.addCleanup(os.remove, self.path)

    def test_endless_erase_polls_are_a_split_link_failure(self):
        _, hid = _hid(erase_polls=FOREVER)
        ok, msg = hid_fw_up.flash_firmware(hid, self.path)
        self.assertFalse(ok)
        self.assertTrue(is_split_link_failure(msg), msg)
        self.assertIn("FW_UP_BEGIN timed out", msg)

    def test_a_short_erase_still_flashes(self):
        _, hid = _hid(erase_polls=3, fw_confirm_polls=0)
        with mock.patch.object(hid_fw_up, "CONFIRM_POLL_INTERVAL_S", 0):
            ok, msg = hid_fw_up.flash_firmware(hid, self.path)
        self.assertTrue(ok, msg)


class FontPackPassTest(unittest.TestCase):
    """The core stops the pass at a dead link instead of 90 s per bundle."""

    def setUp(self):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                  "fontpack_auto_flash": True}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True)):
            p.start()
            self.addCleanup(p.stop)
        self.core = PolyCore(mock.MagicMock(), start_worker=False)
        _fast_clock(self)
        self.events = []
        self.core.emit = lambda name, payload=None: self.events.append((name, payload))

    def _done(self):
        return [p for n, p in self.events if n == "fontpack_flash_done"]

    def test_the_pass_stops_at_the_first_silent_half(self):
        fw = self.core.keeb.firmware
        for slot in (0, 1, 2):
            fw.bundle_versions.pop(slot, None)
        # The fault is consumed by the first BEGIN, so a pass that carried on
        # would flash slots 1 and 2 cleanly; that is what the asserts catch.
        fw.faults.erase_polls = FOREVER
        self.core._fontpack_autocheck_job(threading.Event())
        self.assertNotIn(1, fw.bundle_data)
        self.assertNotIn(2, fw.bundle_data)
        (done,) = self._done()
        self.assertFalse(done["ok"])
        self.assertTrue(done["split_link_down"])
        self.assertIn("Not attempted", done["msg"])

    def test_an_ordinary_failure_does_not_claim_a_dead_link(self):
        fw = self.core.keeb.firmware
        fw.bundle_versions.pop(0, None)
        fw.faults.fontpack_commit.extend(["R"])
        self.core._fontpack_autocheck_job(threading.Event())
        (done,) = self._done()
        self.assertFalse(done["ok"])
        self.assertFalse(done["split_link_down"])


if __name__ == "__main__":
    unittest.main()
