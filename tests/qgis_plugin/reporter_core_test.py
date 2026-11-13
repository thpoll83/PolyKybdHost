"""The QGIS plugin's Qt-free core (qgis-plugin/polykybd_context_reporter/core.py)."""
import importlib.util
import json
import threading
import time
import unittest
from pathlib import Path

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_CORE = (Path(__file__).resolve().parents[2] / "qgis-plugin"
         / "polykybd_context_reporter" / "core.py")
_spec = importlib.util.spec_from_file_location("polykybd_qgis_reporter_core", _CORE)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


class ContextUrlTest(unittest.TestCase):
    def test_map_tool_groups(self):
        for tool in ("pan", "select", "identify", "measure", "digitize", "vertex", "other"):
            self.assertEqual(core.context_url("map", tool), f"qgis://map/{tool}")

    def test_edit_mode(self):
        self.assertEqual(core.context_url("map", "pan", editing=True), "qgis://map/pan/edit")
        self.assertEqual(core.context_url("map", "digitize", editing=True),
                         "qgis://map/digitize/edit")

    def test_cad_only_for_the_tools_it_changes(self):
        self.assertEqual(core.context_url("map", "digitize", True, True),
                         "qgis://map/digitize/cad/edit")
        self.assertEqual(core.context_url("map", "vertex", False, True),
                         "qgis://map/vertex/cad")
        self.assertEqual(core.context_url("map", "pan", True, True), "qgis://map/pan/edit")

    def test_other_windows_carry_no_tool(self):
        self.assertEqual(core.context_url("layout", "digitize", True, True), "qgis://layout")
        self.assertEqual(core.context_url("dialog"), "qgis://dialog")

    def test_unknown_values(self):
        self.assertIsNone(core.context_url("Untitled Project - QGIS"))
        self.assertEqual(core.context_url("map", "My Plugin Tool"), "qgis://map/other")
        self.assertEqual(core.context_url("map", None), "qgis://map/other")


class SendPolicyTest(unittest.TestCase):
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

    def test_default_port_is_the_hosts(self):
        self.assertEqual(core.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)


class PayloadTest(unittest.TestCase):
    def test_carries_the_mode_only(self):
        body = json.loads(core.payload("qgis://map/pan"))
        self.assertEqual(body, {"app": "qgis", "url": "qgis://map/pan", "focused": True})
        self.assertEqual(json.loads(core.payload("u", "t"))["token"], "t")
        body = json.loads(core.payload("u", pid=7, input_age=1.234))
        self.assertEqual((body["pid"], body["input_age"]), (7, 1.2))

    def test_withdrawal_is_an_unfocused_report_without_url(self):
        body = json.loads(core.payload(None, pid=7, focused=False))
        self.assertEqual((body["url"], body["focused"], body["pid"]), (None, False, 7))


class SenderTest(unittest.TestCase):
    def test_latest_wins_and_stop_delivers_the_withdrawal(self):
        gate, got = threading.Event(), []

        def slow_post(port, body):
            gate.wait(2)
            got.append(json.loads(body))

        s = core.Sender(post=slow_post)
        t0 = time.monotonic()
        s.submit(50164, "qgis://map/pan")
        time.sleep(0.05)                       # the first post is now in flight
        for tool in ("select", "measure"):
            s.submit(50164, f"qgis://map/{tool}")
        s.submit(50164, None, focused=False)
        self.assertLess(time.monotonic() - t0, 0.5)
        s.stop()
        gate.set()
        s.join(2)
        self.assertEqual([b["url"] for b in got], ["qgis://map/pan", None])
        self.assertIs(got[-1]["focused"], False)


if __name__ == "__main__":
    unittest.main()
