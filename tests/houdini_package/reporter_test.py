"""The Houdini context reporter (houdini-package/polykybd/python/polykybd_houdini).

`core.py` needs no Houdini. The `hou` glue in `__init__.py` is driven here with
a fake `hou` module, so these tests say nothing about the real `hou` API: they
pin what the glue does with the values the documented calls return.
"""
import importlib.util
import json
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

PKG = Path(__file__).resolve().parents[2] / "houdini-package"
_PY = PKG / "polykybd" / "python" / "polykybd_houdini"


def _load():
    """The package under a private name, so a test never imports a real one."""
    spec = importlib.util.spec_from_file_location(
        "pk_houdini_reporter", _PY / "__init__.py", submodule_search_locations=[str(_PY)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


reporter = _load()
core = reporter.core


class ContextUrlTest(unittest.TestCase):
    def test_pane_and_network_type(self):
        self.assertEqual(core.context_url("NetworkEditor", "Sop"), "houdini://network/sop")
        self.assertEqual(core.context_url("SceneViewer", "Object"), "houdini://scene/obj")
        self.assertEqual(core.context_url("NetworkEditor", "Driver"), "houdini://network/rop")
        self.assertEqual(core.context_url("NetworkEditor", "Cop2"), "houdini://network/cop")

    def test_a_pane_without_a_network(self):
        self.assertEqual(core.context_url("Textport"), "houdini://textport")
        self.assertEqual(core.context_url("PythonShell", None), "houdini://python")

    def test_unknown_names_are_never_sent_verbatim(self):
        # A pane type or a category this file does not know (a newer Houdini,
        # a custom category) is sent as a fixed token, never as given.
        self.assertEqual(core.context_url("HelpBrowser", "MyStudio/../x"), "houdini://other")
        self.assertEqual(core.context_url("NetworkEditor", "Data"), "houdini://network")

    def test_no_pane_sends_nothing(self):
        self.assertIsNone(core.context_url(None, "Sop"))
        self.assertIsNone(core.context_url("", None))

    def test_every_token_is_short_and_plain(self):
        for tok in list(core.PANE_TOKENS.values()) + list(core.CONTEXT_TOKENS.values()):
            self.assertRegex(tok, r"^[a-z]{2,12}$")


class PolicyAndClockTest(unittest.TestCase):
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

    def test_input_clock_counts_mouse_moves_and_pane_changes(self):
        c = core.InputClock()
        self.assertIsNone(c.age(0.0))
        c.feed((1, 1), 1.0)
        self.assertEqual(c.age(3.0), 2.0)
        c.feed((1, 1), 5.0)                    # no move
        self.assertEqual(c.age(5.0), 4.0)
        c.feed((2, 1), 6.0)
        self.assertEqual(c.age(6.5), 0.5)
        c.feed(None, 8.0, changed=True)        # no Qt, but the pane changed
        self.assertEqual(c.age(8.0), 0.0)


class PayloadAndSettingsTest(unittest.TestCase):
    def test_carries_the_url_only(self):
        self.assertEqual(json.loads(core.payload("houdini://network/sop")),
                         {"app": "houdini", "url": "houdini://network/sop", "focused": True})
        body = json.loads(core.payload("u", "t", pid=7, input_age=1.234))
        self.assertEqual((body["token"], body["pid"], body["input_age"]), ("t", 7, 1.2))

    def test_withdrawal(self):
        body = json.loads(core.payload(None, pid=7, focused=False))
        self.assertEqual((body["url"], body["focused"]), (None, False))

    def test_settings_from_the_package_environment(self):
        self.assertEqual(core.settings({}), (True, 50164, ""))
        self.assertEqual(core.settings({"POLYKYBD_REPORT": "0"})[0], False)
        self.assertEqual(core.settings({"POLYKYBD_REPORT_PORT": "51000",
                                        "POLYKYBD_REPORT_TOKEN": "s"}), (True, 51000, "s"))
        self.assertEqual(core.settings({"POLYKYBD_REPORT_PORT": "x"})[1], 50164)
        self.assertEqual(core.settings({"POLYKYBD_REPORT_PORT": "70000"})[1], 50164)

    def test_package_file_defaults_match(self):
        data = json.loads((PKG / "polykybd.json").read_text(encoding="utf-8"))
        env = {k: v for d in data["env"] for k, v in d.items()}
        self.assertEqual(int(env["POLYKYBD_REPORT_PORT"]), DEFAULT_BROWSER_REPORT_PORT)
        self.assertEqual(env["POLYKYBD_HOUDINI"], "$HOUDINI_PACKAGE_PATH/polykybd")
        self.assertEqual(data["hpath"], "$HOUDINI_PACKAGE_PATH/polykybd")

    def test_every_uiready_stub_is_the_same(self):
        stubs = sorted((PKG / "polykybd").glob("python3.*libs/uiready.py"))
        self.assertGreaterEqual(len(stubs), 5)
        self.assertEqual(len({s.read_bytes() for s in stubs}), 1)


class SenderTest(unittest.TestCase):
    def test_latest_wins_and_a_failure_does_not_kill_the_thread(self):
        got, posted = [], threading.Semaphore(0)

        def post(port, body):
            got.append(json.loads(body)["url"])
            posted.release()
            if len(got) == 1:
                raise OSError("refused")

        s = core.Sender(post=post)
        s.submit(1, "houdini://scene/obj")
        self.assertTrue(posted.acquire(timeout=2))
        s.submit(1, "houdini://network/sop")
        self.assertTrue(posted.acquire(timeout=2))
        s.stop()
        self.assertEqual(got, ["houdini://scene/obj", "houdini://network/sop"])


# --- the hou glue, with a fake hou ------------------------------------------

class _Enum:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Node:
    def __init__(self, category):
        self._category = category

    def childTypeCategory(self):
        return _Enum(self._category)


class _Pane:
    def __init__(self, kind, category=None):
        self._kind = kind
        if category is not None:
            self.pwd = lambda: _Node(category)

    def type(self):
        return _Enum(self._kind)


def _fake_hou(ui=True):
    hou = types.ModuleType("hou")
    hou.under = None
    hou.callbacks = []
    hou.isUIAvailable = lambda: ui
    hou.ui = types.SimpleNamespace(
        paneTabUnderCursor=lambda: hou.under,
        addEventLoopCallback=hou.callbacks.append,
        removeEventLoopCallback=hou.callbacks.remove)
    return hou


class GlueTest(unittest.TestCase):

    def setUp(self):
        self.hou = _fake_hou()
        patcher = mock.patch.dict(sys.modules, {"hou": self.hou})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sent = []
        self.direct = []

        class FakeSender:
            def __init__(s, post=None):
                pass

            def submit(s, port, url, token="", pid=None, input_age=None, focused=True):
                self.sent.append((port, url, token, focused))

            def stop(s):
                pass

        for target, value in ((core, "Sender"), ):
            p = mock.patch.object(target, value, FakeSender)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(core, "http_post", lambda port, body: self.direct.append(json.loads(body)))
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(reporter.atexit, "register", lambda f: None)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(reporter.stop)
        self.addCleanup(reporter._state.update, url=None, reported=False, next_poll=0.0)

    def tick(self):
        reporter._state["next_poll"] = 0.0
        reporter._tick()

    def test_pane_under_the_pointer_is_reported(self):
        with mock.patch.dict("os.environ", {"POLYKYBD_REPORT_TOKEN": "tok"}):
            reporter.start()
        self.assertEqual(self.hou.callbacks, [reporter._tick])
        self.hou.under = _Pane("NetworkEditor", "Sop")
        self.tick()
        self.hou.under = _Pane("SceneViewer", "Object")
        self.tick()
        self.hou.under = _Pane("Textport")
        self.tick()
        self.assertEqual([s[1] for s in self.sent],
                         ["houdini://network/sop", "houdini://scene/obj", "houdini://textport"])
        self.assertTrue(all(s[2] == "tok" and s[3] for s in self.sent))

    def test_outside_every_pane_the_last_pane_is_kept(self):
        reporter.start()
        self.hou.under = _Pane("NetworkEditor", "Lop")
        self.tick()
        self.hou.under = None                  # over the shelf or the menu bar
        reporter._state["policy"].last_sent = -100.0   # keep-alive due
        self.tick()
        self.assertEqual([s[1] for s in self.sent],
                         ["houdini://network/lop", "houdini://network/lop"])

    def test_nothing_is_sent_before_a_pane_is_known(self):
        reporter.start()
        self.tick()
        self.assertEqual(self.sent, [])

    def test_a_failing_pwd_still_reports_the_pane(self):
        reporter.start()
        pane = _Pane("NetworkEditor")
        pane.pwd = mock.Mock(side_effect=RuntimeError("node deleted"))
        self.hou.under = pane
        self.tick()
        self.assertEqual(self.sent[-1][1], "houdini://network")

    def test_stop_withdraws_and_unregisters(self):
        reporter.start()
        self.hou.under = _Pane("SceneViewer", "Sop")
        self.tick()
        reporter.stop()
        self.assertEqual(self.hou.callbacks, [])
        self.assertEqual(len(self.direct), 1)
        self.assertEqual((self.direct[0]["url"], self.direct[0]["focused"]), (None, False))
        reporter.stop()                         # twice is harmless
        self.assertEqual(len(self.direct), 1)

    def test_no_ui_or_turned_off_starts_nothing(self):
        self.hou.isUIAvailable = lambda: False
        reporter.start()
        self.assertEqual(self.hou.callbacks, [])
        self.hou.isUIAvailable = lambda: True
        with mock.patch.dict("os.environ", {"POLYKYBD_REPORT": "0"}):
            reporter.start()
        self.assertEqual(self.hou.callbacks, [])


if __name__ == "__main__":
    unittest.main()
