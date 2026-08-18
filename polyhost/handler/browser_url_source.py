"""The browser-URL feed as one unit: the loopback receiver + the URL provider.

Both PolyKybdHost roles need exactly this pair. In **normal mode** `PolyCore`
feeds it into `OverlayHandler`'s matcher so overlays can key off the focused
website. In **forwarder mode** the remote machine needs it too — the browser
extension there is already willing to report (it POSTs to `127.0.0.1` on its own
machine, so nothing about it is host-specific), but `PolyForwarder` owns no
`PolyCore`, so nothing was listening and its `/ping` health check failed. The
URL therefore never reached the keyboard machine and a forwarded browser could
only ever match on its window title.

Kept **Qt-free and core-free** deliberately: `polyhost/forwarder.py` cannot be
imported in the documented test environment (pywinctl), so any forwarder logic
worth testing has to live outside it. `settings_get` and `server_factory` are
injected, so the whole thing is unit-testable without sockets or a config file.
"""

# Mirrors the defaults in `settings.py` `load()`, for the file-only
# `read_setting` path the forwarder uses (it has no PolySettings, and building
# one would create + rewrite the config just to read four keys). Keep in sync.
SETTING_DEFAULTS = {
    "browser_url_detection": True,
    "browser_report_local_enabled": True,
    "browser_report_port": 50164,
    "browser_report_token": "",
}


def read_settings_from_file(key):
    """`settings_get` backed by the YAML file only — no PolySettings."""
    from polyhost.settings import read_setting
    return read_setting(key, SETTING_DEFAULTS.get(key))


class BrowserUrlSource:
    """Owns a `BrowserUrlProvider` and, when enabled, the loopback receiver.

    `on_change` fires when a report actually changes the effective URL — that is
    what lets an SPA route change with no window-title change still re-drive the
    caller (the core invalidates its window cache; the forwarder re-sends).
    """

    def __init__(self, log, settings_get=None, on_change=None,
                 provider=None, server_factory=None):
        self.log = log
        self._get = settings_get if settings_get is not None else read_settings_from_file
        self._on_change = on_change
        self._server_factory = server_factory
        self.server = None
        if provider is None:
            from polyhost.handler.browser_url import BrowserUrlProvider
            provider = BrowserUrlProvider()
        self.provider = provider

    @property
    def enabled(self):
        """Whether URL detection is on at all (the receiver may still be off —
        the macOS AppleScript fallback works without it)."""
        return bool(self._get("browser_url_detection"))

    def start(self):
        """Start the receiver if both settings allow. Returns True when it is
        listening. Best-effort: a bind failure (port in use) logs and leaves the
        feature on the macOS fallback only — it must never block startup."""
        if not (self.enabled and self._get("browser_report_local_enabled")):
            return False
        try:
            factory = self._server_factory
            if factory is None:
                from polyhost.server.browser_report_server import BrowserReportServer
                factory = BrowserReportServer
            self.server = factory(
                self.on_report, self.log,
                port=int(self._get("browser_report_port")),
                token=str(self._get("browser_report_token") or ""))
            self.server.start()
            return True
        except Exception as e:  # noqa: BLE001 — feature is optional, never fatal
            self.server = None
            self.log.warning("Browser-report listener unavailable (%s: %s) — "
                             "browser-URL overlays rely on the macOS fallback only.",
                             type(e).__name__, e)
            return False

    def on_report(self, browser=None, url=None, title=None, focused=True):
        """Ingest one extension report; notify `on_change` on a real change."""
        changed = self.provider.update(
            browser=browser, url=url, title=title, focused=focused)
        if changed and self._on_change is not None:
            self._on_change()
        return changed

    def current_url(self, app_name):
        """URL of the focused browser's active tab, or None — None whenever
        detection is off, so callers need no second gate."""
        if not self.enabled:
            return None
        return self.provider.current_url(app_name)

    def close(self):
        """Stop the receiver. Idempotent; never raises."""
        server, self.server = self.server, None
        if server is not None:
            try:
                server.stop()
            except Exception:  # noqa: BLE001 — teardown must not block a quit
                self.log.debug("Browser-report listener stop failed", exc_info=True)
