"""PolyCore.keymap_set rings the edited key once (docs/tutorials-plan.md, step 1)."""
import types
import unittest

from polyhost.core import poly_core
from polyhost.device.poly_kybd import KEY_ATTENTION_PERIOD_MIN_MS


class _Keyboard:
    def __init__(self, protocol=32, default_layer=0, write_ok=True, ring_ok=True,
                 default_ok=True):
        self.protocol = protocol
        self.default_layer = default_layer
        self.write_ok = write_ok
        self.ring_ok = ring_ok
        self.default_ok = default_ok
        self.calls = []

    def supports(self, feature):
        return feature == "key_attention" and self.protocol >= 32

    def set_dynamic_keycode(self, layer, row, col, keycode):
        self.calls.append(("set", layer, row, col, keycode))
        return (True, "ok") if self.write_ok else (False, "refused")

    def get_default_layer(self):
        self.calls.append(("default",))
        return self.default_ok, self.default_layer

    def key_attention(self, row, col, count, period_ms):
        self.calls.append(("ring", row, col, count, period_ms))
        return (True, "ok") if self.ring_ok else (False, "no display")


def _core(kb):
    core = types.SimpleNamespace(
        keeb=kb, _manual_ring_seq=0,
        log=types.SimpleNamespace(debug=lambda *a: None))
    core._device_call = lambda name, fn: fn(None)
    core._manual_ring = lambda fn: poly_core.PolyCore._manual_ring(core, fn)
    core._ring_edited_key = lambda *a: poly_core.PolyCore._ring_edited_key(core, *a)
    core._keymap_set_and_ring = (
        lambda *a: poly_core.PolyCore._keymap_set_and_ring(core, *a))
    return core


def _set(core, *args):
    return poly_core.PolyCore.keymap_set(core, *args)


class KeymapSetRingTest(unittest.TestCase):
    def test_a_write_on_the_default_layer_rings_the_key_once(self):
        kb = _Keyboard(default_layer=2)
        core = _core(kb)
        self.assertEqual(_set(core, 2, 3, 4, 0x04), (True, "ok"))
        self.assertEqual(kb.calls[-1], ("ring", 3, 4, 1, KEY_ATTENTION_PERIOD_MIN_MS))
        # The ring is a manual request: a queued MIDI guide cancel leaves it alone.
        self.assertEqual(core._manual_ring_seq, 1)

    def test_another_layer_writes_without_a_ring(self):
        kb = _Keyboard(default_layer=0)
        self.assertEqual(_set(_core(kb), 1, 3, 4, 0x04), (True, "ok"))
        self.assertEqual([c[0] for c in kb.calls], ["set", "default"])

    def test_old_firmware_writes_without_a_ring(self):
        kb = _Keyboard(protocol=31)
        self.assertEqual(_set(_core(kb), 0, 3, 4, 0x04), (True, "ok"))
        self.assertEqual([c[0] for c in kb.calls], ["set"])

    def test_a_failed_write_does_not_ring(self):
        kb = _Keyboard(write_ok=False)
        self.assertEqual(_set(_core(kb), 0, 3, 4, 0x04), (False, "refused"))
        self.assertEqual([c[0] for c in kb.calls], ["set"])

    def test_an_unreadable_default_layer_does_not_ring(self):
        kb = _Keyboard(default_ok=False)
        self.assertTrue(_set(_core(kb), 0, 3, 4, 0x04)[0])
        self.assertNotIn("ring", [c[0] for c in kb.calls])

    def test_a_refused_ring_keeps_the_write_result(self):
        kb = _Keyboard(ring_ok=False)
        core = _core(kb)
        self.assertEqual(_set(core, 0, 3, 4, 0x04), (True, "ok"))
        self.assertEqual(core._manual_ring_seq, 0)

    def test_string_arguments_from_the_control_socket(self):
        kb = _Keyboard()
        self.assertTrue(_set(_core(kb), "0", "3", "4", "4")[0])
        self.assertEqual(kb.calls[0], ("set", 0, 3, 4, 4))

    def test_bad_arguments_are_refused_before_the_device(self):
        kb = _Keyboard()
        ok, _msg = _set(_core(kb), 0, "x", 4, 4)
        self.assertFalse(ok)
        self.assertEqual(kb.calls, [])


if __name__ == "__main__":
    unittest.main()
