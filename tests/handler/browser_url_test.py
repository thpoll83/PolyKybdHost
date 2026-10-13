"""BrowserUrlProvider — freshness / focus / browser gating (Qt-free)."""
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


if __name__ == "__main__":
    unittest.main()
