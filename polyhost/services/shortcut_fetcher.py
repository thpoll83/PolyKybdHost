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
"""

from __future__ import annotations

import logging
import threading

from polyhost.services import icon_catalog, shortcut_overlays, shortcut_source

IDLE_SECONDS = 30.0


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

    # ------------------------------------------------------------------

    def overlays_for(self, app: str) -> dict:
        """{source_name: {(modifier, keycode): mask}} for an app; {} until known.

        ⚠️ Keyed on the app name AND the render settings, because a height or
        corner change has to invalidate what is cached here as well as what is
        cached on the keyboard -- the masks in this dict were drawn at the old
        size, and `source_name()` alone would not be consulted again.
        """
        if not app or not enabled():
            return {}
        key = f"{app}\x00{icon_catalog.icon_height()}\x00{icon_catalog.icon_placement()}"
        with self._lock:
            if key in self._overlays:
                return self._overlays[key]
            if key not in self._queue and key not in self._inflight:
                self._queue.append(key)
        self._ensure_thread()
        self._wake.set()
        return {}

    def forget(self):
        """Drop every cached answer, so the next focus re-harvests.

        Called when the settings change or the device reconnects: a plan built
        while auto-fetch was off carries no icons, and nothing else would ever
        ask again.
        """
        with self._lock:
            self._overlays.clear()
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
        while not self._stop.is_set():
            with self._lock:
                key = self._queue.pop(0) if self._queue else None
                if key is not None:
                    self._inflight.add(key)
            if key is None:
                self._wake.clear()
                if not self._wake.wait(IDLE_SECONDS):
                    return
                continue
            app, height, placement = key.split("\x00")
            overlays = self._resolve(app, int(height), placement)
            with self._lock:
                self._overlays[key] = overlays
                self._inflight.discard(key)
            if overlays and self._on_ready is not None:
                try:
                    self._on_ready(app)
                except Exception:
                    # An escape would reach threading.excepthook, which this app
                    # routes into crash_log.txt — a failing observer would then
                    # put a spurious crash in every later problem report.
                    self.log.debug("shortcut-icon ready callback failed",
                                   exc_info=True)

    def _resolve(self, app: str, height: int, placement: str) -> dict:
        """Everything slow, on this thread. Returns {} for every failure.

        The three reasons a `{}` happens are told apart in the log, because they
        need opposite fixes: no accessibility backend (install the bridge, or
        this is macOS), the app exposes nothing (a modern toolkit — nothing to
        do), or nothing in what it exposes matched a concept (curation).
        """
        unusable = shortcut_source.unavailable_reason()
        if unusable is not None:
            # ⚠️ The REASON, not a flat "no backend on this platform". That
            # sentence is true on macOS and misleading everywhere else: the
            # commonest cause is an interpreter that cannot see the system
            # PyGObject, which the sentence rules out, so a user reading it goes
            # and installs a package they already have.
            self._say(app, unusable)
            return {}
        shortcuts = shortcut_source.harvest(app)
        if not shortcuts:
            self._say(app, "the app exposes no accelerators")
            return {}
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
        report = shortcut_overlays.plan_report(shortcuts, known_names=codepoints)
        slots = report.slots
        self._report(app, shortcuts, report)
        if not slots:
            self._say(app, f"none of its {len(shortcuts)} shortcut labels "
                           "matched an icon concept")
            return {}
        names = shortcut_overlays.icon_names(slots)
        try:
            font = icon_catalog.fetch_subset(names, self._cache_dir)
        except Exception:
            self.log.debug("shortcut icon subset failed for '%s'", app, exc_info=True)
            return {}
        if not font or not codepoints:
            self._say(app, "the icon subset is neither cached nor reachable")
            return {}
        try:
            overlays = shortcut_overlays.render(slots, font, codepoints,
                                                height=height, placement=placement)
        except Exception:
            self.log.debug("shortcut icon render failed for '%s'", app, exc_info=True)
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
