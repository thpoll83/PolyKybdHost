"""VIA values on the legacy raw HID ids (protocol 39): the RGB matrix channel
(0x07 / 0x08), uptime (0x02 value 0x01), device indication (0x03 value 0x05) and
the switch matrix read (0x02 value 0x03, only with the firmware's debug_enable on).

The firmware side is keyboards/polykybd/lib/hid/hid_com.c legacy_command_kb."""
import unittest

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import (FEATURE_MIN_PROTOCOL, PolyKybd,
                                       VIA_VALUES_MIN_PROTOCOL)


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0,
                "hid_reconnect_retries": 1}.get(name)


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _keyboard(protocol, clock=None):
    fw = MockFirmware(protocol, clock=clock or _Clock())
    kb = PolyKybd(DeviceSettings(), _Settings())
    kb.hid = MockHidHelper(fw)
    kb.protocol_version = protocol
    return kb, fw


def _via_writes(fw):
    return [bytes(w[:6]) for w in fw.writes if w and w[0] != ord("P")]


class GateTest(unittest.TestCase):
    def test_threshold(self):
        self.assertEqual(VIA_VALUES_MIN_PROTOCOL, 39)
        self.assertEqual(FEATURE_MIN_PROTOCOL["via_values"], 39)

    def test_every_call_refuses_below_39_without_sending(self):
        kb, fw = _keyboard(38)
        calls = [kb.get_rgb_matrix, lambda: kb.set_rgb_matrix(enabled=False),
                 kb.get_uptime_ms, kb.indicate_device, kb.get_switch_matrix]
        for call in calls:
            ok, msg = call()
            self.assertFalse(ok)
            self.assertIn("need v39+", msg)
        self.assertEqual(_via_writes(fw), [])

    def test_a_v38_keyboard_sends_no_reply(self):
        # The control for the gate: an ungated request gets nothing back.
        kb, fw = _keyboard(38)
        kb.protocol_version = 39             # pretend the gate passed
        ok, _ = kb.get_uptime_ms()
        self.assertFalse(ok)
        self.assertEqual(len(fw.refused), 1)


class WireTest(unittest.TestCase):
    def test_uptime_bytes_and_value(self):
        clock = _Clock()
        kb, fw = _keyboard(39, clock)
        clock.t += 70000.123
        ok, ms = kb.get_uptime_ms()
        self.assertTrue(ok)
        self.assertEqual(ms, 70000123)
        self.assertEqual(_via_writes(fw), [bytes([0x02, 0x01, 0, 0, 0, 0])])

    def test_switch_off_sends_effect_zero(self):
        kb, fw = _keyboard(39)
        self.assertEqual(kb.set_rgb_matrix(enabled=False), (True, "ok"))
        self.assertEqual(_via_writes(fw), [bytes([0x07, 3, 2, 0, 0, 0])])
        self.assertFalse(fw.rgb["enabled"])
        self.assertEqual(kb.get_rgb_matrix()[1]["effect"], 0)

    def test_switch_on_keeps_the_current_effect(self):
        kb, fw = _keyboard(39)
        fw.rgb.update(enabled=False, mode=7)
        self.assertTrue(kb.set_rgb_matrix(enabled=True)[0])
        self.assertTrue(fw.rgb["enabled"])
        self.assertEqual(fw.rgb["mode"], 7)
        self.assertEqual(_via_writes(fw), [bytes([0x08, 3, 2, 0, 0, 0]),
                                           bytes([0x03, 0x05, 0, 0, 0, 0])])

    def test_switch_on_when_already_on_sends_only_the_read(self):
        kb, fw = _keyboard(39)
        self.assertTrue(kb.set_rgb_matrix(enabled=True)[0])
        self.assertTrue(fw.rgb["enabled"])
        self.assertEqual(_via_writes(fw), [bytes([0x08, 3, 2, 0, 0, 0])])

    def test_set_each_value(self):
        kb, fw = _keyboard(39)
        ok, _ = kb.set_rgb_matrix(effect=3, brightness=255, speed=50, hue=10, sat=200)
        self.assertEqual(fw.rgb["val"], 100)       # (255 * 101) >> 8
        self.assertTrue(ok)
        self.assertEqual(_via_writes(fw), [bytes([0x07, 3, 2, 3, 0, 0]),
                                           bytes([0x07, 3, 1, 255, 0, 0]),
                                           bytes([0x07, 3, 3, 50, 0, 0]),
                                           bytes([0x07, 3, 4, 10, 200, 0])])
        ok, state = kb.get_rgb_matrix()
        self.assertTrue(ok)
        self.assertEqual(state, {"enabled": True, "effect": 3, "brightness": 255,
                                 "speed": 50, "hue": 10, "sat": 200})

    def test_bad_arguments_send_nothing(self):
        kb, fw = _keyboard(39)
        for kw in ({"brightness": 256}, {"hue": 1}, {"enabled": False, "effect": 2},
                   {"enabled": True, "effect": 0}, {}):
            self.assertFalse(kb.set_rgb_matrix(**kw)[0], kw)
        self.assertEqual(_via_writes(fw), [])

    def test_brightness_get_then_set_keeps_every_level(self):
        kb, fw = _keyboard(39)
        for stored in range(fw.rgb_max_brightness + 1):
            fw.rgb["val"] = stored
            read = kb.get_rgb_matrix()[1]["brightness"]
            kb.set_rgb_matrix(brightness=read)
            self.assertEqual(fw.rgb["val"], stored, read)

    def test_a_reboot_restores_the_stored_rgb_and_restarts_uptime(self):
        clock = _Clock()
        kb, fw = _keyboard(39, clock)
        kb.set_rgb_matrix(effect=7, brightness=255)
        clock.t += 10
        fw.reboot()
        self.assertEqual(fw.rgb, fw.rgb_stored)
        clock.t += 1
        self.assertEqual(kb.get_uptime_ms(), (True, 1000))

    def test_device_indication_toggles(self):
        kb, fw = _keyboard(39)
        for i in range(6):
            self.assertTrue(kb.indicate_device(i)[0])
        self.assertTrue(fw.rgb["enabled"])  # six toggles: as it started
        self.assertEqual(_via_writes(fw)[5], bytes([0x03, 0x05, 5, 0, 0, 0]))

    def test_unhandled_reply_is_a_refusal(self):
        kb, fw = _keyboard(39)
        ok, reply = kb._via_request([0x08, 3, 9, 0, 0], 3)   # unknown value id
        self.assertFalse(ok)
        self.assertIsNone(reply)


class SwitchMatrixTest(unittest.TestCase):
    def test_refused_while_debug_is_off(self):
        kb, fw = _keyboard(39)
        ok, msg = kb.get_switch_matrix()
        self.assertFalse(ok)
        self.assertIn("debug mode", msg)

    def test_rows_while_debug_is_on(self):
        kb, fw = _keyboard(39)
        fw.debug_enable = True
        fw.matrix_rows = [0, 0x04, 0, 0, 0, 0x80, 0, 0, 0, 0]
        ok, rows = kb.get_switch_matrix()
        self.assertTrue(ok)
        self.assertEqual(rows, fw.matrix_rows)
        self.assertEqual(_via_writes(fw), [bytes([0x02, 0x03, 0, 0, 0, 0])])


if __name__ == "__main__":
    unittest.main()
