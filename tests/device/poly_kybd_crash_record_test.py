"""cmd 39 (CRASH_RECORD, protocol v16+) — the gate, the wire bytes, the decode."""
import unittest

from polyhost.device.command_ids import Cmd
from polyhost.device.poly_kybd import (
    CRASH_RECORD_MIN_PROTOCOL, FEATURE_MIN_PROTOCOL, protocol_supports)
from polyhost.services import crash_report as cr

from tests.device.poly_kybd_cmd_test import make_keeb, POLY
from tests.device.fake_hid import ack, nack
from tests.services.crash_report_test import _record_bytes


class CrashRecordGateTest(unittest.TestCase):
    def test_command_id_and_threshold_match_the_firmware(self):
        self.assertEqual(Cmd.CRASH_RECORD.value, 39)
        self.assertEqual(FEATURE_MIN_PROTOCOL["crash_record"], CRASH_RECORD_MIN_PROTOCOL)
        self.assertEqual(CRASH_RECORD_MIN_PROTOCOL, 16)
        self.assertFalse(protocol_supports(15, "crash_record"))
        self.assertTrue(protocol_supports(16, "crash_record"))

    def test_old_firmware_refuses_without_touching_the_device(self):
        keeb, device = make_keeb()
        keeb.protocol_version = 15
        ok, msg = keeb.get_crash_record()
        self.assertFalse(ok)
        self.assertIn("too old", msg)
        ok, msg = keeb.clear_crash_record()
        self.assertFalse(ok)
        self.assertEqual(device.writes, [])


class CrashRecordCommandTest(unittest.TestCase):
    def test_get_master_record(self):
        body = bytes([cr.HID_FLAG_PRESENT | cr.HID_FLAG_FRESH]) + _record_bytes()
        keeb, device = make_keeb(replies=[ack(39, body)])
        ok, rec = keeb.get_crash_record()
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 39, 0]))
        self.assertEqual(rec["side"], "master")
        self.assertEqual(rec["kind"], "hardfault")
        self.assertEqual(rec["pc"], 0x10012345)
        self.assertTrue(rec["fresh"])
        self.assertFalse(keeb.hid.lock.locked())

    def test_get_slave_record_sends_which_1(self):
        body = bytes([cr.HID_FLAG_PRESENT]) + _record_bytes(kind=3, phase=2)
        keeb, device = make_keeb(replies=[ack(39, body)])
        ok, rec = keeb.get_crash_record(1)
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 39, 1]))
        self.assertEqual(rec["side"], "slave")
        self.assertEqual(rec["kind"], "watchdog")
        self.assertFalse(rec["fresh"])

    def test_no_record_is_ok_none(self):
        keeb, _ = make_keeb(replies=[ack(39, bytes(cr.HID_BODY_LEN))])
        ok, rec = keeb.get_crash_record()
        self.assertTrue(ok)
        self.assertIsNone(rec)

    def test_a_nack_is_a_failure_not_a_record(self):
        keeb, _ = make_keeb(replies=[nack(39)])
        ok, msg = keeb.get_crash_record()
        self.assertFalse(ok)
        self.assertIn("refused", msg)

    def test_clear_sends_sub_op_2(self):
        keeb, device = make_keeb(replies=[ack(39)])
        ok, _ = keeb.clear_crash_record()
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 39, 2]))

    def test_a_nacked_clear_is_a_failure(self):
        # The reply prefix alone matches a NACK too; only the '.' is an ACK. A
        # refused clear reported as success would reset the host's dedupe while
        # the record stays on the keyboard.
        keeb, _ = make_keeb(replies=[nack(39)])
        ok, msg = keeb.clear_crash_record()
        self.assertFalse(ok)
        self.assertIn("refused", msg)


if __name__ == "__main__":
    unittest.main()
