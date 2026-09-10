"""PolyCore.apply_reconnect — the operational half of the reconnect apply.

Drives a bare PolyCore (no device construction) through the snapshot
shapes the worker probe produces, pinning: state/present updates, the
post-connect work (unicode push, cache reset, window resend, overlay
reset handshake), fresh-boot cache invalidation, the paused guard, and
the status_changed emission. UI rendering stays in the GUI and is out
of scope here.
"""
import logging
import time
import unittest
from unittest.mock import MagicMock

from polyhost._version import __protocol__
from polyhost.core.poly_core import PolyCore
from polyhost.device.poly_kybd import UNICODE_MODE_VOLATILE_MIN_PROTOCOL


def make_core(*, paused=False, connected=False, unicode_mode=False, ai_key=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore")
    core.ignore_version = False
    core.apply_reconnect_in_core = False
    core.paused = paused
    core.connected = connected
    core.device_present = connected
    core.last_applied_connected = connected
    core.safe_mode = False
    core._newer_fw_policy = None
    core._newer_fw_policy_proto = None
    core.kb_sw_version = None
    core.needs_overlay_reset = False
    core._probe_fail_streak = 0
    core._ai_state = 0          # what the AI key was last told to show
    core._ai_pushed = False     # ...and whether that push reached the keyboard
    core._ai_press_seq = 0      # presses relayed to a forwarder
    core._last_pushed_unicode_mode = None
    core._queued_unicode_mode = None
    core._last_push_was_volatile = False
    core._queued_push_is_volatile = False
    core._started_at = 0.0
    core._last_overlay_activity = 0.0
    core._observers = []
    import threading
    core._observers_lock = threading.Lock()
    core.poly_settings = MagicMock()
    core.poly_settings.get.side_effect = lambda k: {
        "unicode_send_composition_mode": unicode_mode,
        # OFF by default here as in production, so a test that wants the AI key
        # has to say so — and the gate tests get the real default for free.
        "ai_key_enabled": ai_key}.get(k, False)
    core.worker = MagicMock()
    core.device_mgr = MagicMock()
    core.overlay_handler = MagicMock()
    core.keeb = MagicMock()
    # A real protocol number: _apply_unicode_mode reads the CACHED one to decide
    # whether the firmware can apply a mode without storing it.
    core.keeb.protocol_version = __protocol__
    # Real dict so _reported_capabilities can mask it to all-False in safe mode.
    core.keeb.capabilities.return_value = {
        "idle_style": True, "glyph_script": True, "os": True}
    # apply_reconnect re-asserts the host brightness mode on connect via
    # refresh_daylight_brightness(), which reads core.sunlight (set in the real
    # __init__ this bare core skips).
    core.sunlight = MagicMock()
    # apply_reconnect counts connects/flaps for the usage census.
    core.telemetry = MagicMock()
    return core


def connect_snapshot(**over):
    snap = {
        "connected_now": True,
        "device_present": True,
        "lang": "enUS",
        "state_changed": True,
        "fresh_boot": False,
        "version_ok": True,
        "version_msg": "ok",
        "kb_version": "9.9.9",
        "kb_proto": __protocol__,
        "kb_sw_version": [9, 9, 9],
        "name": "Split72",
        "hw_version": "1",
        "lang_list": ["enUS"],
        "current_lang": "enUS",
    }
    snap.update(over)
    return snap


class TestAiStateResync(unittest.TestCase):
    """The keyboard holds the agent status in RAM only, so a reconnect has to
    re-push it — otherwise the key goes dark while the agent is still working."""

    def _submitted(self, core):
        return [c.args[0] for c in core.worker.submit.call_args_list]

    def test_a_reconnect_re_pushes_a_live_status(self):
        core = make_core(connected=False, ai_key=True)
        core._ai_state = 2                      # WORKING
        core.apply_reconnect(connect_snapshot())
        self.assertIn("ai_state_resync", self._submitted(core))

    def test_nothing_is_pushed_when_no_agent_has_reported(self):
        # Pushing OFF to a key that is already off buys nothing and costs a job on
        # the worker that owns the device during the busiest moment it has.
        core = make_core(connected=False, ai_key=True)
        core._ai_state = 0
        core.apply_reconnect(connect_snapshot())
        self.assertNotIn("ai_state_resync", self._submitted(core))

    def test_the_re_push_records_whether_the_keyboard_took_it(self):
        # `pushed` is what stops `ai status` claiming a light that never lit, so the
        # resync has to report its own outcome rather than leaving the flag as the
        # failed set_ai_state left it.
        core = make_core(connected=False, ai_key=True)
        core._ai_state = 2
        core.apply_reconnect(connect_snapshot())
        on_done = core.worker.submit.call_args_list[-1].kwargs["on_done"]
        on_done("ai_state_resync", (True, b"ok"))
        self.assertTrue(core._ai_pushed)
        on_done("ai_state_resync", (False, "no device"))
        self.assertFalse(core._ai_pushed)
        on_done("ai_state_resync", RuntimeError("worker suspended"))
        self.assertFalse(core._ai_pushed)


class TestSetAiState(unittest.TestCase):
    """The DESIRED state and whether the KEYBOARD took it are two different facts.

    Conflating them made `ai status` report a light that never lit: a paused worker,
    an unplugged board or a pre-v17 firmware all left the requested state recorded as
    though it had been pushed."""

    def _core(self, device_result):
        core = make_core(ai_key=True)
        core.worker.run_sync.return_value = device_result
        core.keeb.supports.return_value = True
        core.seen = []
        core.subscribe(lambda name, payload: core.seen.append((name, payload)))
        return core

    def test_a_successful_push_is_reported_as_shown(self):
        core = self._core((True, b"P\x28."))
        ok, _ = core.set_ai_state("working")
        self.assertTrue(ok)
        self.assertEqual(core._ai_state, 2)
        self.assertTrue(core._ai_pushed)
        self.assertTrue(core.ai_status()[1]["pushed"])
        self.assertTrue(core.seen[-1][1]["pushed"])

    def test_a_refused_push_keeps_the_state_but_not_the_claim(self):
        core = self._core((False, "firmware protocol too old"))
        ok, _ = core.set_ai_state("working")
        self.assertFalse(ok)
        # The agent IS working — that is a fact about the host, and it is what the
        # reconnect re-push replays — but the keyboard is not showing it.
        self.assertEqual(core._ai_state, 2)
        self.assertFalse(core._ai_pushed)
        self.assertFalse(core.ai_status()[1]["pushed"])
        self.assertFalse(core.seen[-1][1]["pushed"])

    def test_an_unknown_state_word_never_reaches_the_device(self):
        core = self._core((True, b"."))
        ok, msg = core.set_ai_state("banana")
        self.assertFalse(ok)
        self.assertIn("Unknown AI state", msg)
        core.worker.run_sync.assert_not_called()
        self.assertEqual(core._ai_state, 0)


class TestAiKeyDisabled(unittest.TestCase):
    """`ai_key_enabled` is OFF by default and has to gate the WHOLE feature.

    It gates four separate things — the state push, the reconnect re-push, the press
    that raises a window, and the relay a remote forwarder reads — and a flag that
    gates three of four is not off. Each is asserted here rather than trusting the one
    reader, because each is a different call path into the same setting.
    """

    def test_a_state_push_is_refused_and_not_even_recorded(self):
        # Recording it would leave `ai status` reporting a state nothing will ever
        # show: with the feature off there is no reconnect re-push to carry it.
        core = make_core()
        core.keeb.supports.return_value = True
        ok, msg = core.set_ai_state("working")
        self.assertFalse(ok)
        self.assertIn("ai_key_enabled", msg)
        self.assertEqual(core._ai_state, 0)
        core.worker.run_sync.assert_not_called()

    def test_a_reconnect_does_not_re_push_a_state(self):
        core = make_core(connected=False)
        core._ai_state = 2      # as if it had been set while the flag was on
        core.apply_reconnect(connect_snapshot())
        submitted = [c.args[0] for c in core.worker.submit.call_args_list]
        self.assertNotIn("ai_state_resync", submitted)

    def test_a_press_raises_nothing(self):
        core = make_core()
        core._ai_scanner = _ScannerSaying(1)
        core._ai_raiser = MagicMock()
        core._scan_console_for_ai_key(b"ai: open\n")
        core._ai_raiser.raise_next.assert_not_called()
        self.assertEqual(core._ai_press_seq, 0)

    def test_the_forwarder_relay_reports_nothing_armed(self):
        # A forwarder must not act on a counter from a feature that is off — and 0
        # is exactly what AiRelayFollower treats as "nothing armed".
        core = make_core()
        core._ai_press_seq = 7
        core._ai_state = 2
        self.assertEqual(core.ai_relay_state(), {"raise_seq": 0, "active": False})

    def test_status_says_so(self):
        core = make_core()
        self.assertFalse(core.ai_status()[1]["enabled"])


class _ScannerSaying:
    """Stands in for AiScanner: reports N presses for whatever it is fed."""

    def __init__(self, presses):
        self._presses = presses

    def feed(self, _chunk):
        return self._presses


class TestAiPressRelay(unittest.TestCase):
    """A press has to reach a forwarder whose machine runs the agent."""

    def _core(self):
        core = make_core(ai_key=True)
        core._ai_scanner = _ScannerSaying(1)
        core._ai_raiser = MagicMock()
        core._ai_raiser.raise_next.return_value = (False, "No window matches")
        return core

    def test_the_counter_advances_even_when_nothing_matches_here(self):
        # The normal multi-machine case: the agent runs on the forwarder's machine,
        # so only ITS target matches. Bumping only on a successful local raise would
        # mean the press never leaves this machine.
        core = self._core()
        core._scan_console_for_ai_key(b"ai: open\n")
        self.assertEqual(core.ai_relay_state()["raise_seq"], 1)

    def test_active_follows_the_state_an_agent_reported(self):
        # What lets the forwarder poll faster only while an agent is running.
        core = self._core()
        self.assertFalse(core.ai_relay_state()["active"])
        core._ai_state = 2
        self.assertTrue(core.ai_relay_state()["active"])

    def test_the_relay_names_no_window(self):
        # It crosses the network endpoint, which must not become a place that can
        # learn anything about this machine.
        core = self._core()
        core._scan_console_for_ai_key(b"ai: open\n")
        self.assertEqual(set(core.ai_relay_state()), {"raise_seq", "active"})


class TestReportWindow(unittest.TestCase):
    def test_delegates_to_remote_handler(self):
        core = make_core()
        ok, payload = core.report_window("7", "Code.exe", "x - VS Code")
        self.assertTrue(ok)
        self.assertEqual(payload, {"reported": True})
        core.overlay_handler.remote_handler.report_window.assert_called_once_with(
            "7", "Code.exe", "x - VS Code", os=None)

    def test_forwards_os_to_remote_handler(self):
        core = make_core()
        core.report_window("7", "Code.exe", "x - VS Code", os=2)
        core.overlay_handler.remote_handler.report_window.assert_called_once_with(
            "7", "Code.exe", "x - VS Code", os=2)

    def test_no_window_tracking_returns_error(self):
        core = make_core()
        core.overlay_handler = None
        ok, msg = core.report_window("7", "Code.exe", "x")
        self.assertFalse(ok)
        self.assertIsInstance(msg, str)


class TestApplyReconnect(unittest.TestCase):

    def test_an_ambiguous_unicode_mode_is_pushed_VOLATILE_on_connect(self):
        """At logon a plain-Windows reading may just mean WinCompose has not
        started yet. It is still applied — that IS how the keyboard should type
        while WinCompose is absent — but RAM-only, so a reading the host cannot
        yet trust is never written to EEPROM."""
        core = make_core(unicode_mode=True)
        core._start_wincompose_settle = MagicMock()
        core._unicode_mode_is_ambiguous = MagicMock(return_value=True)

        core.apply_reconnect(connect_snapshot())

        jobs = [c for c in core.worker.submit.call_args_list
                if c.args[0] == "set_unicode_mode"]
        self.assertEqual(len(jobs), 1)
        jobs[0].args[1](None)     # run the job as the worker would
        self.assertEqual(core.keeb.set_unicode_mode.call_args.kwargs["persist"],
                         False)
        # …and the watcher that will make it stick must be armed.
        core._start_wincompose_settle.assert_called_once()

    def test_an_ambiguous_mode_is_HELD_on_firmware_without_the_volatile_flag(self):
        """Protocol 16 cannot apply without storing, so the only alternatives are
        a wrong stored value and a delay — the delay is recoverable."""
        core = make_core(unicode_mode=True)
        core.keeb.protocol_version = UNICODE_MODE_VOLATILE_MIN_PROTOCOL - 1
        core._start_wincompose_settle = MagicMock()
        core._unicode_mode_is_ambiguous = MagicMock(return_value=True)

        core.apply_reconnect(connect_snapshot())

        names = [c.args[0] for c in core.worker.submit.call_args_list]
        self.assertNotIn("set_unicode_mode", names)
        core._start_wincompose_settle.assert_called_once()

    def test_paused_returns_none(self):
        core = make_core(paused=True)
        self.assertIsNone(core.apply_reconnect(connect_snapshot()))

    def test_fresh_compatible_connect_runs_post_connect(self):
        core = make_core(unicode_mode=True)
        events = []
        core.subscribe(lambda n, p: events.append((n, p)))

        applied = core.apply_reconnect(connect_snapshot())

        self.assertTrue(core.connected)
        self.assertTrue(core.device_present)
        self.assertTrue(core.last_applied_connected)
        self.assertEqual(core.kb_sw_version, [9, 9, 9])
        core.device_mgr.reset_all_caches.assert_called_once()
        core.overlay_handler.force_resend.assert_called_once()
        # unicode mode pushed as a worker job
        names = [c.args[0] for c in core.worker.submit.call_args_list]
        self.assertIn("set_unicode_mode", names)
        # overlay reset handshake: flag set by post-connect, consumed same apply
        self.assertFalse(core.needs_overlay_reset)
        self.assertTrue(applied["do_overlay_reset"])
        self.assertTrue(applied["decision"]["do_post_connect"])
        self.assertEqual(events[-1][0], "status_changed")
        self.assertTrue(events[-1][1]["connected"])
        # GUI mode (apply_reconnect_in_core=False): the core leaves the keyboard
        # pool clear to the GUI (host.py consumes do_overlay_reset).
        core.keeb.reset_overlays_and_usage.assert_not_called()

    def test_headless_connect_clears_keyboard_overlay_pool(self):
        # Headless owns the apply (no GUI consumes do_overlay_reset), so the
        # core must clear the keyboard's stale pool itself — otherwise the empty
        # MRU cache and a populated keyboard pool desync (stale icons bleed
        # through). Mirrors the GUI's core.reset_overlays() on connect.
        core = make_core()
        core.apply_reconnect_in_core = True
        applied = core.apply_reconnect(connect_snapshot())
        self.assertTrue(applied["do_overlay_reset"])
        core.keeb.reset_overlays_and_usage.assert_called_once()

    def test_below_floor_protocol_keeps_presence_for_flashing(self):
        # Firmware BELOW the supported floor is still refused (host can't even
        # enumerate languages), but presence is kept so it can be flashed.
        core = make_core()
        applied = core.apply_reconnect(connect_snapshot(kb_proto=1))
        self.assertFalse(core.connected)
        self.assertTrue(core.device_present)      # GET_ID answered → flashable
        self.assertFalse(applied["decision"]["do_post_connect"])
        self.assertFalse(applied["do_overlay_reset"])
        core.overlay_handler.force_resend.assert_not_called()

    def test_older_within_range_connects_and_runs_post_connect(self):
        # An OLDER (but at/above the floor) protocol connects and runs the
        # post-connect work; individual features self-gate by protocol.
        core = make_core()
        applied = core.apply_reconnect(connect_snapshot(kb_proto=__protocol__ - 1))
        self.assertTrue(core.connected)
        self.assertTrue(applied["decision"]["do_post_connect"])
        self.assertFalse(core.safe_mode)
        core.overlay_handler.force_resend.assert_called_once()

    def test_newer_undecided_enters_safe_mode_and_flags_pending(self):
        # NEWER firmware, no policy chosen: connected but restricted safe mode,
        # no post-connect, and the status flags newer_fw_pending for the dialog.
        core = make_core()
        events = []
        core.subscribe(lambda n, p: events.append((n, p)))
        applied = core.apply_reconnect(connect_snapshot(kb_proto=__protocol__ + 1))
        self.assertTrue(core.connected)
        self.assertTrue(core.safe_mode)
        self.assertFalse(applied["decision"]["do_post_connect"])
        core.overlay_handler.force_resend.assert_not_called()
        st = events[-1][1]
        self.assertTrue(st["safe_mode"])
        self.assertTrue(st["newer_fw_pending"])
        # Capabilities are reported all-False in safe mode.
        self.assertTrue(all(v is False for v in st["capabilities"].values()))

    def test_newer_ignore_policy_connects_fully(self):
        core = make_core()
        core.keeb.get_protocol_version.return_value = __protocol__ + 1
        ok, _ = core.set_newer_firmware_policy("ignore")
        self.assertTrue(ok)
        self.assertFalse(core.last_applied_connected)  # forced re-apply
        applied = core.apply_reconnect(connect_snapshot(kb_proto=__protocol__ + 1))
        self.assertTrue(core.connected)
        self.assertFalse(core.safe_mode)
        self.assertTrue(applied["decision"]["do_post_connect"])
        core.overlay_handler.force_resend.assert_called_once()

    def test_policy_reset_when_protocol_changes(self):
        # A remembered choice for one protocol is forgotten if the device reports a
        # different protocol (e.g. after a firmware flash) -> prompt again.
        core = make_core()
        core.keeb.get_protocol_version.return_value = __protocol__ + 1
        core.set_newer_firmware_policy("ignore")
        # Device now reports a different (still newer) protocol.
        applied = core.apply_reconnect(connect_snapshot(kb_proto=__protocol__ + 2))
        self.assertIsNone(core._newer_fw_policy)
        self.assertTrue(core.safe_mode)
        self.assertTrue(applied["decision"]["newer_fw_pending"])

    def test_disconnect_clears_state_without_version_queries(self):
        core = make_core(connected=True)
        snap = connect_snapshot(
            connected_now=False, device_present=False, lang="",
            version_ok=False, version_msg="Could not read reply from PolyKybd",
            kb_version=None, kb_proto=None, kb_sw_version=None,
            name=None, hw_version=None, lang_list=None, current_lang=None)
        applied = core.apply_reconnect(snap)
        self.assertFalse(core.connected)
        self.assertFalse(core.device_present)
        self.assertFalse(core.last_applied_connected)
        self.assertFalse(applied["decision"]["connected"])
        self.assertEqual(applied["decision"]["text"], "Could not read reply from PolyKybd")
        core.device_mgr.reset_all_caches.assert_not_called()

    def test_fresh_boot_resets_caches_without_state_change(self):
        core = make_core(connected=True)
        snap = connect_snapshot(state_changed=False, fresh_boot=True)
        applied = core.apply_reconnect(snap)
        self.assertTrue(applied["fresh_boot"])
        core.device_mgr.reset_all_caches.assert_called_once()
        # The decision NOW runs on a fresh boot too. It used to be skipped, which
        # is the bug below: a reboot the host never saw as a disconnect left every
        # protocol-derived conclusion describing the previous firmware.
        self.assertIsNotNone(applied["decision"])

    def test_a_flash_that_changes_protocol_is_noticed_without_a_disconnect(self):
        """The reported bug: flash new firmware from the host app and the app keeps
        treating the keyboard as the OLD protocol until it is restarted.

        A firmware apply reboots the keyboard INSIDE the flash's own suspend/long-job
        window, so the reconnect probe never observes a disconnect -- connected
        before, connected after, `state_changed` False. Everything derived from the
        protocol (capabilities, the newer-firmware decision, the editor's feature
        gates) was therefore computed from the firmware that had just been replaced.

        `fresh_boot` is the signal that distinguishes this from steady state, and the
        firmware sets it on every boot precisely because a reboot can be too fast for
        the host to see.
        """
        core = make_core(connected=True)
        core.keeb.get_protocol_version.return_value = __protocol__ + 1
        applied = core.apply_reconnect(connect_snapshot(
            state_changed=False, fresh_boot=True, kb_proto=__protocol__ + 1))
        self.assertIsNotNone(applied["decision"], "the decision tree never re-ran")
        self.assertTrue(applied["decision"]["newer_fw_pending"],
                        "the newer-firmware prompt never fired for the new protocol")
        self.assertTrue(core.safe_mode)

    def test_a_remembered_policy_is_dropped_when_a_flash_changes_the_protocol(self):
        """The forget-the-remembered-choice block carries the comment "e.g. after a
        firmware flash" -- and used to sit behind a guard a firmware flash could not
        satisfy, so it could never fire for the case it names."""
        core = make_core(connected=True)
        core.keeb.get_protocol_version.return_value = __protocol__ + 1
        core.set_newer_firmware_policy("ignore")
        self.assertEqual(core._newer_fw_policy, "ignore")
        core.apply_reconnect(connect_snapshot(
            state_changed=False, fresh_boot=True, kb_proto=__protocol__ + 2))
        self.assertIsNone(core._newer_fw_policy, "stale choice reused for new firmware")

    def test_steady_state_still_short_circuits(self):
        """No fresh boot, no state change -> the decision must NOT re-run. This is
        what keeps the ~1 s probe free in steady state."""
        core = make_core(connected=True)
        applied = core.apply_reconnect(
            connect_snapshot(state_changed=False, fresh_boot=False))
        self.assertIsNone(applied["decision"])
        core.device_mgr.reset_all_caches.assert_not_called()

    def test_headless_handler_none_does_not_crash_post_connect(self):
        core = make_core()
        core.overlay_handler = None
        applied = core.apply_reconnect(connect_snapshot())
        self.assertTrue(core.connected)
        self.assertTrue(applied["do_overlay_reset"])

    def test_reconnect_periodic_auto_applies_in_core_when_flagged(self):
        # Headless: the periodic applies its own snapshot (no GUI to do it).
        core = make_core(connected=True)
        core.apply_reconnect_in_core = True
        disconnect = connect_snapshot(
            connected_now=False, device_present=False, lang="",
            version_ok=False, version_msg="gone",
            kb_version=None, kb_proto=None, kb_sw_version=None,
            name=None, hw_version=None, lang_list=None, current_lang=None)
        core._reconnect_probe = lambda cancel: disconnect
        events = []
        core.subscribe(lambda n, p: events.append(n))
        core._reconnect_periodic(cancel=None)
        # Applied in-core: state settled AND a reconnect event still emitted.
        self.assertFalse(core.connected)
        self.assertFalse(core.device_present)
        self.assertIn("status_changed", events)
        self.assertIn("reconnect", events)

    def test_reconnect_periodic_does_not_apply_when_flag_off(self):
        # GUI default: the periodic only emits; the client applies.
        core = make_core(connected=True)
        self.assertFalse(core.apply_reconnect_in_core)
        core._reconnect_probe = lambda cancel: connect_snapshot(
            connected_now=False, device_present=False, lang="",
            version_ok=False, version_msg="gone", kb_version=None, kb_proto=None,
            kb_sw_version=None, name=None, hw_version=None,
            lang_list=None, current_lang=None)
        events = []
        core.subscribe(lambda n, p: events.append(n))
        core._reconnect_periodic(cancel=None)
        self.assertEqual(events, ["reconnect"])     # no in-core status_changed
        self.assertTrue(core.connected)             # unchanged — GUI applies


class TestProbeOverlayCooldown(unittest.TestCase):
    """The probe skips the keyboard's post-send deaf window (no ID query)."""

    def test_probe_skipped_during_overlay_cooldown(self):
        core = make_core(connected=True)
        core.last_applied_connected = True
        core._last_overlay_activity = time.monotonic()      # just sent overlays
        self.assertIsNone(core._reconnect_probe(cancel=None))
        core.keeb.connect.assert_not_called()               # no ID query issued

    def test_probe_runs_after_overlay_cooldown(self):
        core = make_core(connected=True)
        core.last_applied_connected = True
        core._last_overlay_activity = time.monotonic() - 5.0  # window lapsed
        core.keeb.hid = None                                  # skip the drain step
        core.keeb.connect.return_value = False
        core._reconnect_probe(cancel=None)
        core.keeb.connect.assert_called_once()                # probe ran, not skipped

    def test_probe_runs_when_disconnected_even_if_recent_activity(self):
        # Defensive: while disconnected the probe must always run so reconnect
        # isn't delayed, regardless of a stale overlay-activity timestamp.
        core = make_core(connected=False)
        core.last_applied_connected = False
        core._last_overlay_activity = time.monotonic()
        core.keeb.hid = None
        core.keeb.connect.return_value = False
        core._reconnect_probe(cancel=None)
        core.keeb.connect.assert_called_once()


if __name__ == '__main__':
    unittest.main()
