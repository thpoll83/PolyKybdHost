"""The IDA plugin's IDA-free half (ida-plugin/polykybd_ida.py).

The module imports without IDA (the glue is defined only when `ida_idaapi`
imports), so these tests load it as a plain file. The IDA calls themselves
(get_current_widget, get_widget_type, register_timer, the hooks) are not run
here; `FakeKernwin` stands in for the constants they return.
"""
import importlib.util
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_PLUGIN = Path(__file__).resolve().parents[2] / "ida-plugin" / "polykybd_ida.py"
_spec = importlib.util.spec_from_file_location("polykybd_ida", _PLUGIN)
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

# The IDA 9 constant names (python.docs.hex-rays.com, ida_kernwin); the values
# are arbitrary here. No BWN_STRUCTS / BWN_ENUMS: IDA 9 removed them.
FakeKernwin = SimpleNamespace(
    BWN_DISASM=27, BWN_DISASMS=27, BWN_PSEUDOCODE=46, BWN_HEXVIEW=5, BWN_TICSR=64,
    BWN_TILVIEW=64, BWN_LOCTYPS=64, BWN_OUTPUT=41, BWN_CLI=42, BWN_FUNCS=3,
    BWN_CHOOSER=35, BWN_STRINGS=7, BWN_NAVBAND=50,
    TCCRT_INVALID=0, TCCRT_FLAT=1, TCCRT_GRAPH=2, TCCRT_PROXIMITY=3)


class ImportTest(unittest.TestCase):
    def test_the_glue_is_absent_outside_ida(self):
        self.assertIsNone(plugin.ida_idaapi)
        self.assertFalse(hasattr(plugin, "PLUGIN_ENTRY"))


class UrlTest(unittest.TestCase):
    def setUp(self):
        self.table = plugin.type_table(FakeKernwin)

    def url(self, widget_type, renderer=None):
        view = plugin.view_for(widget_type, self.table)
        render = plugin.render_token(renderer, FakeKernwin) if renderer is not None else None
        return plugin.context_url(view, render)

    def test_each_view(self):
        self.assertEqual(self.url(27, FakeKernwin.TCCRT_FLAT), "ida://disasm/text")
        self.assertEqual(self.url(27, FakeKernwin.TCCRT_GRAPH), "ida://disasm/graph")
        self.assertEqual(self.url(27, FakeKernwin.TCCRT_PROXIMITY), "ida://disasm/proximity")
        self.assertEqual(self.url(46), "ida://pseudocode")
        self.assertEqual(self.url(5), "ida://hex")
        self.assertEqual(self.url(64), "ida://types")
        self.assertEqual(self.url(3), "ida://list")
        self.assertEqual(self.url(35), "ida://list")
        self.assertEqual(self.url(41), "ida://output")
        self.assertEqual(self.url(42), "ida://cli")

    def test_an_unknown_widget_is_other_and_no_widget_is_none(self):
        self.assertEqual(self.url(50), "ida://other")
        self.assertEqual(self.url(9999), "ida://other")
        self.assertIsNone(self.url(None))

    def test_render_only_for_the_disassembly(self):
        self.assertEqual(plugin.context_url("pseudocode", "graph"), "ida://pseudocode")
        self.assertEqual(plugin.context_url("disasm", None), "ida://disasm")
        self.assertEqual(plugin.context_url("disasm", "../x"), "ida://disasm")

    def test_a_token_outside_the_fixed_set_is_never_sent(self):
        self.assertIsNone(plugin.context_url("IDA View-A", None))
        self.assertIsNone(plugin.context_url("", None))

    def test_a_missing_constant_is_skipped(self):
        table = plugin.type_table(SimpleNamespace(BWN_DISASM=1, BWN_STRUCTS=None))
        self.assertEqual(table, {1: "disasm"})


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def test_defaults(self):
        self.assertEqual(plugin.read_settings(None, env={}),
                         {"enabled": True, "port": DEFAULT_BROWSER_REPORT_PORT, "token": ""})

    def test_file_then_environment(self):
        with open(os.path.join(self.dir, plugin.CONFIG_NAME), "w", encoding="utf-8") as fh:
            json.dump({"port": 50200, "token": "f", "enabled": False}, fh)
        self.assertEqual(plugin.read_settings(self.dir, env={}),
                         {"enabled": False, "port": 50200, "token": "f"})
        s = plugin.read_settings(self.dir, env={"POLYKYBD_REPORT_PORT": "50300",
                                                "POLYKYBD_REPORT_TOKEN": "e"})
        self.assertEqual((s["port"], s["token"]), (50300, "e"))
        self.assertFalse(plugin.read_settings(None, env={"POLYKYBD_REPORT_DISABLED": "1"})["enabled"])

    def test_bad_values_keep_the_default(self):
        with open(os.path.join(self.dir, plugin.CONFIG_NAME), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(plugin.read_settings(self.dir, env={"POLYKYBD_REPORT_PORT": "x"})["port"],
                         plugin.DEFAULT_PORT)
        with open(os.path.join(self.dir, plugin.CONFIG_NAME), "w", encoding="utf-8") as fh:
            json.dump({"port": 70000, "token": 5}, fh)
        s = plugin.read_settings(self.dir, env={})
        self.assertEqual((s["port"], s["token"]), (plugin.DEFAULT_PORT, ""))


class PayloadTest(unittest.TestCase):
    def test_carries_the_view_only(self):
        self.assertEqual(json.loads(plugin.payload("ida://pseudocode")),
                         {"app": "ida", "url": "ida://pseudocode", "focused": True})
        body = json.loads(plugin.payload("u", "t", pid=7, input_age=1.26))
        self.assertEqual((body["token"], body["pid"], body["input_age"]), ("t", 7, 1.3))

    def test_withdrawal(self):
        body = json.loads(plugin.payload(None, pid=7, focused=False))
        self.assertEqual((body["url"], body["focused"]), (None, False))

    def test_constants_match_the_host(self):
        self.assertEqual(plugin.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)
        self.assertLess(plugin.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)


class FakeSender:
    def __init__(self):
        self.sent = []

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        self.sent.append((port, url, token, pid, input_age, focused))


class ReporterTest(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.sender = FakeSender()
        self.r = plugin.Reporter({"enabled": True, "port": 50164, "token": ""}, self.sender,
                                 clock=lambda: self.now[0], pid=42)

    def test_change_keepalive_and_input_age(self):
        self.r.tick("ida://disasm/text")
        self.now[0] += 1
        self.r.input()
        self.r.tick("ida://disasm/text")            # nothing new
        self.now[0] += 0.5
        self.r.tick("ida://pseudocode")              # a change
        self.now[0] += plugin.KEEPALIVE_S
        self.r.tick("ida://pseudocode")              # keep-alive
        urls = [s[1] for s in self.sender.sent]
        self.assertEqual(urls, ["ida://disasm/text", "ida://pseudocode", "ida://pseudocode"])
        self.assertIsNone(self.sender.sent[0][4])     # no input seen yet
        self.assertEqual(self.sender.sent[1][4], 0.5)
        self.assertEqual(self.sender.sent[1][3], 42)

    def test_no_widget_sends_nothing(self):
        self.r.tick(None)
        self.assertEqual(self.sender.sent, [])

    def test_withdraw_once_and_only_after_a_report(self):
        self.r.withdraw()
        self.assertEqual(self.sender.sent, [])
        self.r.tick("ida://hex")
        self.r.withdraw()
        self.r.withdraw()
        self.assertEqual(self.sender.sent[-1][1:], (None, "", 42, None, False))
        self.assertEqual(len(self.sender.sent), 2)
        self.r.tick("ida://hex")                     # reporting again at once
        self.assertEqual(self.sender.sent[-1][1], "ida://hex")

    def test_disabled_sends_nothing(self):
        self.r.settings["enabled"] = False
        self.r.tick("ida://hex")
        self.assertEqual(self.sender.sent, [])


class SenderTest(unittest.TestCase):
    def test_latest_wins_and_stop_waits_for_the_withdrawal(self):
        gate, got = threading.Event(), []

        def slow_post(port, body):
            gate.wait(2)
            got.append(json.loads(body))

        s = plugin.Sender(post=slow_post)
        s.submit(1, "ida://disasm/text")
        time.sleep(0.05)
        s.submit(1, "ida://pseudocode")
        s.submit(1, None, focused=False)
        gate.set()
        s.stop(wait_s=2)
        self.assertFalse(s._thread.is_alive())
        self.assertEqual([b["url"] for b in got], ["ida://disasm/text", None])
        self.assertFalse(got[-1]["focused"])


if __name__ == "__main__":
    unittest.main()
