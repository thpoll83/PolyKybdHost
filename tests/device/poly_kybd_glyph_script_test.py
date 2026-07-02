"""Tests for the glyph-script override command (cmd 30, protocol v9+)."""
import unittest

from polyhost.device.command_ids import Cmd, GlyphScript
from polyhost.device.cmd_composer import compose_cmd

from tests.device.poly_kybd_cmd_test import make_keeb, POLY
from tests.device.fake_hid import ack, nack


class TestGlyphScriptEncoding(unittest.TestCase):
    def test_command_id_matches_firmware(self):
        # Firmware hid_com.c dispatches this as case 30.
        self.assertEqual(Cmd.GLYPH_SCRIPT.value, 30)

    def test_glyph_script_enum_values(self):
        self.assertEqual(GlyphScript.STANDARD.value, 0)
        self.assertEqual(GlyphScript.TENGWAR.value, 1)

    def test_compose_set_tengwar(self):
        result = compose_cmd(Cmd.GLYPH_SCRIPT, GlyphScript.TENGWAR.value)
        self.assertEqual(result, bytearray([POLY, 30, 1]))


class TestGlyphScriptCommand(unittest.TestCase):
    def test_set_glyph_script_payload(self):
        keeb, device = make_keeb(replies=[ack(30)])
        keeb.protocol_version = 9
        ok, _ = keeb.set_glyph_script(GlyphScript.TENGWAR)
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 30, 1]))
        self.assertFalse(keeb.hid.lock.locked())

    def test_set_glyph_script_accepts_int(self):
        keeb, device = make_keeb(replies=[ack(30)])
        keeb.protocol_version = 9
        ok, _ = keeb.set_glyph_script(0)
        self.assertTrue(ok)
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 30, 0]))

    def test_get_glyph_script(self):
        keeb, device = make_keeb(replies=[ack(30, bytes([1]))])
        keeb.protocol_version = 9
        ok, value = keeb.get_glyph_script()
        self.assertTrue(ok)
        self.assertEqual(value, 1)
        # Query sends the 0xFF sentinel.
        self.assertEqual(device.last_payload()[:3], bytes([POLY, 30, 0xFF]))

    def test_too_old_firmware_refused(self):
        keeb, _ = make_keeb(replies=[])
        keeb.protocol_version = 8
        ok, msg = keeb.set_glyph_script(GlyphScript.TENGWAR)
        self.assertFalse(ok)
        self.assertIn("protocol too old", msg)

    def test_get_glyph_script_too_old_firmware(self):
        keeb, _ = make_keeb(replies=[])
        keeb.protocol_version = 8
        ok, value = keeb.get_glyph_script()
        self.assertFalse(ok)
        self.assertEqual(value, 0)

    def test_get_glyph_script_nack(self):
        keeb, _ = make_keeb(replies=[nack(30)])
        keeb.protocol_version = 9
        ok, value = keeb.get_glyph_script()
        self.assertFalse(ok)
        self.assertEqual(value, 0)


if __name__ == '__main__':
    unittest.main()
