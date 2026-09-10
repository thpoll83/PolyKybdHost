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


# The exact reason line a cached miss reports. Spelled out rather than derived
# from `candidates()`: this IS the log contract, and a derived expectation would
# agree with whatever the code produced.
_MISS_WINWORD = ("no catalog carries "
                 "si:winword, mdi:microsoft-winword, mdi:adobe-winword")


class FetcherTest(unittest.TestCase):

    def setUp(self):
        self.ready = []
        self.fetched = []
        self.threads = []
        self.gate = threading.Event()
        self.gate.set()
        # Keyed by QUALIFIED name: an app is tried against both catalogs in
        # order, so the fixture has to answer per candidate, not per app.
        self.marks = {"si:gimp": "MASK"}

        def fake_fetch(name, cache_dir=None, allow_network=None):
            self.gate.wait(5)
            self.fetched.append(name)
            self.threads.append(threading.current_thread().name)
            return f"/cache/{name}" if name in self.marks else None

        def fake_render(path, box=40):
            return self.marks[path[len("/cache/"):]]

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
            self.assertEqual(self.fetcher.overlay_for("gimp"), (None, "si:gimp"))
        self.gate.set()
        self.assertTrue(_wait(lambda: self.ready))
        time.sleep(0.2)
        self.assertEqual(self.fetched, ["si:gimp"])
        self.assertEqual(self.ready, ["si:gimp"])

    def test_a_resolved_mark_is_served_from_memory(self):
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.fetched.clear()
        for _ in range(5):
            self.assertEqual(self.fetcher.overlay_for("gimp"), ("MASK", "si:gimp"))
        self.assertEqual(self.fetched, [])

    def test_a_MISS_is_cached_too(self):
        # An app the catalog does not carry is the common case (no Office, no
        # Adobe, no VS Code), so asking once per window switch would be a request
        # every few seconds for the rest of the session.
        self.fetcher.overlay_for("winword")
        self.assertTrue(_wait(lambda: self.fetched.count("mdi:microsoft-winword") == 1))
        before = list(self.fetched)
        for _ in range(5):
            self.assertEqual(self.fetcher.overlay_for("winword"), (None, "si:winword"))
        time.sleep(0.2)
        self.assertEqual(self.fetched, before)

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
        self.assertTrue(_wait(lambda: "mdi:microsoft-winword" in self.fetched))
        self.marks["si:winword"] = "WINWORD"
        self.assertEqual(self.fetcher.overlay_for("winword"), (None, "si:winword"))
        self.fetcher.forget_misses()
        self.assertTrue(_wait(
            lambda: self.fetcher.overlay_for("winword")[0] == "WINWORD"))

    def test_a_miss_with_AUTO_FETCH_OFF_says_so_instead_of_blaming_the_catalog(self):
        """⚠️ The two are indistinguishable from the outside and mean opposite
        things: one is an answer, the other is a refusal to ask.

        With the switch off `fetch_icon` returns None without sending a request,
        so "no catalog carries si:winword" is a claim about a lookup that never
        happened -- and it points the next round at the catalog instead of at
        the setting that is actually in the way.
        """
        with mock.patch("polyhost.services.app_icons.auto_fetch_enabled",
                        lambda: False):
            self.fetcher.overlay_for("winword")
            self.assertTrue(_wait(
                lambda: any(app == "winword" for app, _ in self.fetcher._told)
                or self.fetcher.overlay_for("winword") is not None))
            with self.assertLogs("PolyHost", level="INFO") as caught:
                self.assertTrue(_wait(
                    lambda: self.fetcher.overlay_for("winword")[0] is None
                    and any(app == "winword" for app, _ in self.fetcher._told)))
        reasons = [r for a, r in self.fetcher._told if a == "winword"]
        self.assertEqual(len(reasons), 1, self.fetcher._told)
        self.assertIn("auto-fetch is off", reasons[0])
        self.assertNotIn("no catalog carries", reasons[0])
        self.assertTrue(any("auto-fetch is off" in line for line in caught.output),
                        caught.output)

    def test_the_reason_is_the_one_from_the_LOOKUP_not_the_setting_NOW(self):
        # The miss is cached, so the line can be printed long after the switch
        # moved. Re-deriving it in `overlay_for` would describe today's setting
        # while reporting a lookup made under yesterday's -- and would read the
        # settings FILE on every window tick to do it.
        with mock.patch("polyhost.services.app_icons.auto_fetch_enabled",
                        lambda: False):
            self.fetcher.overlay_for("winword")
            self.assertTrue(_wait(
                lambda: self.fetcher.overlay_for("winword")[0] is None
                and any(app == "winword" for app, _ in self.fetcher._told)))
        self.fetcher._told.clear()
        # Switch back on. The cached miss is untouched (forget_misses is what
        # clears it), so the reason must still name the refusal that produced it.
        self.fetcher.overlay_for("winword")
        reasons = [r for a, r in self.fetcher._told if a == "winword"]
        self.assertEqual(len(reasons), 1, self.fetcher._told)
        self.assertIn("auto-fetch is off", reasons[0])

    def test_forgetting_the_misses_keeps_the_marks_it_HAS(self):
        # Only the negative half is dropped: re-downloading a mark that is
        # already in memory would cost a request for nothing.
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.fetched.clear()
        self.fetcher.forget_misses()
        self.assertEqual(self.fetcher.overlay_for("gimp"), ("MASK", "si:gimp"))
        time.sleep(0.2)
        self.assertEqual(self.fetched, [])

    def test_a_re_miss_after_forgetting_is_worth_one_more_line(self):
        # "still no icon, now that fetching is on" is a different fact from the
        # first line, and the only signal that turning the switch on did not help.
        self.fetcher.overlay_for("winword")
        self.assertTrue(_wait(lambda: "mdi:microsoft-winword" in self.fetched))
        # ⚠️ The first line is only emitted by a lookup that SEES the cached
        # miss, so this call is what populates the dedupe -- without it the
        # assertion below passes whether or not `forget_misses` clears it.
        with self.assertLogs("PolyHost", level="INFO"):
            self.assertTrue(_wait(
                lambda: self.fetcher.overlay_for("winword") == (None, "si:winword")
                and ("winword", _MISS_WINWORD) in self.fetcher._told))
        with self.assertLogs("PolyHost", level="INFO") as caught:
            self.fetcher.forget_misses()
            self.fetcher.overlay_for("winword")
            # ⚠️ Wait for the SECOND fetch: the first round already fetched this
            # candidate once, so waiting for a count of 1 returns immediately and
            # the lookups below see an in-flight entry and log nothing.
            self.assertTrue(_wait(lambda: self.fetched.count("si:winword") == 2))
            self.assertTrue(_wait(
                lambda: self.fetcher.overlay_for("winword")[0] is None
                and ("winword", _MISS_WINWORD) in self.fetcher._told))
            self.fetcher.overlay_for("winword")
        lines = [r for r in caught.output if "No program icon for 'winword'" in r]
        self.assertEqual(len(lines), 1, caught.output)

    def test_one_log_line_per_app_and_reason(self):
        # ⚠️ The window tick runs continuously; undeduped this is one line per
        # poll for any app with no mark, which is most of them.
        with self.assertLogs("PolyHost", level="INFO") as caught:
            self.assertTrue(_wait(lambda: self.fetcher.overlay_for("winword")[1]
                                  and "mdi:microsoft-winword" in self.fetched))
            for _ in range(10):
                self.fetcher.overlay_for("winword")
        lines = [r for r in caught.output if "No program icon for 'winword'" in r]
        self.assertEqual(len(lines), 1, caught.output)



class ResolvedIconLogTest(unittest.TestCase):
    """The one INFO line that says which catalog entry an app resolved to.

    It is the only place the resolution is visible: the overlay summary names
    the mark `@prog:<slug>`, so without this nothing says WHY that slug was
    chosen for this app.
    """

    def _log_for(self, title):
        marks = {"mdi:microsoft-word": "MASK"}
        patches = [
            mock.patch("polyhost.services.app_icons.fetch_icon",
                       lambda name, cache_dir=None, allow_network=None:
                       f"/cache/{name}" if name in marks else None),
            mock.patch("polyhost.services.app_icons.render_overlay",
                       lambda path, box=40: marks[path[len("/cache/"):]]),
            mock.patch("polyhost.services.app_icons.title_of", lambda path: title),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        fetcher = AppIconFetcher(on_ready=lambda slug: None,
                                 mapping={"winword": "mdi:microsoft-word"})
        self.addCleanup(fetcher.stop)
        with self.assertLogs("PolyHost", "INFO") as caught:
            _wait(lambda: fetcher.overlay_for("winword")[0] is not None)
        return [r for r in caught.output if "Program icon:" in r]

    def test_a_catalog_WITH_a_title_names_the_brand_and_the_slug(self):
        lines = self._log_for("Microsoft Word")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("Microsoft Word (mdi:microsoft-word)", lines[0])

    def test_a_catalog_with_NO_title_names_the_slug_ONCE(self):
        """⚠️ MDI's SVGs carry no `<title>`, so `title or name` printed the name
        TWICE — `Program icon: mdi:microsoft-word (mdi:microsoft-word)`, which
        reads as a bug in the resolver rather than as a missing title. Half the
        shipped catalog is MDI, so this is the COMMON case, not an edge one.
        """
        lines = self._log_for(None)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("mdi:microsoft-word", lines[0])
        self.assertEqual(lines[0].count("mdi:microsoft-word"), 1, lines[0])

    def test_a_title_that_merely_REPEATS_the_slug_is_not_printed_twice(self):
        # Simple Icons titles are brand names, so one can equal its own slug
        # ("Figma"); the parenthetical would then say nothing.
        lines = self._log_for("MDI:Microsoft-Word")
        self.assertEqual(lines[0].count("icrosoft-"), 1, lines[0])


if __name__ == "__main__":
    unittest.main()
