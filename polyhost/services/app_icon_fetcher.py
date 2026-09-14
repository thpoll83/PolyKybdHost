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

Results are cached in memory INCLUDING the misses: a slug the catalog does not
carry is stored as None, so an app without a mark costs one request per process
rather than one per window switch.
"""

from __future__ import annotations

import logging
import os
import threading

from polyhost.services import app_icons, icon_binarise, os_app_icon

# How long a fetch thread lingers with nothing to do before ending. It restarts
# on the next unseen app, so this is only about not holding a thread for the
# life of a session that has settled.
IDLE_SECONDS = 30.0


class AppIconFetcher:
    """A small work queue over `app_icons`, with an in-memory result cache."""

    def __init__(self, on_ready=None, cache_dir: str | None = None,
                 mapping: dict | None = None):
        self.log = logging.getLogger("PolyHost")
        self._on_ready = on_ready
        self._cache_dir = cache_dir
        self._mapping = mapping
        self._masks: dict[str, object] = {}      # slug -> mask, or None (absent)
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
        self._why: dict[tuple, str] = {}
        # The app name a candidate list was first looked up for. The queue is
        # keyed on the CANDIDATES (two apps can share them), but a log line that
        # names only the slug makes the reader map `mdi:note-text` back to
        # Notepad themselves — which is exactly the mapping this feature is
        # supposed to be reporting on.
        self._asked_for: dict[tuple, str] = {}

    # ------------------------------------------------------------------

    def slug_map(self) -> dict:
        if self._mapping is None:
            self._mapping = app_icons.load_slug_map()
        return self._mapping

    def overlay_for(self, app_name: str, pid=None):
        """(mask, slug) for an app, without blocking. mask is None until known.

        A None mask with a slug may mean "still fetching" or "the catalog does
        not have it"; the caller does not need to tell those apart, because both
        mean *draw nothing now* and only the first will ever call `on_ready`.
        """
        names = app_icons.candidates(app_name, self.slug_map())
        if not names:
            self._say(app_name, "no catalog name for it")
            return None, None
        # ⚠️ Keyed on the whole CANDIDATE LIST, not on one name: an app is tried
        # against both catalogs in order, so "what was looked up" is the list,
        # and two apps that differ only in which candidate wins must not share
        # an answer.
        key = tuple(names)
        with self._lock:
            if key in self._masks:
                mask, resolved = self._masks[key]
                if mask is None:
                    self._say(app_name, self._why.get(
                        key, "no catalog carries " + ", ".join(names)))
                return mask, resolved
            self._asked_for.setdefault(key, (app_name, pid))
            if key not in self._queue and key not in self._inflight:
                self._queue.append(key)
        self._ensure_thread()
        self._wake.set()
        return None, names[0]

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
                app_name, pid = self._asked_for.get(key, ("", None))
            mask, resolved, why = self._resolve(key, app_name, pid)
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

    def _resolve(self, names, app_name="", pid=None):
        """(mask, resolved_name, why_it_missed) -- the first candidate that draws
        something wins, and `why` is None when one did.

        ⚠️ The reason is decided HERE because this is the only place that knows
        it. A miss with auto-fetch OFF is a refusal to ask, not an answer: the
        old line said "no catalog carries si:notepad" on a machine that had
        never sent the request, which is a claim the code cannot support and
        sends the next round after the catalog instead of after the setting.
        """
        for name in names:
            try:
                path = app_icons.fetch_icon(name, self._cache_dir)
                if not path:
                    continue
                mask = app_icons.render_overlay(path)
                if mask is None:
                    continue
                # MDI SVGs carry no <title>, so a bare `title or name` printed
                # the name twice -- say the brand name only when we have one.
                title = app_icons.title_of(path)
                mark = f"{title} ({name})" if title and title.lower() != name.lower() else name
                # ⚠️ Name the APP, not only the mark. A line reading "Program
                # icon: mdi:note-text" leaves the reader to map the slug back to
                # the window it appeared for -- which is the very thing a report
                # on what this feature got right or wrong has to state.
                if app_name:
                    self.log.info("Program icon for '%s': %s", app_name, mark)
                else:
                    self.log.info("Program icon: %s", mark)
                return mask, name, None
            except Exception:
                self.log.debug("app-icon fetch failed for '%s'", name, exc_info=True)
        # No catalog mark. Fall back to the app's OWN icon, which the OS can
        # always answer for a local process -- this is what covers the long tail
        # no catalog has heard of, and it is tried SECOND because catalog art is
        # monochrome by design while an OS icon has to survive thresholding.
        found = os_app_icon.icon_bytes(pid, app_name) if pid is not None else None
        if found:
            data, source = found
            mask, conversion, score = app_icons.render_os_overlay(data)
            if mask is not None and score >= icon_binarise.MIN_SCORE:
                resolved = "os:" + os.path.basename(source)
                self.log.info("Program icon for '%s': %s (from the OS, %s)",
                              app_name or "?", resolved, conversion)
                return mask, resolved, None
            why = ("its own icon does not survive a 1-bit keycap (score %.2f)"
                   % score)
            return None, (names[0] if names else None), why
        if not app_icons.auto_fetch_enabled():
            why = ("not cached, and auto-fetch is off -- enable "
                   "'shortcut_icon_auto_fetch' to look it up")
        else:
            why = "no catalog carries " + ", ".join(names)
        return None, (names[0] if names else None), why
