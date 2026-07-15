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


def make_core(*, paused=False, connected=False, unicode_mode=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore")
    core.ignore_version = False
    core.apply_reconnect_in_core = False
    core.paused = paused
    core.connected = connected
    core.device_present = connected
    core.last_applied_connected = connected
    core.kb_sw_version = None
    core.needs_overlay_reset = False
    core._probe_fail_streak = 0
    core._last_overlay_activity = 0.0
    core._observers = []
    import threading
    core._observers_lock = threading.Lock()
    core.poly_settings = MagicMock()
    core.poly_settings.get.side_effect = lambda k: {
        "unicode_send_composition_mode": unicode_mode}.get(k, False)
    core.worker = MagicMock()
    core.device_mgr = MagicMock()
    core.overlay_handler = MagicMock()
    core.keeb = MagicMock()
    # apply_reconnect re-asserts the host brightness mode on connect via
    # refresh_daylight_brightness(), which reads core.sunlight (set in the real
    # __init__ this bare core skips).
    core.sunlight = MagicMock()
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

    def test_within_range_mismatch_connects_and_runs_post_connect(self):
        # A protocol mismatch that is at/above the floor (older OR newer than the
        # host) now CONNECTS and runs the post-connect work; individual features
        # self-gate by protocol from there.
        for kb_proto in (__protocol__ - 1, __protocol__ + 1):
            with self.subTest(kb_proto=kb_proto):
                core = make_core()
                applied = core.apply_reconnect(connect_snapshot(kb_proto=kb_proto))
                self.assertTrue(core.connected)
                self.assertTrue(core.device_present)
                self.assertTrue(applied["decision"]["do_post_connect"])
                core.overlay_handler.force_resend.assert_called_once()

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
        self.assertIsNone(applied["decision"])
        self.assertFalse(applied["do_overlay_reset"])

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
