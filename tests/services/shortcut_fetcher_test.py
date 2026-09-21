"""The harvest queue: never block the caller, never re-walk a proven-empty app.

The properties worth pinning are the ones whose failure only shows up under a
real workload — a lookup that blocks the window tick, a duplicate harvest per
poll, a negative result that is not cached — so every test drives the real
queue with the slow half stubbed out.
"""

import threading
import time
import types
import unittest
from unittest.mock import patch

from polyhost.services import shortcut_fetcher
from polyhost.services.shortcut_fetcher import ShortcutIconFetcher

MASKS = {"@sc:save:32lower_left": {(1, 0x16): "MASK"}}


def _sc():
    from polyhost.services.shortcut_source.model import Shortcut
    return Shortcut(label="Save", role="", accel="", mods=1, keysym="",
                    hid=0x16, displayable=True)


def _plan():
    from polyhost.services.shortcut_overlays import Plan, Slot
    return Plan([Slot(modifier=1, keycode=0x16, concept="save", icon="save",
                      label="Save", confidence=1.0)], {})


def settled(fetcher, app, timeout=2.0, **kw):
    """Poll `overlays_for` until the thread has answered, or give up.

    ⚠️ RE-READS after seeing the cache filled, rather than returning the `out`
    from the top of the loop. Those are two different instants: the worker
    routinely finishes in between, and the stale `out` is then `{}` while the
    real answer sits in the cache -- which reads as "the fetcher returned
    nothing" and fails the test for a reason that is entirely the helper's.
    Measured at ~1 run in 5, and recorded as an unexplained flake for a while
    before the two reads were noticed.
    """
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        out = fetcher.overlays_for(app, **kw)
        if out:
            return out
        with fetcher._lock:
            done = any(k.startswith(app + "\x00") for k in fetcher._overlays)
        if done:
            return fetcher.overlays_for(app, **kw)
        time.sleep(0.01)
    return None


class QueueTest(unittest.TestCase):

    def setUp(self):
        self.ready = []
        self.fetcher = ShortcutIconFetcher(on_ready=self.ready.append)
        self.addCleanup(self.fetcher.stop)

    def test_the_FIRST_lookup_never_blocks_and_returns_nothing(self):
        """⚠️ The whole reason this class exists: the caller is the window tick,
        and the work behind it is a tree walk over another process plus a
        possible download."""
        with patch.object(self.fetcher, "_resolve", side_effect=lambda *a: MASKS):
            started = time.monotonic()
            self.assertEqual(self.fetcher.overlays_for("mousepad"), {})
            self.assertLess(time.monotonic() - started, 0.2)
            self.assertEqual(settled(self.fetcher, "mousepad"), MASKS)

    def test_the_answer_reaches_on_ready(self):
        """Without it the icons appear only the SECOND time you focus an app."""
        with patch.object(self.fetcher, "_resolve", side_effect=lambda *a: MASKS):
            settled(self.fetcher, "mousepad")
        self.assertEqual(self.ready, ["mousepad"])

    def test_an_app_is_harvested_ONCE_not_once_per_poll(self):
        """⚠️ A name is neither queued nor cached while it is in flight, so
        without the `_inflight` set the tick re-queues it every time — a
        duplicate tree walk and a duplicate re-send. Measured on the app-icon
        fetcher, where the first cut fired the callback twice."""
        calls = []

        def slow(app, height, placement):
            calls.append(app)
            time.sleep(0.05)
            return MASKS

        with patch.object(self.fetcher, "_resolve", side_effect=slow):
            for _ in range(20):
                self.fetcher.overlays_for("mousepad")
            settled(self.fetcher, "mousepad")
        self.assertEqual(calls, ["mousepad"])

    def test_an_EMPTY_result_is_cached(self):
        """Most apps yield nothing — a modern toolkit exposes no accelerator at
        all — so a re-walk per window switch would be the normal case."""
        calls = []
        with patch.object(self.fetcher, "_resolve",
                          side_effect=lambda a, h, p: calls.append(a) or {}):
            self.fetcher.overlays_for("gedit")
            settled(self.fetcher, "gedit")
            for _ in range(5):
                self.assertEqual(self.fetcher.overlays_for("gedit"), {})
            time.sleep(0.05)
        self.assertEqual(calls, ["gedit"])

    def test_an_empty_result_does_NOT_fire_on_ready(self):
        """A re-send that can only draw the same nothing is pure cost."""
        with patch.object(self.fetcher, "_resolve", side_effect=lambda *a: {}):
            self.fetcher.overlays_for("gedit")
            settled(self.fetcher, "gedit")
            time.sleep(0.05)
        self.assertEqual(self.ready, [])

    def test_a_RENDER_SETTING_change_re_harvests(self):
        """⚠️ The cached masks were drawn at the old size, and `source_name()`
        alone would not be consulted again — so height and corner are part of
        this cache's key as well as the keyboard's."""
        seen = []
        with patch.object(self.fetcher, "_resolve",
                          side_effect=lambda a, h, p: seen.append((h, p)) or MASKS):
            with patch.object(shortcut_fetcher.icon_catalog, "icon_height",
                              return_value=32):
                self.fetcher.overlays_for("mousepad")
                settled(self.fetcher, "mousepad")
            with patch.object(shortcut_fetcher.icon_catalog, "icon_height",
                              return_value=16):
                self.fetcher.overlays_for("mousepad")
                time.sleep(0.2)
        self.assertEqual([h for h, _ in seen], [32, 16])

    def test_the_switch_OFF_asks_nothing(self):
        """Off means another process's accessibility tree is never read."""
        with patch.object(shortcut_fetcher, "enabled", return_value=False):
            with patch.object(self.fetcher, "_resolve") as resolve:
                self.assertEqual(self.fetcher.overlays_for("mousepad"), {})
                time.sleep(0.05)
                resolve.assert_not_called()

    def test_a_raising_on_ready_never_reaches_the_EXCEPTHOOK(self):
        """⚠️ This is the property, and it is NOT "the queue keeps working" —
        `_ensure_thread` restarts a dead thread on the next lookup, so a suite
        that only re-queries passes with the `except` deleted. Measured: that
        mutation escaped until this test watched the hook instead.

        What the `except` is really for: an escape reaches
        `threading.excepthook`, and this app installs one that writes
        crash_log.txt — so a failing observer would put a spurious crash in
        every later problem report.
        """
        seen = []
        previous = threading.excepthook
        threading.excepthook = seen.append
        self.addCleanup(lambda: setattr(threading, "excepthook", previous))
        boom = ShortcutIconFetcher(on_ready=lambda app: 1 / 0)
        self.addCleanup(boom.stop)
        with patch.object(boom, "_resolve", side_effect=lambda *a: MASKS):
            self.assertEqual(settled(boom, "mousepad"), MASKS)
            self.assertEqual(settled(boom, "gedit"), MASKS)
        time.sleep(0.05)
        self.assertEqual([type(e.exc_value).__name__ for e in seen], [])

    def test_stop_is_idempotent_and_blocks_a_restart(self):
        """⚠️ One-way flag under the lock the start path takes, or a window
        switch landing concurrently restarts the thread after shutdown."""
        self.fetcher.overlays_for("mousepad")
        self.fetcher.stop()
        self.fetcher.stop()
        self.fetcher.overlays_for("kate")
        self.assertIsNone(self.fetcher._thread)

    def test_forget_makes_the_next_focus_re_harvest(self):
        calls = []
        with patch.object(self.fetcher, "_resolve",
                          side_effect=lambda a, h, p: calls.append(a) or {}):
            self.fetcher.overlays_for("gedit")
            settled(self.fetcher, "gedit")
            self.fetcher.forget()
            self.fetcher.overlays_for("gedit")
            time.sleep(0.2)
        self.assertEqual(calls, ["gedit", "gedit"])


class RelayedHarvestTest(unittest.TestCase):
    """A forwarded app's shortcuts are harvested on the OTHER machine.

    Only the harvest moves. Which concept a label means, which catalog subset to
    fetch and what height and corner to raster at are all knowable only here,
    so everything after the harvest runs unchanged.
    """

    def setUp(self):
        self.fetcher = ShortcutIconFetcher()
        self.addCleanup(self.fetcher.stop)

    def test_a_RELAYED_harvest_never_touches_the_local_backend(self):
        """⚠️ The whole point. The local backend would walk THIS machine's tree,
        never find the app, and report "exposes no accelerators" — which is
        indistinguishable from an app that genuinely has none. Measured from a
        real log: a Windows daemon reported 0 icons for a gnome-terminal whose
        own machine exposes 16."""
        relayed = [_sc()]
        with patch.object(shortcut_fetcher.shortcut_source, "harvest") as harvest, \
             patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason") as why, \
             patch.object(shortcut_fetcher.shortcut_overlays, "plan_report",
                          return_value=_plan()), \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value={"save": 1}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          return_value="f.ttf"), \
             patch.object(shortcut_fetcher.shortcut_overlays, "render",
                          return_value=MASKS):
            self.assertEqual(settled(self.fetcher, "gnome-terminal",
                                     harvested=relayed), MASKS)
            harvest.assert_not_called()
            # ⚠️ And the availability probe is not consulted either: a keyboard
            # machine with NO backend at all (macOS, or a venv that cannot see
            # PyGObject) must still draw a forwarded app's icons. Gating on it
            # would make the relay useless on exactly the setups that need it.
            why.assert_not_called()

    def test_the_RELAYED_shortcuts_are_what_gets_PLANNED(self):
        relayed = [_sc(), _sc()]
        with patch.object(shortcut_fetcher.shortcut_overlays, "plan_report",
                          return_value=_plan()) as plan, \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value={"save": 1}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          return_value="f.ttf"), \
             patch.object(shortcut_fetcher.shortcut_overlays, "render",
                          return_value=MASKS):
            settled(self.fetcher, "gnome-terminal", harvested=relayed)
        self.assertEqual(plan.call_args.args[0], tuple(relayed))

    def test_an_EMPTY_relayed_harvest_says_WHOSE_answer_it_is(self):
        # A user reading "the app exposes no accelerators" on a forwarded app
        # goes and checks the wrong machine.
        said = []
        self.fetcher._say = lambda app, reason: said.append(reason)
        self.fetcher._harvested["gedit"] = ()
        self.assertEqual(self.fetcher._resolve("gedit", 32, "lower_left"), {})
        self.assertEqual(len(said), 1)
        self.assertIn("forwarder", said[0])

    def test_the_relayed_answer_SURVIVES_forget(self):
        # `forget()` invalidates masks drawn at the old size; it does not
        # invalidate the other machine's answer about its own application, and
        # nothing would ever ask for it again.
        self.fetcher.overlays_for("gnome-terminal", harvested=[_sc()])
        self.fetcher.forget()
        self.assertIn("gnome-terminal", self.fetcher._harvested)


class BackendReasonTest(unittest.TestCase):
    """The log has to say WHICH of the three causes, not a flat platform claim."""

    def test_the_REASON_reaches_the_log_verbatim(self):
        # ⚠️ It used to say "no accessibility backend on this platform" whatever
        # the cause -- true on macOS, and misleading for the commonest case,
        # which is an interpreter that cannot see the system PyGObject. A user
        # reading that line installs a package they already have.
        f = ShortcutIconFetcher()
        said = []
        f._say = lambda app, reason: said.append((app, reason))
        with patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                               return_value="this virtualenv cannot see the "
                                            "system PyGObject"):
            self.assertEqual(f._resolve("gimp", 32, "lower_left"), {})
        self.assertEqual(len(said), 1)
        self.assertIn("virtualenv", said[0][1])

    def test_a_USABLE_backend_gets_past_the_gate(self):
        f = ShortcutIconFetcher()
        said = []
        f._say = lambda app, reason: said.append(reason)
        with patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                               return_value=None), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest", return_value=[]):
            self.assertEqual(f._resolve("gimp", 32, "lower_left"), {})
        # It reached the NEXT refusal, which is a different sentence entirely.
        self.assertEqual(said, ["the app exposes no accelerators"])


class EmptyHarvestReasonTest(unittest.TestCase):
    """What the backend said about an empty harvest, and what is cached.

    ⚠️ *"The app exposes no accelerators"* is true of exactly ONE of the six
    ways the macOS backend returns [], and reads as settled fact for the other
    five. Four macOS apps reported it on a machine where Chrome harvested 65 in
    the same session (field, 2026-09-21).
    """

    def resolve(self, harvested=(), reason=None):
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        said = []
        f._say = lambda app, why: said.append(why)

        def harvest(app, reason=None, pid=None):
            if reason is not None and self._reason:
                reason.update(self._reason)
            return list(harvested)

        self._reason = reason or {}
        with patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest", harvest):
            got = f._resolve("gimp", 32, "lower_left")
        return got, said

    def test_the_BACKENDS_sentence_wins_over_the_generic_one(self):
        got, said = self.resolve(reason={"why": "focus moved to 'Xcode' before "
                                                "the harvest ran", "retry": True})
        self.assertEqual(said, ["focus moved to 'Xcode' before the harvest ran"])
        self.assertIsNone(got)

    def test_a_BACKEND_WITHOUT_a_sentence_keeps_the_generic_one(self):
        """AT-SPI and UIA fill nothing, so their behaviour must not change."""
        got, said = self.resolve()
        self.assertEqual(said, ["the app exposes no accelerators"])
        self.assertEqual(got, {})

    def test_a_DID_NOT_LOOK_answer_is_NOT_CACHEABLE(self):
        """⚠️ None, not {}. `_resolve`'s empty dict IS cached by `_loop`, so a
        harvest that never looked would pin "this app has no shortcuts" for the
        life of the process — the same trap `overlays_for` warns about for the
        relay, one layer down."""
        got, _ = self.resolve(reason={"why": "the AX API failed", "retry": True})
        self.assertIsNone(got)

    def test_a_REAL_empty_menu_IS_cacheable(self):
        """The one correct empty answer. Caching it is the point — without the
        negative cache every window switch re-walks a tree already proven
        empty."""
        got, _ = self.resolve(reason={"why": "not one key equivalent in them",
                                      "retry": False})
        self.assertEqual(got, {})


class PidPassThroughTest(unittest.TestCase):
    """⚠️ The pid must reach the backend, or macOS harvests the wrong app.

    Without it the macOS backend falls back to `NSWorkspace.frontmostApplication`,
    which is frozen on this fetcher's worker thread — measured in the field as
    every app but one reporting a focus race that had not happened.
    """

    def resolve(self, pid=None):
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        f._say = lambda *a: None
        seen = {}

        def harvest(app, reason=None, pid=None):
            seen["pid"] = pid
            return []

        if pid is not None:
            f.overlays_for("gimp", pid=pid)
        with patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest", harvest):
            f._resolve("gimp", 32, "lower_left")
        return seen

    def test_the_pid_reaches_the_backend(self):
        self.assertEqual(self.resolve(pid=4242)["pid"], 4242)

    def test_NO_pid_is_still_None_not_an_error(self):
        """A forwarded window and the headless paths have no pid; the backend
        falls back to frontmost, which is correct off the worker thread."""
        self.assertIsNone(self.resolve()["pid"])

    def test_the_pid_is_NOT_part_of_the_cache_key(self):
        """⚠️ The same app restarted under a new pid exposes the same
        shortcuts, so keying on it would re-harvest every app on every restart
        and never hit the cache."""
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        # ⚠️ No worker, or it drains the queue between the two calls and the
        # comparison reads whatever the thread left behind.
        f._ensure_thread = lambda: None
        f.overlays_for("gimp", pid=1)
        first = list(f._queue)
        self.assertEqual(len(first), 1, first)
        f.overlays_for("gimp", pid=999)
        self.assertEqual(list(f._queue), first)
        self.assertEqual(f._pids["gimp"], 999)   # the newest pid still wins


class LoopCacheTest(unittest.TestCase):
    """⚠️ `_loop` decides what is remembered, and the two answers look alike."""

    def _one_pass(self, f, answer):
        """Run `_loop` for exactly one queued item.

        ⚠️ Setting `_stop` BEFORE the call runs zero passes, not one -- the
        `while` tests it first -- so the flag is set from inside `_resolve`,
        after the body has done its work.
        """
        def resolve(*_a, **_k):
            f._stop.set()
            return answer

        f._resolve = resolve
        f._loop()

    def run_once(self, answer):
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        key = "gimp\x0032\x00lower_left"
        with f._lock:
            f._queue.append(key)
        self._one_pass(f, answer)
        return f._overlays, key

    def test_an_EMPTY_result_IS_remembered(self):
        overlays, key = self.run_once({})
        self.assertIn(key, overlays)

    def test_a_DID_NOT_LOOK_result_is_NOT_remembered(self):
        """So the next focus re-harvests instead of reading back a non-answer."""
        overlays, key = self.run_once(None)
        self.assertNotIn(key, overlays)

    def test_a_DID_NOT_LOOK_result_still_clears_INFLIGHT(self):
        """Or the app is wedged: `overlays_for` refuses to re-queue a key it
        believes is already being worked on, so it would never ask again."""
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        key = "gimp\x0032\x00lower_left"
        with f._lock:
            f._queue.append(key)
        self._one_pass(f, None)
        self.assertEqual(f._inflight, set())

    def test_a_DID_NOT_LOOK_result_does_not_fire_the_READY_callback(self):
        ready = []
        f = ShortcutIconFetcher(on_ready=ready.append)
        self.addCleanup(f.stop)
        with f._lock:
            f._queue.append("gimp\x0032\x00lower_left")
        self._one_pass(f, None)
        self.assertEqual(ready, [])


class ResolveTest(unittest.TestCase):
    """`_resolve` is the slow half; every failure in it must cost {} and a line."""

    def setUp(self):
        self.fetcher = ShortcutIconFetcher()
        self.addCleanup(self.fetcher.stop)

    def test_no_backend_is_reported_as_such(self):
        with patch.object(shortcut_fetcher.shortcut_source, "pick", return_value=None):
            self.assertEqual(self.fetcher._resolve("mousepad", 32, "lower_left"), {})

    def test_a_render_that_raises_costs_nothing(self):
        with patch.object(shortcut_fetcher.shortcut_source, "pick", return_value=object()), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest",
                          return_value=[object()]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "plan",
                          return_value=["slot"]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "icon_names",
                          return_value=["save"]), \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value={"save": 1}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          return_value="f.ttf"), \
             patch.object(shortcut_fetcher.shortcut_overlays, "render",
                          side_effect=OSError("boom")):
            self.assertEqual(self.fetcher._resolve("mousepad", 32, "lower_left"), {})

    def test_an_unreachable_subset_costs_nothing(self):
        with patch.object(shortcut_fetcher.shortcut_source, "pick", return_value=object()), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest",
                          return_value=[object()]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "plan",
                          return_value=["slot"]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "icon_names",
                          return_value=["save"]), \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value={"save": 1}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          return_value=None), \
             patch.object(shortcut_fetcher.shortcut_overlays, "render") as render:
            self.assertEqual(self.fetcher._resolve("mousepad", 32, "lower_left"), {})
            # ⚠️ Asserting the RETURN alone is not enough: the real renderer
            # swallows a None font path and answers {} of its own accord, so the
            # guard could be deleted and this would still pass. What must hold is
            # that nothing is asked to draw from a font that does not exist.
            render.assert_not_called()


class TheSubsetRequestIsStableAcrossApps(unittest.TestCase):
    """⚠️ `icon_catalog.subset_path` keys its cache on the SET of names asked
    for, so asking for only the names one app needs is a new cache file and a
    fresh HTTPS round-trip on first sight of every application, for the life of
    the machine. `_resolve` therefore asks for the whole lexicon as well."""

    def setUp(self):
        self.fetcher = shortcut_fetcher.ShortcutIconFetcher(cache_dir="/tmp")

    def _asked(self, icon):
        from polyhost.services.shortcut_overlays import Plan, Slot
        plan = Plan([Slot(modifier=1, keycode=0x16, concept="save", icon=icon,
                          label="Save", confidence=1.0)], {})
        seen = []
        with patch.object(shortcut_fetcher.shortcut_overlays, "plan_report",
                          return_value=plan), \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value={"save": 1}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          side_effect=lambda names, *a, **kw:
                              (seen.append((kw.get("face"), tuple(names))), "f.ttf")[1]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "render",
                          return_value=MASKS):
            self.fetcher._harvested["app"] = (_sc(),)
            self.fetcher._resolve("app", 32, "lower_left")
        return dict(seen)

    def test_two_apps_with_DIFFERENT_lexicon_icons_ask_for_the_same_names(self):
        from polyhost.services import shortcut_overlays as so
        material = so.lexicon_names_by_face()["material"]
        one = self._asked("material:" + material[0])
        two = self._asked("material:" + material[-1])
        self.assertEqual(one["material"], two["material"])
        self.assertEqual(set(one["material"]), set(material))

    def test_a_name_OUTSIDE_the_lexicon_is_still_requested(self):
        """The floor must not swallow a derived name, or its icon never draws."""
        asked = self._asked("material:rocket_launch")
        self.assertIn("rocket_launch", asked["material"])

class UnreachableFontReasonTest(unittest.TestCase):
    """⚠️ "the <face> icons are neither cached nor reachable" is FOUR causes.

    A refused download, an unwritable cache, a proxy page served with a 200 and
    a stylesheet carrying no font url all produced that one sentence, and they
    need four different remedies. Nothing below INFO said anything at all.
    Measured on macOS 2026-09-21: 65 shortcuts harvested, 20 matched a concept,
    and NOTHING was drawn because both faces failed — with the log unable to
    narrow it.
    """

    def _said(self, font=None, table=None, reason=None):
        f = ShortcutIconFetcher()
        self.addCleanup(f.stop)
        said = []
        f._say = lambda app, why: said.append(why)

        def fake_fetch(names, cache_dir, face=None, reasons=None, **kw):
            if reason is not None and reasons is not None:
                reasons[face] = reason
            return font

        report = types.SimpleNamespace(slots=["slot"])
        f._report = lambda *a, **k: None
        with patch.object(shortcut_fetcher.shortcut_source, "pick",
                          return_value=object()), \
             patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_fetcher.shortcut_source, "harvest",
                          return_value=[object()]), \
             patch.object(shortcut_fetcher.shortcut_overlays, "plan_report",
                          return_value=report), \
             patch.object(shortcut_fetcher.shortcut_overlays, "icon_names_by_face",
                          return_value={"material": ["save"]}), \
             patch.object(shortcut_fetcher.icon_catalog, "fetch_subset",
                          side_effect=fake_fetch), \
             patch.object(shortcut_fetcher.icon_catalog, "load_codepoints",
                          return_value=table):
            f._resolve("gimp", 32, "lower_left")
        return said

    def test_the_REASON_reaches_the_line(self):
        said = [w for w in self._said(reason="download failed: proxy refused")
                if "neither cached" in w]
        self.assertTrue(said, "no unreachable-font line at all")
        self.assertIn("proxy refused", said[0])

    def test_it_names_WHICH_HALF_is_missing(self):
        """The font and the codepoint table are separate fetches from separate
        URLs, so "neither cached nor reachable" was ambiguous even before the
        reason: either one alone produces it."""
        said = [w for w in self._said(font=None, table={"save": 1})
                if "neither cached" in w]
        self.assertTrue(said)
        self.assertIn("the font is missing", said[0])

    def test_a_missing_TABLE_is_named_as_the_TABLE(self):
        said = [w for w in self._said(font="/tmp/f.ttf", table={})
                if "neither cached" in w]
        self.assertTrue(said)
        self.assertIn("the codepoint table is missing", said[0])

    def test_NO_reason_still_produces_a_usable_line(self):
        """`reasons` is best effort — an empty one must not append "()"."""
        said = [w for w in self._said(reason=None) if "neither cached" in w]
        self.assertTrue(said)
        self.assertNotIn("()", said[0])


if __name__ == "__main__":
    unittest.main()
