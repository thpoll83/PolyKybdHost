"""TutorialsDialog and TutorialPanel: the list, Start, the steps and Stop."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QPushButton
    from polyhost.gui.tutorials_dialog import TutorialPanel, TutorialsDialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e

_TUTORIALS = [
    {"id": "midi-layer", "category": "layers", "title": {"en": "The MIDI layer"},
     "summary": {"en": "Play notes."}, "min_protocol": 32, "steps": 2, "user": False,
     "path": ""},
    {"id": "future", "category": "layers", "title": {"en": "Spotlight"},
     "summary": {}, "min_protocol": 35, "steps": 1, "user": True, "path": ""},
    {"id": "brightness", "category": "light", "title": {"en": "Brightness"},
     "summary": {}, "min_protocol": 32, "steps": 3, "user": False, "path": ""},
]


def _state(step=0, steps=2, finished=None, **over):
    state = {"id": "midi-layer", "title": {"en": "The MIDI layer"}, "step": step,
             "steps": steps, "say": ["Hold Fn"], "text": {"en": "Hold Fn now."},
             "wait": {"kind": "next", "value": None}, "auto": False,
             "remaining_s": None, "ring": "point", "ring_error": None,
             "finished": finished}
    state.update(over)
    return state


class _Core:
    def __init__(self):
        self.calls = []
        self.errors = []

    def tutorials_list(self):
        return {"tutorials": _TUTORIALS, "errors": self.errors, "protocol": 34,
                "user_dir": "/tmp/tutorials", "running": None}

    def tutorial_start(self, tid):
        self.calls.append(("start", tid))
        return True, _state()

    def tutorial_action(self, action):
        self.calls.append(("action", action))
        return True, _state(step=1) if action == "next" else _state(finished="stopped")


def _sync(fn, done):
    done(*fn())


def _buttons(widget, text):
    return [b for b in widget.findChildren(QPushButton) if b.text() == text]


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TutorialsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_categories_and_cards(self):
        d = TutorialsDialog(_Core(), _sync, lambda s: None)
        d.load()
        self.assertEqual([d.nav.item(i).text() for i in range(d.nav.count())],
                         ["Layers", "Light and displays"])
        starts = _buttons(d.scroll.widget(), "Start")
        self.assertEqual([b.isEnabled() for b in starts], [True, False])
        d.nav.setCurrentRow(1)
        self.assertEqual(len(_buttons(d.scroll.widget(), "Start")), 1)

    def test_start_opens_the_panel(self):
        core, started = _Core(), []
        d = TutorialsDialog(core, _sync, started.append)
        d.load()
        _buttons(d.scroll.widget(), "Start")[0].click()
        self.assertEqual(core.calls, [("start", "midi-layer")])
        self.assertEqual(started[0]["id"], "midi-layer")

    def test_script_errors_are_shown(self):
        core = _Core()
        core.errors = [{"path": "/u/bad.yaml", "error": "steps[0]: unknown field"}]
        d = TutorialsDialog(core, _sync, lambda s: None)
        d.load()
        self.assertIn("/u/bad.yaml: steps[0]: unknown field", d.status.text())

    def test_a_failed_list(self):
        d = TutorialsDialog(_Core(), lambda fn, done: done(False, "daemon away"),
                            lambda s: None)
        d.load()
        self.assertIn("daemon away", d.status.text())


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TutorialPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_step(self):
        p = TutorialPanel(_Core(), _sync)
        p.update_state(_state(ring_error="no key has keycode 0x0029"))
        self.assertEqual(p.progress.text(), "Step 1 of 2")
        self.assertEqual(p.oled.text(), "Hold Fn")
        self.assertEqual(p.text.text(), "Hold Fn now.")
        self.assertIn("0x0029", p.note.text())
        self.assertFalse(p.back_button.isEnabled())
        self.assertEqual(p.next_button.text(), "Next")
        p.update_state(_state(step=1))
        self.assertTrue(p.back_button.isEnabled())
        self.assertEqual(p.next_button.text(), "Finish")

    def test_next_and_stop(self):
        core = _Core()
        p = TutorialPanel(core, _sync)
        p.update_state(_state())
        p.show()
        p.next_button.click()
        self.assertEqual(p.state["step"], 1)
        p.stop_button.click()
        self.assertIsNone(p.state)
        self.assertFalse(p.isVisible())
        self.assertEqual(core.calls, [("action", "next"), ("action", "stop")])

    def test_closing_the_window_stops_the_tutorial(self):
        core = _Core()
        p = TutorialPanel(core, _sync)
        p.update_state(_state())
        p.show()
        p.close()
        self.assertEqual(core.calls, [("action", "stop")])

    def test_a_finished_state_closes_without_a_stop(self):
        core = _Core()
        p = TutorialPanel(core, _sync)
        p.update_state(_state())
        p.show()
        p.update_state(_state(finished="done"))
        self.assertFalse(p.isVisible())
        self.assertEqual(core.calls, [])


if __name__ == "__main__":
    unittest.main()
