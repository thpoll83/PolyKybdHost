"""The harvest queue: never block the caller, never re-walk a proven-empty app.

The properties worth pinning are the ones whose failure only shows up under a
real workload — a lookup that blocks the window tick, a duplicate harvest per
poll, a negative result that is not cached — so every test drives the real
queue with the slow half stubbed out.
"""

import threading
import time
import unittest
from unittest import mock
from unittest.mock import patch

from polyhost.services import shortcut_fetcher
from polyhost.services.shortcut_fetcher import ShortcutIconFetcher

MASKS = {"@sc:save:32lower_left": {(1, 0x16): "MASK"}}


def settled(fetcher, app, timeout=2.0):
    """Poll `overlays_for` until the thread has answered, or give up."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        out = fetcher.overlays_for(app)
        if out:
            return out
        with fetcher._lock:
            done = any(k.startswith(app + "\x00") for k in fetcher._overlays)
        if done:
            return out
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
        with mock.patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                               return_value="this virtualenv cannot see the "
                                            "system PyGObject"):
            self.assertEqual(f._resolve("gimp", 32, "lower_left"), {})
        self.assertEqual(len(said), 1)
        self.assertIn("virtualenv", said[0][1])

    def test_a_USABLE_backend_gets_past_the_gate(self):
        f = ShortcutIconFetcher()
        said = []
        f._say = lambda app, reason: said.append(reason)
        with mock.patch.object(shortcut_fetcher.shortcut_source, "unavailable_reason",
                               return_value=None), \
             mock.patch.object(shortcut_fetcher.shortcut_source, "harvest", return_value=[]):
            self.assertEqual(f._resolve("gimp", 32, "lower_left"), {})
        # It reached the NEXT refusal, which is a different sentence entirely.
        self.assertEqual(said, ["the app exposes no accelerators"])


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


if __name__ == "__main__":
    unittest.main()
