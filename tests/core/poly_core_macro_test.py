"""PolyCore's macro API against the mock device, end to end.

The mock is backed by a real byte buffer rather than a dict of strings, so the
NUL-delimited packing -- which is the whole point of the encoding -- is genuinely
exercised here rather than mocked away. That matters because the failure this guards
against is a neighbouring macro being corrupted by a write to the one before it, which
a per-macro mock could never show.
"""

import unittest
from unittest.mock import MagicMock

from polyhost.core.poly_core import PolyCore
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.poly_kybd_mock import PolyKybdMock


def _core_for(keeb):
    """A real PolyCore with the worker hop replaced by a direct call.

    `_device_call` normally marshals onto the HID worker thread; here it runs the
    lambda inline, so these tests exercise the real macro_list / macro_set logic
    without a thread or a device.

    This deliberately builds a REAL PolyCore rather than subclassing it with a
    stub __init__ -- a subclass that skips the base constructor leaves every other
    attribute unset, so a test would pass while touching an object no production
    code path could produce (and CodeQL flags exactly that).
    """
    core = PolyCore(MagicMock(), start_worker=False)
    core.keeb = keeb
    core._device_call = lambda name, fn: fn(None)
    return core


class MacroCoreTest(unittest.TestCase):
    def setUp(self):
        self.keeb = PolyKybdMock(DeviceSettings())
        self.core = _core_for(self.keeb)

    def test_a_fresh_keyboard_lists_empty_macros(self):
        ok, info = self.core.macro_list()
        self.assertTrue(ok)
        self.assertEqual(len(info["macros"]), info["count"])
        self.assertEqual(info["used"], 0)
        self.assertTrue(all(m["text"] == "" for m in info["macros"]))

    def test_set_then_list_round_trips_text_and_label(self):
        ok, _ = self.core.macro_set(3, text="tom@example.com", label="email")
        self.assertTrue(ok)
        ok, info = self.core.macro_list()
        self.assertTrue(ok)
        self.assertEqual(info["macros"][3]["text"], "tom@example.com")
        self.assertEqual(info["macros"][3]["label"], "email")

    def test_editing_one_macro_leaves_its_neighbours_alone(self):
        """The bodies share one buffer, so writing macro 1 rewrites everything after
        it. This is the corruption the whole read-modify-write shape exists to avoid."""
        for i, word in enumerate(["alpha", "beta", "gamma"]):
            self.assertTrue(self.core.macro_set(i, text=word)[0])
        self.assertTrue(self.core.macro_set(1, text="a much longer replacement")[0])
        ok, info = self.core.macro_list()
        self.assertTrue(ok)
        self.assertEqual([m["text"] for m in info["macros"][:3]],
                         ["alpha", "a much longer replacement", "gamma"])

    def test_a_label_only_edit_does_not_touch_the_bodies(self):
        self.assertTrue(self.core.macro_set(0, text="hello")[0])
        self.keeb.calls.clear()
        self.assertTrue(self.core.macro_set(0, label="hi")[0])
        # No buffer write at all -- re-streaming ~2 KB to change twelve bytes would be
        # both slow and a chance to corrupt a body that was already fine.
        self.assertNotIn("write_macro_buffer", [c[0] for c in self.keeb.calls])

    def test_used_bytes_grow_with_the_macros(self):
        _, before = self.core.macro_list()
        self.assertTrue(self.core.macro_set(0, text="x" * 40)[0])
        _, after = self.core.macro_list()
        self.assertGreater(after["used"], before["used"])

    def test_clear_empties_both_halves(self):
        self.assertTrue(self.core.macro_set(2, text="bye", label="wave")[0])
        self.assertTrue(self.core.macro_clear(2)[0])
        ok, info = self.core.macro_list()
        self.assertTrue(ok)
        self.assertEqual(info["macros"][2]["text"], "")
        self.assertEqual(info["macros"][2]["label"], "")

    def test_untypeable_text_is_refused_before_anything_is_written(self):
        self.assertTrue(self.core.macro_set(0, text="safe")[0])
        self.keeb.calls.clear()
        ok, msg = self.core.macro_set(0, text="café")
        self.assertFalse(ok)
        self.assertNotIn("write_macro_buffer", [c[0] for c in self.keeb.calls])
        # ...and the macro that was there is untouched.
        _, info = self.core.macro_list()
        self.assertEqual(info["macros"][0]["text"], "safe")

    def test_an_out_of_range_id_is_refused(self):
        ok, msg = self.core.macro_set(99, text="x")
        self.assertFalse(ok)
        self.assertIn("range", msg)

    def test_a_macro_too_big_for_the_buffer_is_refused_by_name(self):
        ok, msg = self.core.macro_set(0, text="x" * 4000)
        self.assertFalse(ok)
        self.assertIn("bytes", msg)

    def test_steps_can_carry_a_chord(self):
        ok, _ = self.core.macro_set(0, steps=[
            {"kind": "down", "code": 0xE0},
            {"kind": "tap", "code": 0x06},
            {"kind": "up", "code": 0xE0},
        ])
        self.assertTrue(ok)
        _, info = self.core.macro_list()
        m = info["macros"][0]
        # Not expressible as text, and reported as such rather than as an empty macro.
        self.assertIsNone(m["text"])
        self.assertEqual([s["kind"] for s in m["steps"]], ["down", "tap", "up"])


if __name__ == "__main__":
    unittest.main()
