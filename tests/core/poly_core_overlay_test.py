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
    core.safe_mode = False
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
    # Seed the OS dedup to the local OS so the window tick's OS-tracking re-assert
    # is a no-op here (these tests pin overlay-send behaviour, not OS pushes).
    from polyhost.input.unicode_input import get_host_os
    core._last_pushed_os = get_host_os().value
    if handler:
        core.overlay_handler.is_remote_mapping_entry.return_value = False
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

    def test_safe_mode_skips_overlay_tracking(self):
        # Newer-firmware safe mode: connected but no operational overlay/OS traffic.
        core = make_core(connected=True)
        core.safe_mode = True
        core.tick_window_tracking()
        core.overlay_handler.handle_active_window.assert_not_called()

    def test_disconnected_dev_flag_polls_without_device(self):
        core = make_core(connected=False, run_when_disconnected=True)
        core.tick_window_tracking()
        core.overlay_handler.handle_active_window.assert_called_once()
        core.worker.submit.assert_not_called()


class TestOsTracking(unittest.TestCase):
    """The window tick pushes the forwarder's OS while a remote-forwarded window
    drives the display, and reverts to the local OS when local tracking resumes —
    deduped so set_os only fires on a change."""

    def _os_submits(self, core):
        return [c for c in core.worker.submit.call_args_list if c.args and c.args[0] == "set_os"]

    def test_forwarded_os_pushed_then_reverts(self):
        from polyhost.input.unicode_input import get_host_os
        core = make_core()
        core._last_pushed_os = None  # nothing pushed yet
        core.overlay_handler.handle_active_window.return_value = (None, OverlayCommand.NONE)

        # Remote-forwarded window active, forwarder reports macOS (2).
        core.overlay_handler.is_remote_mapping_entry.return_value = True
        core.overlay_handler.remote_handler.forwarded_os = 2
        core.tick_window_tracking()
        self.assertEqual(self._os_submits(core), self._os_submits(core)[:1])  # at least one
        self.assertEqual(core._last_pushed_os, 2)

        # A second identical tick is deduped (no new set_os).
        before = len(self._os_submits(core))
        core.tick_window_tracking()
        self.assertEqual(len(self._os_submits(core)), before)

        # Local window takes back over -> revert to the local OS.
        core.overlay_handler.is_remote_mapping_entry.return_value = False
        core.tick_window_tracking()
        self.assertEqual(core._last_pushed_os, get_host_os().value)

    def test_remote_without_os_keeps_local(self):
        from polyhost.input.unicode_input import get_host_os
        core = make_core()
        core._last_pushed_os = None
        core.overlay_handler.handle_active_window.return_value = (None, OverlayCommand.NONE)
        core.overlay_handler.is_remote_mapping_entry.return_value = True
        core.overlay_handler.remote_handler.forwarded_os = None  # old forwarder
        core.tick_window_tracking()
        self.assertEqual(core._last_pushed_os, get_host_os().value)


if __name__ == '__main__':
    unittest.main()
