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
import threading
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
    # Editors with a mode plugin, in their own GUI window. Windows reports
    # gvim.exe / emacs.exe, Linux the WM_CLASS, macOS the display name.
    "gvim": "vim",
    "macvim": "vim",
    "neovide": "vim",
    "emacs": "emacs",
}

# Reporters that also run INSIDE a terminal (vim, emacs -nw). While a terminal
# is the focused app, the freshest focused report from one of them answers for
# it, the way a browser's tab URL answers for the browser. The plugins send
# focused=false on the terminal's focus-out event and when they exit, so a
# terminal window running a plain shell gets no URL.
HOSTED_REPORTERS = frozenset({"vim", "emacs"})
_REPORTER_TOKENS = frozenset(CONTEXT_REPORTERS.values()) | HOSTED_REPORTERS

# Terminal apps that host those reporters, as the OS reports them (lowercased).
# Only local terminals: an editor in an SSH session (PuTTY, a remote shell)
# cannot reach this host's loopback receiver. None of the names was checked on
# an install (docs/architecture.md, "Terminal-hosted editors").
TERMINAL_APPS = frozenset({
    # Windows
    "windowsterminal", "wt", "openconsole", "conhost", "alacritty", "wezterm-gui",
    # Linux (WM_CLASS or Flatpak/app id)
    "gnome-terminal", "gnome-terminal-server", "org.gnome.terminal",
    "ptyxis", "org.gnome.ptyxis", "kgx", "org.gnome.console",
    "konsole", "org.kde.konsole", "kitty", "org.wezfurlong.wezterm", "wezterm",
    "foot", "xterm", "uxterm", "urxvt", "tilix", "com.gexperts.tilix",
    "terminator", "xfce4-terminal", "ghostty", "com.mitchellh.ghostty",
    # macOS (display names)
    "terminal", "iterm2", "iterm",
})


def _app_key(app_name):
    """``app_name`` lowercased and without a Windows ``.exe`` suffix, or None.
    The window handler passes names already normalised; the forwarder passes
    the raw Windows process name (``WindowsTerminal.exe``)."""
    if not isinstance(app_name, str):
        return None
    n = app_name.strip().lower()
    return n[:-4] if n.endswith(".exe") else n


def context_reporter_for(app_name):
    """The reporter token for a focused app with a context add-on, or None."""
    return CONTEXT_REPORTERS.get(_app_key(app_name))


def is_terminal_app(app_name) -> bool:
    """Whether ``app_name`` (a getAppName(), normalised or a raw Windows
    process name) is a terminal that can host a vim or emacs mode reporter."""
    return _app_key(app_name) in TERMINAL_APPS


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
        # source key -> dict(url, title, focused, ts, input_ts). Keys:
        # ("browser", brand) with brand None for a report naming no
        # recognisable browser, and ("app", token, pid) for one running
        # instance of a context reporter (pid None from an add-on that does not
        # send one). Bounded: the browser keys are a closed set, and stale app
        # instances are pruned on every app report.
        self._reports = {}
        # update() runs on the report server's request threads and
        # current_url() on window tracking's: both walk _reports.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Ingest (from the extension / add-on via browser_report_server)
    # ------------------------------------------------------------------

    def update(self, browser=None, url=None, title=None, focused=True, app=None,
               pid=None, input_age=None) -> bool:
        """Store one report. Returns True when that source's effective URL
        changed (a real navigation / tab switch / mode change / (de)focus), so
        the caller can nudge window tracking to re-match -- this is what lets an
        SPA route change, or a Blender mode switch, with no window-title change
        still swap overlays.

        A report with ``focused`` false / no URL clears the effective URL (the
        browser lost focus or the tab has no address, e.g. a new-tab page).
        A report naming an ``app`` that is not a known context reporter is
        ignored (returns False)."""
        with self._lock:
            return self._update(browser, url, title, focused, app, pid, input_age)

    def _update(self, browser, url, title, focused, app, pid, input_age):
        now = self._clock()
        if app is not None:
            token = str(app).strip().lower()
            if token not in _REPORTER_TOKENS:
                return False
            prev = self._app_url(token)
            # A terminal answers with the newest input over every hosted
            # editor, so input to one can change that answer while its own
            # URL stays the same (vim stays in normal mode, emacs had input).
            prev_hosted = self._app_url(HOSTED_REPORTERS)
            # Drop instances that stopped reporting (Blender closed), so the
            # per-pid key space cannot grow without bound.
            for k in [k for k, r in self._reports.items()
                      if k[0] == "app" and now - r["ts"] > self._max_age_s]:
                del self._reports[k]
            self._reports[("app", token, pid)] = {
                "url": url or None,
                "title": title,
                "focused": bool(focused),
                "ts": now,
                # When this instance last saw user input; without input_age
                # (older add-on) the report itself counts as the input.
                "input_ts": now - (input_age or 0.0),
            }
            return (self._app_url(token) != prev
                    or self._app_url(HOSTED_REPORTERS) != prev_hosted)
        key = ("browser", _canonical_browser(browser))
        prev = self._effective_url(key)
        self._reports[key] = {
            "url": url or None,
            "title": title,
            "focused": bool(focused),
            "ts": now,
        }
        return self._effective_url(key) != prev

    def _fresh(self, key):
        """Whether that source has a report inside the freshness window,
        whatever it says (a cleared tab is still a fresh report)."""
        r = self._reports.get(key)
        return bool(r) and self._clock() - r["ts"] <= self._max_age_s

    def _app_url(self, token):
        """The context reporter's URL from the running instance with the most
        recent user input. Several Blenders can be open; each re-sends on a
        keep-alive, so "the newest report" would let a background instance
        overwrite the one being worked in. The newest INPUT cannot.

        The winner is picked BEFORE looking at its URL: an instance that
        withdrew its context (reporting turned off) stays the newest and
        answers None, instead of handing the keyboard to a background one.

        ``token`` may also be a set of tokens (the terminal-hosted editors):
        the winner is then the newest input over all of them, so a vim that
        lost focus to an emacs in another terminal window answers nothing."""
        tokens = token if isinstance(token, frozenset) else frozenset((token,))
        best = None
        for k, r in self._reports.items():
            if k[0] != "app" or k[1] not in tokens or not self._fresh(k):
                continue
            if best is None or r["input_ts"] > best[0]:
                best = (r["input_ts"], k)
        return self._effective_url(best[1]) if best else None

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
        * A **terminal** gets the fresh, focused pseudo-URL of the vim or emacs
          running in it (``vim://insert``), the one with the newest input, and
          nothing else.
        * A **browser** gets a fresh, focused report from *that same browser*
          (cross-browser leakage guarded: a Chrome report never answers for
          Firefox). A report naming no recognisable browser (an older
          extension) stays permissive. Otherwise the macOS AppleScript fallback
          is tried (a no-op off macOS / for Firefox).
        * Any other app gets ``None``, so neither a website nor a background
          Blender's context can ever leak onto a native app's overlay."""
        token = context_reporter_for(app_name)
        if token is None and is_terminal_app(app_name):
            token = HOSTED_REPORTERS
        if token is None and not is_browser_app(app_name):
            return None
        with self._lock:
            url = self._report_url(token, app_name)
        if url or token is not None:
            return url
        # No fresh matching extension report — try the zero-install macOS path.
        try:
            return self._macos_lookup(app_name)
        except Exception:
            return None

    def _report_url(self, token, app_name):
        """The answer current_url() takes from stored reports (lock held)."""
        if token is not None:
            return self._app_url(token)
        brand = _canonical_browser(app_name)
        # The anonymous slot (an older extension naming no browser) answers
        # only when this browser has no fresh report of its own. A fresh one
        # with no URL is a cleared tab (new-tab page, lost focus) and must
        # stay cleared, not revive another report's website.
        if brand is not None and self._fresh(("browser", brand)):
            url = self._effective_url(("browser", brand))
        else:
            url = self._effective_url(("browser", None))
        return url
