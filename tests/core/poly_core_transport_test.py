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


if __name__ == "__main__":
    unittest.main()
