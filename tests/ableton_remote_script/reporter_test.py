"""The Ableton Live remote script (ableton-remote-script/PolyKybd/), without Live.

core.py is tested directly. reporter.py (the Live glue) runs against a fake
`Live` module that stands in for `Live.Application.get_application().view`;
that fake follows the Live Object Model documentation, not a running Live.
The sender is tested against the host's real report server on loopback.
"""
import importlib.util
import json
import logging
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S, BrowserUrlProvider
from polyhost.server.browser_report_server import (DEFAULT_BROWSER_REPORT_PORT,
                                                   BrowserReportServer)

_PKG_DIR = Path(__file__).resolve().parents[2] / "ableton-remote-script" / "PolyKybd"


def _load_package(fake_live):
    """Import the script package as Live does (a package with relative
    imports), with `fake_live` as the `Live` module."""
    name = "polykybd_ableton_script"
    for mod in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        del sys.modules[mod]
    old_live = sys.modules.get("Live")
    sys.modules["Live"] = fake_live
    try:
        spec = importlib.util.spec_from_file_location(
            name, _PKG_DIR / "__init__.py", submodule_search_locations=[str(_PKG_DIR)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[name] = pkg
        spec.loader.exec_module(pkg)
        reporter = importlib.import_module(name + ".reporter")
        core = importlib.import_module(name + ".core")
    finally:
        if old_live is None:
            sys.modules.pop("Live", None)
        else:
            sys.modules["Live"] = old_live
    return pkg, reporter, core


class FakeView:
    """Application.View as the LOM documents it."""

    def __init__(self):
        self.focused_document_view = "Session"
        self.visible = {"Detail/Clip": False, "Detail/DeviceChain": False}
        self.listeners = []

    def is_view_visible(self, name, main_window_only=True):
        return self.visible.get(name, False)

    def add_focused_document_view_listener(self, cb):
        self.listeners.append(("doc", None, cb))

    def remove_focused_document_view_listener(self, cb):
        self.listeners.remove(("doc", None, cb))

    def add_is_view_visible_listener(self, name, cb):
        self.listeners.append(("vis", name, cb))

    def remove_is_view_visible_listener(self, name, cb):
        self.listeners.remove(("vis", name, cb))

    def fire(self):
        for _kind, _name, cb in list(self.listeners):
            cb()


def _fake_live(view):
    app = types.SimpleNamespace(view=view)
    application = types.SimpleNamespace(get_application=lambda: app)
    return types.SimpleNamespace(Application=application)


_, _reporter_mod, core = _load_package(_fake_live(FakeView()))


class ContextUrlTest(unittest.TestCase):
    def test_main_views(self):
        self.assertEqual(core.context_url("Session"), "ableton://session")
        self.assertEqual(core.context_url("Arranger"), "ableton://arrangement")

    def test_detail_view(self):
        self.assertEqual(core.context_url("Session", True, False), "ableton://session/clip")
        self.assertEqual(core.context_url("Arranger", False, True),
                         "ableton://arrangement/device")
        self.assertEqual(core.context_url("Arranger", True, True),
                         "ableton://arrangement/clip")

    def test_unknown_view_sends_nothing(self):
        self.assertIsNone(core.context_url(None))
        self.assertIsNone(core.context_url("Browser"))
        self.assertIsNone(core.context_url("session"))


class PolicyAndPayloadTest(unittest.TestCase):
    def test_change_and_keepalive(self):
        p = core.SendPolicy(keepalive_s=3.0)
        self.assertTrue(p.due("u1", 0.0))
        p.sent("u1", 0.0)
        self.assertFalse(p.due("u1", 2.9))
        self.assertTrue(p.due("u2", 1.0))
        self.assertTrue(p.due("u1", 3.0))
        self.assertFalse(p.due(None, 99.0))

    def test_keepalive_keeps_the_host_report_fresh(self):
        self.assertLess(core.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)
        self.assertEqual(core.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)

    def test_payload_carries_the_view_only(self):
        body = json.loads(core.payload("ableton://session/clip", pid=7, input_age=1.26))
        self.assertEqual(body, {"app": "ableton", "url": "ableton://session/clip",
                                "focused": True, "pid": 7, "input_age": 1.3})
        self.assertEqual(json.loads(core.payload("u", "t"))["token"], "t")
        body = json.loads(core.payload(None, pid=7, focused=False))
        self.assertEqual((body["url"], body["focused"]), (None, False))

    def test_http_request_has_length_and_json_type(self):
        req = core.http_request(50164, b'{"a":1}')
        head, body = req.split(b"\r\n\r\n", 1)
        self.assertTrue(head.startswith(b"POST /report HTTP/1.1\r\n"))
        self.assertIn(b"Content-Type: application/json", head)
        self.assertIn(b"Content-Length: 7", head)
        self.assertEqual(body, b'{"a":1}')

    def test_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(core.load_settings(d), (50164, ""))
            (Path(d) / "settings.json").write_text('{"port": 50200, "token": "x"}',
                                                   encoding="utf-8")
            self.assertEqual(core.load_settings(d), (50200, "x"))
            (Path(d) / "settings.json").write_text('{"port": "no", "token": 5}',
                                                   encoding="utf-8")
            self.assertEqual(core.load_settings(d), (50164, ""))
            (Path(d) / "settings.json").write_text("{", encoding="utf-8")
            self.assertEqual(core.load_settings(d), (50164, ""))


# The server logs through .debug_detailed (a PolyHost logger extension).
_LOG = logging.getLogger("ableton-remote-script-test")
if not hasattr(_LOG, "debug_detailed"):
    _LOG.debug_detailed = lambda *a, **k: None


def _server(token=""):
    got = []
    srv = BrowserReportServer(lambda **r: got.append(r), _LOG,
                              port=0, token=token)
    srv.start()
    return srv, srv._httpd.server_address[1], got


def _pump_until(sender, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not cond():
        sender.pump(time.monotonic())
        time.sleep(0.002)


class SenderTest(unittest.TestCase):
    def test_delivers_to_the_real_report_server_without_blocking(self):
        srv, port, got = _server()
        try:
            s = core.Sender()
            s.submit(port, "ableton://session", pid=42, input_age=0.5)
            longest = 0.0
            end = time.monotonic() + 3
            while time.monotonic() < end and not s.delivered:
                t0 = time.monotonic()
                s.pump(time.monotonic())
                longest = max(longest, time.monotonic() - t0)
                time.sleep(0.002)
            self.assertEqual(s.delivered, 1)
            self.assertFalse(s.busy)
            # No step waits on the network; a loopback step takes well under 50 ms.
            self.assertLess(longest, 0.05)
            self.assertEqual(got[-1]["app"], "ableton")
            self.assertEqual(got[-1]["url"], "ableton://session")
            self.assertEqual((got[-1]["pid"], got[-1]["input_age"]), (42, 0.5))
        finally:
            srv.stop()

    def test_latest_report_wins(self):
        srv, port, got = _server()
        try:
            s = core.Sender()
            for v in ("session", "arrangement", "session/clip"):
                s.submit(port, f"ableton://{v}")
            _pump_until(s, lambda: not s.busy)
            self.assertEqual([r["url"] for r in got], ["ableton://session/clip"])
        finally:
            srv.stop()

    def test_a_wrong_token_is_logged_once(self):
        srv, port, got = _server(token="secret")
        lines = []
        try:
            s = core.Sender(log=lines.append)
            for _ in range(3):
                s.submit(port, "ableton://session", token="wrong")
                _pump_until(s, lambda: not s.busy)
            self.assertEqual(got, [])
            self.assertEqual(len(lines), 1)
            self.assertIn("HTTP 403", lines[0])
            s.submit(port, "ableton://session", token="secret")
            _pump_until(s, lambda: not s.busy)
            self.assertEqual(len(got), 1)
        finally:
            srv.stop()

    def test_no_host_running_fails_quietly(self):
        srv, port, _got = _server()
        srv.stop()                       # the port is now closed
        lines = []
        s = core.Sender(log=lines.append)
        s.submit(port, "ableton://session")
        _pump_until(s, lambda: not s.busy)
        self.assertFalse(s.busy)
        self.assertEqual(s.delivered, 0)
        self.assertEqual(len(lines), 1)

    def test_a_hung_exchange_is_dropped_after_the_timeout(self):
        class Never:
            def setblocking(self, _f): pass
            def connect_ex(self, _a): return 0
            def close(self): self.closed = True

        sock = Never()
        s = core.Sender(sock_factory=lambda: sock, select_fn=lambda r, w, x, t: ([], [], []),
                        timeout_s=1.0)
        s.submit(1, "ableton://session")
        s.pump(0.0)
        s.pump(0.5)
        self.assertTrue(s.busy)
        s.pump(1.5)
        self.assertFalse(s.busy)
        self.assertTrue(sock.closed)


class _CInstance:
    def __init__(self):
        self.lines = []

    def log_message(self, msg):
        self.lines.append(msg)


class ReporterGlueTest(unittest.TestCase):
    """reporter.py against the fake view and the real report server."""

    def setUp(self):
        self.srv, self.port, self.got = _server()
        self.view = FakeView()
        pkg, self.mod, _core = _load_package(_fake_live(self.view))
        self.clock = [100.0]
        self.c = _CInstance()
        self.r = pkg.create_instance(self.c)
        self.r._clock = lambda: self.clock[0]
        self.r._last_change = self.clock[0]
        self.r._port = self.port

    def tearDown(self):
        self.srv.stop()

    def _ticks(self, n=1, step=0.1):
        for _ in range(n):
            self.clock[0] += step
            self.r.update_display()
            # The server answers on its own thread; let a tick see it.
            for _ in range(200):
                if not self.r._sender.busy:
                    break
                time.sleep(0.002)
                self.r._sender.pump(self.clock[0])

    def test_reports_each_view_change(self):
        self._ticks()
        self.view.focused_document_view = "Arranger"
        self.view.fire()
        self._ticks()
        self.view.visible["Detail/DeviceChain"] = True
        self._ticks()
        urls = [g["url"] for g in self.got]
        self.assertEqual(urls, ["ableton://session", "ableton://arrangement",
                                "ableton://arrangement/device"])
        self.assertTrue(all(g["app"] == "ableton" and g["focused"] for g in self.got))

    def test_keepalive_and_no_resend_between(self):
        self._ticks()
        self._ticks(20)                  # 2 s: nothing new
        self.assertEqual(len(self.got), 1)
        self._ticks(11)                  # past 3 s
        self.assertEqual(len(self.got), 2)

    def test_input_age_counts_from_the_last_view_change(self):
        self._ticks(32)                  # first report, then a keep-alive at ~3 s
        self.assertGreaterEqual(self.got[-1]["input_age"], 2.9)
        self.view.focused_document_view = "Arranger"
        self.view.fire()
        self._ticks()
        self.assertLess(self.got[-1]["input_age"], 0.2)

    def test_listeners_are_registered_and_removed(self):
        kinds = sorted((k, n) for k, n, _cb in self.view.listeners)
        self.assertEqual(kinds, [("doc", None), ("vis", "Detail/Clip"),
                                 ("vis", "Detail/DeviceChain")])
        self._ticks()
        self.r.disconnect()
        self.assertEqual(self.view.listeners, [])

    def test_disconnect_withdraws_the_view(self):
        self._ticks()
        self.r.disconnect()
        self.assertEqual((self.got[-1]["url"], self.got[-1]["focused"]), (None, False))

    def test_disconnect_without_a_report_sends_nothing(self):
        self.r.disconnect()
        self.assertEqual(self.got, [])

    def test_the_host_routes_the_report(self):
        """The report goes through the host's own report store."""
        src = BrowserUrlProvider(macos_lookup=lambda _a: None)
        self._ticks()
        g = self.got[-1]
        src.update(app=g["app"], url=g["url"], focused=g["focused"], pid=g.get("pid"),
                   input_age=g.get("input_age"))
        self.assertEqual(src.current_url("Ableton Live 12 Suite"), "ableton://session")
        self.assertEqual(src.current_url("ableton live 12 lite"), "ableton://session")

    def test_a_live_error_does_not_raise(self):
        def boom(*_a, **_k):
            raise RuntimeError("view gone")
        self.view.is_view_visible = boom
        self._ticks()                    # must not raise into Live
        self.assertTrue(any("view gone" in line for line in self.c.lines))


if __name__ == "__main__":
    unittest.main()
