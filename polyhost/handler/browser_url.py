"""Focused-browser active-tab URL tracking (Qt-free, import-safe everywhere).

The window title alone can't tell which website a browser is showing — web apps
(Gmail, Jira, Figma, …) all live inside one browser process and put inconsistent
strings in the title. This provider supplies the missing signal: the URL of the
focused browser's active tab, so `handler/common.find_matching_entry` can key
overlays off the site (a `url` / `urls-contains` mapping entry).

Two sources feed it, in preference order:

1. **Browser extension** (`browser-extension/`) → `server/browser_report_server`
   POSTs a report here via :meth:`update`. Works on every OS and browser,
   including native-Wayland browsers pywinctl can't even see. This is the
   authoritative, low-latency source.
2. **macOS AppleScript** (`services/browser_url_macos`) — a zero-install
   fallback for the scriptable macOS browsers, consulted by :meth:`current_url`
   when there's no fresh extension report.

:meth:`current_url` is the single lookup `OverlayHandler` calls each time it
matches a focused window. It is deliberately conservative: it returns a URL
*only* when the focused app is actually a browser and the signal is fresh, so a
background browser's tab can never override the overlay for the foreground app,
and a stale report can never linger — worst case it returns ``None`` and
matching degrades to app-name + title exactly as before this feature existed.
"""
import time

from polyhost.services import browser_url_macos

# Focused-app gate. `getAppName()` normalises differently per OS (Windows
# "chrome"/"msedge", Linux "google-chrome"/"microsoft-edge", macOS "Google
# Chrome"/"Microsoft Edge"), so match distinctive substrings, plus a couple of
# whole-name-only tokens too generic for a substring test.
_BROWSER_SUBSTRINGS = (
    "chrome", "chromium", "firefox", "msedge", "microsoft edge",
    "microsoft-edge", "brave", "vivaldi", "safari", "opera",
)
_BROWSER_EXACT = ("arc",)

# How long an extension report stays usable. The extension pushes on every tab
# switch / focus change, so a fresh report is always at hand while a browser is
# in use; past this the report is considered stale and the macOS fallback (or
# None) takes over — a browser that closed or crashed can't pin an old URL.
DEFAULT_MAX_AGE_S = 8.0


def is_browser_app(app_name) -> bool:
    """Whether ``app_name`` (a normalised getAppName()) is a known browser."""
    if not isinstance(app_name, str):
        return False
    n = app_name.strip().lower()
    if not n:
        return False
    if n in _BROWSER_EXACT:
        return True
    return any(tok in n for tok in _BROWSER_SUBSTRINGS)


class BrowserUrlProvider:
    """Latest focused-browser URL, with freshness + focus gating.

    ``clock`` and ``macos_lookup`` are injectable for tests. ``clock`` is a
    monotonic seconds source; ``macos_lookup(app_name) -> Optional[str]`` is the
    zero-install fallback (defaults to the real AppleScript query, a no-op off
    macOS)."""

    def __init__(self, max_age_s=DEFAULT_MAX_AGE_S, clock=time.monotonic,
                 macos_lookup=browser_url_macos.frontmost_url):
        self._max_age_s = max_age_s
        self._clock = clock
        self._macos_lookup = macos_lookup
        self._report = None  # dict: browser, url, title, focused, ts

    # ------------------------------------------------------------------
    # Ingest (from the extension via browser_report_server)
    # ------------------------------------------------------------------

    def update(self, browser=None, url=None, title=None, focused=True) -> bool:
        """Store one report from the extension. Returns True when the effective
        URL changed (a real navigation / tab switch / (de)focus), so the caller
        can nudge window tracking to re-match — this is what lets an SPA route
        change with no window-title change still swap overlays.

        A report with ``focused`` false / no URL clears the effective URL (the
        browser lost focus or the tab has no address, e.g. a new-tab page)."""
        prev = self._effective_url()
        self._report = {
            "browser": browser,
            "url": url or None,
            "title": title,
            "focused": bool(focused),
            "ts": self._clock(),
        }
        return self._effective_url() != prev

    def _effective_url(self):
        """The stored report's URL if it is fresh AND focused, else None."""
        r = self._report
        if not r or not r["focused"] or not r["url"]:
            return None
        if self._clock() - r["ts"] > self._max_age_s:
            return None
        return r["url"]

    # ------------------------------------------------------------------
    # Lookup (from OverlayHandler)
    # ------------------------------------------------------------------

    def current_url(self, app_name):
        """URL of the focused window's active tab, or ``None``.

        Returns a URL only when ``app_name`` is a browser: a fresh, focused
        extension report wins; otherwise the macOS AppleScript fallback is
        tried (a no-op off macOS / for Firefox). ``None`` for any non-browser
        app, so a browser URL can never leak onto a native app's overlay."""
        if not is_browser_app(app_name):
            return None
        url = self._effective_url()
        if url:
            return url
        # No fresh extension report — try the zero-install macOS path.
        try:
            return self._macos_lookup(app_name)
        except Exception:
            return None
