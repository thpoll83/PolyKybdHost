"""cmd 45 (AI) and cmd 46 (AI_CARD), protocol v31: the wire bytes, the gate, the
CLOSED state range, and a round trip through the emulated firmware."""
import unittest

from polyhost.device.command_ids import Cmd
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import (AGENT_KEYS_MIN_PROTOCOL, AGENT_PAGES_MIN_PROTOCOL,
                                       PolyKybd)


class _Settings:
    def get(self, name):
        return {"max_hid_message_before_delay": 1 << 30,
                "delay_time_after_max_hid_messages": 0,
                "hid_reconnect_retries": 1}.get(name)


def _keyboard(protocol=AGENT_KEYS_MIN_PROTOCOL):
    ds = DeviceSettings()
    fw = MockFirmware(protocol=protocol, settings=ds)
    kb = PolyKybd(ds, _Settings())
    kb.hid = MockHidHelper(fw)
    kb.protocol_version = protocol
    return kb, fw


class AgentKeysTest(unittest.TestCase):
    def test_gate(self):
        kb, fw = _keyboard(AGENT_KEYS_MIN_PROTOCOL - 1)
        for ok, msg in (kb.ai_query(), kb.ai_read_events(0),
                        kb.ai_set_keys([0] * 10, 0, [0xFFFF] * 12),
                        kb.ai_upload_card(590, bytes(360))):
            self.assertFalse(ok)
            self.assertIn("too old", msg)
        self.assertEqual(fw.refused, [])

    def test_set_keys_round_trip(self):
        kb, fw = _keyboard()
        ok, _ = kb.ai_set_keys([1, 2, 3, 4, 5, 0, 0, 0, 0, 0], 0x0B,
                               [588, 589, 590, 591, 592] + [0xFFFF] * 5 + [598, 599])
        self.assertTrue(ok)
        self.assertEqual(fw.ai_states[:5], [1, 2, 3, 4, 5])
        self.assertEqual(fw.ai_flags, 0x0B)
        self.assertEqual(fw.ai_slots[:6], [588, 589, 590, 591, 592, 0xFFFF])
        self.assertEqual(fw.ai_slots[10:], [598, 599])

    def test_a_reboot_clears_the_agent_keys(self):
        kb, fw = _keyboard()
        kb.ai_set_keys([1] * 10, 0x0B, [588] * 12)
        fw.key_attention = (1, 1, 0, 2300)
        fw.reboot()
        self.assertEqual((fw.ai_states, fw.ai_flags, fw.ai_slots, fw.key_attention),
                         ([0] * 10, 0, [0xFFFF] * 12, None))

    def test_closed_range(self):
        kb, fw = _keyboard()
        ok, msg = kb.ai_set_keys([6] + [0] * 9, 0, [0xFFFF] * 12)
        self.assertFalse(ok)
        self.assertEqual(fw.ai_states, [0] * 10)          # refused before sending
        self.assertFalse(kb.ai_set_keys([0] * 10, 0x10, [0xFFFF] * 12)[0])   # unknown flag
        self.assertFalse(kb.ai_set_keys([0] * 10, 0, [0xFFFF] * 10)[0])      # 10 slots, not 12
        ok, msg = kb.ai_set_keys([0] * 10, 0, [600] + [0xFFFF] * 11)
        self.assertFalse(ok)                               # the firmware NACKs a slot past the pool
        self.assertIn("refused", msg)

    def test_card_upload(self):
        kb, fw = _keyboard()
        data = bytes(i % 256 for i in range(360))
        ok, _ = kb.ai_upload_card(597, data)
        self.assertTrue(ok)
        self.assertEqual(bytes(fw.ai_cards[597]), data)
        self.assertFalse(kb.ai_upload_card(600, data)[0])
        self.assertFalse(kb.ai_upload_card(597, data[:10])[0])

    def test_events(self):
        kb, fw = _keyboard()
        ok, (newest, events) = kb.ai_read_events(0)
        self.assertTrue(ok)
        self.assertEqual((newest, events), (0, []))
        for key in (3, 10, 0):
            fw.ai_press(key)
        ok, (newest, events) = kb.ai_read_events(0)
        self.assertTrue(ok)
        self.assertEqual((newest, events), (3, [(1, 3), (2, 10), (3, 0)]))
        ok, (newest, events) = kb.ai_read_events(2)
        self.assertTrue(ok)
        self.assertEqual((newest, events), (3, [(3, 0)]))

    def test_query(self):
        kb, fw = _keyboard()
        fw.ai_press(4)
        ok, info = kb.ai_query()
        self.assertTrue(ok)
        self.assertEqual(info, {"ai_mode": False, "newest_seq": 1, "number_keys": 10,
                                "esc_found": True})

    def test_wire_bytes(self):
        payload = PolyKybd._ai_keys_payload([1] + [0] * 9, 0x02, [0x0255] + [0xFFFF] * 11)
        self.assertEqual(payload[0], 1)                    # op SET_KEYS
        self.assertEqual(payload[1:11], (1, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(payload[11], 0x02)                # flags: more pages
        self.assertEqual(payload[12:14], (0x55, 0x02))    # little-endian
        self.assertEqual(len(payload), 1 + 10 + 1 + 24)
        self.assertEqual(Cmd.AI.value, 45)
        self.assertEqual(Cmd.AI_CARD.value, 46)


    def test_page_bytes_follow_the_35_from_v36(self):
        kb, fw = _keyboard(AGENT_PAGES_MIN_PROTOCOL)
        sent = []
        real = kb.hid.send_and_read_validate
        kb.hid.send_and_read_validate = lambda msg, *a, **k: (sent.append(bytes(msg)), real(msg, *a, **k))[1]
        ok, _ = kb.ai_set_keys([1] + [0] * 9, 0x03, [0xFFFF] * 12, page=(1, 2, 7))
        self.assertTrue(ok)
        # report id, cmd, op, 10 states, flags, 24 slot bytes, then page, count, counter
        self.assertEqual(sent[0][2 + 36:2 + 39], bytes([1, 2, 7]))
        self.assertEqual(fw.ai_page, (1, 2, 7))

    def test_an_older_keyboard_gets_the_v35_report(self):
        # The gate is on the page bytes, not on the command: below v36 the keys still
        # go out, without them.
        kb, fw = _keyboard(AGENT_PAGES_MIN_PROTOCOL - 1)
        ok, _ = kb.ai_set_keys([2] + [0] * 9, 0x02, [0xFFFF] * 12, page=(1, 2, 7))
        self.assertTrue(ok)
        self.assertEqual(fw.ai_states[0], 2)
        self.assertEqual(fw.ai_page, (0, 0, 0))
        self.assertEqual(fw.refused, [])

    def test_a_page_not_below_its_count_is_refused(self):
        kb, fw = _keyboard(AGENT_PAGES_MIN_PROTOCOL)
        for bad in ((2, 2, 0), (1, 0, 0), (0, 256, 0), (0, 1, 256)):
            ok, msg = kb.ai_set_keys([0] * 10, 0, [0xFFFF] * 12, page=bad)
            self.assertFalse(ok, bad)
        self.assertEqual(fw.ai_page, (0, 0, 0))             # nothing reached the keyboard


if __name__ == "__main__":
    unittest.main()
