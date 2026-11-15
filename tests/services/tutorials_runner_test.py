"""services/tutorials/runner: which step rings what, and when it ends."""
import types
import unittest

from polyhost.services.tutorials.loader import parse_script
from polyhost.services.tutorials.runner import RING_COUNT, RING_PERIOD_MS, TutorialRun

ROWS, COLS = 2, 3
MO1, TO2, KC_A, KC_B = 0x5221, 0x5202, 0x04, 0x05
# Layer 0 (Base): MO(1) at (0, 0), A at (1, 1). Layer 1 (Fn): TO(2) at (1, 2), B at
# (0, 2). Layer 2 (MIDI): B at (0, 1).
BUFFER = [MO1, 0, 0, 0, KC_A, 0,
          0, 0, KC_B, 0, 0, TO2,
          0, KC_B, 0, 0, 0, 0]


class _Keyboard:
    def __init__(self, protocol=34, buffer=BUFFER, base=0):
        self.protocol_version = protocol
        self.device_settings = types.SimpleNamespace(MATRIX_ROWS=ROWS, MATRIX_COLUMNS=COLS)
        self.buffer = buffer
        self.base = base
        self.calls = []
        self.refuse_ring = False

    def supports(self, feature):
        return self.protocol_version >= {"key_attention": 32, "key_guide": 34}[feature]

    def get_layer_names(self):
        self.calls.append(("names",))
        return True, ["Base", "Fn", "MIDI"]

    def get_default_layer(self):
        return True, self.base

    def get_dynamic_buffer(self):
        self.calls.append(("buffer",))
        return True, bytes() if self.buffer is None else self.buffer

    def key_attention(self, row, col, count, period_ms):
        self.calls.append(("ring", row, col, count, period_ms))
        return (False, "no display") if self.refuse_ring else (True, "ok")

    def key_guide(self, steps, target, count, period_ms):
        self.calls.append(("guide", [tuple(s) for s in steps], target, count, period_ms))
        return True, "ok"

    def key_attention_cancel(self):
        self.calls.append(("cancel",))
        return True, "ok"

    def rings(self):
        return [c for c in self.calls if c[0] in ("ring", "guide", "cancel")]


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def _run(steps, kb=None, clock=None, **script):
    tutorial = parse_script({"id": "t", "category": "other", "title": "T",
                             "steps": steps, **script})
    kb = kb or _Keyboard()
    return TutorialRun(tutorial, kb, clock=clock or _Clock()), kb


class StartTest(unittest.TestCase):
    def test_old_firmware_is_refused(self):
        run, kb = _run([{"say": "x"}], _Keyboard(protocol=31))
        ok, msg = run.start()
        self.assertFalse(ok)
        self.assertIn("32", msg)
        self.assertEqual(kb.calls, [])

    def test_min_protocol_of_the_script(self):
        run, _kb = _run([{"say": "x"}], _Keyboard(protocol=34), min_protocol=35)
        self.assertFalse(run.start()[0])

    def test_a_step_without_a_ring_reads_no_keymap(self):
        run, kb = _run([{"say": "x"}, {"point": {"key": [1, 2]}}])
        self.assertTrue(run.start()[0])
        self.assertEqual(kb.calls, [])
        run.next()
        self.assertEqual(kb.calls, [("ring", 1, 2, RING_COUNT, RING_PERIOD_MS)])


class PointTest(unittest.TestCase):
    def test_a_keycode_on_the_base_layer_first(self):
        # B is on Fn at (0, 2) and on MIDI at (0, 1); with MIDI as the base layer the
        # MIDI one is found.
        run, kb = _run([{"point": {"keycode": KC_B}}], _Keyboard(base=2))
        run.start()
        self.assertEqual(kb.rings()[-1][:3], ("ring", 0, 1))

    def test_a_keycode_on_another_layer(self):
        run, kb = _run([{"point": {"keycode": KC_B}}])
        run.start()
        self.assertEqual(kb.rings()[-1][:3], ("ring", 0, 2))
        self.assertEqual(run.state()["ring"], "point")

    def test_a_layer_key_is_the_first_key_of_the_path(self):
        run, kb = _run([{"point": {"layer_key": "midi"}}])
        run.start()
        self.assertEqual(kb.rings()[-1][:3], ("ring", 0, 0))      # MO(1) on Base

    def test_the_keymap_is_read_once_per_run(self):
        run, kb = _run([{"point": {"keycode": KC_A}}, {"point": {"keycode": KC_B}},
                        {"guide_to_layer": "MIDI"}])
        run.start()
        run.next()
        run.next()
        self.assertEqual(kb.calls.count(("buffer",)), 1)

    def test_a_missing_key_cancels_the_ring_and_says_why(self):
        run, kb = _run([{"point": {"keycode": KC_A}}, {"point": {"keycode": 0x29}}])
        run.start()
        run.next()
        self.assertEqual(kb.rings()[-1], ("cancel",))
        state = run.state()
        self.assertIsNone(state["ring"])
        self.assertIn("0x0029", state["ring_error"])

    def test_an_unknown_layer(self):
        run, _kb = _run([{"point": {"layer_key": "Numpad"}}])
        run.start()
        self.assertIn("Numpad", run.state()["ring_error"])

    def test_a_refused_ring(self):
        kb = _Keyboard()
        kb.refuse_ring = True
        run, _kb = _run([{"point": {"key": [0, 0]}}, {"say": "x"}], kb)
        run.start()
        self.assertEqual(run.state()["ring_error"], "no display")
        run.next()
        # Nothing rang, so nothing is cancelled.
        self.assertNotIn(("cancel",), kb.calls)

    def test_a_step_without_a_ring_cancels_the_one_before(self):
        run, kb = _run([{"point": {"key": [0, 0]}}, {"say": "x"}])
        run.start()
        run.next()
        self.assertEqual(kb.rings()[-1], ("cancel",))


class GuideTest(unittest.TestCase):
    def test_protocol_34_sends_the_path(self):
        run, kb = _run([{"guide_to_layer": "MIDI"}])
        run.start()
        self.assertEqual(kb.rings()[-1],
                         ("guide", [(0, 0, 0), (1, 2, 1)], 2, RING_COUNT, RING_PERIOD_MS))
        self.assertEqual(run.state()["ring"], "guide")

    def test_protocol_32_rings_the_first_key(self):
        run, kb = _run([{"guide_to_layer": "MIDI"}], _Keyboard(protocol=32))
        run.start()
        self.assertEqual(kb.rings()[-1][:3], ("ring", 0, 0))
        self.assertEqual(run.state()["ring"], "point")

    def test_no_path(self):
        run, kb = _run([{"guide_to_layer": "Base"}])
        run.start()
        self.assertIsNotNone(run.state()["ring_error"])
        self.assertEqual(kb.rings(), [])


class StepsTest(unittest.TestCase):
    def test_next_back_and_the_end(self):
        run, kb = _run([{"point": {"key": [0, 0]}}, {"say": "b"}])
        run.start()
        run.back()
        self.assertEqual(run.index, 0)
        run.next()
        self.assertEqual(run.state()["step"], 1)
        run.back()
        self.assertEqual(run.index, 0)
        run.next()
        run.next()
        self.assertEqual(run.finished, "done")
        run.next()
        run.back()
        self.assertEqual(run.finished, "done")

    def test_stop_cancels_the_ring(self):
        run, kb = _run([{"point": {"key": [0, 0]}}, {"say": "b"}])
        run.start()
        run.stop()
        self.assertEqual(run.finished, "stopped")
        self.assertEqual(kb.rings()[-1], ("cancel",))
        run.stop()
        self.assertEqual(kb.calls.count(("cancel",)), 1)

    def test_a_seconds_step_ends_by_itself(self):
        clock = _Clock()
        run, _kb = _run([{"say": "a", "wait": {"seconds": 2}}, {"say": "b"}], clock=clock)
        run.start()
        state = run.state()
        self.assertTrue(state["auto"])
        self.assertEqual(state["remaining_s"], 2.0)
        clock.t += 1.9
        self.assertFalse(run.tick())
        clock.t += 0.2
        self.assertTrue(run.tick())
        self.assertEqual(run.index, 1)
        self.assertFalse(run.state()["auto"])
        clock.t += 100
        self.assertFalse(run.tick())        # a `next` step waits for the user

    def test_back_restarts_the_seconds(self):
        clock = _Clock()
        run, _kb = _run([{"say": "a", "wait": {"seconds": 2}}, {"say": "b"}], clock=clock)
        run.start()
        clock.t += 3
        run.tick()
        run.back()
        self.assertEqual(run.state()["remaining_s"], 2.0)

    def test_an_event_wait_ends_with_next_until_cmd_49(self):
        run, _kb = _run([{"say": "a", "wait": {"layer": "MIDI"}}])
        run.start()
        state = run.state()
        self.assertEqual(state["wait"], {"kind": "layer", "value": "MIDI"})
        self.assertFalse(state["auto"])

    def test_the_state_is_json_serializable(self):
        import json
        run, _kb = _run([{"say": ["a", "b"], "text": {"en": "x", "de": "y"},
                          "point": {"key": [0, 0]}}])
        run.start()
        state = json.loads(json.dumps(run.state()))
        self.assertEqual(state["say"], ["a", "b"])
        self.assertEqual(state["text"], {"en": "x", "de": "y"})
        self.assertEqual((state["step"], state["steps"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
