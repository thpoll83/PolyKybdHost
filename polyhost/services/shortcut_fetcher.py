"""Harvest the focused app's shortcuts and render their icons, off the tick.

The Phase-2 sibling of `AppIconFetcher`, and it keeps that module's discipline
for the same reasons -- but the work is heavier, so the thread matters more:

* the HARVEST alone is a tree walk over another process. AT-SPI charges a D-Bus
  round trip per node (budget 4000), UIA one cross-process `FindAllBuildCache`;
* then a catalog subset may be downloaded at a 15 s timeout;
* then every icon is rasterised through Pillow.

None of that may touch the HID worker (1 s reconnect probe, 250 ms console read)
or the Qt main thread. `overlays_for()` is therefore a dict lookup and nothing
else: an app it has not seen is queued and the answer arrives through
`on_ready`, which is what lets the core re-send while the app is still focused
rather than making the icons appear the second time you focus it.

⚠️ AN EMPTY RESULT IS CACHED, exactly like a missing program mark. Most apps
yield nothing -- a modern Linux toolkit exposes no accelerator at all -- so
without the negative cache every window switch would re-walk a tree that has
already been proven empty.

⚠️ ONE EXCEPTION: A WINDOW TITLE CHANGE RE-HARVESTS, because an app's menus
can change under a cached answer. Kate first seen on its welcome page has no
Save/Undo/Copy, which its editor component adds only once a document is open,
and nothing re-asked (Plasma, 2026-10-09). Document apps retitle on exactly
that transition. Two guards keep the cost bounded, both measured on Kate with
`tools/atspi_event_probe.py`:

* one harvest in flight per app, so a burst of titles collapses into one
  follow-up -- Kate retitles an unsaved document on EVERY keystroke (nine
  titles in 0.6 s while typing);
* a re-harvest that returns the SAME shortcuts backs the next one off, 5 s
  doubling to 2 min; one that returns different shortcuts resets the
  backoff. A terminal or a browser, which retitle constantly and never
  change their menus, settle at one walk every two minutes;
* and a hard FLOOR of 3 s between re-harvests of one app WHATEVER the result,
  because the backoff alone trusts the result: an app whose title cycles in
  seconds (a clock, a progress counter) and whose harvest kept differing
  would reset it every time. A title change inside the floor is not dropped
  -- the tick re-asks continuously, so it is taken once the floor passes.
  Welcome -> document is at most 3 s late.

A NEW PID for a cached app re-harvests once, past all three guards and even
under an unchanged title: a fresh instance starts on its own page, and a
second Kate inherited the first one's backoff and showed its document
shortcuts on the welcome page for 12 s (Plasma, 2026-10-09).

The old answer keeps being served until the new one lands. An event listener
was measured as the alternative and rejected: Qt emits no
object:children-changed when its menus are rebuilt.

⚠️ EVERY ANSWER IS ALSO KEPT PER TITLE, for `TITLE_CACHE_SECONDS` (30 min), so
coming BACK to a title costs no harvest. A browser retitles on every tab
switch, and each tab answers differently, so the backoff above never engaged:
31 full UIA walks of Chrome in 38 minutes, the slowest over two minutes
(2026-10-15). Now a tab seen in the last 30 minutes is served from here. An
entry that old is read again when its title is next focused, and dropped from
the cache in the meantime, so a page that gained a shortcut without retitling
(a permission prompt's "Allow once") is at most 30 minutes stale.

A harvest still in flight when focus leaves its app is CANCELLED (`_resolve`
passes `cancel`). Only the out-of-process UIA harvest can honour it; see
`shortcut_source.out_of_process`.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
import threading
import time

from polyhost.services import icon_catalog, shortcut_overlays, shortcut_source

IDLE_SECONDS = 30.0

#: Backoff for a title-triggered re-harvest that found nothing new: the first
#: wait, and the cap it doubles towards. See the module docstring.
REHARVEST_BACKOFF_FIRST = 5.0
REHARVEST_BACKOFF_MAX = 120.0
#: The floor between two re-harvests of one app, whatever they returned.
REHARVEST_MIN_GAP = 3.0
#: How long an answer is served for a title it was harvested under. The
#: maintainer's number (2026-10-15): see the module docstring.
TITLE_CACHE_SECONDS = 30 * 60


#: Keys `title_tag`'s hash. Random per process and never written anywhere, so a
#: log reader cannot test guessed titles against a logged hash (Sourcery, #393).
_TITLE_KEY = os.urandom(16)


def title_tag(title: str | None) -> str:
    """A window title as the log may show it: a short keyed hash and the length.

    ⚠️ Never the title itself. Titles name documents, and the log bundle masks
    them only in the lines it knows; a new line format would leak them. The
    length matches the `<redacted:N chars>` of the window-change lines, and the
    hash ties this module's lines for one title together within one run.
    ⚠️ Keyed (HMAC with `_TITLE_KEY`), not a plain hash: an unkeyed one lets
    anyone holding the bundle confirm a guessed title offline.
    """
    if title is None:
        return "no title"
    digest = hmac.new(_TITLE_KEY, title.encode("utf-8", "replace"),
                      hashlib.sha256).hexdigest()[:6]
    return f"title #{digest} ({len(title)} chars)"


def _now() -> float:
    """The re-harvest clock. A function so tests can move it."""
    return time.monotonic()


def _signature(overlays: dict) -> frozenset:
    """What a harvest drew, without the pixels: which icon on which key."""
    return frozenset((source, frozenset(keys)) for source, keys in overlays.items())


def enabled() -> bool:
    """Is the shortcut fall-back switched on?

    Separate from `shortcut_icon_auto_fetch`, which governs only whether the
    NETWORK may be used. This governs whether another application's
    accessibility tree is read at all, which is a different question and the one
    someone on a locked-down machine actually wants to answer.
    """
    try:
        from polyhost.settings import read_setting
        return bool(read_setting("shortcut_icons_enabled", True))
    except Exception:
        return True


class ShortcutIconFetcher:
    """A work queue over harvest → plan → fetch → render, cached per app."""

    def __init__(self, on_ready=None, cache_dir: str | None = None):
        self.log = logging.getLogger("PolyHost")
        self._on_ready = on_ready
        self._cache_dir = cache_dir
        self._overlays: dict[str, dict] = {}     # app -> {source_name: {(mod, kc): mask}}
        self._queue: list[str] = []
        self._inflight: set[str] = set()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._shutting_down = False
        self._told: set[tuple] = set()
        # app -> shortcuts somebody ELSE harvested, for an application running
        # on the forwarder's machine. Keyed on the app alone, deliberately
        # unlike `_overlays`: what was harvested does not depend on the icon
        # height or the corner, only what is DRAWN from it does. Survives
        # `forget()` for the same reason -- a settings change invalidates the
        # masks, never the other machine's answer about its own app.
        self._harvested: dict[str, tuple] = {}
        # app -> the pid it was focused as. ⚠️ On macOS this is what decides
        # whether the harvest reads the app the caller meant or whatever
        # NSWorkspace last called frontmost -- a value frozen on this thread.
        # See `shortcut_source.macos._frontmost_name`.
        self._pids: dict[str, int] = {}
        # Title-triggered re-harvest (module docstring). `_titles` is the
        # latest title the caller reported per app; the rest is per cache KEY,
        # like `_overlays`: the title the cached answer was harvested under,
        # what it drew, and the (interval, not_before) backoff.
        self._titles: dict[str, str] = {}
        self._harvest_title: dict[str, str] = {}
        self._drew: dict[str, frozenset] = {}
        self._backoff: dict[str, tuple[float, float]] = {}
        self._harvested_at: dict[str, float] = {}
        # Keys whose app came back under a NEW pid since their last harvest.
        # One re-harvest each, past the title test, the floor and the backoff:
        # a fresh instance starts on its own page (Kate's welcome page), and
        # the old instance's backoff kept its answer on screen for 12 s.
        self._restarted: set[str] = set()
        # key -> {title: (overlays, signature, harvested_at)}: every answer,
        # per title it was harvested under, for TITLE_CACHE_SECONDS. `_overlays`
        # stays the answer being SERVED; this is where a revisited title's
        # answer is taken back from.
        self._by_title: dict[str, dict[str, tuple]] = {}
        # The focused app, from `note_focus` (every tick) and `overlays_for`.
        # A harvest of any other app is cancelled (`_resolve`).
        self._focused: str | None = None
        # The window handle the harvest in flight was asked for, taken with
        # its title when it was dequeued (`_run_queue`). Only the one harvest
        # thread reads or writes it.
        self._harvest_hwnd: int | None = None
        # app -> the focused window's handle (Windows): which window to read.
        self._hwnds: dict[str, int] = {}

    # ------------------------------------------------------------------

    def overlays_for(self, app: str, harvested=None, pid: int | None = None,
                     title: str | None = None, hwnd: int | None = None) -> dict:
        """{source_name: {(modifier, keycode): mask}} for an app; {} until known.

        ⚠️ Keyed on the app name AND the render settings, because a height or
        corner change has to invalidate what is cached here as well as what is
        cached on the keyboard -- the masks in this dict were drawn at the old
        size, and `source_name()` alone would not be consulted again.

        `harvested` supplies the shortcuts instead of reading them here, for an
        application running on the FORWARDER's machine: its accessibility tree
        is only readable there, so the harvest is done on that machine and
        relayed as text (`services.shortcut_relay`). Everything after the
        harvest -- which concept a label means, which catalog subset to fetch,
        what height and corner to raster at -- is unchanged, because all of it
        is knowable only here.

        ⚠️ Pass `()` for "the other machine looked and found nothing", never for
        "it has not answered yet". This method CACHES an empty result, so a
        not-yet-answered app fed in as `()` is cached as having no shortcuts and
        the real answer is ignored for the life of the process. The caller holds
        that distinction (`RemoteHandler.forwarded_shortcuts` answers None) and
        must not call at all until it has one.

        `title` is the focused window's title. A change from the title the
        cached answer was harvested under queues a re-harvest while the cached
        answer keeps being returned; see the module docstring. None (a
        forwarded window, or a caller that has none) never re-harvests.

        `hwnd` is the focused window's handle (Windows). The harvest reads THAT
        window rather than whatever has focus when it runs: a read queued for
        Zoom ran seven minutes later on Chrome and filed Chrome's shortcuts
        under Zoom (2026-10-15). Like `pid`, it says which window to read and is
        not part of the cache key.
        """
        if not app or not enabled():
            return {}
        if harvested is not None:
            self._harvested[app] = tuple(harvested)
        self._focused = app
        if hwnd is not None:
            self._hwnds[app] = int(hwnd)
        else:
            # ⚠️ Not the previous window's handle: the harvest would read a
            # window that is no longer the focused one (Revix, #393).
            self._hwnds.pop(app, None)
        key = f"{app}\x00{icon_catalog.icon_height()}\x00{icon_catalog.icon_placement()}"
        with self._lock:
            if pid is not None:
                # ⚠️ Keyed on the app alone and deliberately NOT part of the
                # cache key, exactly like `_harvested`: a pid says WHICH
                # PROCESS to read. A new pid re-harvests once (`_restarted`)
                # rather than starting a new cache entry, so the old answer
                # stays on screen until the new one lands.
                previous_pid = self._pids.get(app)
                self._pids[app] = int(pid)
                if previous_pid is not None and previous_pid != int(pid):
                    prefix = f"{app}\x00"
                    for k in self._overlays:
                        if k.startswith(prefix):
                            self._restarted.add(k)
                            self._backoff.pop(k, None)
                            # The old process's per-title answers say nothing
                            # about the new one's pages.
                            self._by_title.pop(k, None)
            if title is not None:
                self._titles[app] = title
            if key in self._overlays:
                if title is not None:
                    self._serve_title(key, title)
                cached = self._overlays[key]
                why = self._reharvest_reason(key, title)
                if why is None:
                    return cached
                self.log.info("Shortcut icons for '%s': reading it again (%s)",
                              app, why)
                self._queue.append(key)
            else:
                cached = {}
                _, not_before = self._backoff.get(key, (0.0, 0.0))
                if (key not in self._queue and key not in self._inflight
                        and _now() >= not_before):
                    self._queue.append(key)
        self._ensure_thread()
        self._wake.set()
        return cached

    def note_focus(self, app: str | None):
        """The app the window tracker sees focused NOW, called on every tick.

        `overlays_for` alone is not called for every focus: the core skips it
        while a template covers the window with gap filling off, and while no
        app is named. A read of the app focus has LEFT is cancelled by this
        (`_resolve`'s `cancel`), so a long Chrome walk no longer runs on behind
        such a window (Greptile, Sourcery and Revix, #393). None (nothing
        named) also cancels.
        """
        self._focused = app

    def _serve_title(self, key: str, title: str):
        """Under `_lock`: serve the cached answer for `title`, if it has one.

        Switches what `_overlays[key]` serves and what it counts as harvested
        under, so `_wants_reharvest` sees an unchanged title and asks nothing.
        An entry past TITLE_CACHE_SECONDS is dropped instead, and the title
        then reads as new: the ordinary re-harvest rules take it from there.
        """
        if self._harvest_title.get(key) == title or key in self._restarted:
            return
        entry = self._title_entry(key, title)
        if entry is None:
            return
        self._overlays[key], self._drew[key], at = entry
        self._harvest_title[key] = title
        self.log.info("Shortcut icons for '%s': %s served from the cache "
                      "(read %d s ago, %d icon source(s)), no read",
                      key.split("\x00", 1)[0], title_tag(title), _now() - at,
                      len(entry[0]))

    def _title_entry(self, key: str, title: str):
        """Under `_lock`: the fresh per-title entry, or None. Drops a stale one."""
        titles = self._by_title.get(key)
        entry = titles.get(title) if titles else None
        if entry is None:
            return None
        if _now() - entry[2] >= TITLE_CACHE_SECONDS:
            del titles[title]
            self.log.info("Shortcut icons for '%s': the cached answer for %s is "
                          "%d min old, dropped", key.split("\x00", 1)[0],
                          title_tag(title), (_now() - entry[2]) // 60)
            return None
        return entry

    def _remember_title(self, key: str, title: str, overlays: dict):
        """Under `_lock`: keep this answer for `title`, and evict the expired."""
        now = _now()
        titles = self._by_title.setdefault(key, {})
        for old in [t for t, e in titles.items()
                    if now - e[2] >= TITLE_CACHE_SECONDS]:
            del titles[old]
        titles[title] = (overlays, self._drew[key], now)

    def _wants_reharvest(self, key: str, title: str | None) -> bool:
        """Under `_lock`: has the title or the process moved on from the
        cached answer's? See `_reharvest_reason`."""
        return self._reharvest_reason(key, title) is not None

    def _reharvest_reason(self, key: str, title: str | None) -> str | None:
        """Under `_lock`: why the cached answer must be read again, or None.

        A new pid skips the title test and the floor, but not the backoff,
        so a backend that keeps answering None for it still slows down. The
        reason is a sentence for the log line that queues the read.
        """
        if key in self._queue or key in self._inflight:
            return None
        _, not_before = self._backoff.get(key, (0.0, 0.0))
        if key in self._restarted:
            return "the app runs as a new process" if _now() >= not_before else None
        if title is None:
            return None
        harvested_under = self._harvest_title.get(key)
        if harvested_under is None:
            return None
        if harvested_under == title:
            # The served answer IS this title's. Read it again only once it
            # has aged out of the per-title cache.
            entry = self._by_title.get(key, {}).get(title)
            if entry is None or _now() - entry[2] < TITLE_CACHE_SECONDS:
                return None
            why = (f"the answer for {title_tag(title)} is over "
                   f"{TITLE_CACHE_SECONDS // 60} min old")
        else:
            why = f"new {title_tag(title)}, not cached"
        not_before = max(not_before,
                         self._harvested_at.get(key, 0.0) + REHARVEST_MIN_GAP)
        return why if _now() >= not_before else None

    def _note_result(self, key: str, overlays: dict | None, title: str | None,
                     remember: bool = True):
        """Under `_lock`: record a harvest and move the backoff.

        Only a RE-harvest's ANSWER moves it -- the first answer for a key has
        nothing to compare against. None ("did not look") always backs off,
        first read included, so a backend that keeps failing for a focused app slows down,
        but it records NOTHING else: the title or pid it was asked for stays
        pending and is retried once the backoff passes.
        """
        restarted = key in self._restarted
        # A new process: its answer is a first answer, not a repeat.
        previous = None if restarted else self._drew.get(key)
        self._harvested_at[key] = _now()
        if overlays is None:
            # ⚠️ Every time, the FIRST read too: `overlays_for` re-queues an
            # uncached app on every tick, so a first read that keeps failing
            # (UIA raising, an unreadable pid) would otherwise repeat every
            # 250 ms (Greptile, #393).
            self._back_off(key)
            return
        self._restarted.discard(key)
        self._overlays[key] = overlays
        self._drew[key] = _signature(overlays)
        # "" for a harvest made under no title, so a title that appears later
        # still differs from it. `focused_title()` never reports "".
        self._harvest_title[key] = title if title is not None else ""
        if remember:
            self._remember_title(key, self._harvest_title[key], overlays)
        if previous is None:
            self._backoff.pop(key, None)
            return
        if self._drew[key] != previous:
            self._backoff[key] = (0.0, 0.0)
            return
        self._back_off(key)

    def _back_off(self, key: str):
        """Under `_lock`: double the key's backoff, 5 s to 2 min."""
        interval, _ = self._backoff.get(key, (0.0, 0.0))
        interval = min(max(REHARVEST_BACKOFF_FIRST, interval * 2),
                       REHARVEST_BACKOFF_MAX)
        self._backoff[key] = (interval, _now() + interval)

    def forget(self):
        """Drop every cached answer, so the next focus re-harvests.

        Called when the settings change or the device reconnects: a plan built
        while auto-fetch was off carries no icons, and nothing else would ever
        ask again.
        """
        with self._lock:
            self._overlays.clear()
            self._harvest_title.clear()
            self._drew.clear()
            self._backoff.clear()
            self._harvested_at.clear()
            self._restarted.clear()
            self._by_title.clear()
        self._told.clear()

    def stop(self):
        """Stop the thread. Safe twice, never raises — see AppIconFetcher.stop."""
        with self._lock:
            self._shutting_down = True
            self._stop.set()
            thread = self._thread
            self._thread = None
        self._wake.set()
        if thread is not None:
            thread.join(timeout=2)
        # The UIA helper process, if this process ever started one. Looked up
        # rather than imported: a platform that never harvested out of process
        # has nothing to stop.
        helper = sys.modules.get("polyhost.services.shortcut_source.out_of_process")
        if helper is not None:
            helper.stop()

    # ------------------------------------------------------------------

    def _say(self, app: str, reason: str):
        key = (app, reason)
        if key in self._told:
            return
        self._told.add(key)
        self.log.info("No shortcut icons for '%s' (%s)", app, reason)

    def _ensure_thread(self):
        with self._lock:
            if self._shutting_down:
                return
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop,
                                            name="poly-shortcut-icons", daemon=True)
            self._thread.start()

    def _loop(self):
        # ⚠️ This thread ends after IDLE_SECONDS and a new one replaces it, so
        # whatever the harvest backend built here must be released HERE, on
        # the way out. On Windows that is a COM apartment plus the
        # IUIAutomation object inside it; handing them to the next thread is
        # what crashed the daemon (see `shortcut_source.uia`).
        try:
            self._run_queue()
        finally:
            shortcut_source.release_thread()

    def _run_queue(self):
        while not self._stop.is_set():
            with self._lock:
                key = self._queue.pop(0) if self._queue else None
                if key is not None:
                    self._inflight.add(key)
                    # The title this harvest answers for: the newest one, read
                    # as it STARTS. A title that arrives mid-walk is newer than
                    # the answer and queues the one follow-up.
                    harvesting_title = self._titles.get(key.split("\x00", 1)[0])
                    harvesting_pid = self._pids.get(key.split("\x00", 1)[0])
                    # ⚠️ Taken WITH the title, under the same lock: a handle
                    # read later could name a newer window than the title the
                    # answer is filed under (Sourcery, #393).
                    self._harvest_hwnd = self._hwnds.get(key.split("\x00", 1)[0])
            if key is None:
                self._wake.clear()
                if not self._wake.wait(IDLE_SECONDS):
                    return
                continue
            app, height, placement = key.split("\x00")
            overlays = self._resolve(app, int(height), placement)
            with self._lock:
                # ⚠️ None means "this harvest never LOOKED" -- focus had already
                # moved on, or the accessibility call failed outright -- and it
                # must not be cached. An empty dict IS cached, deliberately (see
                # the module docstring), so storing a did-not-look answer as one
                # pins "this app has no shortcuts" for the life of the process
                # and the app is never re-harvested however long it is focused.
                # Exactly the distinction the relay path is warned about in
                # `overlays_for`, one layer down.
                # ⚠️ Kept in the per-title cache only if the title and the
                # process held for the whole read. Chrome's tabs share ONE
                # window handle, so a tab switch mid-read gives an answer for
                # tab B that would be filed under tab A for 30 minutes
                # (Greptile, #393); and an old process's answer must not
                # refill the cache its restart cleared (Sourcery, #393). The
                # answer is still served now, as it was before the cache.
                held = (self._titles.get(app) == harvesting_title
                        and self._pids.get(app) == harvesting_pid)
                if overlays is not None and not held:
                    self.log.info("Shortcut icons for '%s': the window changed "
                                  "during the read (%s), answer not cached",
                                  app, title_tag(harvesting_title))
                self._note_result(key, overlays, harvesting_title, remember=held)
                self._inflight.discard(key)
                if (overlays is not None
                        and self._pids.get(app) != harvesting_pid):
                    # The app restarted mid-walk: this answer is the OLD
                    # process's, so the new one is still owed a harvest.
                    self._restarted.add(key)
            if overlays and self._on_ready is not None:
                try:
                    self._on_ready(app)
                except Exception:
                    # An escape would reach threading.excepthook, which this app
                    # routes into crash_log.txt — a failing observer would then
                    # put a spurious crash in every later problem report.
                    self.log.debug("shortcut-icon ready callback failed",
                                   exc_info=True)

    def _resolve(self, app: str, height: int, placement: str) -> dict | None:
        """Everything slow, on this thread. `{}` for a failure, None to retry.

        The three reasons a `{}` happens are told apart in the log, because they
        need opposite fixes: the backend is unusable (install the bridge, or
        grant Accessibility permission on macOS), the app exposes nothing (a
        modern toolkit — nothing to do), or nothing in what it exposes matched a
        concept (curation). On macOS the middle one splits further still — see
        `shortcut_source.harvest`.

        ⚠️ **None is not a failure, it is "did not look"**, and `_loop` must not
        cache it. A harvest the backend abandoned -- focus moved before it ran,
        or the API failed -- says nothing about the app, so caching it as an
        empty result is indistinguishable from the app genuinely having no
        shortcuts and just as permanent.
        """
        relayed = self._harvested.get(app)
        if relayed is not None:
            # A forwarded app: the harvest already happened on the machine
            # running it. The local backend is not consulted at all -- asking it
            # would walk THIS machine's tree, never find the app, and report
            # "exposes no accelerators" for one that exposes sixteen.
            shortcuts = relayed
            if not shortcuts:
                self._say(app, "the forwarder harvested it and it exposes no "
                               "accelerators")
                return {}
        else:
            unusable = shortcut_source.unavailable_reason()
            if unusable is not None:
                # ⚠️ The REASON, not a flat "no backend on this platform".
                # That sentence is now true on NO platform -- macOS has a
                # backend since the AX one landed -- and it was always
                # misleading everywhere else: the commonest cause is an
                # interpreter that cannot see the system PyGObject, which the
                # sentence rules out, so a user reading it goes and installs a
                # package they already have. On macOS the likeliest cause is a
                # permission nobody has granted yet, which reads as an app with
                # no shortcuts unless the reason says otherwise.
                self._say(app, unusable)
                return {}
            reason: dict = {}
            # ⚠️ Cancelled once focus has left this app: a read that took two
            # minutes on a long Chrome tab otherwise ran on for a tab nobody
            # was looking at any more (2026-10-15).
            shortcuts = shortcut_source.harvest(
                app, reason=reason, pid=self._pids.get(app),
                cancel=lambda: self._focused != app,
                hwnd=self._harvest_hwnd)
            if not shortcuts:
                # ⚠️ The backend's own sentence when it has one. *"The app
                # exposes no accelerators"* is true of exactly ONE of the six
                # ways the macOS backend returns [], and reads as settled fact
                # for the other five -- a revoked permission, an app with no
                # AXMenuBar, a focus race, an AX failure. Four macOS apps
                # reported it on a machine where Chrome harvested 65, so the
                # import and the permission were provably fine and the line
                # narrowed nothing (field, 2026-09-21).
                self._say(app, reason.get("why")
                          or "the app exposes no accelerators")
                # Nothing was learned about this app, so do not cache it;
                # `_loop` reads the None, and its comment says why.
                return None if reason.get("retry") else {}
        # ⚠️ The codepoint table is loaded BEFORE planning, not after, because
        # the planner now uses it: a label the lexicon does not know falls back
        # to a name derived from the label, and the table is what rejects a
        # derivation the catalog does not carry. A failure here is not fatal --
        # planning without it simply skips that fall-back, which is the
        # behaviour before it existed.
        try:
            codepoints = icon_catalog.load_codepoints(self._cache_dir)
        except Exception:
            self.log.debug("shortcut codepoints unavailable for '%s'", app,
                           exc_info=True)
            codepoints = {}
        report = shortcut_overlays.plan_report(shortcuts, known_names=codepoints,
                                               app=app)
        slots = report.slots
        self._report(app, shortcuts, report)
        if not slots:
            self._say(app, f"none of its {len(shortcuts)} shortcut labels "
                           "matched an icon concept")
            return {}
        # ⚠️ ONE FETCH AND ONE RENDER PER CATALOG. The plan can mix faces --
        # Fluent draws most concepts and Material keeps the five it loses at
        # 36 px -- and the two are fetched differently (a server-side subset of
        # exactly the names asked for, versus one whole font), so they cannot
        # share a request. `render` therefore draws a single face and the
        # results merge here.
        by_face = shortcut_overlays.icon_names_by_face(slots)
        # ⚠️ The Material request is the WHOLE LEXICON plus whatever this app
        # derived, not just this app's names -- `subset_path` keys its cache on
        # the set asked for, so a per-app set is a new cache file and a fresh
        # HTTPS round-trip on first sight of every application, forever. The
        # union keeps the common case on one stable file (an app that needs
        # only lexicon names asks for exactly the lexicon) while an app that
        # derived a name outside it still gets that name drawn.
        floor = shortcut_overlays.lexicon_names_by_face()
        overlays: dict = {}
        for face, names in sorted(by_face.items()):
            wanted = sorted(set(names) | set(floor.get(face, ())))
            reasons: dict = {}
            try:
                font = icon_catalog.fetch_subset(wanted, self._cache_dir, face=face,
                                                 reasons=reasons)
                table = (codepoints if face == icon_catalog.MATERIAL
                         else icon_catalog.load_codepoints(self._cache_dir, face=face))
            except Exception:
                self.log.debug("shortcut icon subset failed for '%s' (%s)", app,
                               face, exc_info=True)
                continue
            if not font or not table:
                # ⚠️ Per face, not fatal: Fluent being unreachable must still
                # leave the Material half drawn rather than blanking the app.
                #
                # ⚠️ And it names WHICH of the two is missing and WHY. The bare
                # sentence reads the same for a refused download, an unwritable
                # cache, a proxy page served with a 200 and a stylesheet that
                # carried no url -- four causes with four different remedies,
                # and nothing below INFO said anything at all (field, macOS,
                # 2026-09-21: both faces failed and the log could not narrow it).
                missing = ("the font" if not font else "the codepoint table")
                self._say(app, f"the {face} icons are neither cached nor "
                               f"reachable -- {missing} is missing"
                               + (f" ({reasons[face]})" if reasons.get(face) else ""))
                continue
            try:
                overlays.update(shortcut_overlays.render(
                    slots, font, table, height=height, placement=placement,
                    face=face))
            except Exception:
                self.log.debug("shortcut icon render failed for '%s' (%s)", app,
                               face, exc_info=True)
        if not overlays:
            return {}
        drawn = sum(len(v) for v in overlays.values())
        if drawn < len(slots):
            # A concept the subset font did not carry — planned, then dropped at
            # render time. Worth its own line: it is the one refusal the plan
            # report above cannot predict.
            self.log.info("  %d icon(s) planned for '%s' were not in the "
                          "fetched font and were skipped", len(slots) - drawn, app)
        return overlays

    def _report(self, app, shortcuts, report):
        """What this app's harvest produced, in a form that can be pasted back.

        ⚠️ INFO, not debug — and that is the whole point of it. This feature
        decides on its own what to draw on ~20 keycaps, so "it worked" and "it
        did not" are only distinguishable to a user who can see WHICH key got
        WHICH icon and which labels were refused. At debug level that report
        needs `--dev 2`, which nobody running the shipped app has on.

        Three lines per app, once per app per session (the answer is cached), so
        the volume is bounded by how many applications get focused rather than
        by how long the session runs.
        """
        self.log.info("Shortcut icons for '%s': %d shortcut(s) harvested -> %s",
                      app, len(shortcuts), report.summary())
        if report.slots:
            drawn = " ".join(
                f"{shortcut_overlays.pretty_key(s.modifier, s.keycode)}={s.concept}"
                for s in sorted(report.slots, key=lambda s: (s.modifier, s.keycode)))
            self.log.info("  drawn: %s", drawn)
        for why, items in sorted(report.refused.items()):
            self.log.info("  no icon (%s): %s", why, " ".join(items))
