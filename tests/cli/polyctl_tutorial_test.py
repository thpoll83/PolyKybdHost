"""`polyctl tutorial`: list, start, next/back/stop, status."""
import json
import unittest

from polyhost.server import protocol
from tests.cli.polyctl_test import run_main

_STATE = {"id": "midi-layer", "title": {"en": "The MIDI layer"}, "step": 0, "steps": 5,
          "say": ["Hold Fn, then tap", "the ringed key"], "text": {"en": "Hold Fn."},
          "wait": {"kind": "next", "value": None}, "auto": False, "remaining_s": None,
          "ring": "guide", "ring_error": None, "finished": None}
_LIST = {"tutorials": [
    {"id": "midi-layer", "category": "layers", "title": {"en": "The MIDI layer"},
     "summary": {}, "min_protocol": 32, "steps": 5, "user": False, "path": "x"},
    {"id": "future", "category": "other", "title": {"de": "Zukunft"},
     "summary": {}, "min_protocol": 35, "steps": 1, "user": True, "path": "y"}],
    "errors": [{"path": "/u/bad.yaml", "error": "steps[0].wait: next, or ..."}],
    "protocol": 34, "user_dir": "/u", "running": None}


class PolyctlTutorialTest(unittest.TestCase):
    def test_list(self):
        rc, out, _err, _server = run_main(["tutorial", "list"],
                                          {protocol.M_TUTORIALS_LIST: _LIST})
        self.assertEqual(rc, 0)
        self.assertIn("midi-layer", out)
        self.assertIn("Zukunft  (needs firmware protocol 35)", out)
        self.assertNotIn("The MIDI layer  (needs", out)
        self.assertIn("error: /u/bad.yaml: steps[0].wait", out)
        self.assertIn("user folder: /u", out)

    def test_list_is_the_default_and_has_json(self):
        rc, out, _err, _server = run_main(["tutorial"], {protocol.M_TUTORIALS_LIST: _LIST})
        self.assertEqual(rc, 0)
        self.assertIn("midi-layer", out)
        rc, out, _err, _server = run_main(["tutorial", "list", "--json"],
                                          {protocol.M_TUTORIALS_LIST: _LIST})
        self.assertEqual(json.loads(out), _LIST)

    def test_start_sends_the_id_and_prints_the_step(self):
        rc, out, _err, server = run_main(["tutorial", "start", "midi-layer"],
                                         {protocol.M_TUTORIAL_START: _STATE})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_TUTORIAL_START],
                         {"id": "midi-layer"})
        self.assertIn("step 1 of 5", out)
        self.assertIn("| Hold Fn, then tap", out)
        self.assertIn("polyctl tutorial next", out)

    def test_actions(self):
        for action in ("next", "back", "stop"):
            with self.subTest(action):
                rc, _out, _err, server = run_main(
                    ["tutorial", action], {protocol.M_TUTORIAL_ACTION: _STATE})
                self.assertEqual(rc, 0)
                self.assertEqual(dict(server.received)[protocol.M_TUTORIAL_ACTION],
                                 {"action": action})

    def test_a_keyboard_event_wait(self):
        state = {**_STATE, "auto": True, "wait": {"kind": "layer", "value": "MIDI"}}
        rc, out, _err, _server = run_main(["tutorial", "status"],
                                          {protocol.M_TUTORIAL_STATE: state})
        self.assertIn("ends when the keyboard reports: layer MIDI", out)
        self.assertNotIn("None", out)

    def test_status_and_the_end(self):
        rc, out, _err, _server = run_main(["tutorial", "status"],
                                          {protocol.M_TUTORIAL_STATE: None})
        self.assertIn("no tutorial is running", out)
        rc, out, _err, _server = run_main(
            ["tutorial", "stop"], {protocol.M_TUTORIAL_ACTION: {**_STATE, "finished": "stopped"}})
        self.assertIn("tutorial midi-layer: stopped", out)


if __name__ == "__main__":
    unittest.main()
