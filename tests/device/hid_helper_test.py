"""Characterization tests for HidHelper.

These pin the locking and reply-draining behavior of HidHelper. Since the
HID worker-thread refactor a single thread owns the device, so the lock is a
purely internal per-call guard: after any public call the lock must be free —
including on every error path. No lock is ever handed back to the caller.
"""
import unittest

from polyhost.device.device_settings import DeviceSettings

from tests.device.fake_hid import FakeHidDevice, make_hid_helper, pad, ack

EXPECT = b'P\x06'                 # expected prefix used throughout (GET_ID)
CMD = bytearray(b'\x50\x06')      # ID_POLYKYBD + GET_ID
GOOD = ack(0x06, b'reply')        # matching reply
STALE = ack(0x15)                 # non-matching reply (different cmd)


def _helper(replies=None, auto_ack=False):
    device = FakeHidDevice(replies=replies, auto_ack=auto_ack)
    return make_hid_helper(device), device


class TestSendAndReadValidate(unittest.TestCase):

    def test_happy_path_returns_reply(self):
        helper, device = _helper(replies=[GOOD])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertTrue(ok)
        self.assertTrue(reply.startswith(EXPECT))
        self.assertFalse(helper.lock.locked())

    def test_report_is_padded_with_report_id_prefix(self):
        helper, device = _helper(replies=[GOOD])
        helper.send_and_read_validate(CMD, 30, EXPECT)
        settings = DeviceSettings()
        self.assertEqual(len(device.writes[0]), settings.HID_REPORT_SIZE + 1)
        self.assertEqual(device.writes[0][0], 0x00)          # report ID
        self.assertEqual(device.writes[0][1:3], bytes(CMD))  # payload

    def test_default_expected_prefix_is_first_two_bytes(self):
        helper, device = _helper(replies=[pad(bytes(CMD) + b'.ok')])
        ok, reply = helper.send_and_read_validate(CMD)
        self.assertTrue(ok)

    def test_stale_replies_are_drained_until_match(self):
        helper, device = _helper(replies=[STALE, STALE, GOOD])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertTrue(ok)
        self.assertTrue(reply.startswith(EXPECT))
        self.assertFalse(helper.lock.locked())

    def test_buffer_exhausted_after_stale_waits_once_more(self):
        # stale reply, then an empty read (buffer dry), then the real reply
        # arrives on the final full-timeout read.
        helper, device = _helper(replies=[STALE, b'', GOOD])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertTrue(ok)
        self.assertTrue(reply.startswith(EXPECT))

    def test_stale_on_full_timeout_rewait_keeps_draining(self):
        # The buffer runs dry, the one full-timeout re-wait returns ANOTHER
        # stale (a late ACK from a previous command, seen in the field on
        # Windows 2026-06-11), and the real reply is right behind it. The
        # drain must continue past the re-wait stale instead of misreporting
        # it as the response.
        helper, device = _helper(replies=[STALE, b'', STALE, GOOD])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertTrue(ok)
        self.assertTrue(reply.startswith(EXPECT))
        self.assertFalse(helper.lock.locked())

    def test_only_one_full_timeout_rewait_is_granted(self):
        # After the single re-wait the drain continues non-blocking only;
        # a second dry buffer ends the call without further blocking reads.
        helper, device = _helper(replies=[STALE, b'', STALE, b'', GOOD])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())
        # Both empty reads consumed; GOOD stays queued for the next command.
        self.assertEqual(device.replies[0], GOOD)

    def test_no_reply_returns_false(self):
        helper, device = _helper()
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())

    def test_wrong_prefix_only_returns_false(self):
        helper, device = _helper(replies=[STALE])
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())

    def test_write_exception_returns_false_and_releases_lock(self):
        helper, device = _helper()
        device.write_exception = RuntimeError("USB gone")
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)
        self.assertIn(b'Exception', bytes(reply))
        self.assertFalse(helper.lock.locked())

    def test_read_exception_returns_false_and_releases_lock(self):
        helper, device = _helper()
        device.read_exception = RuntimeError("USB gone")
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())

    def test_no_interface_returns_false(self):
        helper, device = _helper()
        helper.interface = None
        ok, reply = helper.send_and_read_validate(CMD, 30, EXPECT)
        self.assertFalse(ok)


class TestSendMultiple(unittest.TestCase):

    def test_writes_and_frees_lock(self):
        helper, device = _helper()
        ok, result = helper.send_multiple(CMD)
        self.assertTrue(ok)
        self.assertEqual(len(device.writes), 1)
        self.assertFalse(helper.lock.locked())

    def test_sequence_of_sends(self):
        helper, device = _helper()
        for _ in range(3):
            ok, result = helper.send_multiple(CMD)
            self.assertTrue(ok)
            self.assertFalse(helper.lock.locked())
        self.assertEqual(len(device.writes), 3)

    def test_write_exception_releases_lock(self):
        helper, device = _helper()
        device.write_exception = RuntimeError("USB gone")
        ok, result = helper.send_multiple(CMD)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())

    def test_no_interface_returns_false(self):
        helper, device = _helper()
        helper.interface = None
        ok, result = helper.send_multiple(CMD)
        self.assertFalse(ok)


class TestSimpleSendAndRead(unittest.TestCase):

    def test_send_writes_and_ignores_reply(self):
        helper, device = _helper()
        ok, result = helper.send(CMD)
        self.assertTrue(ok)
        self.assertEqual(len(device.writes), 1)
        self.assertFalse(helper.lock.locked())

    def test_send_exception_returns_false_and_releases(self):
        helper, device = _helper()
        device.write_exception = RuntimeError("USB gone")
        ok, result = helper.send(CMD)
        self.assertFalse(ok)
        self.assertFalse(helper.lock.locked())

    def test_read_returns_queued_reply(self):
        helper, device = _helper(replies=[GOOD])
        ok, reply = helper.read(timeout=5)
        self.assertTrue(ok)
        self.assertTrue(bytes(reply).startswith(EXPECT))
        self.assertFalse(helper.lock.locked())

    def test_send_and_read_round_trip(self):
        helper, device = _helper(replies=[GOOD])
        ok, reply = helper.send_and_read(CMD, timeout=5)
        self.assertTrue(ok)
        self.assertTrue(bytes(reply).startswith(EXPECT))
        self.assertFalse(helper.lock.locked())

    def test_no_interface_paths(self):
        helper, device = _helper()
        helper.interface = None
        self.assertFalse(helper.read(5)[0])
        self.assertFalse(helper.send(CMD)[0])
        self.assertFalse(helper.send_and_read(CMD, 5)[0])
        self.assertFalse(helper.interface_acquired())


class TestDrainReplies(unittest.TestCase):

    def test_discards_all_queued_and_reports_count(self):
        helper, device = _helper(replies=[GOOD, STALE, GOOD])
        self.assertEqual(helper.drain_replies(timeout_ms=5), 3)
        self.assertFalse(helper.lock.locked())

    def test_stops_at_empty_buffer(self):
        helper, device = _helper()
        self.assertEqual(helper.drain_replies(timeout_ms=5), 0)

    def test_no_interface_returns_zero(self):
        helper, device = _helper()
        helper.interface = None
        self.assertEqual(helper.drain_replies(), 0)


class TestCloseInterface(unittest.TestCase):

    def test_closes_device_and_clears_interface(self):
        helper, device = _helper()
        helper.close_interface()
        self.assertTrue(device.closed)
        self.assertIsNone(helper.interface)
        self.assertFalse(helper.lock.locked())


class TestConsole(unittest.TestCase):

    def test_no_console_returns_empty(self):
        helper, device = _helper()
        self.assertEqual(len(helper.get_console_output()), 0)

    def test_console_read_passthrough(self):
        console = FakeHidDevice(replies=[pad(b'log line')])
        device = FakeHidDevice()
        helper = make_hid_helper(device, console=console)
        out = helper.get_console_output()
        self.assertTrue(bytes(out).startswith(b'log line'))


if __name__ == '__main__':
    unittest.main()
