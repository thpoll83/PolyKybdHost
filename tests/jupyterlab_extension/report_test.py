"""The JupyterLab extension's Jupyter-free server half
(jupyterlab-extension/polykybd_jupyterlab/report.py)."""
import contextlib
import importlib.util
import io
import json
import threading
import unittest
from pathlib import Path

from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_REPORT = (Path(__file__).resolve().parents[2] / "jupyterlab-extension"
           / "polykybd_jupyterlab" / "report.py")
_spec = importlib.util.spec_from_file_location("polykybd_jupyterlab_report", _REPORT)
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)


class PayloadTest(unittest.TestCase):
    def test_each_url_passes(self):
        for url in report.URLS:
            body = json.loads(report.payload({"url": url, "focused": True,
                                              "input_age": 1.26}, pid=42))
            self.assertEqual(body, {"app": "jupyter", "url": url, "focused": True,
                                    "pid": 42, "input_age": 1.3})

    def test_only_the_six_urls(self):
        self.assertEqual(len(report.URLS), 6)
        for url in ("jupyter://notebook/command/x", "file:///home/u/a.ipynb",
                    "jupyter://notebook/a.ipynb", "", None, 3, ["jupyter://editor"]):
            self.assertIsNone(report.payload({"url": url, "focused": True}), url)

    def test_unfocused_withdraws_and_drops_the_url(self):
        body = json.loads(report.payload({"url": "anything/at/all", "focused": False}))
        self.assertEqual(body, {"app": "jupyter", "url": None, "focused": False})
        # Only a literal true counts as focused.
        body = json.loads(report.payload({"url": "jupyter://editor", "focused": "yes"}))
        self.assertIs(body["focused"], False)

    def test_bad_body_and_odd_ages(self):
        for data in (None, [], "x", 5):
            self.assertIsNone(report.payload(data))
        for age in (-1, True, "1", None):
            body = json.loads(report.payload({"url": "jupyter://editor", "focused": True,
                                              "input_age": age}))
            self.assertNotIn("input_age", body, age)

    def test_token_only_when_set(self):
        self.assertNotIn("token", json.loads(report.payload(
            {"url": "jupyter://editor", "focused": True})))
        self.assertEqual(json.loads(report.payload(
            {"url": "jupyter://editor", "focused": True}, token="s"))["token"], "s")

    def test_no_extra_keys_from_the_page_reach_the_host(self):
        body = json.loads(report.payload({"url": "jupyter://editor", "focused": True,
                                          "title": "secret.ipynb", "app": "blender",
                                          "pid": 1}, pid=9))
        self.assertEqual(set(body), {"app", "url", "focused", "pid"})
        self.assertEqual((body["app"], body["pid"]), ("jupyter", 9))


class SettingsTest(unittest.TestCase):
    def test_defaults_match_the_host(self):
        self.assertEqual(report.settings({}, {}), (DEFAULT_BROWSER_REPORT_PORT, ""))

    def test_config_then_environment(self):
        self.assertEqual(report.settings({"port": 5000, "token": "c"}, {}), (5000, "c"))
        self.assertEqual(report.settings({"port": 5000, "token": "c"},
                                         {"POLYKYBD_REPORT_PORT": "6000",
                                          "POLYKYBD_REPORT_TOKEN": "e"}), (6000, "e"))

    def test_bad_port_falls_back(self):
        for port in ("x", 0, 70000, None):
            self.assertEqual(report.settings({"port": port}, {})[0],
                             DEFAULT_BROWSER_REPORT_PORT, port)


class SenderTest(unittest.TestCase):
    def test_posts_off_thread_and_survives_errors(self):
        got, done = [], threading.Event()

        def post(port, body):
            got.append((port, body))
            if len(got) == 1:
                raise OSError("refused")
            done.set()

        s = report.Sender(post=post)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            s.submit(50164, b"a")
            for _ in range(200):
                if got:
                    break
                threading.Event().wait(0.01)
            s.submit(50164, b"b")
            self.assertTrue(done.wait(2.0))
        self.assertEqual(got[-1], (50164, b"b"))
        self.assertIn("refused", err.getvalue())

    def test_real_post_reaches_a_receiver(self):
        from polyhost.server.browser_report_server import BrowserReportServer

        reports, done = [], threading.Event()

        class Log:
            def info(self, *a): pass
            def warning(self, *a): pass
            def debug_detailed(self, *a): pass

        def on_report(**kw):
            reports.append(kw)
            done.set()

        srv = BrowserReportServer(on_report, Log(), port=0)
        srv.start()
        try:
            port = srv._httpd.server_address[1]
            report._http_post(port, report.payload(
                {"url": "jupyter://notebook/edit", "focused": True, "input_age": 0.2},
                pid=4242))
            self.assertTrue(done.wait(2.0))
        finally:
            srv.stop()
        self.assertEqual(reports[0]["app"], "jupyter")
        self.assertEqual(reports[0]["url"], "jupyter://notebook/edit")
        self.assertEqual(reports[0]["pid"], 4242)
        self.assertEqual(reports[0]["input_age"], 0.2)


if __name__ == "__main__":
    unittest.main()
