"""The FreeCAD add-on's FreeCAD-free core (freecad-addon/PolyKybd/polykybd_freecad_core.py),
and one report through the real loopback receiver."""
import importlib.util
import json
import threading
import time
import unittest
import unittest.mock
from pathlib import Path

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S, BrowserUrlProvider
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_ADDON = Path(__file__).resolve().parents[2] / "freecad-addon" / "PolyKybd"
_spec = importlib.util.spec_from_file_location("polykybd_freecad_core",
                                               _ADDON / "polykybd_freecad_core.py")
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


class ContextUrlTest(unittest.TestCase):
    def test_builtin_workbenches_get_their_token(self):
        self.assertEqual(core.context_url("SketcherWorkbench"), "freecad://sketcher")
        self.assertEqual(core.context_url("PartDesignWorkbench"), "freecad://partdesign")
        self.assertEqual(core.context_url("BIMWorkbench"), "freecad://bim")
        self.assertEqual(core.context_url("TechDrawWorkbench"), "freecad://techdraw")
        self.assertEqual(core.context_url("AssemblyWorkbench"), "freecad://assembly")
        self.assertEqual(core.context_url("SpreadsheetWorkbench"), "freecad://spreadsheet")

    def test_an_addon_workbench_name_is_not_sent(self):
        self.assertEqual(core.context_url("MyPrivateClientWorkbench"), "freecad://other")
        self.assertEqual(core.context_url("Sketcher/../x"), "freecad://other")

    def test_no_workbench_sends_nothing(self):
        self.assertIsNone(core.context_url(None))
        self.assertIsNone(core.context_url(""))

    def test_tokens_are_short_and_unique(self):
        tokens = list(core.WORKBENCHES.values()) + [core.OTHER]
        self.assertEqual(len(tokens), len(set(tokens)))
        for t in tokens:
            self.assertRegex(t, r"^[a-z]{2,24}$")


class SendPolicyTest(unittest.TestCase):
    def test_change_focus_and_keepalive(self):
        p = core.SendPolicy(keepalive_s=3)
        self.assertTrue(p.due("freecad://part", True, 0))
        p.sent("freecad://part", True, 0)
        self.assertFalse(p.due("freecad://part", True, 1))
        self.assertTrue(p.due("freecad://sketcher", True, 1))
        self.assertTrue(p.due("freecad://part", False, 1))     # lost focus: at once
        self.assertTrue(p.due("freecad://part", True, 3))      # keep-alive
        self.assertFalse(p.due(None, True, 10))

    def test_keepalive_keeps_the_host_report_fresh(self):
        self.assertLess(2 * core.KEEPALIVE_S, DEFAULT_MAX_AGE_S + core.KEEPALIVE_S)
        self.assertLess(core.KEEPALIVE_S, DEFAULT_MAX_AGE_S)
        self.assertLessEqual(core.POLL_S, 0.5)

    def test_default_port_is_the_hosts(self):
        self.assertEqual(core.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)


class PayloadTest(unittest.TestCase):
    def test_carries_the_workbench_only(self):
        body = json.loads(core.payload("freecad://sketcher", pid=42, input_age=0.04))
        self.assertEqual(body, {"app": "freecad", "url": "freecad://sketcher",
                                "focused": True, "pid": 42, "input_age": 0.0})
        self.assertEqual(json.loads(core.payload("freecad://part", token="t"))["token"], "t")

    def test_withdrawal_is_an_unfocused_report_without_url(self):
        body = json.loads(core.payload(None, focused=False))
        self.assertIsNone(body["url"])
        self.assertFalse(body["focused"])


class SenderTest(unittest.TestCase):
    def test_latest_wins_and_stop_delivers_the_withdrawal(self):
        gate, got = threading.Event(), []

        def slow_post(port, body):
            gate.wait(2)
            got.append(json.loads(body))

        s = core.Sender(post=slow_post, log=lambda m: None)
        t0 = time.monotonic()
        s.submit(1, "freecad://part")
        time.sleep(0.05)
        for wb in ("draft", "bim", "sketcher"):
            s.submit(1, f"freecad://{wb}")
        s.submit(1, None, focused=False)
        self.assertLess(time.monotonic() - t0, 0.5)
        s.stop()
        gate.set()
        s._thread.join(2)
        self.assertFalse(s._thread.is_alive())
        self.assertEqual(len(got), 2)                    # in flight, then the latest
        self.assertEqual((got[-1]["url"], got[-1]["focused"]), (None, False))

    def test_a_delivery_error_is_logged_once(self):
        lines = []

        def refused(port, body):
            raise OSError("refused")

        s = core.Sender(post=refused, log=lines.append)
        for url in ("a", "b", "c"):
            s.submit(1, url)
            time.sleep(0.05)
        s.stop(wait_s=1)
        self.assertEqual(len(lines), 1)
        self.assertIn("OSError: refused", lines[0])


class LoopbackTest(unittest.TestCase):
    """http_post() against the host's real receiver, on a free port."""

    def test_a_report_reaches_the_provider(self):
        from polyhost.server.browser_report_server import BrowserReportServer
        provider = BrowserUrlProvider()
        log = unittest.mock.MagicMock()
        server = BrowserReportServer(provider.update, log, port=0)
        server.start()
        try:
            port = server._httpd.server_address[1]
            core.http_post(port, core.payload("freecad://techdraw", pid=7, input_age=0))
            self.assertEqual(provider.current_url("FreeCAD"), "freecad://techdraw")
            core.http_post(port, core.payload(None, pid=7, focused=False))
            self.assertIsNone(provider.current_url("freecad"))
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
