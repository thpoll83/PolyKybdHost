"""PolyCore's tutorial methods: start, step, the periodic, and the MIDI guide."""
import os
import tempfile
import types
import unittest
import unittest.mock as mock

from polyhost.core import poly_core
from polyhost.services.tutorials import loader
from tests.services.tutorials_runner_test import _Keyboard

SCRIPT = """id: demo
category: other
title: Demo
steps:
  - point: {key: [0, 0]}
    wait: {seconds: 1}
  - say: Last
"""


def _core(kb):
    core = types.SimpleNamespace(
        keeb=kb, safe_mode=False, _manual_ring_seq=0, _tutorial_run=None,
        _tutorial_state=None, events=[], log=types.SimpleNamespace(
            info=lambda *a: None, debug=lambda *a: None))
    kb.get_protocol_version = lambda: kb.protocol_version
    core._device_call = lambda name, fn: fn(None)
    core.emit = lambda name, payload: core.events.append((name, payload))
    for name in ("_tutorial_begin", "_tutorial_step", "_tutorial_publish",
                 "_tutorial_periodic"):
        setattr(core, name, getattr(poly_core.PolyCore, name).__get__(core))
    return core


def _call(core, name, *args):
    return getattr(poly_core.PolyCore, name)(core, *args)


class TutorialCoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self._tmp.name, "demo.yaml"), "w", encoding="utf-8") as f:
            f.write(SCRIPT)
        patcher = mock.patch.object(loader, "user_dir", return_value=self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_list_has_shipped_and_user_scripts(self):
        info = _call(_core(_Keyboard()), "tutorials_list")
        ids = [t["id"] for t in info["tutorials"]]
        self.assertIn("demo", ids)
        self.assertIn("midi-layer", ids)
        self.assertEqual(info["protocol"], 34)
        self.assertEqual(info["user_dir"], self._tmp.name)
        self.assertIsNone(info["running"])

    def test_an_unknown_id(self):
        ok, msg = _call(_core(_Keyboard()), "tutorial_start", "nope")
        self.assertFalse(ok)
        self.assertIn("nope", msg)

    def test_safe_mode_refuses(self):
        core = _core(_Keyboard())
        core.safe_mode = True
        self.assertFalse(_call(core, "tutorial_start", "demo")[0])

    def test_start_step_and_finish(self):
        kb = _Keyboard()
        core = _core(kb)
        ok, state = _call(core, "tutorial_start", "demo")
        self.assertTrue(ok)
        self.assertEqual(state["step"], 0)
        self.assertEqual(core.events[-1], ("tutorial", state))
        self.assertEqual(_call(core, "tutorial_state"), state)
        # The tutorial's ring counts as a manual request for the MIDI guide cancel.
        self.assertEqual(core._manual_ring_seq, 1)
        ok, state = _call(core, "tutorial_action", "next")
        self.assertEqual(state["step"], 1)
        ok, state = _call(core, "tutorial_action", "next")
        self.assertEqual(state["finished"], "done")
        self.assertIsNone(_call(core, "tutorial_state"))
        self.assertIsNone(core._tutorial_run)
        self.assertEqual(core.events[-1][1]["finished"], "done")
        self.assertFalse(_call(core, "tutorial_action", "next")[0])

    def test_an_unknown_action(self):
        core = _core(_Keyboard())
        _call(core, "tutorial_start", "demo")
        self.assertFalse(_call(core, "tutorial_action", "skip")[0])

    def test_a_second_start_stops_the_first(self):
        kb = _Keyboard()
        core = _core(kb)
        _call(core, "tutorial_start", "demo")
        first = core._tutorial_run
        _call(core, "tutorial_start", "midi-layer")
        self.assertEqual(first.finished, "stopped")
        self.assertEqual(core._tutorial_state["id"], "midi-layer")

    def test_a_refused_start_keeps_nothing(self):
        core = _core(_Keyboard(protocol=31))
        self.assertFalse(_call(core, "tutorial_start", "demo")[0])
        self.assertIsNone(core._tutorial_run)
        self.assertEqual(core.events, [])

    def test_the_periodic_ends_a_seconds_step(self):
        core = _core(_Keyboard())
        _call(core, "tutorial_start", "demo")
        run = core._tutorial_run
        core._tutorial_periodic()
        self.assertEqual(run.index, 0)
        run._deadline = 0          # its time is up
        core._tutorial_periodic()
        self.assertEqual(core._tutorial_state["step"], 1)

    def test_the_periodic_with_no_tutorial(self):
        core = _core(_Keyboard())
        core._tutorial_periodic()
        self.assertEqual(core.events, [])


class MidiGuideWaitsForTheTutorialTest(unittest.TestCase):
    def test_no_guide_while_a_tutorial_runs(self):
        from tests.services.midi_guide_test import TrackMidiGuideTest
        case = TrackMidiGuideTest()
        core = case._core()
        core._tutorial_state = {"id": "demo"}
        window = case._window("bitwig studio", {"overlay": "b.png", "midi": True})
        core.track(window)
        self.assertEqual(core.run_jobs(), [])
        core._tutorial_state = None
        core.track(case._window("other", {}))
        core.track(window)
        self.assertEqual(core.run_jobs(), ["midi_guide"])


if __name__ == "__main__":
    unittest.main()
