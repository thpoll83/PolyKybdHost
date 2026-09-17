"""The app-icon fetch queue: offline, deterministic, no network.

What these pin is the QUEUE's behaviour, not the catalog's — `app_icons` has its
own suite. The two properties that matter both cost something real when they
break: a duplicate fetch re-sends every overlay a second time, and a lookup that
touches the network on the caller's thread freezes the tray.
"""
import threading
import time
import unittest
import unittest.mock as mock

from polyhost.services import app_icon_fetcher, app_icons, os_app_icon
from polyhost.services.app_icon_fetcher import AppIconFetcher


def _wait(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class FetcherTest(unittest.TestCase):

    def setUp(self):
        self.ready = []
        self.resolved_on = []          # thread names `program_overlay` ran on
        self.identities_for = []       # every app_identity() call
        self.gate = threading.Event()
        self.gate.set()
        self.marks = {"gimp": ("MASK", "si:gimp")}

        def fake_program_overlay(app_name, identity=None, cache_dir=None,
                                 allow_network=None):
            self.gate.wait(5)
            self.resolved_on.append(threading.current_thread().name)
            return self.marks.get(app_name, (None, None))

        def fake_identity(pid, app_name=""):
            self.identities_for.append((pid, app_name))
            return os_app_icon.AppIdentity(icon=None, icon_path="", names=())

        for target, fn in (("polyhost.services.app_icons.program_overlay", fake_program_overlay),
                           ("polyhost.services.os_app_icon.app_identity", fake_identity),
                           ("polyhost.services.app_icons.auto_fetch_enabled", lambda: True)):
            patcher = mock.patch(target, fn)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.fetcher = AppIconFetcher(on_ready=self.ready.append)
        self.addCleanup(self.fetcher.stop)

    def test_a_mark_is_resolved_once_and_reported_once(self):
        # ⚠️ THE REGRESSION THIS EXISTS FOR: an app is neither queued nor cached
        # while it is in flight, so the poll loop re-queued it every tick — two
        # resolutions and two `on_ready`s, the second of which re-sends every
        # overlay for nothing. Measured on the first cut, not imagined.
        self.gate.clear()
        for _ in range(20):
            self.assertEqual(self.fetcher.overlay_for("gimp"), (None, None))
        self.gate.set()
        self.assertTrue(_wait(lambda: self.ready))
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.assertEqual(len(self.resolved_on), 1)
        self.assertEqual(self.ready, ["si:gimp"])

    def test_the_lookup_NEVER_runs_on_the_caller_thread(self):
        # The whole reason the class exists: `program_overlay` can be an HTTP GET
        # at a 15 s timeout, and the two threads that would otherwise call it —
        # the HID worker and the GUI main thread — are both forbidden.
        caller = threading.current_thread().name
        self.fetcher.overlay_for("gimp")
        self.assertTrue(_wait(lambda: self.resolved_on))
        self.assertNotIn(caller, self.resolved_on)

    def test_overlay_for_does_NO_identity_lookup_ITSELF(self):
        # ⚠️ New in E2/E3 and the reason the cache key changed: resolving an app
        # now starts with `app_identity()`, which opens a file and on Windows
        # opens the process. That must not happen on the window tick, so the
        # first call cannot know a candidate name and returns None for it.
        self.gate.clear()
        self.assertEqual(self.fetcher.overlay_for("gimp", pid=42), (None, None))
        self.assertEqual(self.identities_for, [])
        self.gate.set()
        self.assertTrue(_wait(lambda: self.identities_for == [(42, "gimp")]))

    def test_the_identity_is_resolved_exactly_ONCE_per_app(self):
        # E1's contract: the icon and the display names come from one lookup, so
        # the mark and the caption cannot describe two different applications.
        for _ in range(5):
            self.fetcher.overlay_for("gimp", pid=7)
        self.assertTrue(_wait(lambda: self.resolved_on))
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))
        self.assertEqual(self.identities_for, [(7, "gimp")])

    def test_a_MISS_is_cached_so_it_costs_one_resolution_not_one_per_tick(self):
        self.fetcher.overlay_for("nosuchapp")
        self.assertTrue(_wait(lambda: self.resolved_on))
        for _ in range(10):
            self.assertEqual(self.fetcher.overlay_for("nosuchapp"), (None, None))
        # ⚠️ SETTLE before counting. A re-queued lookup runs on the fetch thread,
        # so asserting straight after the loop reads the count before the thread
        # has got to any of them — the assertion passes for an uncached miss and
        # the test proves nothing. Found by a mutation that deleted the caching
        # and escaped.
        time.sleep(0.2)
        self.assertEqual(len(self.resolved_on), 1)
        self.assertEqual(self.ready, [])        # a miss never calls back

    def test_forget_misses_retries_but_keeps_the_HITS(self):
        # ⚠️ Without it, turning `shortcut_icon_auto_fetch` back ON does nothing
        # until a restart: every app focused while it was off is cached as a
        # miss, and that cache is what stops the lookup.
        self.fetcher.overlay_for("nosuchapp")
        self.fetcher.overlay_for("gimp")
        self.assertTrue(_wait(lambda: len(self.resolved_on) == 2))
        self.assertTrue(_wait(lambda: self.fetcher.overlay_for("gimp")[0] == "MASK"))

        self.fetcher.forget_misses()
        self.assertEqual(self.fetcher.overlay_for("gimp")[0], "MASK")   # still cached
        self.fetcher.overlay_for("nosuchapp")                           # re-queued
        self.assertTrue(_wait(lambda: len(self.resolved_on) == 3))

    def test_an_empty_app_name_is_not_queued_at_all(self):
        self.assertEqual(self.fetcher.overlay_for(""), (None, None))
        self.assertEqual(self.fetcher.overlay_for(None), (None, None))
        time.sleep(0.05)
        self.assertEqual(self.resolved_on, [])

    def test_a_RAISING_callback_never_reaches_THREADING_EXCEPTHOOK(self):
        # ⚠️ Assert the HOOK, not that the mask still arrives. The mask is stored
        # before the callback fires, so it arrives either way — a mutation that
        # narrowed the `except` to a type that cannot match escaped a test
        # written that way. What the guard buys is that this app's excepthook,
        # which writes crash_log.txt, does not record a spurious crash in every
        # later problem report.
        escaped = []
        with mock.patch("threading.excepthook", escaped.append):
            boom = AppIconFetcher(on_ready=mock.Mock(side_effect=RuntimeError("no")))
            self.addCleanup(boom.stop)
            boom.overlay_for("gimp")
            self.assertTrue(_wait(lambda: boom.overlay_for("gimp")[0] == "MASK"))
            time.sleep(0.1)         # give a dying thread time to report itself
        self.assertEqual(escaped, [])

    def test_stop_is_idempotent_and_never_restarts_the_thread(self):
        # ⚠️ A window switch landing here concurrently with shutdown would
        # otherwise restart the thread after stop() returned.
        self.fetcher.overlay_for("gimp")
        self.assertTrue(_wait(lambda: self.resolved_on))
        self.fetcher.stop()
        self.fetcher.stop()
        self.fetcher.overlay_for("brandnew")
        time.sleep(0.05)
        self.assertEqual(len(self.resolved_on), 1)


class MissReasonTest(unittest.TestCase):
    """Why a miss missed — the line a user reads when no icon appears."""

    def _fetcher(self):
        f = AppIconFetcher()
        self.addCleanup(f.stop)
        return f

    def test_an_OS_icon_that_failed_the_gate_says_SO(self):
        # ⚠️ Distinct from "no catalog carries it": the app HAD an icon and it
        # did not survive 1-bit, which sends the next round at the binariser
        # rather than at the catalog.
        identity = os_app_icon.AppIdentity(icon=b"PNG", icon_path="/x.png", names=())
        why = self._fetcher()._why_missed("gimp", identity, "si:gimp")
        self.assertIn("does not survive", why)

    def test_auto_fetch_OFF_is_reported_as_a_refusal_to_ASK(self):
        # Saying "no catalog carries si:notepad" on a machine that never sent the
        # request is a claim the code cannot support.
        identity = os_app_icon.AppIdentity(icon=None, icon_path="", names=())
        with mock.patch("polyhost.services.app_icons.auto_fetch_enabled", lambda: False):
            why = self._fetcher()._why_missed("notepad", identity, "si:notepad")
        self.assertIn("auto-fetch is off", why)

    def test_an_unnameable_app_is_reported_as_such(self):
        identity = os_app_icon.AppIdentity(icon=None, icon_path="", names=())
        why = self._fetcher()._why_missed("", identity, None)
        self.assertIn("no catalog name", why)

    def test_a_plain_catalog_miss_NAMES_what_was_tried(self):
        identity = os_app_icon.AppIdentity(icon=None, icon_path="", names=())
        with mock.patch("polyhost.services.app_icons.auto_fetch_enabled", lambda: True):
            why = self._fetcher()._why_missed("winword", identity, "si:winword")
        self.assertIn("si:winword", why)
        self.assertIn("mdi:microsoft-winword", why)



class ForwardedIdentityShapeTest(unittest.TestCase):
    """A forwarded identity is a DICT, and every consumer reads an AppIdentity.

    ⚠️ The regression, measured on a live pair 2026-09-17: the forwarder
    resolved GNOME Text Editor correctly and sent names + icon, and the daemon
    logged `No program mark for gnome-text-edit ... (OS names: <none>)`.
    `program_overlay` reads `getattr(identity, "names", ())`, a dict answers
    neither attribute, and getattr hands back the default -- so the whole
    identity was discarded in silence. The transport, the cache and the key
    were all working. gnome-terminal and the log window kept drawing because
    they hit the CATALOG on their app name and need no identity at all.
    """

    ICON = b"\x89PNG\r\n\x1a\n" + b"x" * 64

    def test_a_dict_becomes_an_AppIdentity(self):
        ident = app_icon_fetcher._as_identity(
            {"names": ("Text Editor",), "icon": self.ICON, "icon_key": "k1"},
            "gnome-text-edit")
        self.assertEqual(ident.names, ("Text Editor",))
        self.assertEqual(ident.icon, self.ICON)

    def test_an_AppIdentity_passes_through_and_None_stays_None(self):
        from polyhost.services.os_app_icon import AppIdentity
        native = AppIdentity(icon=None, icon_path="/x.png", names=("A",))
        self.assertIs(app_icon_fetcher._as_identity(native), native)
        self.assertIsNone(app_icon_fetcher._as_identity(None))

    def test_anything_else_RAISES_rather_than_degrading(self):
        # A silent getattr miss is what cost the round this test exists for.
        with self.assertRaises(TypeError):
            app_icon_fetcher._as_identity(("Text Editor",), "x")

    def test_program_overlay_REFUSES_a_raw_dict(self):
        # The guard that stops a second caller re-introducing the silence.
        with self.assertRaises(TypeError):
            app_icons.program_overlay(
                "gnome-text-edit", {"names": ("Text Editor",)},
                allow_network=False)

    def test_two_forwarded_apps_get_DIFFERENT_mark_slugs(self):
        # ⚠️ The second defect, found while fixing the first. The real
        # `icon_path` is on the other machine, and `program_overlay` names the
        # mark `"os:" + basename(icon_path)` -- so an empty path made every
        # forwarded app share the slug `"os:"`, and the tick skips a slug
        # already on the device. Switching from VS Code to Text Editor would
        # have left VS Code's mark up.
        first = app_icon_fetcher._as_identity(
            {"icon": self.ICON, "icon_key": "aaaaaaaaaaaa"}, "code")
        second = app_icon_fetcher._as_identity(
            {"icon": self.ICON, "icon_key": "bbbbbbbbbbbb"}, "gnome-text-edit")
        self.assertNotEqual(first.icon_path, second.icon_path)
        self.assertIn("code", first.icon_path)

    def test_the_slug_CHANGES_when_the_icon_does(self):
        # The key is a content hash, so a theme change re-draws rather than
        # being deduped away as "already on the device".
        same_app = [app_icon_fetcher._as_identity(
            {"icon": self.ICON, "icon_key": k}, "code")
            for k in ("aaaaaaaaaaaa", "bbbbbbbbbbbb")]
        self.assertNotEqual(same_app[0].icon_path, same_app[1].icon_path)

    def test_a_real_path_is_kept_when_there_is_one(self):
        ident = app_icon_fetcher._as_identity(
            {"icon": self.ICON, "icon_path": "/usr/share/icons/x.png",
             "icon_key": "k"}, "x")
        self.assertEqual(ident.icon_path, "/usr/share/icons/x.png")

if __name__ == "__main__":
    unittest.main()
