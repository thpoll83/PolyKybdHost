"""Protocol foundation: JSON framing over a real multiprocessing Connection,
authkey create/reuse with 0600 perms, and the message builders. No Qt.
"""
import multiprocessing
import os
import sys
import unittest
from unittest import mock

from polyhost.server import protocol as p


class TestFraming(unittest.TestCase):
    def test_roundtrip_json_over_connection(self):
        a, b = multiprocessing.Pipe()
        p.send_message(a, p.make_request(1, "status.get", {"x": 1}))
        msg = p.recv_message(b)
        self.assertEqual(msg["id"], 1)
        self.assertEqual(msg["method"], "status.get")
        self.assertEqual(msg["params"], {"x": 1})

    def test_event_notification_shape(self):
        ev = p.make_event("status_changed", {"connected": True})
        self.assertNotIn("id", ev)
        self.assertEqual(ev["method"], p.EVENT_NOTIFICATION)
        self.assertEqual(ev["params"]["name"], "status_changed")
        self.assertEqual(ev["params"]["payload"], {"connected": True})

    def test_error_and_response_builders(self):
        self.assertEqual(p.make_response(7, {"ok": 1}),
                         {"jsonrpc": "2.0", "id": 7, "result": {"ok": 1}})
        err = p.make_error(7, p.ERR_DEVICE, "boom")
        self.assertEqual(err["error"]["code"], p.ERR_DEVICE)


class TestHello(unittest.TestCase):
    def test_matching_version_ok(self):
        ok, _ = p.check_hello(p.hello_params("0.8.31"))
        self.assertTrue(ok)

    def test_major_mismatch_rejected(self):
        ok, msg = p.check_hello({"control_protocol": p.CONTROL_PROTOCOL_VERSION + 1})
        self.assertFalse(ok)
        self.assertIn("mismatch", msg)


class TestAuthkey(unittest.TestCase):
    def test_create_then_reuse_with_0600(self):
        with mock.patch.object(p, "user_config_dir") as cfg:
            import tempfile
            d = tempfile.mkdtemp()
            cfg.return_value = d
            k1 = p.load_or_create_authkey()
            k2 = p.load_or_create_authkey()
            self.assertEqual(k1, k2)
            self.assertTrue(len(k1) >= 32)
            if sys.platform != "win32":
                mode = os.stat(p.authkey_path()).st_mode & 0o777
                self.assertEqual(mode, 0o600)


class TestEndpoint(unittest.TestCase):
    def test_address_family_matches_platform(self):
        addr = p.endpoint_address()
        if sys.platform == "win32":
            self.assertTrue(addr.startswith(r"\\.\pipe"))
        else:
            self.assertTrue(addr.endswith(".sock"))


if __name__ == "__main__":
    unittest.main()
