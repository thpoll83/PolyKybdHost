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

    def test_app_report_reaches_callback(self):
        status, _ = _post(self.port, {
            "app": "blender", "url": "blender://OBJECT/VIEW_3D", "focused": True})
        self.assertEqual(status, 200)
        self.assertEqual(self.reports[0]["app"], "blender")
        self.assertEqual(self.reports[0]["url"], "blender://OBJECT/VIEW_3D")
        self.assertIsNone(self.reports[0]["browser"])

    def test_app_report_passes_sane_instance_identity(self):
        _post(self.port, {"app": "blender", "url": "blender://OBJECT/VIEW_3D",
                          "focused": True, "pid": 4242, "input_age": 0.4})
        self.assertEqual(self.reports[0]["pid"], 4242)
        self.assertEqual(self.reports[0]["input_age"], 0.4)

    def test_app_report_drops_malformed_instance_identity(self):
        _post(self.port, {"app": "blender", "url": "blender://OBJECT/VIEW_3D",
                          "focused": True, "pid": "4242", "input_age": -1})
        self.assertNotIn("pid", self.reports[0])
        self.assertNotIn("input_age", self.reports[0])

    def test_text_fields_that_are_not_text_pass_as_none(self):
        _post(self.port, {"app": "vim", "url": {"a": 1}, "title": 5,
                          "browser": ["chrome"], "focused": True})
        self.assertIsNone(self.reports[0]["url"])
        self.assertIsNone(self.reports[0]["title"])
        self.assertIsNone(self.reports[0]["browser"])
        _post(self.port, {"app": 7, "url": 12345, "focused": True})
        self.assertNotIn("app", self.reports[1])
        self.assertIsNone(self.reports[1]["url"])

    def test_browser_report_carries_no_app_key(self):
        # Callbacks written before context reporters keep their signature.
        _post(self.port, {"browser": "chrome", "url": "https://a", "focused": True})
        self.assertNotIn("app", self.reports[0])

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

    def test_non_json_content_type_rejected(self):
        # A "simple" content type (no CORS preflight) must not be accepted on
        # /report — closes the cross-origin web-page spoofing vector.
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/report", method="POST",
            data=b'{"browser": "chrome", "url": "https://x"}',
            headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=2)
        self.assertEqual(cm.exception.code, 415)
        self.assertEqual(self.reports, [])

    def test_report_has_no_cors_grant_but_ping_does(self):
        # /ping is CORS-enabled (the options page tests it cross-origin)...
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/ping", timeout=2) as r:
            self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        # ...but /report must never emit a wildcard CORS grant.
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/report", method="POST",
            data=json.dumps({"browser": "chrome", "url": "https://x"}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as r:
            self.assertIsNone(r.headers.get("Access-Control-Allow-Origin"))

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
        status, _body = _post(self.port, {
            "browser": "chrome", "url": "https://x", "token": "s3cret"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.reports), 1)


URL = "https://claude.ai/code/session_abc"


class TabCommandsTest(unittest.TestCase):
    """The host -> extension command queue, without sockets."""

    def test_no_extension_listening_answers_none(self):
        from polyhost.server.browser_report_server import TabCommands
        self.assertIsNone(TabCommands().focus(URL, 0.1))

    def test_command_and_answer(self):
        import threading
        from polyhost.server.browser_report_server import TabCommands
        cmds = TabCommands()
        self.assertIsNone(cmds.next(0.01))           # a poll: now listening
        got = []

        def extension():
            command = cmds.next(2)
            got.append(command)
            cmds.answer(command["id"], True)
        t = threading.Thread(target=extension)
        t.start()
        self.assertTrue(cmds.focus(URL, 2))
        t.join(2)
        self.assertEqual(got[0]["focus_url"], URL)
        self.assertFalse(cmds.answer(got[0]["id"], True))   # one answer per command
        self.assertFalse(cmds.answer("1", True))

    def test_unanswered_command_is_withdrawn(self):
        from polyhost.server.browser_report_server import TabCommands
        cmds = TabCommands()
        cmds.next(0.01)
        self.assertIsNone(cmds.focus(URL, 0.05))
        self.assertIsNone(cmds.next(0.01))           # not handed out later


def _call(port, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                 data=data, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


class CommandEndpointTest(unittest.TestCase):
    EXT = {"X-PolyKybd-Extension": "1"}

    def setUp(self):
        self.srv = BrowserReportServer(lambda **kw: None, _log, port=0, token="s3cret")
        self.srv.command_wait_s = 1.0
        self.srv.start()
        self.port = self.srv._httpd.server_address[1]
        self.addCleanup(self.srv.stop)

    def test_header_and_token_required_and_no_cors(self):
        status, _, _ = _call(self.port, "GET", "/command")
        self.assertEqual(status, 403)                 # a page cannot send the header
        status, _, _ = _call(self.port, "GET", "/command", headers=self.EXT)
        self.assertEqual(status, 403)                 # the token is set here
        status, body, headers = _call(self.port, "GET", "/command",
                                      headers={**self.EXT, "X-PolyKybd-Token": "s3cret"})
        self.assertEqual((status, body["command"]), (200, None))
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_round_trip_over_http(self):
        import threading
        hdrs = {**self.EXT, "X-PolyKybd-Token": "s3cret"}
        _call(self.port, "GET", "/command", headers=hdrs)   # the extension is there
        result = []
        t = threading.Thread(target=lambda: result.append(self.srv.commands.focus(URL, 3)))
        t.start()
        status, body, _ = _call(self.port, "GET", "/command", headers=hdrs)
        command = body["command"]
        self.assertEqual(command["focus_url"], URL)
        status, body, _ = _call(self.port, "POST", "/command_result",
                                {"id": command["id"], "found": True}, hdrs)
        self.assertEqual(status, 200)
        t.join(3)
        self.assertEqual(result, [True])


if __name__ == "__main__":
    unittest.main()
