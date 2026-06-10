"""Tests for the Qt-free reconnect decision logic (decide_reconnect_apply).

These pin the compatibility decision tree extracted from PolyHost.reconnect so
it can be exercised without a QApplication.
"""
import unittest

from polyhost.gui.worker_bridge import decide_reconnect_apply, decide_probe_publish

HOST_PROTO = 7
HOST_VERSION = "1.2.3"


def _snap(**kw):
    base = {
        "version_ok": True,
        "version_msg": "",
        "kb_version": HOST_VERSION,
        "kb_proto": HOST_PROTO,
        "name": "Split72",
        "hw_version": "A",
    }
    base.update(kw)
    return base


class DecideReconnectApplyTest(unittest.TestCase):
    def test_protocol_match_connects_and_compatible(self):
        d = decide_reconnect_apply(_snap(), HOST_PROTO, HOST_VERSION, False)
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertTrue(d["do_post_connect"])
        self.assertEqual(d["icon"], "sync.svg")
        self.assertIn("FW 1.2.3", d["text"])
        self.assertIn("P7", d["text"])

    def test_protocol_mismatch_disconnects(self):
        d = decide_reconnect_apply(_snap(kb_proto=6), HOST_PROTO, HOST_VERSION, False)
        self.assertFalse(d["connected"])
        self.assertFalse(d["compatible"])
        self.assertEqual(d["icon"], "sync_disabled.svg")
        self.assertIn("Protocol mismatch", d["text"])
        self.assertIn("host P7", d["text"])
        self.assertIn("firmware P6", d["text"])

    def test_protocol_mismatch_bypassed_by_ignore_version(self):
        d = decide_reconnect_apply(_snap(kb_proto=6), HOST_PROTO, HOST_VERSION, True)
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertEqual(d["icon"], "sync_problem.svg")
        self.assertIn("version check bypassed", d["text"])

    def test_old_firmware_no_proto_exact_version(self):
        d = decide_reconnect_apply(
            _snap(kb_proto=None, kb_version=HOST_VERSION), HOST_PROTO, HOST_VERSION, False)
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertEqual(d["icon"], "sync.svg")
        self.assertNotIn("version_warning", d)

    def test_old_firmware_no_proto_version_prefix_warns(self):
        d = decide_reconnect_apply(
            _snap(kb_proto=None, kb_version="1.2.9"), HOST_PROTO, HOST_VERSION, False)
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertEqual(d["icon"], "sync_problem.svg")
        self.assertIn("please update firmware", d["text"])
        self.assertEqual(d["version_warning"], (HOST_VERSION, "1.2.9"))

    def test_old_firmware_incompatible_version(self):
        d = decide_reconnect_apply(
            _snap(kb_proto=None, kb_version="9.9.9", version_msg="m"),
            HOST_PROTO, HOST_VERSION, False)
        self.assertFalse(d["connected"])
        self.assertFalse(d["compatible"])
        self.assertEqual(d["icon"], "sync_disabled.svg")
        self.assertIn("Incompatible version", d["text"])

    def test_incompatible_version_bypassed(self):
        d = decide_reconnect_apply(
            _snap(kb_proto=None, kb_version="9.9.9"), HOST_PROTO, HOST_VERSION, True)
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertEqual(d["icon"], "sync_problem.svg")

    def test_version_parse_failure_disconnects(self):
        d = decide_reconnect_apply(
            _snap(version_ok=False, version_msg="bad string"),
            HOST_PROTO, HOST_VERSION, False)
        self.assertFalse(d["connected"])
        self.assertFalse(d["compatible"])
        self.assertEqual(d["icon"], "sync_disabled.svg")
        self.assertEqual(d["text"], "bad string")

    def test_version_parse_failure_bypassed_uses_bypass_text(self):
        d = decide_reconnect_apply(
            _snap(version_ok=False, version_msg="bad", kb_proto=None,
                  kb_version="0.0.1", name="KB"),
            HOST_PROTO, HOST_VERSION, True)
        # version_ok False but ignore_version: connected becomes True; then the
        # version-prefix check fails (0.0.1 vs 1.2.3) and the ignore bypass text
        # is used.
        self.assertTrue(d["connected"])
        self.assertTrue(d["compatible"])
        self.assertEqual(d["icon"], "sync_problem.svg")
        self.assertIn("version check bypassed", d["text"])
        self.assertEqual(d["ignore_bypass_msg"], "bad")


class TestDecideProbePublish(unittest.TestCase):
    """Debounce of the reconnect probe: a keyboard that is busy syncing a
    large overlay transfer to its slave half misses probes without being
    disconnected — flapping the state wipes and resends the overlays in a
    self-sustaining loop (observed in the field, 2026-06-10)."""

    def test_success_publishes_and_resets_streak(self):
        self.assertEqual(decide_probe_publish(True, True, 2), (True, 0))
        self.assertEqual(decide_probe_publish(True, False, 5), (True, 0))

    def test_transient_failures_while_connected_are_suppressed(self):
        publish, streak = decide_probe_publish(False, True, 0)
        self.assertEqual((publish, streak), (False, 1))
        publish, streak = decide_probe_publish(False, True, streak)
        self.assertEqual((publish, streak), (False, 2))

    def test_threshold_consecutive_failures_publish_disconnect(self):
        publish, streak = decide_probe_publish(False, True, 2)
        self.assertEqual((publish, streak), (True, 3))

    def test_failure_while_already_disconnected_publishes(self):
        # Matches the old 1 s "Reconnect failed" cadence while unplugged.
        publish, _ = decide_probe_publish(False, False, 0)
        self.assertTrue(publish)

    def test_recovery_within_streak_publishes_success(self):
        # Two missed probes, then the device answers again: publish, streak gone.
        _, streak = decide_probe_publish(False, True, 0)
        _, streak = decide_probe_publish(False, True, streak)
        publish, streak = decide_probe_publish(True, True, streak)
        self.assertEqual((publish, streak), (True, 0))


if __name__ == "__main__":
    unittest.main()
