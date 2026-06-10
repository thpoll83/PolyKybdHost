"""Tests for the Qt-free reconnect decision logic (decide_reconnect_apply).

These pin the compatibility decision tree extracted from PolyHost.reconnect so
it can be exercised without a QApplication.
"""
import unittest

from polyhost.gui.worker_bridge import decide_reconnect_apply

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


if __name__ == "__main__":
    unittest.main()
