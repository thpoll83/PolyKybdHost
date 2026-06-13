"""PolyCore.apply_reconnect — the operational half of the reconnect apply.

Drives a bare PolyCore (no device construction) through the snapshot
shapes the worker probe produces, pinning: state/present updates, the
post-connect work (unicode push, cache reset, window resend, overlay
reset handshake), fresh-boot cache invalidation, the paused guard, and
the status_changed emission. UI rendering stays in the GUI and is out
of scope here.
"""
import logging
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

    def test_protocol_mismatch_keeps_presence_for_flashing(self):
        core = make_core()
        applied = core.apply_reconnect(connect_snapshot(kb_proto=__protocol__ + 1))
        self.assertFalse(core.connected)
        self.assertTrue(core.device_present)      # GET_ID answered → flashable
        self.assertFalse(applied["decision"]["do_post_connect"])
        self.assertFalse(applied["do_overlay_reset"])
        core.overlay_handler.force_resend.assert_not_called()

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


if __name__ == '__main__':
    unittest.main()
