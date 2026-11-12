"""Tap-hold timing (cmd 44, protocol v29+) and Auto Shift (v30+): the gates, the
wire bytes, the closed ranges and the reply parse. The firmware side is qmk_firmware
keyboards/polykybd/hid_com.c hid_cmd_44 and base/tap_terms.h."""

import unittest
from unittest.mock import MagicMock

from polyhost.device.command_ids import Cmd, TapTerms
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import (AUTO_SHIFT_MIN_PROTOCOL, FEATURE_MIN_PROTOCOL, PolyKybd,
                                       TAP_TERMS_MIN_PROTOCOL, protocol_supports)
from polyhost.settings import PolySettings
from polyhost._version import __protocol__


def _reply(ok, tap, flow, flags=TapTerms.FLAG_FLOW_TAP, auto_shift_ms=None):
    """A v29 reply (8 bytes), or a v30 one when auto_shift_ms is given."""
    body = [ord("P"), Cmd.TAP_TERMS.value, ord("." if ok else "!"),
            tap & 0xFF, tap >> 8, flow & 0xFF, flow >> 8, flags]
    if auto_shift_ms is not None:
        body += [auto_shift_ms & 0xFF, auto_shift_ms >> 8]
    return bytes(body)


_NO_AUTO_SHIFT = {"auto_shift_available": False, "auto_shift": False,
                  "auto_shift_ms": TapTerms.DEFAULT_AUTO_SHIFT_MS}


class TapTermsGateTest(unittest.TestCase):
    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_feature_threshold(self):
        self.assertEqual(TAP_TERMS_MIN_PROTOCOL, 29)
        self.assertEqual(FEATURE_MIN_PROTOCOL["tap_terms"], TAP_TERMS_MIN_PROTOCOL)
        self.assertFalse(protocol_supports(TAP_TERMS_MIN_PROTOCOL - 1, "tap_terms"))
        self.assertTrue(protocol_supports(TAP_TERMS_MIN_PROTOCOL, "tap_terms"))
        self.assertGreaterEqual(__protocol__, TAP_TERMS_MIN_PROTOCOL)

    def test_old_firmware_refuses_without_touching_the_device(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL - 1)
        ok, msg = keeb.set_tap_terms(250, 120)
        self.assertFalse(ok)
        self.assertIn("too old", msg)
        ok, msg = keeb.get_tap_terms()
        self.assertFalse(ok)
        self.assertIn("too old", msg)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_set_sends_op_and_both_terms_little_endian(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 300, 120))
        ok, terms = keeb.set_tap_terms(300, 120)
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        # 300 = 0x012C: little-endian, or the firmware reads 11 264 ms.
        self.assertEqual(bytes(report[:7]),
                         bytes([0x50, 44, 1, 0x2C, 0x01, 120, 0]))
        self.assertEqual(terms, {"tapping_term": 300, "flow_tap_term": 120,
                                 "flow_tap_available": True, **_NO_AUTO_SHIFT})

    def test_none_is_sent_as_keep(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 200, 0))
        keeb.set_tap_terms(flow_tap_term=0)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[2:7]), bytes([1, 0xFF, 0xFF, 0, 0]))

    def test_get_sends_op_0(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 200, 150, flags=0))
        ok, terms = keeb.get_tap_terms()
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(report[1], 44)
        self.assertEqual(report[2], 0)
        self.assertEqual(terms, {"tapping_term": 200, "flow_tap_term": 150,
                                 "flow_tap_available": False, **_NO_AUTO_SHIFT})

    def test_values_outside_the_closed_ranges_are_refused_before_io(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        for tap, flow in ((90, None), (510, None), (205, None), (None, 310),
                          (None, 5), (None, -10), ("200", None), (True, None)):
            with self.subTest(tap=tap, flow=flow):
                ok, _ = keeb.set_tap_terms(tap, flow)
                self.assertFalse(ok)
        ok, _ = keeb.set_tap_terms()
        self.assertFalse(ok)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_range_boundaries_are_accepted(self):
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 100, 0))
        for tap, flow in ((100, 0), (500, 300)):
            with self.subTest(tap=tap, flow=flow):
                ok, _ = keeb.set_tap_terms(tap, flow)
                self.assertTrue(ok)

    def test_a_nack_is_a_failure(self):
        """expect() matches a NACK too; reply[2] decides."""
        keeb = self._keeb(TAP_TERMS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, _reply(False, 200, 150))
        ok, _ = keeb.set_tap_terms(250, 120)
        self.assertFalse(ok)
        ok, _ = keeb.get_tap_terms()
        self.assertFalse(ok)


class AutoShiftGateTest(unittest.TestCase):
    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_feature_threshold(self):
        self.assertEqual(AUTO_SHIFT_MIN_PROTOCOL, 30)
        self.assertEqual(FEATURE_MIN_PROTOCOL["auto_shift"], AUTO_SHIFT_MIN_PROTOCOL)
        self.assertGreaterEqual(__protocol__, AUTO_SHIFT_MIN_PROTOCOL)

    def test_v29_refuses_auto_shift_but_still_sets_the_terms(self):
        """The gate is on the Auto Shift fields, not on cmd 44: a v29 keyboard
        would ACK the extra bytes and ignore them."""
        keeb = self._keeb(AUTO_SHIFT_MIN_PROTOCOL - 1)
        for kwargs in ({"auto_shift": True}, {"auto_shift_ms": 200},
                       {"tapping_term": 250, "auto_shift": False}):
            with self.subTest(kwargs=kwargs):
                ok, msg = keeb.set_tap_terms(**kwargs)
                self.assertFalse(ok)
                self.assertIn("Auto Shift", msg)
        keeb.hid.send_and_read_validate.assert_not_called()
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 250, 150))
        ok, _ = keeb.set_tap_terms(250)
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        # The v29 form: 5 payload bytes, zero-padded on the wire.
        self.assertEqual(bytes(report[2:]), bytes([1, 250, 0, 0xFF, 0xFF]))

    def test_terms_only_set_keeps_auto_shift_on_v30(self):
        """data[7..9] are not sent, so the zero padding reads as "keep" on a v30
        keyboard."""
        keeb = self._keeb(AUTO_SHIFT_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (
            True, _reply(True, 250, 150, TapTerms.FLAG_FLOW_TAP | TapTerms.FLAG_AUTO_SHIFT, 180))
        keeb.set_tap_terms(250)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[7:]).ljust(3, b"\0")[:3], bytes([0, 0, 0]))

    def test_set_sends_op_and_timeout_little_endian(self):
        keeb = self._keeb(AUTO_SHIFT_MIN_PROTOCOL)
        flags = TapTerms.FLAG_FLOW_TAP | TapTerms.FLAG_AUTO_SHIFT | TapTerms.FLAG_AUTO_SHIFT_ON
        keeb.hid.send_and_read_validate.return_value = (True, _reply(True, 200, 150, flags, 300))
        ok, terms = keeb.set_tap_terms(auto_shift=True, auto_shift_ms=300)
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[2:10]),
                         bytes([1, 0xFF, 0xFF, 0xFF, 0xFF, TapTerms.AUTO_SHIFT_OP_ON, 0x2C, 0x01]))
        self.assertEqual((terms["auto_shift_available"], terms["auto_shift"], terms["auto_shift_ms"]),
                         (True, True, 300))
        keeb.set_tap_terms(auto_shift=False)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[7:10]), bytes([TapTerms.AUTO_SHIFT_OP_OFF, 0, 0]))

    def test_timeout_outside_the_closed_range_is_refused_before_io(self):
        keeb = self._keeb(AUTO_SHIFT_MIN_PROTOCOL)
        for ms in (90, 510, 175, 0, True, "200"):
            with self.subTest(ms=ms):
                ok, _ = keeb.set_tap_terms(auto_shift_ms=ms)
                self.assertFalse(ok)
        keeb.hid.send_and_read_validate.assert_not_called()


class TapTermsMockFirmwareTest(unittest.TestCase):
    """Against the emulated keyboard: the round trip, and that a report with one
    bad field changes neither term (the firmware validates both first)."""

    def _keyboard(self, protocol=__protocol__):
        fw = MockFirmware(protocol)
        kb = PolyKybd(DeviceSettings(), PolySettings())
        kb.hid = MockHidHelper(fw)
        kb.protocol_version = protocol
        return kb, fw

    def test_round_trip_and_defaults(self):
        kb, _ = self._keyboard()
        ok, terms = kb.get_tap_terms()
        self.assertTrue(ok)
        self.assertEqual((terms["tapping_term"], terms["flow_tap_term"]), (200, 150))
        ok, terms = kb.set_tap_terms(250)
        self.assertTrue(ok)
        self.assertEqual((terms["tapping_term"], terms["flow_tap_term"]), (250, 150))
        ok, terms = kb.get_tap_terms()
        self.assertEqual((terms["tapping_term"], terms["flow_tap_term"]), (250, 150))

    def test_one_bad_field_changes_nothing(self):
        kb, fw = self._keyboard()
        # Bypass the host's own range check to reach the emulated firmware.
        ok, reply = kb.hid.send_and_read_validate(
            bytearray([0x50, 44, 1, 250, 0, 0x36, 0x01]), 100, b"P,")   # flow 310
        self.assertTrue(ok)
        self.assertEqual(reply[2:3], b"!")
        ok, terms = kb.get_tap_terms()
        self.assertEqual((terms["tapping_term"], terms["flow_tap_term"]), (200, 150))

    def test_auto_shift_round_trip(self):
        kb, _ = self._keyboard()
        ok, terms = kb.get_tap_terms()
        self.assertTrue(ok)
        self.assertEqual((terms["auto_shift_available"], terms["auto_shift"], terms["auto_shift_ms"]),
                         (True, False, 180))
        ok, terms = kb.set_tap_terms(auto_shift=True, auto_shift_ms=220)
        self.assertTrue(ok)
        ok, terms = kb.set_tap_terms(250)   # a terms-only set keeps Auto Shift
        self.assertEqual((terms["auto_shift"], terms["auto_shift_ms"]), (True, 220))

    def test_bad_auto_shift_field_changes_nothing(self):
        kb, _ = self._keyboard()
        for tail in ([3, 0, 0], [2, 0x5A, 0]):   # op 3; timeout 90 ms
            with self.subTest(tail=tail):
                ok, reply = kb.hid.send_and_read_validate(
                    bytearray([0x50, 44, 1, 250, 0, 0xFF, 0xFF] + tail), 100, b"P,")
                self.assertEqual(reply[2:3], b"!")
        ok, terms = kb.get_tap_terms()
        self.assertEqual((terms["tapping_term"], terms["auto_shift"]), (200, False))

    def test_v29_keyboard_reports_no_auto_shift(self):
        kb, _ = self._keyboard(TAP_TERMS_MIN_PROTOCOL)
        ok, terms = kb.get_tap_terms()
        self.assertTrue(ok)
        self.assertFalse(terms["auto_shift_available"])

    def test_older_keyboard_nacks_the_command(self):
        kb, _ = self._keyboard(TAP_TERMS_MIN_PROTOCOL - 1)
        kb.protocol_version = TAP_TERMS_MIN_PROTOCOL   # pretend the gate is wrong
        ok, _ = kb.get_tap_terms()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
