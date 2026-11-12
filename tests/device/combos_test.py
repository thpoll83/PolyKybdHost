"""Runtime combos and tap dance (cmd 48, protocol v33+): the gate, the wire bytes,
the closed validation and the round trip against the emulated keyboard. The
firmware side is qmk_firmware keyboards/polykybd/poly_combos.c and
base/combo_store.h."""

import unittest
import unittest.mock as mock

from polyhost.device.command_ids import Combos
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.mock_firmware import MockFirmware, MockHidHelper
from polyhost.device.poly_kybd import (COMBOS_MIN_PROTOCOL, FEATURE_MIN_PROTOCOL, PolyKybd,
                                       protocol_supports)
from polyhost.settings import PolySettings
from polyhost._version import __protocol__

KC_J, KC_K, KC_ESC, KC_CAPS = 0x0D, 0x0E, 0x29, 0x39
MO1, TG2 = 0x5221, 0x5262
MT_LSFT_A = 0x2204


class CombosValidationTest(unittest.TestCase):
    def test_combo_records(self):
        self.assertTrue(Combos.combo_valid([], 0))                    # empty slot
        self.assertTrue(Combos.combo_valid([KC_J, KC_K], KC_ESC))
        self.assertTrue(Combos.combo_valid([KC_J, KC_K, 0x0F, MT_LSFT_A], 0x7700))
        self.assertFalse(Combos.combo_valid([KC_J], KC_ESC))          # one key
        self.assertFalse(Combos.combo_valid([KC_J, 0, KC_K], KC_ESC))  # a gap
        self.assertFalse(Combos.combo_valid([KC_J, KC_K], 0))         # no result
        self.assertFalse(Combos.combo_valid([KC_J] * 5, KC_ESC))      # five keys
        self.assertFalse(Combos.combo_valid([KC_J, KC_J], KC_ESC))    # the same key twice
        self.assertFalse(Combos.combo_valid([KC_J, True], KC_ESC))

    def test_tap_dance_records(self):
        self.assertTrue(Combos.tap_dance_valid(0, 0, 0, 0, 0))
        self.assertTrue(Combos.tap_dance_valid(KC_ESC, MO1, KC_CAPS, TG2, 250))
        self.assertTrue(Combos.tap_dance_valid(0x0226, 0, 0, 0, 0))   # S(KC_9)
        self.assertFalse(Combos.tap_dance_valid(KC_ESC, MT_LSFT_A, 0, 0, 0))
        self.assertFalse(Combos.tap_dance_valid(0x7700, 0, 0, 0, 0))  # macro
        for term in (90, 510, 205, -10):
            self.assertFalse(Combos.tap_dance_valid(KC_ESC, 0, 0, 0, term), term)


class CombosGateTest(unittest.TestCase):
    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = mock.MagicMock()
        return keeb

    def test_feature_threshold(self):
        self.assertEqual(COMBOS_MIN_PROTOCOL, 33)
        self.assertEqual(FEATURE_MIN_PROTOCOL["combos"], COMBOS_MIN_PROTOCOL)
        self.assertFalse(protocol_supports(COMBOS_MIN_PROTOCOL - 1, "combos"))
        self.assertGreaterEqual(__protocol__, COMBOS_MIN_PROTOCOL)

    def test_old_firmware_refuses_without_touching_the_device(self):
        keeb = self._keeb(COMBOS_MIN_PROTOCOL - 1)
        for call in (keeb.get_combo_info, lambda: keeb.get_combo_record(0, 0),
                     lambda: keeb.set_combo_record(0, 0, [KC_J, KC_K, 0, 0, KC_ESC]),
                     keeb.commit_combos):
            ok, msg = call()
            self.assertFalse(ok)
            self.assertIn("too old", msg)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_set_sends_kind_index_and_little_endian_words(self):
        keeb = self._keeb(COMBOS_MIN_PROTOCOL)
        reply = bytes([0x50, 48, ord("."), 1, 3]) + bytes([0x29, 0, 0x21, 0x52, 0x39, 0, 0x62, 0x52, 0xFA, 0])
        keeb.hid.send_and_read_validate.return_value = (True, reply)
        ok, words = keeb.set_combo_record(Combos.KIND_TAP_DANCE, 3, [KC_ESC, MO1, KC_CAPS, TG2, 250])
        self.assertTrue(ok)
        report = keeb.hid.send_and_read_validate.call_args.args[0]
        self.assertEqual(bytes(report[:15]),
                         bytes([0x50, 48, 2, 1, 3, 0x29, 0, 0x21, 0x52, 0x39, 0, 0x62, 0x52, 0xFA, 0]))
        self.assertEqual(words, [KC_ESC, MO1, KC_CAPS, TG2, 250])

    def test_invalid_records_are_refused_before_io(self):
        keeb = self._keeb(COMBOS_MIN_PROTOCOL)
        for kind, index, words in ((0, 0, [KC_J, 0, 0, 0, KC_ESC]), (0, 16, [KC_J, KC_K, 0, 0, KC_ESC]),
                                   (1, 0, [KC_ESC, MT_LSFT_A, 0, 0, 0]), (1, 0, [KC_ESC, 0, 0, 0, 205]),
                                   (2, 0, [0] * 5), (0, 0, [1, 2, 3])):
            with self.subTest(kind=kind, index=index, words=words):
                ok, _ = keeb.set_combo_record(kind, index, words)
                self.assertFalse(ok)
        keeb.hid.send_and_read_validate.assert_not_called()

    def test_a_nack_is_a_failure(self):
        keeb = self._keeb(COMBOS_MIN_PROTOCOL)
        keeb.hid.send_and_read_validate.return_value = (True, bytes([0x50, 48, ord("!")]) + bytes(12))
        ok, _ = keeb.set_combo_record(0, 0, [KC_J, KC_K, 0, 0, KC_ESC])
        self.assertFalse(ok)
        ok, _ = keeb.commit_combos()
        self.assertFalse(ok)


class CombosMockFirmwareTest(unittest.TestCase):
    def _keyboard(self, protocol=__protocol__):
        fw = MockFirmware(protocol)
        kb = PolyKybd(DeviceSettings(), PolySettings())
        kb.hid = MockHidHelper(fw)
        kb.protocol_version = protocol
        return kb, fw

    def test_round_trip_and_commit(self):
        kb, fw = self._keyboard()
        ok, info = kb.get_combo_info()
        self.assertTrue(ok)
        self.assertEqual((info["available"], info["combo_slots"], info["tap_dance_slots"]), (True, 16, 16))
        ok, _ = kb.set_combo_record(Combos.KIND_COMBO, 2, [KC_J, KC_K, 0, 0, KC_ESC])
        self.assertTrue(ok)
        ok, words = kb.get_combo_record(Combos.KIND_COMBO, 2)
        self.assertEqual(words, [KC_J, KC_K, 0, 0, KC_ESC])
        self.assertIsNone(fw.combos_flash)                # set is RAM only
        ok, res = kb.commit_combos()
        self.assertTrue(ok)
        self.assertTrue(res["other_half"])
        self.assertEqual(fw.combos_flash[Combos.KIND_COMBO][2], [KC_J, KC_K, 0, 0, KC_ESC])

    def test_a_reboot_keeps_only_what_was_committed(self):
        kb, fw = self._keyboard()
        kb.set_combo_record(Combos.KIND_COMBO, 0, [KC_J, KC_K, 0, 0, KC_ESC])
        kb.commit_combos()
        kb.set_combo_record(Combos.KIND_COMBO, 0, [KC_J, KC_K, 0, 0, KC_CAPS])
        fw.reboot()
        _, words = kb.get_combo_record(Combos.KIND_COMBO, 0)
        self.assertEqual(words, [KC_J, KC_K, 0, 0, KC_ESC])

    def test_a_reboot_with_nothing_committed_empties_the_tables(self):
        kb, fw = self._keyboard()
        kb.set_combo_record(Combos.KIND_COMBO, 0, [KC_J, KC_K, 0, 0, KC_ESC])
        fw.reboot()
        _, words = kb.get_combo_record(Combos.KIND_COMBO, 0)
        self.assertEqual(words, [0, 0, 0, 0, 0])

    def test_a_bad_record_changes_nothing(self):
        kb, fw = self._keyboard()
        kb.set_combo_record(Combos.KIND_TAP_DANCE, 0, [KC_ESC, 0, 0, 0, 0])
        # Bypass the host's own check to reach the emulated firmware.
        ok, reply = kb.hid.send_and_read_validate(
            bytearray([0x50, 48, 2, 1, 0, 0x29, 0, 0x04, 0x22, 0, 0, 0, 0, 0, 0]), 100, b"P0")
        self.assertEqual(reply[2:3], b"!")
        ok, words = kb.get_combo_record(Combos.KIND_TAP_DANCE, 0)
        self.assertEqual(words, [KC_ESC, 0, 0, 0, 0])

    def test_older_keyboard_nacks_the_command(self):
        kb, _ = self._keyboard(COMBOS_MIN_PROTOCOL - 1)
        kb.protocol_version = COMBOS_MIN_PROTOCOL   # pretend the gate is wrong
        ok, _ = kb.get_combo_info()
        self.assertTrue(ok)
        _, info = kb.get_combo_info()
        self.assertFalse(info["available"])


class CombosPolyKybdMockTest(unittest.TestCase):
    def test_a_firmware_nack_reaches_the_caller(self):
        from polyhost.device.mock_firmware import FaultPlan
        from polyhost.device.poly_kybd_mock import PolyKybdMock
        kb = PolyKybdMock(DeviceSettings(), protocol=__protocol__,
                          faults=FaultPlan(nack={48: 1}))
        kb.connect()
        ok, _ = kb.set_combo_record(Combos.KIND_COMBO, 0, [KC_J, KC_K, 0, 0, KC_ESC])
        self.assertFalse(ok)
        ok, words = kb.get_combo_record(Combos.KIND_COMBO, 0)
        self.assertEqual((ok, words), (True, [0, 0, 0, 0, 0]))


class CombosSafeModeTest(unittest.TestCase):
    def test_restricted_mode_refuses_before_any_device_call(self):
        from polyhost.core.poly_core import PolyCore, SAFE_MODE_REFUSAL
        core = PolyCore.__new__(PolyCore)
        core.safe_mode = True
        core.keeb = mock.MagicMock()
        core._device_call = mock.MagicMock()
        self.assertEqual(core.combos_get(), (False, SAFE_MODE_REFUSAL))
        self.assertEqual(core.combos_set(combos=[{"slot": 0, "keys": [], "result": 0}]),
                         (False, SAFE_MODE_REFUSAL))
        core._device_call.assert_not_called()


class CombosCoreTest(unittest.TestCase):
    """PolyCore.combos_get / combos_set over the emulated keyboard."""

    def _core(self):
        from polyhost.core.poly_core import PolyCore
        fw = MockFirmware(__protocol__)
        kb = PolyKybd(DeviceSettings(), PolySettings())
        kb.hid = MockHidHelper(fw)
        kb.protocol_version = __protocol__
        core = PolyCore.__new__(PolyCore)
        core.safe_mode = False
        core.keeb = kb

        def device_call(_name, fn):
            result = fn(None)
            return (bool(result[0]), result[1]) if isinstance(result, tuple) else (True, result)
        core._device_call = device_call
        return core, fw

    def test_get_lists_every_slot(self):
        core, _fw = self._core()
        ok, data = core.combos_get()
        self.assertTrue(ok)
        self.assertTrue(data["available"])
        self.assertEqual((len(data["combos"]), len(data["tap_dances"])), (16, 16))
        self.assertEqual(data["combos"][0], {"slot": 0, "keys": [], "result": 0})

    def test_set_stores_and_commits_both_kinds(self):
        core, fw = self._core()
        ok, res = core.combos_set(
            combos=[{"slot": 1, "keys": [KC_J, KC_K], "result": KC_ESC}],
            tap_dances=[{"slot": 2, "on_tap": KC_ESC, "on_hold": MO1, "term_ms": 200}])
        self.assertTrue(ok)
        self.assertTrue(res["other_half"])
        self.assertEqual(fw.combos_flash[Combos.KIND_COMBO][1], [KC_J, KC_K, 0, 0, KC_ESC])
        self.assertEqual(fw.combos_flash[Combos.KIND_TAP_DANCE][2], [KC_ESC, MO1, 0, 0, 200])
        _ok, data = core.combos_get()
        self.assertEqual(data["combos"][1]["keys"], [KC_J, KC_K])

    def test_a_slot_with_no_keys_is_cleared(self):
        core, fw = self._core()
        core.combos_set(combos=[{"slot": 0, "keys": [KC_J, KC_K], "result": KC_ESC}])
        ok, _res = core.combos_set(combos=[{"slot": 0, "keys": [], "result": KC_ESC}])
        self.assertTrue(ok)
        self.assertEqual(fw.combos_flash[Combos.KIND_COMBO][0], [0, 0, 0, 0, 0])

    def test_a_refused_tap_dance_sends_nothing(self):
        core, fw = self._core()
        ok, msg = core.combos_set(
            combos=[{"slot": 0, "keys": [KC_J, KC_K], "result": KC_ESC}],
            tap_dances=[{"slot": 0, "on_tap": MT_LSFT_A}])
        self.assertFalse(ok)
        self.assertIn("Tap dance 1", msg)
        _ok, words = core.keeb.get_combo_record(Combos.KIND_COMBO, 0)
        self.assertEqual(words, [0, 0, 0, 0, 0])
        self.assertIsNone(getattr(fw, "combos_flash", None))

    def test_a_write_that_fails_part_way_puts_the_earlier_records_back(self):
        core, _fw = self._core()
        real_set = core.keeb.set_combo_record
        calls = []

        def flaky_set(kind, slot, words):
            calls.append((kind, slot, list(words)))
            if len(calls) == 2:
                return False, "link dropped"
            return real_set(kind, slot, words)
        core.keeb.set_combo_record = flaky_set
        ok, msg = core.combos_set(combos=[{"slot": 0, "keys": [KC_J, KC_K], "result": KC_ESC},
                                          {"slot": 1, "keys": [KC_J, TG2], "result": KC_CAPS}])
        self.assertFalse(ok)
        self.assertEqual(msg, "link dropped")
        _ok, words = real_set.__self__.get_combo_record(Combos.KIND_COMBO, 0)
        self.assertEqual(words, [0, 0, 0, 0, 0])     # the first record was put back

    def test_a_restore_that_fails_is_reported(self):
        core, _fw = self._core()
        real_set = core.keeb.set_combo_record
        calls = []

        def flaky_set(kind, slot, words):
            calls.append((kind, slot, list(words)))
            if len(calls) >= 2:          # the second write and the restore both fail
                return False, "link dropped"
            return real_set(kind, slot, words)
        core.keeb.set_combo_record = flaky_set
        ok, msg = core.combos_set(combos=[{"slot": 0, "keys": [KC_J, KC_K], "result": KC_ESC},
                                          {"slot": 1, "keys": [KC_J, TG2], "result": KC_CAPS}])
        self.assertFalse(ok)
        self.assertTrue(msg.startswith("link dropped. 1 earlier record(s) could not be put back"))
        self.assertEqual(len(calls), 3)  # write, failed write, failed restore


if __name__ == "__main__":
    unittest.main()
