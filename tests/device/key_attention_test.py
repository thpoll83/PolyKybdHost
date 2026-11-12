"""cmd 47 KEY ATTENTION, protocol v32: the wire bytes, the gate, the CLOSED period
range, and a round trip through the emulated firmware."""
import unittest

from polyhost.device.command_ids import Cmd
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import KEY_ATTENTION_MIN_PROTOCOL, PolyKybd


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0,
                "hid_reconnect_retries": 1}.get(name)


def _keyboard(protocol=KEY_ATTENTION_MIN_PROTOCOL):
    ds = DeviceSettings()
    fw = MockFirmware(protocol=protocol, settings=ds)
    kb = PolyKybd(ds, _Settings())
    kb.hid = MockHidHelper(fw)
    kb.protocol_version = protocol
    return kb, fw


class _Recorder:
    def __init__(self):
        self.sent = []

    def send_and_read_validate(self, msg, timeout, validate):
        self.sent.append(bytes(msg))
        return True, b"P\x2f."


class KeyAttentionTest(unittest.TestCase):
    def test_gate(self):
        kb, fw = _keyboard(KEY_ATTENTION_MIN_PROTOCOL - 1)
        for ok, msg in (kb.key_attention(0, 1), kb.key_attention_cancel()):
            self.assertFalse(ok)
            self.assertIn("too old", msg)
        self.assertEqual(fw.refused, [])

    def test_round_trip_and_cancel(self):
        kb, fw = _keyboard()
        self.assertEqual(kb.key_attention(4, 3, count=0, period_ms=2300), (True, "ok"))
        self.assertEqual(fw.key_attention, (4, 3, 0, 2300))
        self.assertEqual(kb.key_attention_cancel(), (True, "ok"))
        self.assertIsNone(fw.key_attention)

    def test_period_range_is_closed(self):
        kb, fw = _keyboard()
        for period in (2200, 10100):
            ok, msg = kb.key_attention(0, 1, period_ms=period)
            self.assertFalse(ok)
            self.assertIn("period", msg)
        self.assertIsNone(fw.key_attention)
        ok, msg = kb.key_attention(99, 1)              # the keyboard NACKs it
        self.assertFalse(ok)
        self.assertIn("refused", msg)

    def test_wire_bytes(self):
        kb, _ = _keyboard()
        rec = _Recorder()
        kb.hid = rec
        kb.key_attention(5, 2, count=7, period_ms=4000)
        kb.key_attention_cancel()
        start, cancel = rec.sent
        self.assertEqual(Cmd.KEY_ATTENTION.value, 47)
        # report id, cmd, op START, row, col, count, period / 100 ms
        self.assertEqual(start[1:7], bytes([47, 0, 5, 2, 7, 40]))
        self.assertEqual(cancel[1:3], bytes([47, 1]))


if __name__ == "__main__":
    unittest.main()
