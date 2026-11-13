"""The Maya-free half of the Maya plug-in (maya-plugin/plug-ins/polykybd_mode_reporter.py).

The file imports without Maya: `maya.cmds` and PySide are imported only inside
the Maya glue. These tests run the URL, payload, send-policy and sender parts.
The Maya calls themselves are not run here (no Maya in CI)."""
import importlib.util
import json
import sys
import threading
import unittest
from pathlib import Path

from polyhost.handler.browser_url import CONTEXT_REPORTERS, DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_PLUGIN = (Path(__file__).resolve().parents[2] / "maya-plugin" / "plug-ins"
           / "polykybd_mode_reporter.py")
_spec = importlib.util.spec_from_file_location("polykybd_mode_reporter", _PLUGIN)
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)


class ImportTest(unittest.TestCase):
    def test_imports_without_maya(self):
        self.assertNotIn("maya", sys.modules)
        self.assertNotIn("maya.cmds", sys.modules)

    def test_maya_entry_points_exist(self):
        for name in ("maya_useNewAPI", "initializePlugin", "uninitializePlugin"):
            self.assertTrue(callable(getattr(rep, name)), name)


class PanelKindTest(unittest.TestCase):
    def test_built_in_types(self):
        self.assertEqual(rep.panel_kind("modelPanel"), "model")
        self.assertEqual(rep.panel_kind("outlinerPanel"), "outliner")

    def test_scripted_types(self):
        cases = {"graphEditor": "graph", "dopeSheetPanel": "dopesheet",
                 "timeEditorPanel": "timeeditor", "polyTexturePlacementPanel": "uv",
                 "nodeEditorPanel": "node", "hyperShadePanel": "hypershade"}
        for stype, kind in cases.items():
            self.assertEqual(rep.panel_kind("scriptedPanel", stype, "x"), kind, stype)

    def test_unknown_type_falls_back_to_the_panel_name(self):
        self.assertEqual(rep.panel_kind("scriptedPanel", None, "graphEditor1"), "graph")
        self.assertEqual(rep.panel_kind(None, None, "modelPanel4"), "model")

    def test_anything_else_is_other(self):
        self.assertEqual(rep.panel_kind("scriptedPanel", "myStudioPanel", "myStudioPanel1"),
                         "other")
        self.assertEqual(rep.panel_kind(None, None, None), "other")


class SelectModeTest(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(rep.select_mode(True, False), "object")
        self.assertEqual(rep.select_mode(False, True), "component")
        self.assertEqual(rep.select_mode(False, False, True), "hierarchy")
        self.assertEqual(rep.select_mode(False, False, False), "other")


class ContextUrlTest(unittest.TestCase):
    def test_url(self):
        self.assertEqual(rep.context_url("graph", "object"), "maya://graph/object")
        self.assertEqual(rep.context_url("model", "component"), "maya://model/component")

    def test_only_known_tokens_are_sent(self):
        # A panel name or a user type never reaches the URL.
        self.assertIsNone(rep.context_url("graphEditor1", "object"))
        self.assertIsNone(rep.context_url("graph", "my scene.ma"))

    def test_every_routed_panel_has_a_token(self):
        kinds = set(rep.PANEL_TYPES.values()) | set(rep.SCRIPTED_TYPES.values())
        self.assertLessEqual({"graph", "timeeditor", "uv", "node", "hypershade"}, kinds)


class PayloadTest(unittest.TestCase):
    def test_fields(self):
        body = json.loads(rep.payload("maya://uv/component", pid=42, input_age=1.234))
        self.assertEqual(body, {"app": "maya", "url": "maya://uv/component",
                                "focused": True, "pid": 42, "input_age": 1.2})

    def test_token_only_when_set(self):
        self.assertNotIn("token", json.loads(rep.payload("maya://model/object")))
        self.assertEqual(json.loads(rep.payload("maya://model/object", token="t"))["token"], "t")

    def test_withdrawal(self):
        body = json.loads(rep.payload(None, focused=False))
        self.assertIsNone(body["url"])
        self.assertIs(body["focused"], False)

    def test_app_is_on_the_host_allow_list(self):
        self.assertIn(rep.APP, set(CONTEXT_REPORTERS.values()))


class SettingsTest(unittest.TestCase):
    def test_defaults_match_the_host(self):
        self.assertEqual(rep.settings({}), (DEFAULT_BROWSER_REPORT_PORT, ""))

    def test_values_and_bad_port(self):
        self.assertEqual(rep.settings({"POLYKYBD_REPORT_PORT": "5000",
                                       "POLYKYBD_REPORT_TOKEN": "abc"}), (5000, "abc"))
        self.assertEqual(rep.settings({"POLYKYBD_REPORT_PORT": "x"})[0], rep.DEFAULT_PORT)
        self.assertEqual(rep.settings({"POLYKYBD_REPORT_PORT": "70000"})[0], rep.DEFAULT_PORT)


class SendPolicyTest(unittest.TestCase):
    def test_keepalive_inside_the_host_freshness_window(self):
        self.assertLess(rep.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)

    def test_change_and_keepalive(self):
        p = rep.SendPolicy(keepalive_s=3.0)
        self.assertTrue(p.due("maya://model/object", 0.0))
        p.sent("maya://model/object", 0.0)
        self.assertFalse(p.due("maya://model/object", 1.0))
        self.assertTrue(p.due("maya://graph/object", 1.0))
        self.assertTrue(p.due("maya://model/object", 3.0))
        self.assertFalse(p.due(None, 10.0))


class SenderTest(unittest.TestCase):
    def test_delivers_the_withdrawal_on_stop(self):
        got, done = [], threading.Event()

        def post(port, body):
            got.append((port, json.loads(body)))
            if json.loads(body)["url"] is None:
                done.set()

        s = rep.Sender(post=post)
        s.submit(50164, None, focused=False)
        s.stop(wait_s=2.0)
        self.assertTrue(done.wait(2.0))
        self.assertEqual(got[-1][0], 50164)
        self.assertIs(got[-1][1]["focused"], False)

    def test_survives_a_failing_post(self):
        calls, second = [], threading.Event()

        def post(port, body):
            calls.append(body)
            if len(calls) == 1:
                raise ConnectionRefusedError("down")
            second.set()

        s = rep.Sender(post=post)
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            s.submit(1, "maya://model/object")
            for _ in range(200):
                if calls:
                    break
                threading.Event().wait(0.01)
            s.submit(1, "maya://graph/object")
            self.assertTrue(second.wait(2.0))
        s.stop()


if __name__ == "__main__":
    unittest.main()
