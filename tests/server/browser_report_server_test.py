"""BrowserReportServer — the loopback HTTP receiver for browser tab reports."""
import json
import logging
import unittest
import urllib.error
import urllib.request

from polyhost.server.browser_report_server import BrowserReportServer

# The server logs via .debug_detailed (a PolyHost logger extension); a plain
# logger lacks it, so give the test one.
_log = logging.getLogger("browser_report_test")
if not hasattr(_log, "debug_detailed"):
    _log.debug_detailed = lambda *a, **k: None


def _post(port, obj):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/report", method="POST",
        data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


class TestBrowserReportServer(unittest.TestCase):
    def setUp(self):
        self.reports = []
        self.srv = BrowserReportServer(
            lambda **kw: self.reports.append(kw), _log, port=0)
        self.srv.start()
        # port=0 asks the OS for a free port; read back what it bound.
        self.port = self.srv._httpd.server_address[1]

    def tearDown(self):
        self.srv.stop()

    def test_bound_to_loopback_only(self):
        self.assertEqual(self.srv._httpd.server_address[0], "127.0.0.1")

    def test_report_reaches_callback(self):
        status, body = _post(self.port, {
            "browser": "chrome", "url": "https://mail.google.com",
            "title": "Inbox", "focused": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(len(self.reports), 1)
        self.assertEqual(self.reports[0]["url"], "https://mail.google.com")
        self.assertEqual(self.reports[0]["browser"], "chrome")
        self.assertTrue(self.reports[0]["focused"])

    def test_ping(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/ping", timeout=2) as r:
            body = json.loads(r.read().decode("utf-8"))
        self.assertTrue(body["ok"])
        self.assertEqual(body["app"], "PolyKybdHost")

    def test_bad_json_rejected(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/report", method="POST",
            data=b"not json", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=2)
        self.assertEqual(cm.exception.code, 400)
        self.assertEqual(self.reports, [])

    def test_unknown_path_404(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/other", method="POST", data=b"{}")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=2)
        self.assertEqual(cm.exception.code, 404)


class TestBrowserReportToken(unittest.TestCase):
    def setUp(self):
        self.reports = []
        self.srv = BrowserReportServer(
            lambda **kw: self.reports.append(kw), _log, port=0, token="s3cret")
        self.srv.start()
        self.port = self.srv._httpd.server_address[1]

    def tearDown(self):
        self.srv.stop()

    def test_missing_token_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.port, {"browser": "chrome", "url": "https://x"})
        self.assertEqual(cm.exception.code, 403)
        self.assertEqual(self.reports, [])

    def test_correct_token_accepted(self):
        status, body = _post(self.port, {
            "browser": "chrome", "url": "https://x", "token": "s3cret"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.reports), 1)


if __name__ == "__main__":
    unittest.main()
