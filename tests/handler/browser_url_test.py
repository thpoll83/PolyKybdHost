"""BrowserUrlProvider — freshness / focus / browser gating (Qt-free)."""
import sys
import threading
import unittest

from polyhost.handler.browser_url import BrowserUrlProvider, is_browser_app


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestIsBrowserApp(unittest.TestCase):
    def test_known_browsers_across_os_naming(self):
        for name in ["chrome", "google-chrome", "Google Chrome", "msedge",
                     "microsoft-edge", "Microsoft Edge", "firefox", "brave",
                     "brave-browser", "vivaldi", "opera", "chromium", "Safari",
                     "arc"]:
            self.assertTrue(is_browser_app(name), name)

    def test_non_browsers(self):
        for name in ["code", "explorer", "gimp", "", None, "slack", "kicad"]:
            self.assertFalse(is_browser_app(name), name)


class TestBrowserUrlProvider(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        # macOS fallback disabled by default in these tests.
        self.p = BrowserUrlProvider(max_age_s=8.0, clock=self.clock,
                                    macos_lookup=lambda app: None)

    def test_cleared_named_tab_does_not_revive_anonymous_report(self):
        # An older extension (no browser name) reported a site; then Chrome
        # itself reports an empty tab. The empty tab must win.
        self.p.update(browser=None, url="https://github.com/x", focused=True)
        self.p.update(browser="chrome", url=None, focused=True)
        self.assertIsNone(self.p.current_url("chrome"))

    def test_anonymous_report_used_when_browser_has_none_of_its_own(self):
        self.p.update(browser=None, url="https://github.com/x", focused=True)
        self.assertEqual(self.p.current_url("chrome"), "https://github.com/x")

    def test_none_when_no_report(self):
        self.assertIsNone(self.p.current_url("chrome"))

    def test_fresh_focused_report_used_for_browser(self):
        self.p.update(browser="chrome", url="https://mail.google.com", focused=True)
        self.assertEqual(self.p.current_url("chrome"), "https://mail.google.com")

    def test_url_never_leaks_onto_non_browser_app(self):
        self.p.update(browser="chrome", url="https://mail.google.com", focused=True)
        self.assertIsNone(self.p.current_url("code"))

    def test_unfocused_report_is_ignored(self):
        self.p.update(browser="chrome", url="https://x.com", focused=False)
        self.assertIsNone(self.p.current_url("chrome"))

    def test_stale_report_expires(self):
        self.p.update(browser="chrome", url="https://x.com", focused=True)
        self.clock.t += 9.0  # past max_age
        self.assertIsNone(self.p.current_url("chrome"))

    def test_update_returns_change_flag(self):
        self.assertTrue(self.p.update(browser="chrome", url="https://a.com"))
        self.assertFalse(self.p.update(browser="chrome", url="https://a.com"))
        self.assertTrue(self.p.update(browser="chrome", url="https://b.com"))
        # Losing focus clears the effective URL -> a change.
        self.assertTrue(self.p.update(browser="chrome", url="https://b.com", focused=False))

    def test_macos_fallback_when_no_report(self):
        p = BrowserUrlProvider(clock=self.clock,
                               macos_lookup=lambda app: "https://from-osascript")
        self.assertEqual(p.current_url("Safari"), "https://from-osascript")
        # Still gated on being a browser.
        self.assertIsNone(p.current_url("code"))

    def test_extension_report_preferred_over_macos_fallback(self):
        called = []
        p = BrowserUrlProvider(clock=self.clock,
                               macos_lookup=lambda app: called.append(app) or "fallback")
        p.update(browser="chrome", url="https://ext", focused=True)
        self.assertEqual(p.current_url("Google Chrome"), "https://ext")
        self.assertEqual(called, [])  # fallback not consulted

    def test_report_gated_by_browser(self):
        # A fresh Chrome report must NOT satisfy a Firefox lookup...
        self.p.update(browser="chrome", url="https://ext", focused=True)
        self.assertIsNone(self.p.current_url("firefox"))
        # ...but the same brand under any OS naming still matches.
        self.assertEqual(self.p.current_url("google-chrome"), "https://ext")
        self.assertEqual(self.p.current_url("Google Chrome"), "https://ext")

    def test_cross_browser_report_falls_back_to_macos(self):
        called = []
        p = BrowserUrlProvider(clock=self.clock,
                               macos_lookup=lambda app: called.append(app) or "fallback")
        p.update(browser="chrome", url="https://ext", focused=True)
        # Focused app is Safari, cached report is Chrome -> gate rejects the
        # report and the macOS fallback is consulted instead.
        self.assertEqual(p.current_url("Safari"), "fallback")
        self.assertEqual(called, ["Safari"])

    def test_report_without_browser_stays_permissive(self):
        # An older extension may omit `browser`; don't gate then (unchanged behaviour).
        self.p.update(browser=None, url="https://ext", focused=True)
        self.assertEqual(self.p.current_url("firefox"), "https://ext")

    def test_macos_lookup_exception_is_swallowed(self):
        def boom(app):
            raise RuntimeError("nope")
        p = BrowserUrlProvider(clock=self.clock, macos_lookup=boom)
        self.assertIsNone(p.current_url("Safari"))


class TestContextReporter(unittest.TestCase):
    """A non-browser app with a context add-on (Blender) rides the same gates."""

    URL = "blender://EDIT_MESH/VIEW_3D"

    def setUp(self):
        self.clock = FakeClock()
        self.mac = []
        self.p = BrowserUrlProvider(max_age_s=8.0, clock=self.clock,
                                    macos_lookup=lambda app: self.mac.append(app) or "osa")

    def test_report_used_when_blender_is_focused(self):
        self.p.update(app="blender", url=self.URL, focused=True)
        for name in ("blender", "Blender", "org.blender.blender"):
            self.assertEqual(self.p.current_url(name), self.URL, name)
        self.assertEqual(self.mac, [])          # never the AppleScript path

    def test_ignored_while_another_app_is_focused(self):
        # A background Blender keeps reporting; the foreground app must not see it.
        self.p.update(app="blender", url=self.URL, focused=True)
        for name in ("code", "gimp", "explorer", "chrome", "firefox"):
            got = self.p.current_url(name)
            self.assertNotEqual(got, self.URL, name)
        self.assertIsNone(self.p.current_url("code"))

    def test_withdrawal_clears_and_asks_for_a_rematch(self):
        # Turning "Report context" off sends an unfocused report with no URL
        # from the same instance: the overlay must leave that mode at once.
        self.p.update(app="blender", url=self.URL, pid=7)
        self.assertTrue(self.p.update(app="blender", url=None, focused=False, pid=7))
        self.assertIsNone(self.p.current_url("blender"))

    def test_stale_report_ignored(self):
        self.p.update(app="blender", url=self.URL, focused=True)
        self.clock.t += 8.5
        self.assertIsNone(self.p.current_url("blender"))

    def test_keep_alive_refreshes_freshness(self):
        self.p.update(app="blender", url=self.URL, focused=True)
        self.clock.t += 5
        self.assertFalse(self.p.update(app="blender", url=self.URL, focused=True))
        self.clock.t += 5
        self.assertEqual(self.p.current_url("blender"), self.URL)

    def test_background_instance_keepalive_cannot_take_over(self):
        # Two Blenders: B is worked in (recent input), A only keeps alive.
        a, b = "blender://OBJECT/VIEW_3D", "blender://SCULPT/VIEW_3D"
        self.p.update(app="blender", url=b, pid=2, input_age=0.2)
        self.clock.t += 1
        self.p.update(app="blender", url=a, pid=1, input_age=40.0)
        self.assertEqual(self.p.current_url("blender"), b)
        # A gets input again: it is now the one being worked in.
        self.clock.t += 1
        self.assertTrue(self.p.update(app="blender", url=a, pid=1, input_age=0.0))
        self.assertEqual(self.p.current_url("blender"), a)

    def test_closed_instance_is_pruned(self):
        self.p.update(app="blender", url=self.URL, pid=1, input_age=0.0)
        self.clock.t += 9          # instance 1 stopped reporting
        self.p.update(app="blender", url="blender://OBJECT/VIEW_3D", pid=2, input_age=5.0)
        self.assertNotIn(("app", "blender", 1), self.p._reports)
        self.assertEqual(self.p.current_url("blender"), "blender://OBJECT/VIEW_3D")

    def test_non_browser_non_reporter_app_still_ignored(self):
        self.p.update(app="blender", url=self.URL, focused=True)
        self.p.update(browser="chrome", url="https://x.com", focused=True)
        for name in ("code", "kicad", "", None, "blender-launcher"):
            self.assertIsNone(self.p.current_url(name), name)

    def test_browser_report_never_answers_for_blender(self):
        self.p.update(browser=None, url="https://x.com", focused=True)
        self.assertIsNone(self.p.current_url("blender"))

    def test_blender_keep_alive_does_not_clobber_the_browser(self):
        # The add-on cannot see OS focus, so it never sends focused=false; with
        # one shared slot its keep-alive would erase Chrome's report.
        self.p.update(browser="chrome", url="https://mail.google.com", focused=True)
        self.p.update(app="blender", url=self.URL, focused=True)
        self.assertEqual(self.p.current_url("chrome"), "https://mail.google.com")
        self.assertEqual(self.p.current_url("blender"), self.URL)

    def test_mode_change_is_a_change(self):
        self.assertTrue(self.p.update(app="blender", url=self.URL))
        self.assertTrue(self.p.update(app="blender", url="blender://SCULPT/VIEW_3D"))

    def test_unknown_app_token_is_dropped(self):
        self.assertFalse(self.p.update(app="maya", url="maya://x", focused=True))
        self.assertIsNone(self.p.current_url("maya"))
        self.assertEqual(self.p._reports, {})


class TestConcurrentReports(unittest.TestCase):
    """update() runs on the report server's threads, current_url() on window
    tracking's. A lookup walking the instances while a report adds or prunes
    one must not raise (Greptile, #382)."""

    def test_lookup_during_reports_never_raises(self):
        # Every 4th report comes from a new instance: a short max_age makes
        # each one prune the others, so the dict changes size constantly.
        p = BrowserUrlProvider(max_age_s=0.0005, macos_lookup=lambda _: None)
        errors, stop = [], threading.Event()

        def report():
            n = 0
            while not stop.is_set():
                n += 1
                p.update(app="blender", url=f"blender://M{n}/VIEW_3D", pid=n // 4)

        def lookup():
            try:
                while not stop.is_set():
                    p.current_url("blender")
            except Exception as e:      # noqa: BLE001 -- the assertion reports it
                errors.append(e)
                stop.set()

        old = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            threads = [threading.Thread(target=report) for _ in range(2)]
            threads.append(threading.Thread(target=lookup))
            for t in threads:
                t.start()
            stop.wait(1.5)
            stop.set()
            for t in threads:
                t.join()
        finally:
            sys.setswitchinterval(old)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
