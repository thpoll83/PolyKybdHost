"""PolyCore overlay-send queueing, the overlay_activity event, and the
Qt-free window-tracking tick (tick_window_tracking).

Drives a bare PolyCore (no device construction) with mocked worker /
overlay handler — pins the event contract the GUI icon and the headless
H3 tick thread both depend on.
"""
import logging
import threading
import unittest
from unittest.mock import MagicMock

from polyhost.core.poly_core import PolyCore
from polyhost.handler.common import OverlayCommand


def make_core(*, connected=True, handler=True, run_when_disconnected=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.overlay")
    core.connected = connected
    core._observers = []
    core._observers_lock = threading.Lock()
    core.worker = MagicMock()
    core.device_mgr = MagicMock()
    core.overlay_handler = MagicMock() if handler else None
    core.keeb = MagicMock()
    core.poly_settings = MagicMock()
    core.poly_settings.get.side_effect = lambda k: {
        "dev_run_window_detection_if_not_connected_to_poly_kybd": run_when_disconnected,
    }.get(k, False)
    return core


class TestSendOverlayData(unittest.TestCase):

    def test_empty_returns_false_no_event(self):
        core = make_core()
        events = []
        core.subscribe(lambda n, p: events.append(n))
        self.assertFalse(core.send_overlay_data([]))
        core.worker.submit.assert_not_called()
        self.assertEqual(events, [])

    def test_queues_send_and_emits_thinking(self):
        core = make_core()
        events = []
        core.subscribe(lambda n, p: events.append((n, p)))
        self.assertTrue(core.send_overlay_data("vscode_template.mods.png"))
        self.assertEqual(events[0], ("overlay_activity", {"state": "thinking"}))
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"], "overlay")


class TestTickWindowTracking(unittest.TestCase):

    def test_no_handler_is_noop(self):
        core = make_core(handler=False)
        core.tick_window_tracking()  # must not raise

    def test_off_on_queues_send(self):
        core = make_core()
        core.overlay_handler.handle_active_window.return_value = (["chrome.mods.png"], OverlayCommand.OFF_ON)
        events = []
        core.subscribe(lambda n, p: events.append(n))
        core.tick_window_tracking()
        self.assertIn("overlay_activity", events)
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")

    def test_enable_disable_submits_cmd_without_thinking(self):
        core = make_core()
        core.overlay_handler.handle_active_window.return_value = (None, OverlayCommand.ENABLE)
        events = []
        core.subscribe(lambda n, p: events.append(n))
        core.tick_window_tracking()
        self.assertNotIn("overlay_activity", events)   # enable/disable is silent
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"], "overlay")

    def test_disconnected_skips_query_unless_dev_flag(self):
        core = make_core(connected=False, run_when_disconnected=False)
        core.tick_window_tracking()
        core.overlay_handler.handle_active_window.assert_not_called()

    def test_disconnected_dev_flag_polls_without_device(self):
        core = make_core(connected=False, run_when_disconnected=True)
        core.tick_window_tracking()
        core.overlay_handler.handle_active_window.assert_called_once()
        core.worker.submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
