"""The Blender add-on's bpy-free core (blender-addon/polykybd_context_reporter/core.py)."""
import contextlib
import importlib.util
import io
import json
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_CORE = (Path(__file__).resolve().parents[2] / "blender-addon"
         / "polykybd_context_reporter" / "core.py")
_spec = importlib.util.spec_from_file_location("polykybd_reporter_core", _CORE)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


class ContextUrlTest(unittest.TestCase):
    def test_mode_and_editor(self):
        self.assertEqual(core.context_url("EDIT_MESH", "VIEW_3D", "VIEW_3D"),
                         "blender://EDIT_MESH/VIEW_3D")

    def test_ui_type_only_when_it_says_more(self):
        self.assertEqual(core.context_url("EDIT_MESH", "IMAGE_EDITOR", "UV"),
                         "blender://EDIT_MESH/IMAGE_EDITOR/UV")
        self.assertEqual(core.context_url("OBJECT", "NODE_EDITOR", "ShaderNodeTree"),
                         "blender://OBJECT/NODE_EDITOR/ShaderNodeTree")

    def test_unknown_editor_sends_nothing(self):
        self.assertIsNone(core.context_url("OBJECT", None))
        self.assertIsNone(core.context_url("", "VIEW_3D"))

    def test_odd_tokens_are_dropped_not_sent(self):
        # An add-on's node tree idname is not ours to vouch for.
        self.assertEqual(core.context_url("OBJECT", "NODE_EDITOR", "My Tree/../x"),
                         "blender://OBJECT/NODE_EDITOR")
        self.assertIsNone(core.context_url("OBJECT", "VIEW 3D"))


class AreaAtTest(unittest.TestCase):
    def test_finds_the_containing_area(self):
        a = SimpleNamespace(x=0, y=0, width=100, height=50, type="A")
        b = SimpleNamespace(x=100, y=0, width=100, height=50, type="B")
        self.assertIs(core.area_at([a, b], 150, 10), b)
        self.assertIs(core.area_at([a, b], 99, 49), a)
        self.assertIsNone(core.area_at([a, b], 200, 10))
        self.assertIsNone(core.area_at([a, b], None, None))


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
        # Two lost keep-alives must still land inside the host's freshness window.
        self.assertLess(core.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)

    def test_default_port_is_the_hosts(self):
        self.assertEqual(core.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)


class PayloadTest(unittest.TestCase):
    def test_carries_mode_and_editor_only(self):
        body = json.loads(core.payload("blender://OBJECT/VIEW_3D"))
        self.assertEqual(body, {"app": "blender", "url": "blender://OBJECT/VIEW_3D",
                                "focused": True})
        self.assertEqual(json.loads(core.payload("u", "t"))["token"], "t")
        body = json.loads(core.payload("u", pid=7, input_age=1.234))
        self.assertEqual((body["pid"], body["input_age"]), (7, 1.2))
        self.assertNotIn("pid", json.loads(core.payload("u")))


class SenderTest(unittest.TestCase):
    def test_submit_never_blocks_and_latest_wins(self):
        gate, got = threading.Event(), []

        def slow_post(port, body):
            gate.wait(2)
            got.append((port, json.loads(body)["url"]))

        s = core.Sender(post=slow_post)
        t0 = time.monotonic()
        for i in range(5):
            s.submit(50164, f"blender://M{i}/VIEW_3D")
        self.assertLess(time.monotonic() - t0, 0.1)
        gate.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and (not got or got[-1][1] != "blender://M4/VIEW_3D"):
            time.sleep(0.01)
        s.stop()
        self.assertEqual(got[-1], (50164, "blender://M4/VIEW_3D"))
        self.assertLessEqual(len(got), 2)   # the in-flight one, then only the latest

    def test_a_failing_post_does_not_kill_the_thread(self):
        calls, posted = [], threading.Semaphore(0)

        def boom(port, body):
            calls.append(1)
            posted.release()
            raise OSError("refused")

        s = core.Sender(post=boom)
        s.submit(1, "a")
        self.assertTrue(posted.acquire(timeout=2))
        s.submit(1, "b")
        self.assertTrue(posted.acquire(timeout=2))   # the thread survived "a"
        s.stop()
        self.assertEqual(len(calls), 2)

    def test_a_delivery_error_is_printed_once(self):
        # A wrong port or token must be diagnosable from Blender's console
        # without a line on every keep-alive.
        def refused(port, body):
            raise OSError("refused")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            s = core.Sender(post=refused)
            for url in ("a", "b", "c"):
                s.submit(1, url)
                time.sleep(0.05)
            s.stop()
        self.assertEqual(err.getvalue().count("report not delivered: OSError: refused"), 1)


if __name__ == "__main__":
    unittest.main()
