"""Resolve the focused app to a rendered mark, off the caller's thread.

⚠️ THE THREAD IS NOT OPTIONAL, and the reason is documented twice already in
this repo. `fetch_icon` is an HTTP GET at a 15 s timeout, and the two threads
that would otherwise call it are both forbidden:

* the **HID worker**, where a 15 s block sits between the 1 s reconnect probe
  and the 250 ms console read;
* the **GUI main thread**, where `wincompose_install.find_installer()` did
  exactly this and froze the tray for ~10 s on an unreachable network.

So `overlay_for()` is a dict lookup and nothing else. A name it has not seen is
queued, and the answer arrives on a later call — or through `on_ready`, which is
what lets the core re-send while the app is still focused instead of making the
icon appear only the second time you focus an app.

Results are cached in memory INCLUDING the misses: an app nothing can draw a mark
for is stored as None, so it costs one resolution per process rather than one per
window switch.

⚠️ **The cache is keyed on the APP NAME, not on a candidate list, and that is a
consequence of E2 rather than a simplification.** Resolving an app now starts
with `os_app_icon.app_identity()`, which opens a file (and on Windows opens the
process and parses its resources) -- so the candidate list is no longer knowable
without I/O, and `overlay_for()` runs on the window tick where I/O is exactly
what this class exists to keep out. The app name is the only key available for
free, and it is the right one: the identity is a function of it.
"""

from __future__ import annotations

import logging
import threading

from polyhost.services import app_icons, os_app_icon

# How long a fetch thread lingers with nothing to do before ending. It restarts
# on the next unseen app, so this is only about not holding a thread for the
# life of a session that has settled.
IDLE_SECONDS = 30.0


class AppIconFetcher:
    """A small work queue over `app_icons`, with an in-memory result cache."""

    def __init__(self, on_ready=None, cache_dir: str | None = None):
        self.log = logging.getLogger("PolyHost")
        self._on_ready = on_ready
        self._cache_dir = cache_dir
        self._masks: dict[str, tuple] = {}       # app name -> (mask, resolved name)
        self._queue: list[str] = []
        # ⚠️ A slug is neither queued nor cached while it is being fetched, so
        # without this the poll loop re-queues it on every tick until the answer
        # lands: a duplicate request, and a duplicate `on_ready` that re-sends
        # the whole overlay set a second time. Measured, not theorised -- the
        # first cut fired the callback twice for one app.
        self._inflight: set[str] = set()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._shutting_down = False
        self._told: set[tuple] = set()           # (app, reason) already logged
        # Why a miss missed, recorded on the FETCH thread where it is known.
        # ⚠️ Not re-derived in `overlay_for`: that runs on the window tick, and
        # `auto_fetch_enabled()` reads the settings file -- so asking there is
        # both a per-poll file read and, worse, a read of the setting as it is
        # NOW rather than as it was when the lookup was refused.
        self._why: dict[str, str] = {}
        # The pid an app was first seen with, so the fetch thread can resolve
        # the identity the window tick was not allowed to.
        self._asked_for: dict[str, object] = {}

    # ------------------------------------------------------------------

    def overlay_for(self, app_name: str, pid=None):
        """(mask, resolved name) for an app, without blocking. mask is None until known.

        A None mask with a name may mean "still resolving" or "nothing can draw
        it"; the caller does not need to tell those apart, because both mean
        *draw nothing now* and only the first will ever call `on_ready`.

        ⚠️ Does NO I/O, deliberately -- see the class docstring. It is a dict
        lookup and a queue append, because the window tick calls it continuously.
        """
        if not app_name:
            return None, None
        with self._lock:
            if app_name in self._masks:
                mask, resolved = self._masks[app_name]
                if mask is None:
                    self._say(app_name, self._why.get(
                        app_name, "nothing could draw a mark for it"))
                return mask, resolved
            self._asked_for.setdefault(app_name, pid)
            if app_name not in self._queue and app_name not in self._inflight:
                self._queue.append(app_name)
        self._ensure_thread()
        self._wake.set()
        return None, None

    def forget_misses(self):
        """Drop the negative cache, so a slug looked up while offline is retried.

        ⚠️ Without this, turning `shortcut_icon_auto_fetch` back ON does nothing
        until a restart: every app focused while it was off is cached as "the
        catalog has no mark", and that cache is what stops the fetch.

        The log dedupe is cleared with it so a RE-miss is reported once more —
        "still no icon, now that fetching is on" is a different fact from the
        first line, and it is the only thing that would tell someone the switch
        did not help.
        """
        with self._lock:
            for key in [k for k, (mask, _) in self._masks.items() if mask is None]:
                del self._masks[key]
                # Bookkeeping, not behaviour: `_why` is read only for a key that
                # HAS a cached miss, and a re-fetch overwrites it -- so leaving
                # it behind is unobservable (mutation-checked). Dropped anyway so
                # the negative cache and its explanation cannot disagree.
                self._why.pop(key, None)
        self._told.clear()

    def stop(self):
        """Stop the fetch thread. Safe to call twice, and never raises.

        ⚠️ One-way flag under the same lock the start path takes, or a window
        switch landing here concurrently restarts the thread after shutdown —
        the same race `_start_wincompose_settle` guards.
        """
        with self._lock:
            self._shutting_down = True
            self._stop.set()
            thread = self._thread
            self._thread = None
        self._wake.set()
        if thread is not None:
            thread.join(timeout=1)

    # ------------------------------------------------------------------

    def _say(self, app_name: str, reason: str):
        """One INFO line per (app, reason).

        ⚠️ Deduped because the window tick runs continuously: undeduped this is
        one line per poll for any app with no mark, which is most of them.
        """
        key = (app_name, reason)
        if key in self._told:
            return
        self._told.add(key)
        self.log.info("No program icon for '%s' (%s)", app_name, reason)

    def _ensure_thread(self):
        with self._lock:
            if self._shutting_down:
                return
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop,
                                            name="poly-app-icons", daemon=True)
            self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            with self._lock:
                key = self._queue.pop(0) if self._queue else None
                if key is not None:
                    self._inflight.add(key)
            if key is None:
                self._wake.clear()
                if not self._wake.wait(IDLE_SECONDS):
                    return          # nothing left to do; restarted on demand
                continue
            with self._lock:
                pid = self._asked_for.get(key)
            mask, resolved, why = self._resolve(key, pid)
            with self._lock:
                self._masks[key] = (mask, resolved)
                if why is not None:
                    self._why[key] = why
                self._inflight.discard(key)
            if mask is not None and self._on_ready is not None:
                try:
                    self._on_ready(resolved)
                except Exception:
                    # ⚠️ NOT because the queue would break -- _ensure_thread
                    # restarts a dead thread on the next lookup, measured. It is
                    # because an escape reaches `threading.excepthook`, and this
                    # app installs one that writes crash_log.txt: a failing
                    # observer would put a spurious crash in every later problem
                    # report.
                    self.log.debug("app-icon ready callback failed", exc_info=True)

    def _resolve(self, app_name: str, pid=None):
        """(mask, resolved_name, why_it_missed) -- `why` is None when one drew.

        Runs on the fetch thread, which is the only place allowed to do I/O.

        ⚠️ **ONE `app_identity()` call**, and its result is handed whole to
        `program_overlay`. That is E1's contract made real: the icon and the
        display names come out of the same resolution, so the mark and the name
        this logs cannot describe two different applications -- and on Windows
        the lookup opens the process and parses its resources, which is not a
        thing to do twice per app.

        The ORDER lives in `program_overlay` (OS icon, then catalog), not here.
        This function decides only what to log and why a miss missed.
        """
        try:
            identity = os_app_icon.app_identity(pid, app_name)
        except Exception:
            # Never raises by contract, but a backend is three platforms of
            # file parsing and a miss here must cost the catalog route, not
            # the whole lookup.
            self.log.debug("app identity failed for '%s'", app_name, exc_info=True)
            identity = os_app_icon.app_identity(None, "")
        try:
            mask, resolved = app_icons.program_overlay(
                app_name, identity, self._cache_dir)
        except Exception:
            self.log.debug("program mark failed for '%s'", app_name, exc_info=True)
            return None, None, "resolving it raised"
        if mask is not None:
            self.log.info("Program icon for '%s': %s", app_name, self._describe(resolved))
            return mask, resolved, None
        return None, resolved, self._why_missed(app_name, identity, resolved)

    def _describe(self, resolved: str) -> str:
        """`Inkscape (si:inkscape)` — the brand name beside the catalog name.

        An `os:` mark names a file and has no brand title to look up, and mdi
        SVGs carry no `<title>` at all, so a bare `title or name` would print the
        name twice.
        """
        if not resolved or resolved.startswith("os:"):
            return resolved or "?"
        try:
            path = app_icons.icon_path(resolved, self._cache_dir)
            title = app_icons.title_of(path)
        except Exception:
            return resolved
        return f"{title} ({resolved})" if title and title.lower() != resolved.lower() else resolved

    def _why_missed(self, app_name: str, identity, resolved) -> str:
        """Why nothing drew, decided HERE because this is the only place that knows.

        ⚠️ A miss with auto-fetch OFF is a refusal to ask, not an answer: saying
        "no catalog carries si:notepad" on a machine that never sent the request
        is a claim the code cannot support, and it sends the next round after the
        catalog instead of after the setting.
        """
        if not resolved:
            return "no catalog name could be derived from it"
        if getattr(identity, "icon", None):
            return "its own icon does not survive a 1-bit keycap"
        if not app_icons.auto_fetch_enabled():
            return ("not cached, and auto-fetch is off -- enable "
                    "'shortcut_icon_auto_fetch' to look it up")
        names = app_icons.candidates(app_name, getattr(identity, "names", ()))
        return "no catalog carries " + ", ".join(names)
