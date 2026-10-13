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

A third, non-browser source shares the same channel: **context reporters**.
An application on the small allow-list below (Blender) runs an add-on that
POSTs ``{app, url, focused}`` to the same receiver, where ``url`` is a
pseudo-URL naming its current context (``blender://EDIT_MESH/VIEW_3D``). The
mapping then routes on it with ``urls-contains`` exactly as for a website, and
the same freshness and focus gates apply: the report counts only while that
app is the focused one, so a Blender in the background can never override the
foreground app's overlay.

Reports are kept PER SOURCE (one per browser brand, one per reporter app).
A context reporter cannot see OS focus, so it never sends the browser's
``focused: false`` on blur; it keeps re-sending its context. With a single
slot those keep-alives would overwrite the browser's report every few seconds
and drop website overlays at random -- per-source storage makes the two
independent.

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


def _canonical_browser(name):
    """Collapse an OS app-name or an extension ``browser`` token to one brand
    key (``chrome``/``firefox``/``edge``/…), or ``None`` if unrecognised.

    Distinctive brands are checked before the generic ``chrome``/``chromium``
    base so a Chromium-derived browser (Brave/Edge/Opera/Vivaldi) maps to its own
    brand rather than ``chrome``."""
    if not isinstance(name, str):
        return None
    n = name.strip().lower()
    if not n:
        return None
    if "firefox" in n:
        return "firefox"
    if "brave" in n:
        return "brave"
    if "vivaldi" in n:
        return "vivaldi"
    if "opera" in n or "opr" in n:
        return "opera"
    if "edg" in n:  # msedge, microsoft edge, microsoft-edge, edge
        return "edge"
    if "safari" in n:
        return "safari"
    if n == "arc":
        return "arc"
    if "chrome" in n or "chromium" in n:
        return "chrome"
    return None

# How long an extension report stays usable. The extension pushes on every tab
# switch / focus change, so a fresh report is always at hand while a browser is
# in use; past this the report is considered stale and the macOS fallback (or
# None) takes over — a browser that closed or crashed can't pin an old URL.
DEFAULT_MAX_AGE_S = 8.0

# Context reporters: normalised app name -> the `app` token its add-on sends.
# An allow-list on purpose: the receiver stores one report per source, and an
# unlisted `app` value is dropped rather than given a slot. The names are the
# ones the mapping's `blender` entry is keyed on (Windows strips `.exe`; the
# Flatpak id is reported lowercased).
CONTEXT_REPORTERS = {
    "blender": "blender",
    "org.blender.blender": "blender",
}
_REPORTER_TOKENS = frozenset(CONTEXT_REPORTERS.values())


def context_reporter_for(app_name):
    """The reporter token for a focused app with a context add-on, or None."""
    if not isinstance(app_name, str):
        return None
    return CONTEXT_REPORTERS.get(app_name.strip().lower())


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
    """Latest focused-browser URL (and context-reporter pseudo-URL), with
    freshness + focus gating.

    ``clock`` and ``macos_lookup`` are injectable for tests. ``clock`` is a
    monotonic seconds source; ``macos_lookup(app_name) -> Optional[str]`` is the
    zero-install fallback (defaults to the real AppleScript query, a no-op off
    macOS)."""

    def __init__(self, max_age_s=DEFAULT_MAX_AGE_S, clock=time.monotonic,
                 macos_lookup=browser_url_macos.frontmost_url):
        self._max_age_s = max_age_s
        self._clock = clock
        self._macos_lookup = macos_lookup
        # source key -> dict(url, title, focused, ts). Keys: ("browser", brand)
        # with brand None for a report naming no recognisable browser, and
        # ("app", token) for a context reporter. Bounded: both key spaces are
        # closed sets.
        self._reports = {}

    # ------------------------------------------------------------------
    # Ingest (from the extension / add-on via browser_report_server)
    # ------------------------------------------------------------------

    def update(self, browser=None, url=None, title=None, focused=True, app=None) -> bool:
        """Store one report. Returns True when that source's effective URL
        changed (a real navigation / tab switch / mode change / (de)focus), so
        the caller can nudge window tracking to re-match -- this is what lets an
        SPA route change, or a Blender mode switch, with no window-title change
        still swap overlays.

        A report with ``focused`` false / no URL clears the effective URL (the
        browser lost focus or the tab has no address, e.g. a new-tab page).
        A report naming an ``app`` that is not a known context reporter is
        ignored (returns False)."""
        if app is not None:
            token = str(app).strip().lower()
            if token not in _REPORTER_TOKENS:
                return False
            key = ("app", token)
        else:
            key = ("browser", _canonical_browser(browser))
        prev = self._effective_url(key)
        self._reports[key] = {
            "url": url or None,
            "title": title,
            "focused": bool(focused),
            "ts": self._clock(),
        }
        return self._effective_url(key) != prev

    def _effective_url(self, key):
        """That source's URL if its report is fresh AND focused, else None."""
        r = self._reports.get(key)
        if not r or not r["focused"] or not r["url"]:
            return None
        if self._clock() - r["ts"] > self._max_age_s:
            return None
        return r["url"]

    # ------------------------------------------------------------------
    # Lookup (from OverlayHandler)
    # ------------------------------------------------------------------

    def current_url(self, app_name):
        """URL for the focused window, or ``None``.

        * A **context reporter** (Blender) gets its own add-on's fresh, focused
          pseudo-URL, and nothing else -- never a browser's URL, and no macOS
          fallback.
        * A **browser** gets a fresh, focused report from *that same browser*
          (cross-browser leakage guarded: a Chrome report never answers for
          Firefox). A report naming no recognisable browser (an older
          extension) stays permissive. Otherwise the macOS AppleScript fallback
          is tried (a no-op off macOS / for Firefox).
        * Any other app gets ``None``, so neither a website nor a background
          Blender's context can ever leak onto a native app's overlay."""
        token = context_reporter_for(app_name)
        if token is not None:
            return self._effective_url(("app", token))
        if not is_browser_app(app_name):
            return None
        brand = _canonical_browser(app_name)
        url = None
        if brand is not None:
            url = self._effective_url(("browser", brand))
        if url is None:
            url = self._effective_url(("browser", None))
        if url:
            return url
        # No fresh matching extension report — try the zero-install macOS path.
        try:
            return self._macos_lookup(app_name)
        except Exception:
            return None
