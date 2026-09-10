"""The app-icon fetch queue: offline, deterministic, no network.

What these pin is the queue's behaviour, not the catalog's — `app_icons` has its
own suite. The two properties that matter here both cost something real when
they break: a duplicate fetch re-sends every overlay a second time, and a lookup
that touches the network on the caller's thread freezes the tray.
"""
import threading
import time
import unittest
from unittest import mock

from polyhost.services.app_icon_fetcher import AppIconFetcher


def _wait(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FetcherTest(unittest.TestCase):

    def setUp(self):
        self.ready = []
        self.fetched = []
        self.threads = []
        self.gate = threading.Event()
        self.gate.set()
        self.marks = {"gimp": "MASK"}

        def fake_fetch(slug, cache_dir=None, allow_network=None):
            self.gate.wait(5)
            self.fetched.append(slug)
            self.threads.append(threading.current_thread().name)
            return f"/cache/{slug}.svg" if slug in self.marks else None

        def fake_render(path, box=40):
            return self.marks[path.split("/")[-1][:-4]]

        for name, fn in (("fetch_icon", fake_fetch), ("render_overlay", fake_render),
                         ("title_of", lambda p: "Brand")):
            patcher = mock.patch(f"polyhost.services.app_icons.{name}", fn)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.fetcher = AppIconFetcher(on_ready=self.ready.append, mapping={})
        self.addCleanup(self.fetcher.stop)

    def test_a_mark_is_fetched_once_and_reported_once(self):
        # ⚠️ THE REGRESSION THIS EXISTS FOR: a slug is neither queued nor cached
        # while it is in flight, so the poll loop re-queued it every tick — two
        # fetches and two `on_ready`s, the second of which re-sends every overlay
        # for nothing. Measured on the first cut, not imagined.
        self.gate.clear()
        for _ in range(20):
            self.assertEqual(self.fetcher.overlay_for("gimp"), (None, "gimp"))
        self.gate.set()
        self.assertTrue(_wait(lambda: self.ready))
        time.sleep(0.2)
        self.assertEqual(self.fetched, ["gimp"])
        self.assertEqual(self.ready, ["gimp"])

    def test_a_resolved_mark_is_served_from_memory(self):
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.fetched.clear()
        for _ in range(5):
            self.assertEqual(self.fetcher.overlay_for("gimp"), ("MASK", "gimp"))
        self.assertEqual(self.fetched, [])

    def test_a_MISS_is_cached_too(self):
        # An app the catalog does not carry is the common case (no Office, no
        # Adobe, no VS Code), so asking once per window switch would be a request
        # every few seconds for the rest of the session.
        self.assertTrue(_wait(lambda: "winword" in self.fetched
                              or self.fetcher.overlay_for("winword") is None))
        self.assertTrue(_wait(lambda: self.fetched.count("winword") == 1))
        for _ in range(5):
            self.assertEqual(self.fetcher.overlay_for("winword"), (None, "winword"))
        time.sleep(0.2)
        self.assertEqual(self.fetched.count("winword"), 1)

    def test_the_lookup_runs_NO_fetch_on_the_calling_thread(self):
        # The whole reason this class exists: `fetch_icon` is an HTTP GET at a
        # 15 s timeout, and the callers are the GUI main thread and the tick.
        self.fetcher.overlay_for("gimp")
        self.assertTrue(_wait(lambda: self.threads))
        for name in self.threads:
            self.assertNotEqual(name, threading.current_thread().name)

    def test_a_suppressed_app_is_never_queued(self):
        fetcher = AppIconFetcher(mapping={"java": None})
        self.addCleanup(fetcher.stop)
        self.assertEqual(fetcher.overlay_for("java"), (None, None))
        time.sleep(0.2)
        self.assertEqual(self.fetched, [])

    def test_a_raising_callback_is_CAUGHT_not_reported_as_a_crash(self):
        # ⚠️ The queue would survive an escape anyway -- `_ensure_thread` restarts
        # a dead thread on the next lookup -- so "the icons still work" is NOT
        # what this pins, and a test asserting that passes with the guard
        # removed (measured). What the guard buys is that `threading.excepthook`
        # never fires: the app installs one that writes crash_log.txt, so an
        # escape here would put a spurious crash in every later problem report.
        seen = []
        original = threading.excepthook
        threading.excepthook = lambda args: seen.append(args)
        self.addCleanup(lambda: setattr(threading, "excepthook", original))

        boom = AppIconFetcher(on_ready=lambda slug: 1 / 0, mapping={})
        self.addCleanup(boom.stop)
        boom.overlay_for("gimp")
        self.assertTrue(_wait(lambda: boom.overlay_for("gimp")[0] == "MASK"))
        time.sleep(0.2)
        self.assertEqual(seen, [])

    def test_stop_is_idempotent_and_keeps_the_thread_stopped(self):
        # ⚠️ One-way flag: a window switch landing after shutdown must not start
        # a fresh thread holding the core — the race `_start_wincompose_settle`
        # documents.
        self.fetcher.overlay_for("gimp")
        self.assertTrue(_wait(lambda: self.ready))
        self.fetcher.stop()
        self.fetcher.stop()
        self.fetched.clear()
        self.fetcher.overlay_for("krita")
        time.sleep(0.2)
        self.assertEqual(self.fetched, [])

    def test_forgetting_the_misses_lets_an_offline_app_be_retried(self):
        # Turning `shortcut_icon_auto_fetch` back on is worth nothing while the
        # "no mark" answers from the offline period are still cached.
        self.fetcher.overlay_for("winword")
        self.assertTrue(_wait(lambda: "winword" in self.fetched))
        self.marks["winword"] = "WINWORD"
        self.assertEqual(self.fetcher.overlay_for("winword"), (None, "winword"))
        self.fetcher.forget_misses()
        self.assertTrue(_wait(
            lambda: self.fetcher.overlay_for("winword")[0] == "WINWORD"))

    def test_forgetting_the_misses_keeps_the_marks_it_HAS(self):
        # Only the negative half is dropped: re-downloading a mark that is
        # already in memory would cost a request for nothing.
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.fetched.clear()
        self.fetcher.forget_misses()
        self.assertEqual(self.fetcher.overlay_for("gimp"), ("MASK", "gimp"))
        time.sleep(0.2)
        self.assertEqual(self.fetched, [])

    def test_a_re_miss_after_forgetting_is_worth_one_more_line(self):
        # "still no icon, now that fetching is on" is a different fact from the
        # first line, and the only signal that turning the switch on did not help.
        self.fetcher.overlay_for("winword")
        self.assertTrue(_wait(lambda: "winword" in self.fetched))
        # ⚠️ The first line is only emitted by a lookup that SEES the cached
        # miss, so this call is what populates the dedupe -- without it the
        # assertion below passes whether or not `forget_misses` clears it.
        with self.assertLogs("PolyHost", level="INFO"):
            self.assertTrue(_wait(
                lambda: self.fetcher.overlay_for("winword") == (None, "winword")
                and ("winword", "the catalog has no 'winword'") in self.fetcher._told))
        with self.assertLogs("PolyHost", level="INFO") as caught:
            self.fetcher.forget_misses()
            self.fetcher.overlay_for("winword")
            self.assertTrue(_wait(lambda: self.fetched.count("winword") == 2))
            self.fetcher.overlay_for("winword")
            self.fetcher.overlay_for("winword")
        lines = [r for r in caught.output if "No program icon for 'winword'" in r]
        self.assertEqual(len(lines), 1, caught.output)

    def test_one_log_line_per_app_and_reason(self):
        # ⚠️ The window tick runs continuously; undeduped this is one line per
        # poll for any app with no mark, which is most of them.
        with self.assertLogs("PolyHost", level="INFO") as caught:
            self.assertTrue(_wait(lambda: self.fetcher.overlay_for("winword")[1]
                                  and "winword" in self.fetched))
            for _ in range(10):
                self.fetcher.overlay_for("winword")
        lines = [r for r in caught.output if "No program icon for 'winword'" in r]
        self.assertEqual(len(lines), 1, caught.output)


if __name__ == "__main__":
    unittest.main()
