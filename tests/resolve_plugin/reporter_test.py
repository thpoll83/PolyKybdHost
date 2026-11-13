"""The DaVinci Resolve page reporter (resolve-plugin/polykybd_context_reporter.py).

Runs the script's Resolve-free half: the URL, the payload, the send policy
and the poll loop with a fake GetCurrentPage. Nothing here talks to Resolve.
"""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S, CONTEXT_REPORTERS
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_SCRIPT = (Path(__file__).resolve().parents[2] / "resolve-plugin"
           / "polykybd_context_reporter.py")
_spec = importlib.util.spec_from_file_location("polykybd_resolve_reporter", _SCRIPT)
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)      # must not start anything: no Resolve names here


class PageUrlTest(unittest.TestCase):
    def test_every_page(self):
        for page in ("media", "cut", "edit", "fusion", "color", "fairlight", "deliver"):
            self.assertEqual(rep.page_url(page), f"resolve://{page}")

    def test_case_and_space_are_normalised(self):
        self.assertEqual(rep.page_url(" Edit "), "resolve://edit")

    def test_unknown_or_no_page_sends_nothing(self):
        for page in (None, "", "project", "edit/../x", 42):
            self.assertIsNone(rep.page_url(page))


class PayloadTest(unittest.TestCase):
    def test_fields(self):
        body = json.loads(rep.payload("resolve://color", pid=7))
        self.assertEqual(body, {"app": "resolve", "url": "resolve://color",
                                "focused": True, "pid": 7})

    def test_token_only_when_set(self):
        self.assertNotIn("token", json.loads(rep.payload("resolve://cut")))
        self.assertEqual(json.loads(rep.payload("resolve://cut", token="t"))["token"], "t")

    def test_withdrawal(self):
        body = json.loads(rep.payload(None, focused=False))
        self.assertIsNone(body["url"])
        self.assertIs(body["focused"], False)

    def test_app_token_is_on_the_host_allow_list(self):
        self.assertIn(rep.APP, set(CONTEXT_REPORTERS.values()))

    def test_defaults_match_the_host(self):
        self.assertEqual(rep.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)
        self.assertLess(rep.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)


class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(rep.settings({}), (rep.DEFAULT_PORT, ""))

    def test_environment(self):
        self.assertEqual(rep.settings({"POLYKYBD_PORT": "50200", "POLYKYBD_TOKEN": "s"}),
                         (50200, "s"))

    def test_bad_port_falls_back(self):
        for bad in ("x", "0", "70000"):
            self.assertEqual(rep.settings({"POLYKYBD_PORT": bad})[0], rep.DEFAULT_PORT)


class ReporterLoopTest(unittest.TestCase):

    def make(self, pages):
        self.now = 0.0
        self.sent = []
        it = iter(pages)

        def get_page():
            v = next(it)
            if isinstance(v, Exception):
                raise v
            return v

        r = rep.Reporter(get_page, port=1234, pid=99, post=lambda p, b: self.sent.append(
            (p, json.loads(b))), clock=lambda: self.now)
        return r

    def urls(self):
        return [(b["url"], b["focused"]) for _p, b in self.sent]

    def test_sends_on_change_and_keepalive(self):
        r = self.make(["edit", "edit", "edit", "color"])
        r.step()                       # t=0 edit: sent
        self.now = 1.0
        r.step()                       # same page, too soon: nothing
        self.now = 3.5
        r.step()                       # keep-alive
        self.now = 3.6
        r.step()                       # change
        self.assertEqual(self.urls(), [("resolve://edit", True), ("resolve://edit", True),
                                       ("resolve://color", True)])
        self.assertEqual({p for p, _b in self.sent}, {1234})
        self.assertEqual({b["pid"] for _p, b in self.sent}, {99})

    def test_no_page_is_one_withdrawal(self):
        r = self.make(["cut", None, None, "cut"])
        for _ in range(4):
            r.step()
        self.assertEqual(self.urls(), [("resolve://cut", True), (None, False),
                                       ("resolve://cut", True)])

    def test_nothing_before_a_page_is_known(self):
        r = self.make([None, None])
        r.step()
        r.step()
        self.assertEqual(self.sent, [])

    def test_resolve_gone_ends_the_loop_with_a_withdrawal(self):
        pages = ["fusion"] + [RuntimeError("gone")] * rep.MAX_FAILURES
        r = self.make(pages)
        r.sleep = lambda _s: None
        r.run()
        self.assertEqual(self.urls(), [("resolve://fusion", True), (None, False)])

    def test_stop_withdraws(self):
        r = self.make(["deliver"] * 10)

        def sleep(_s):
            r.stop()
        r.sleep = sleep
        r.run()
        self.assertEqual(self.urls(), [("resolve://deliver", True), (None, False)])

    def test_delivery_error_does_not_stop_the_loop(self):
        r = self.make(["edit", "color"])

        def post(_p, _b):
            raise OSError("refused")
        r.post = post
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertTrue(r.step())
            self.now = 1
            self.assertTrue(r.step())
        self.assertEqual(err.getvalue().count("not delivered"), 1)


class ResolveLookupTest(unittest.TestCase):
    def test_menu_names_are_used_first(self):
        sentinel = object()
        self.assertIs(rep._find_resolve({"resolve": sentinel}), sentinel)

        class Fusion:
            def GetResolve(self):
                return sentinel
        self.assertIs(rep._find_resolve({"fusion": Fusion()}), sentinel)

        class Bmd:
            def scriptapp(self, name):
                return sentinel if name == "Resolve" else None
        self.assertIs(rep._find_resolve({"bmd": Bmd()}), sentinel)


if __name__ == "__main__":
    unittest.main()
