"""cmd 49 HOST TUTORIAL, protocol v35: the wire bytes, the gate, and a round trip
through the emulated firmware (the same refusals as base/host_tutorial_plan.c)."""
import unittest

from polyhost.device.command_ids import Cmd, HostTutorial
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import HOST_TUTORIAL_MIN_PROTOCOL, PolyKybd


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0,
                "hid_reconnect_retries": 1}.get(name)


def _keyboard(protocol=HOST_TUTORIAL_MIN_PROTOCOL):
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
        return True, b"P\x31." + bytes(61)


class HostTutorialTest(unittest.TestCase):
    def test_gate(self):
        self.assertEqual(HOST_TUTORIAL_MIN_PROTOCOL, 35)
        kb, fw = _keyboard(protocol=34)
        for ok, msg in (kb.tutorial_info(), kb.tutorial_text("a"), kb.tutorial_spotlight([]),
                        kb.tutorial_reveal(0, 0), kb.tutorial_arm([]), kb.tutorial_poll(),
                        kb.tutorial_end()):
            self.assertFalse(ok)
            self.assertIn("too old", msg)
        self.assertEqual(fw.refused, [])

    def test_wire_bytes(self):
        kb, _ = _keyboard()
        rec = _Recorder()
        kb.hid = rec
        self.assertEqual(Cmd.HOST_TUTORIAL.value, 49)
        kb.tutorial_text("Hi", "Fn")
        kb.tutorial_spotlight([(2, 0), (9, 7)])
        kb.tutorial_spotlight(None)
        kb.tutorial_reveal(9, 0)
        kb.tutorial_arm([(1, 2, 0), (3, 0x08, 0x7E)])
        kb.tutorial_poll()
        kb.tutorial_end()
        kb.tutorial_info()
        text, spot, off, reveal, arm, poll, end, info = rec.sent
        # report id 'P', cmd 49, op, then the op's bytes
        self.assertEqual(text[:10], b"P\x31\x01\x02Hi\x02Fn")
        mask = bytearray(10)
        mask[2] = 0x01            # (2, 0): bit 16 on an 8-column matrix
        mask[9] = 0x80            # (9, 7): bit 79
        self.assertEqual(spot[:14], b"P\x31\x02\x01" + bytes(mask))
        self.assertEqual(off[:14], b"P\x31\x02\x00" + bytes(10))
        self.assertEqual(reveal[:5], bytes([0x50, 49, 3, 9, 0]))
        self.assertEqual(arm[:10], bytes([0x50, 49, 4, 2, 1, 2, 0, 3, 0x08, 0x7E]))
        self.assertEqual(poll[:3], bytes([0x50, 49, 5]))
        self.assertEqual(end[:3], bytes([0x50, 49, 6]))
        self.assertEqual(info[:3], bytes([0x50, 49, 0]))

    def test_round_trip(self):
        kb, fw = _keyboard()
        ok, info = kb.tutorial_info()
        self.assertTrue(ok)
        self.assertEqual(info, {"ops": 0x7F, "max_conds": 4, "watchdog_s": 10,
                                "text_bytes": HostTutorial.TEXT_BYTES})
        self.assertEqual(kb.tutorial_text("Hold Fn", ""), (True, "ok"))
        self.assertEqual(fw.tutorial_text, ("Hold Fn", ""))
        self.assertEqual(kb.tutorial_spotlight([(2, 0)]), (True, "ok"))
        self.assertEqual(fw.tutorial_spotlight, {(2, 0)})
        self.assertEqual(kb.tutorial_arm([(HostTutorial.COND_LAYER, 8, 0),
                                          (HostTutorial.COND_KEY, 2, 0)]), (True, "ok"))
        ok, poll = kb.tutorial_poll()
        self.assertEqual(poll["armed"], 2)
        self.assertEqual(poll["matched"], 0)
        self.assertEqual(poll["flags"], HostTutorial.POLL_TEXT | HostTutorial.POLL_SPOT |
                         HostTutorial.POLL_ARMED)
        fw.tutorial_press(2, 0, 0x5225)
        fw.tutorial_layers(1 << 8)
        self.assertEqual(kb.tutorial_poll()[1]["matched"], 0x03)
        self.assertEqual(kb.tutorial_end(), (True, "ok"))
        self.assertEqual(fw.tutorial_text, ("", ""))
        self.assertIsNone(fw.tutorial_spotlight)
        self.assertEqual(kb.tutorial_poll()[1]["flags"], 0)

    def test_host_side_refusals(self):
        kb, fw = _keyboard()
        rec = _Recorder()
        kb.hid = rec
        self.assertFalse(kb.tutorial_text("Größe")[0])          # not ASCII
        self.assertFalse(kb.tutorial_text("tab\there")[0])      # a control character
        self.assertFalse(kb.tutorial_text("i" * 30, "i" * 30)[0])   # 60 > 59 bytes
        self.assertFalse(kb.tutorial_spotlight([(10, 0)])[0])    # no such row
        self.assertFalse(kb.tutorial_arm([(1, 0, 0)] * 5)[0])    # more than 4
        self.assertFalse(kb.tutorial_arm([(1, 256, 0)])[0])
        self.assertEqual(rec.sent, [])
        self.assertTrue(kb.tutorial_text("i" * 29, "i" * 30)[0])   # 59 bytes fit

    def test_keyboard_refusals(self):
        kb, fw = _keyboard()
        ok, msg = kb.tutorial_arm([(2, 13, 0)])                  # no layer 13
        self.assertFalse(ok)
        self.assertIn("refused", msg)
        self.assertFalse(kb.tutorial_arm([(7, 0, 0)])[0])        # unknown kind
        self.assertFalse(kb.tutorial_reveal(12, 0)[0])



class EmojiModeTest(unittest.TestCase):
    """cmd 49 op 7 (v37): the tutorial sets the emoji layer's mode; END restores it."""

    def test_gate(self):
        from polyhost.device.poly_kybd import TUTORIAL_EMOJI_MODE_MIN_PROTOCOL
        self.assertEqual(TUTORIAL_EMOJI_MODE_MIN_PROTOCOL, 37)
        kb, fw = _keyboard(protocol=36)
        ok, msg = kb.tutorial_emoji_mode(True)
        self.assertFalse(ok)
        self.assertIn("too old", msg)
        self.assertTrue(kb.tutorial_text("a")[0])       # the rest of cmd 49 still works
        self.assertEqual(fw.refused, [])

    def test_wire_bytes(self):
        kb, _ = _keyboard(protocol=37)
        rec = _Recorder()
        kb.hid = rec
        kb.tutorial_emoji_mode(True)
        kb.tutorial_emoji_mode(False)
        kb.tutorial_emoji_mode(None)
        # report id 'P', cmd 49, op 7, then search 1 / tab 0 / query 0xFF
        self.assertEqual([m[:4] for m in rec.sent],
                         [bytes([0x50, 49, 7, 1]), bytes([0x50, 49, 7, 0]),
                          bytes([0x50, 49, 7, 0xFF])])

    def test_set_then_end_restores(self):
        kb, fw = _keyboard(protocol=37)
        self.assertEqual(kb.tutorial_emoji_mode(None), (True, False))
        self.assertEqual(kb.tutorial_emoji_mode(True), (True, False))   # the mode before
        self.assertTrue(fw.emoji_search_mode)
        self.assertEqual(kb.tutorial_emoji_mode(False), (True, True))
        self.assertTrue(kb.tutorial_end()[0])
        self.assertFalse(fw.emoji_search_mode)          # the mode before the first set
        fw.emoji_search_mode = True
        kb.tutorial_emoji_mode(False)
        kb.tutorial_end()
        self.assertTrue(fw.emoji_search_mode)

    def test_refused_without_a_dictionary(self):
        kb, fw = _keyboard(protocol=37)
        fw.emoji_dict = False
        ok, msg = kb.tutorial_emoji_mode(True)
        self.assertFalse(ok)
        self.assertIn("refused", msg)
        self.assertTrue(kb.tutorial_emoji_mode(None)[0])   # a query is still answered


if __name__ == "__main__":
    unittest.main()
