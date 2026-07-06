"""Tests for the idle (anti-burn-in) display-style command (cmd 28, protocol v4+)."""
import unittest

from polyhost.device.command_ids import Cmd, IdleStyle
from polyhost.device.cmd_composer import compose_cmd

from tests.device.poly_kybd_cmd_test import make_keeb, POLY
from tests.device.fake_hid import ack, nack


class TestIdleStyleEncoding(unittest.TestCase):
    def test_command_id_matches_firmware(self):
        # Firmware hid_com.c dispatches this as case 28.
        self.assertEqual(Cmd.IDLE_STYLE.value, 28)

    def test_idle_style_enum_values(self):
        # Lockstep with the firmware's poly_idle_style (state.h) — append-only.
        self.assertEqual(IdleStyle.PULSE.value, 0)
        self.assertEqual(IdleStyle.JITTER.value, 1)
        self.assertEqual(IdleStyle.IDDQD.value, 2)

    def test_compose_set_jitter(self):
        result = compose_cmd(Cmd.IDLE_STYLE, IdleStyle.JITTER.value)
        self.assertEqual(result, bytearray([POLY, 28, 1]))


class TestIdleStyleCommand(unittest.TestCase):
    def test_set_idle_style_payload(self):
        keeb, device = make_keeb(replies=[ack(28)])
        keeb.protocol_version = 4
        ok, _ = keeb.set_idle_style(IdleStyle.JITTER)
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 28, 1]))
        self.assertFalse(keeb.hid.lock.locked())

    def test_set_idle_style_accepts_int(self):
        keeb, device = make_keeb(replies=[ack(28)])
        keeb.protocol_version = 4
        ok, _ = keeb.set_idle_style(0)
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 28, 0]))

    def test_get_idle_style(self):
        keeb, device = make_keeb(replies=[ack(28, bytes([1]))])
        keeb.protocol_version = 4
        ok, value = keeb.get_idle_style()
        self.assertTrue(ok)
        self.assertEqual(value, 1)
        # Query sends the 0xFF sentinel.
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 28, 0xFF]))

    def test_too_old_firmware_refused(self):
        keeb, _ = make_keeb(replies=[])
        keeb.protocol_version = 3
        ok, msg = keeb.set_idle_style(IdleStyle.JITTER)
        self.assertFalse(ok)
        self.assertIn("protocol too old", msg)

    def test_get_idle_style_nack(self):
        keeb, _ = make_keeb(replies=[nack(28)])
        keeb.protocol_version = 4
        ok, value = keeb.get_idle_style()
        self.assertFalse(ok)
        self.assertEqual(value, 0)


if __name__ == '__main__':
    unittest.main()
