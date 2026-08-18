"""BrowserUrlSource — the receiver + provider pair both roles share.

The forwarder needs this because its own module cannot be imported in the test
environment (pywinctl), so the wiring lives here where it can be tested: the
settings gate, the receiver's best-effort start, the change notification that
re-drives an SPA navigation, and the teardown.

No sockets and no config file — settings_get and server_factory are injected.
"""
import unittest

from polyhost.handler.browser_url_source import BrowserUrlSource, SETTING_DEFAULTS


class _NullLog:
    def __init__(self):
        self.warnings = []

    def warning(self, *a, **k):
        self.warnings.append(a)

    def debug(self, *a, **k):
        pass


class _FakeServer:
    def __init__(self, on_report, log, port=None, token=""):
        self.on_report = on_report
        self.port = port
        self.token = token
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def _settings(**over):
    values = dict(SETTING_DEFAULTS)
    values.update(over)
    return lambda key: values[key]


class BrowserUrlSourceTest(unittest.TestCase):
    def setUp(self):
        self.log = _NullLog()
        self.built = []

    def _factory(self, *a, **k):
        srv = _FakeServer(*a, **k)
        self.built.append(srv)
        return srv

    def _source(self, settings=None, on_change=None):
        return BrowserUrlSource(self.log, settings_get=settings or _settings(),
                                on_change=on_change, server_factory=self._factory)

    def test_starts_the_receiver_with_the_configured_port_and_token(self):
        src = self._source(_settings(browser_report_port=50999,
                                     browser_report_token="s3cret"))
        self.assertTrue(src.start())
        self.assertEqual((self.built[0].port, self.built[0].token), (50999, "s3cret"))
        self.assertTrue(self.built[0].started)

    def test_detection_off_starts_nothing(self):
        src = self._source(_settings(browser_url_detection=False))
        self.assertFalse(src.start())
        self.assertEqual(self.built, [])
        self.assertIsNone(src.server)

    def test_local_receiver_off_starts_nothing_but_detection_stays_on(self):
        # The macOS AppleScript fallback still works without the receiver, so
        # current_url must not be gated on it.
        src = self._source(_settings(browser_report_local_enabled=False))
        self.assertFalse(src.start())
        self.assertEqual(self.built, [])
        self.assertTrue(src.enabled)

    def test_a_bind_failure_is_survivable_and_logged(self):
        def boom(*a, **k):
            raise OSError("address already in use")
        src = BrowserUrlSource(self.log, settings_get=_settings(),
                               server_factory=boom)
        self.assertFalse(src.start())
        self.assertIsNone(src.server)
        self.assertTrue(self.log.warnings, "a failed bind must be reported")

    def test_a_report_reaches_the_provider_and_is_readable(self):
        src = self._source()
        src.start()
        self.built[0].on_report(browser="chrome", url="https://miro.com/app/x",
                                title="A board", focused=True)
        self.assertEqual(src.current_url("chrome"), "https://miro.com/app/x")

    def test_current_url_is_none_for_a_non_browser_app(self):
        src = self._source()
        src.start()
        src.on_report(browser="chrome", url="https://miro.com/app/x", focused=True)
        self.assertIsNone(src.current_url("code"))

    def test_current_url_is_none_while_detection_is_off(self):
        src = self._source(_settings(browser_url_detection=False))
        src.on_report(browser="chrome", url="https://miro.com/app/x", focused=True)
        self.assertIsNone(src.current_url("chrome"))

    def test_on_change_fires_only_when_the_url_actually_changes(self):
        # This is what re-sends an SPA route change: it moves no window title,
        # so without the notification it would wait out the 15 s heartbeat.
        fired = []
        src = self._source(on_change=lambda: fired.append(1))
        src.on_report(browser="chrome", url="https://a.example/", focused=True)
        self.assertEqual(len(fired), 1)
        src.on_report(browser="chrome", url="https://a.example/", focused=True)
        self.assertEqual(len(fired), 1, "an identical report is not a change")
        src.on_report(browser="chrome", url="https://b.example/", focused=True)
        self.assertEqual(len(fired), 2)

    def test_close_stops_the_receiver_and_is_idempotent(self):
        src = self._source()
        src.start()
        src.close()
        self.assertTrue(self.built[0].stopped)
        self.assertIsNone(src.server)
        src.close()  # must not raise

    def test_close_survives_a_server_that_raises(self):
        src = self._source()
        src.start()
        self.built[0].stop = lambda: (_ for _ in ()).throw(OSError("nope"))
        src.close()  # teardown must never block a quit
        self.assertIsNone(src.server)


if __name__ == "__main__":
    unittest.main()
