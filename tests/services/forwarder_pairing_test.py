"""services/forwarder_pairing.py: the code round-trips the key, a bad code is
refused, and the saved pairing is what a forwarder picks up."""
import os
import shutil
import tempfile
import unittest
import unittest.mock as mock

from polyhost.services import forwarder_pairing as fp


class ForwarderPairingTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        from polyhost.server import protocol
        p = mock.patch.object(protocol, "_config_dir", lambda: self.dir)
        p.start()
        self.addCleanup(p.stop)

    def test_code_round_trips_the_key(self):
        from polyhost.server import protocol
        code = fp.pairing_code()
        groups = code.split("-")
        self.assertEqual((len(groups), {len(g) for g in groups}), (8, {8}))
        key = protocol.load_or_create_authkey(protocol.window_report_authkey_path())
        self.assertEqual(fp.parse_code(code), key)
        self.assertEqual(fp.parse_code("  " + code.upper().replace("-", " ") + "\n"), key)

    def test_bad_codes(self):
        for text in ("", "abc", "g" * 64, "a" * 63, "a" * 65):
            self.assertIsNone(fp.parse_code(text), text)

    def test_save_load_forget(self):
        self.assertIsNone(fp.paired_key_file())
        key = b"0123456789abcdef" * 4
        path = fp.save_paired_key(key)
        self.assertEqual(os.path.dirname(path), self.dir)
        self.assertEqual(fp.paired_key_file(), path)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), key)
        if os.name == "posix":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        with open(path, "wb") as fh:
            fh.write(b"not a key")
        self.assertIsNone(fp.paired_key_file())          # a broken file is no pairing
        self.assertTrue(fp.forget_pairing())
        self.assertFalse(fp.forget_pairing())

    def test_the_paired_key_opens_the_endpoint(self):
        """The forwarder's side of the handshake with the saved key matches the
        keyboard computer's endpoint key."""
        import socket
        from polyhost.server import window_report_client as wrc
        from polyhost.server.window_report_server import WindowReportServer
        from polyhost.server import protocol
        server_key = protocol.load_or_create_authkey(protocol.window_report_authkey_path())
        path = fp.save_paired_key(fp.parse_code(fp.pairing_code()))
        with open(path, "rb") as fh:
            client_key = fh.read().strip()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()

        class _Log:
            def __getattr__(self, _name):
                return lambda *a, **k: None
        server = WindowReportServer(lambda *a, **k: (True, {"ok": True}), "0.0.1", _Log(),
                                    bind_host="127.0.0.1", port=port, authkey=server_key)
        server.start()
        self.addCleanup(server.stop)
        client = wrc.connect("127.0.0.1", port=port, authkey=client_key, timeout=3.0)
        self.addCleanup(client.close)
        self.assertTrue(client.report(1, "term", "t"))


if __name__ == "__main__":
    unittest.main()
