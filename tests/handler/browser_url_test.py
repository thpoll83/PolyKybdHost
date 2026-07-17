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

    def test_macos_lookup_exception_is_swallowed(self):
        def boom(app):
            raise RuntimeError("nope")
        p = BrowserUrlProvider(clock=self.clock, macos_lookup=boom)
        self.assertIsNone(p.current_url("Safari"))


if __name__ == "__main__":
    unittest.main()
