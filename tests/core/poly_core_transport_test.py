"""The transport (bulk pipe vs HID only) rides the core's status seam.

Drives the bare core from tests/core/poly_core_apply_test.py: the
status_changed payload names the transport the keyboard layer cached, and
get_status() carries it with the PING info, so a late-attaching client and
polyctl status see the same thing the tray colours its mark by.
"""
import unittest

from tests.core.poly_core_apply_test import make_core


def _snapshot(connected=True):
    return {
        "connected_now": connected, "device_present": connected, "lang": "enUS",
        "state_changed": True, "fresh_boot": False, "version_ok": True,
        "version_msg": "", "kb_version": "1.9.3", "kb_proto": 23,
        "kb_sw_version": (1, 9, 3), "name": "Split72", "hw_version": "3.2.0",
        "lang_list": ["enUS"], "current_lang": "enUS", "transport": "hid",
    }


class TransportOnStatusTest(unittest.TestCase):
    def test_status_changed_names_the_transport(self):
        core = make_core()
        core.keeb.get_transport.return_value = "hid"
        core.keeb.get_link_rate_mbps.return_value = None
        seen = []
        core.subscribe(lambda name, payload: seen.append((name, payload)))
        core.apply_reconnect(_snapshot())
        payloads = [p for n, p in seen if n == "status_changed"]
        self.assertTrue(payloads)
        self.assertEqual(payloads[-1]["transport"], "hid")
        self.assertIsNone(payloads[-1]["link_rate_mbps"])

    def test_get_status_carries_transport_and_pipe_info(self):
        core = make_core(connected=True)
        core.keeb.get_transport.return_value = "pipe"
        core.keeb.get_pipe_info.return_value = {"port": "COM7", "fw": "1.9.3", "rate_mbps": 0.6}
        core.keeb.get_link_rate_mbps.return_value = 0.6
        core.window_backend = "test"
        st = core.get_status()
        self.assertEqual(st["transport"], "pipe")
        self.assertEqual(st["pipe"]["port"], "COM7")
        self.assertEqual(st["link_rate_mbps"], 0.6)


def _probe_core(transport="hid", rate=None):
    """A bare core whose keyboard answers a steady-state probe (connected
    before and after, no fresh boot), so _reconnect_probe takes the early
    return. ``transport`` is what the keyboard layer has cached."""
    core = make_core(connected=True)
    core._last_overlay_activity = -1e9
    core._pipe_probes_left = 0
    core.keeb.hid = None
    core.keeb.connect.return_value = True
    core.keeb.query_current_lang.return_value = (True, "enUS")
    core.keeb.pop_fresh_boot.return_value = False
    core.keeb.get_transport.return_value = transport
    core.keeb.get_link_rate_mbps.return_value = rate
    return core


class SteadyStateProbeTest(unittest.TestCase):
    """The pipe block runs BEFORE the steady-state early return: every published
    snapshot names the transport (the tray reads it from each one, and a snapshot
    without the key cleared the mark one second after connect), and the bounded
    re-probes for a tty node that appears after the hidraw node actually run."""

    def test_steady_state_snapshot_carries_the_cached_transport(self):
        core = _probe_core("pipe", 0.6)
        snap = core._reconnect_probe(lambda: False)
        self.assertFalse(snap["state_changed"])
        self.assertEqual(snap["transport"], "pipe")
        self.assertEqual(snap["link_rate_mbps"], 0.6)
        core.keeb.probe_bulk_pipe.assert_not_called()

    def test_hid_only_keyboard_is_reprobed_a_bounded_number_of_times(self):
        core = _probe_core("hid")
        core._pipe_probes_left = 2
        for _ in range(4):
            core._reconnect_probe(lambda: False)
        self.assertEqual(core.keeb.probe_bulk_pipe.call_count, 2)
        self.assertEqual(core._pipe_probes_left, 0)

    def test_forced_hid_link_skips_the_probe_on_every_path(self):
        # dev_force_hid_link: the fresh connect and the steady-state probes record
        # HID only without touching the port, and the snapshot says "hid".
        core = _probe_core("hid")
        core.poly_settings.get.side_effect = lambda k: {"dev_force_hid_link": True}.get(k, False)
        core.keeb.use_hid_only.return_value = "hid"
        core._pipe_probes_left = 3
        snap = core._reconnect_probe(lambda: False)
        self.assertEqual(snap["transport"], "hid")
        core.keeb.probe_bulk_pipe.assert_not_called()
        core.keeb.use_hid_only.assert_called()
        core.last_applied_connected = False          # the next probe is a fresh connect
        core.keeb.query_version_info.return_value = (True, "")
        core.keeb.enumerate_lang.return_value = (True, ["enUS"])
        snap = core._reconnect_probe(lambda: False)
        self.assertTrue(snap["state_changed"])
        self.assertEqual(snap["transport"], "hid")
        core.keeb.probe_bulk_pipe.assert_not_called()

    def test_settings_change_applies_the_link_choice_without_a_reconnect(self):
        core = _probe_core("pipe", 0.6)
        forced = {"dev_force_hid_link": True}
        core.poly_settings.get.side_effect = lambda k: forced.get(k, False)
        core.note_settings_changed({"dev_force_hid_link"})
        core.keeb.use_hid_only.assert_called_once()
        forced["dev_force_hid_link"] = False
        core.note_settings_changed({"dev_force_hid_link"})
        core.keeb.forget_bulk_pipe.assert_called()
        self.assertEqual(core._pipe_probes_left, 5)

    def test_update_port_reads_the_setting_not_only_the_cache(self):
        # A probe that finished after the setting was turned on left the port in
        # the cache; the flash paths still get None while the setting is on.
        core = _probe_core("pipe", 0.6)
        core.keeb.get_pipe_info.return_value = {"port": "/dev/ttyACM0", "rate_mbps": 0.6}
        self.assertEqual(core.pipe_port_for_update(), "/dev/ttyACM0")
        core.poly_settings.get.side_effect = lambda k: {"dev_force_hid_link": True}.get(k, False)
        self.assertIsNone(core.pipe_port_for_update())

    def test_a_keyboard_on_the_pipe_is_not_reprobed(self):
        core = _probe_core("pipe", 0.6)
        core._pipe_probes_left = 2
        core._reconnect_probe(lambda: False)
        core.keeb.probe_bulk_pipe.assert_not_called()
        self.assertEqual(core._pipe_probes_left, 2)


if __name__ == "__main__":
    unittest.main()
