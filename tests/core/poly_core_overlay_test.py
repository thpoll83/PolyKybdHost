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
    # No focused app and no mark by default: these tests pin the overlay-send
    # contract, and the program icon has its own class below.
    core.app_icons = MagicMock()
    core.app_icons.overlay_for.return_value = (None, None)
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
        core.overlay_handler.current_app = None
        # The real OverlayHandler.icon_app() answers `current_app` for a LOCAL
        # window; a bare MagicMock would return a MagicMock and every icon
        # lookup here would silently ask about the wrong app. The forwarder
        # branch has its own tests against the real handler.
        core.overlay_handler.icon_app.side_effect = (
            lambda: core.overlay_handler.current_app)
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

    def test_a_mark_only_send_TELLS_THE_HANDLER_overlays_are_on(self):
        """⚠️ Or the NEXT real disable is swallowed and the mark stays lit.

        `handle_active_window` flips its optimistic `overlays_enabled` to False
        for the DISABLE, and the tick then declines to issue it in favour of
        sending the mark -- which ends in `enable_overlays()`. Device ON,
        handler believes OFF. Focus something with neither template nor mark and
        `_is_redundant_overlay_cmd` reads that DISABLE as already done, so the
        previous app's icon sits on ESC over an app that has none.
        `tests/handler/active_window_test.py` pins that swallow directly.
        """
        core = make_core()
        core.overlay_handler.current_app = "notepad"
        core.app_icons.overlay_for.return_value = ("MASK", "mdi:note-text")
        core.overlay_handler.handle_active_window.return_value = (None, OverlayCommand.DISABLE)
        core.tick_window_tracking()
        core.overlay_handler.note_overlay_state.assert_called_once_with(True)
        # ...and the disable really was superseded rather than issued alongside.
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")

    def test_a_disable_with_NO_mark_still_disables_and_touches_nothing(self):
        core = make_core()
        core.overlay_handler.current_app = "searchhost"
        core.app_icons.overlay_for.return_value = (None, None)
        core.overlay_handler.handle_active_window.return_value = (None, OverlayCommand.DISABLE)
        core.tick_window_tracking()
        core.overlay_handler.note_overlay_state.assert_not_called()
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"], "overlay")


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

class TestProgramIcon(unittest.TestCase):
    """The focused app's brand mark, appended to whatever the template sends.

    ⚠️ These pin BEHAVIOUR, not plumbing: that the mark rides the same coalesced
    send, that an app with no template still gets one, and that the fetch never
    happens on this thread.
    """

    def _core(self, app="gimp", mask="MASK"):
        core = make_core()
        core.overlay_handler.current_app = app
        core.app_icons.overlay_for.return_value = (mask, "gimp") if mask else (None, None)
        return core

    def _submitted(self, core):
        """What the queued job would hand the device: (files, program)."""
        seen = {}
        core._overlay_send_job = lambda files, cancel, program=None: seen.update(
            files=files, program=program)
        core.worker.submit.call_args.args[1](threading.Event())
        return seen["files"], seen["program"]

    def test_the_mark_is_appended_to_a_templates_own_files(self):
        core = self._core()
        self.assertTrue(core.send_overlay_data("vscode_template.mods.png"))
        files, program = self._submitted(core)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[-1], "@prog:gimp")
        self.assertEqual(program, ("@prog:gimp", "MASK"))

    def test_the_mark_goes_LAST_so_a_template_wins_the_key(self):
        # send_overlays_mru decides which source draws a key by the order it
        # walks them, so appending is what makes the hand-made design win ESC.
        core = self._core()
        core.send_overlay_data(["a.png", "b.png"])
        files, _ = self._submitted(core)
        self.assertEqual(files[-1], "@prog:gimp")
        self.assertEqual(len(files), 3)

    def test_the_mark_names_the_app_ICON_APP_reports_not_current_app(self):
        """⚠️ The two DIFFER on a forwarder setup, and only there.

        `current_app` is the local window -- the remote-desktop client -- while
        the keycaps show the forwarded app, so a mark taken from it would put a
        NoMachine icon on ESC for every app on the other machine.
        `OverlayHandler.icon_app()` is what resolves that; this pins that the
        core CONSULTS it. The fixture makes the two disagree on purpose: with
        both answering the same thing (the default here, mirroring a local
        window) reverting the call site is invisible -- measured, that mutation
        escaped the whole suite.
        """
        core = self._core(app="nxplayer")
        core.overlay_handler.icon_app.side_effect = lambda: "gimp"
        self.assertTrue(core.send_overlay_data("a.png"))
        core.app_icons.overlay_for.assert_called_with("gimp")

    def test_an_app_with_no_mark_sends_only_the_template(self):
        core = self._core(mask=None)
        self.assertTrue(core.send_overlay_data("a.png"))
        files, program = self._submitted(core)
        self.assertEqual(len(files), 1)
        self.assertIsNone(program)

    def test_an_app_with_NO_template_still_gets_its_mark(self):
        # The whole point of the fall-back. handle_active_window returns DISABLE
        # for an unmatched app; before this, that meant the keycaps went blank.
        core = self._core()
        core.overlay_handler.handle_active_window.return_value = (
            None, OverlayCommand.DISABLE)
        core.tick_window_tracking()
        # ⚠️ Assert the SEND, not that the worker was used: a disable submits on
        # the same queue with the same coalesce key, so "submit was called" is
        # true whichever branch ran. Mutation-checked -- dropping the mark path
        # escaped a `submit.assert_called()` entirely.
        files, program = self._submitted(core)
        self.assertEqual(files, ["@prog:gimp"])
        self.assertEqual(program, ("@prog:gimp", "MASK"))

    def test_an_app_with_no_MARK_and_no_template_still_disables(self):
        # Without a mark there is nothing to draw, so the old behaviour has to
        # stand -- an ENABLE with no overlays would leave the last app's keycaps
        # on screen.
        core = self._core(mask=None)
        core.overlay_handler.handle_active_window.return_value = (
            None, OverlayCommand.DISABLE)
        core.tick_window_tracking()
        self.assertEqual(core.worker.submit.call_count, 1)
        # the disable path submits without an on_done/thinking event
        self.assertNotIn("on_done", core.worker.submit.call_args.kwargs)

    def test_no_focused_app_asks_for_no_mark(self):
        core = self._core(app=None)
        self.assertFalse(core.send_overlay_data([]))
        core.app_icons.overlay_for.assert_not_called()

    def test_the_lookup_never_blocks_this_thread(self):
        # `overlay_for` is a dict lookup that queues an unseen app; a fetch here
        # would sit on the GUI main thread for the HTTP timeout.
        core = self._core()
        core.send_overlay_data([])
        core.app_icons.overlay_for.assert_called_once_with("gimp")

    def test_turning_the_fetch_setting_on_clears_the_misses(self):
        # Otherwise the switch does nothing until a restart: every app focused
        # while it was off is cached as "no mark", and that cache is what stops
        # the fetch. The rule this follows is that a settings side effect belongs
        # in note_settings_changed, never in one of its two callers.
        core = self._core()
        core.refresh_daylight_brightness = lambda: None
        core._refresh_unicode_watch = lambda: None
        core.note_settings_changed({"shortcut_icon_auto_fetch"})
        core.app_icons.forget_misses.assert_called_once()

    def test_an_unrelated_setting_leaves_the_cache_alone(self):
        core = self._core()
        core.refresh_daylight_brightness = lambda: None
        core._refresh_unicode_watch = lambda: None
        core.note_settings_changed({"brightness_gamma"})
        core.app_icons.forget_misses.assert_not_called()

    def test_a_mark_arriving_LATER_re_matches_so_it_reaches_the_keycap(self):
        # Without this the icon would only ever appear the SECOND time an app is
        # focused. Reuses the browser-URL invalidation rather than adding a
        # second re-send path.
        core = self._core()
        core._on_app_icon_ready("gimp")
        core.overlay_handler.invalidate_window_cache.assert_called_once()

    def test_the_re_match_FORCES_a_resend_of_the_entry_already_on_screen(self):
        """⚠️ THE FIELD BUG (2026-09-10, "so far nothing"), and the reason the
        test above was not enough.

        The mark arrives for the app that is STILL focused, so the re-match
        finds the SAME entry and `try_to_match_window` returns ENABLE -- which
        the redundant-command guard drops, because overlays are already on. The
        plain invalidation therefore re-evaluated and sent nothing, and the icon
        waited for the user to switch away and back. Measured: a Chrome mark
        resolved 0.8 s into the send that had gone without it and reached the
        keycap four minutes later, on the third activation of the app.

        Asserting the CALL could never have caught that -- the handler is a
        MagicMock, so any argument satisfies it. What matters is the argument,
        and `tests/handler/active_window_test.py` pins what it does.
        """
        core = self._core()
        core._on_app_icon_ready("gimp")
        _, kwargs = core.overlay_handler.invalidate_window_cache.call_args
        self.assertTrue(kwargs.get("resend_same_entry"))

