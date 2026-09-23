"""The cross-machine shortcut wire format.

Two properties matter, and they pull in opposite directions: the frame has to
carry EVERYTHING the host-side planner reads (or the relay silently degrades an
app to no icons), and `decode` has to survive anything at all (or a cosmetic
field takes the window report down with it on the one endpoint reachable over
the network).
"""

import logging
import threading
import unittest
from unittest.mock import Mock, patch

from polyhost.services import shortcut_overlays, shortcut_relay
from polyhost.services.shortcut_source.model import Shortcut


def sc(label="Save", mods=1, hid=0x16, **kw):
    return Shortcut(label=label, role=kw.get("role", "menu item"),
                    accel=kw.get("accel", "<Control>s"), mods=mods,
                    keysym=kw.get("keysym", "s"), hid=hid,
                    displayable=True)


class WhatTheWireCarriesTest(unittest.TestCase):

    def test_the_THREE_fields_are_the_planner_s_WHOLE_input(self):
        """⚠️ The real contract, and the reason the frame carries no pixels: if
        `plan_report` ever reads a fourth field off a shortcut, a relayed app
        starts planning against a default and the failure is a WRONG icon, not
        a missing one. Driving the real planner is what would catch that -- an
        assertion listing the three field names would not."""
        planned = shortcut_overlays.plan(shortcut_relay.decode(
            shortcut_relay.encode([sc(label="Save", mods=1, hid=0x16)])))
        self.assertEqual([(s.modifier, s.keycode, s.concept) for s in planned],
                         [(1, 0x16, "save")])

    def test_a_round_trip_preserves_the_chord_and_the_label(self):
        out = shortcut_relay.decode(shortcut_relay.encode([sc(label="Copy",
                                                             mods=1, hid=0x06)]))
        self.assertEqual(shortcut_overlays.describe(out[0]), "Ctrl+C 'Copy'")

    def test_it_is_JSON_SAFE(self):
        """The frame is JSON, so a dataclass or a tuple would not survive it."""
        import json
        wire = shortcut_relay.encode([sc()])
        self.assertEqual(json.loads(json.dumps(wire)), wire)

    def test_the_backend_s_RAW_STRINGS_do_not_travel(self):
        # `accel`/`keysym`/`role` are consumed before the wire and never read
        # again. Not carrying them is deliberate: they are the largest fields
        # and the only free-text ones the receiver has no use for.
        flat = str(shortcut_relay.encode([sc(accel="<Control>s", keysym="s",
                                             role="menu item")]))
        self.assertNotIn("Control", flat)
        self.assertNotIn("menu item", flat)


class EncodeDropsWhatCannotBeUsedTest(unittest.TestCase):

    def test_a_key_with_NO_KEYCAP_is_not_carried(self):
        # A keypad or media key has no overlay slot, so the receiver would
        # refuse it anyway — the frame should not pay to carry it.
        self.assertEqual(shortcut_relay.encode([sc(hid=0x01)]), [])

    def test_an_EMPTY_label_is_not_carried(self):
        self.assertEqual(shortcut_relay.encode([sc(label="   ")]), [])

    def test_a_modifier_outside_the_NIBBLE_is_not_carried(self):
        self.assertEqual(shortcut_relay.encode([sc(mods=0x99)]), [])

    def test_NO_modifier_IS_carried(self):
        # F5 or Delete is a real accelerator whose overlay is simply always on
        # screen — the same rule `plan_report` follows.
        self.assertEqual(shortcut_relay.encode([sc(label="Refresh", mods=0,
                                                   hid=0x3E)]),
                         [[0, 0x3E, "Refresh"]])

    def test_it_is_BOUNDED(self):
        self.assertEqual(len(shortcut_relay.encode([sc()] * 500)),
                         shortcut_relay.MAX_SHORTCUTS)

    def test_a_long_LABEL_is_clamped_not_dropped(self):
        long = "x" * 500
        self.assertEqual(len(shortcut_relay.encode([sc(label=long)])[0][2]),
                         shortcut_relay.MAX_LABEL)

    def test_junk_in_a_field_costs_that_ENTRY_and_no_more(self):
        good = sc(label="Save")
        self.assertEqual(shortcut_relay.encode([sc(hid=None), good]),
                         [[1, 0x16, "Save"]])


class DecodeIsTOTALTest(unittest.TestCase):
    """⚠️ The property: nothing here may fail a window report.

    Shortcuts ride the MAIN report frame, unlike the icon, which travels in a
    follow-up the forwarder already guards. A raise here would mean the keyboard
    stops tracking windows because a keycap decoration was malformed — so every
    one of these must be an empty/short answer, never an exception.
    """

    def test_a_non_LIST_is_empty_not_an_error(self):
        for junk in ("shortcuts", 7, None, {"a": 1}, object()):
            with self.subTest(junk=junk):
                self.assertEqual(shortcut_relay.decode(junk), ())

    def test_a_malformed_ENTRY_is_skipped_and_the_rest_survive(self):
        out = shortcut_relay.decode([[1, 0x16], "nope", None, {}, [1, 0x06, "Copy"]])
        self.assertEqual([s.label for s in out], ["Copy"])

    def test_a_non_NUMERIC_chord_is_skipped(self):
        self.assertEqual(shortcut_relay.decode([["ctrl", "s", "Save"]]), ())

    def test_an_out_of_range_chord_is_skipped(self):
        self.assertEqual(shortcut_relay.decode([[99, 0x16, "Save"],
                                                [1, 0x01, "Save"]]), ())

    def test_an_oversize_LIST_is_clamped(self):
        self.assertEqual(len(shortcut_relay.decode([[1, 0x16, "Save"]] * 5000)),
                         shortcut_relay.MAX_SHORTCUTS)

    def test_an_oversize_LABEL_is_clamped(self):
        out = shortcut_relay.decode([[1, 0x16, "y" * 100000]])
        self.assertEqual(len(out[0].label), shortcut_relay.MAX_LABEL)

    def test_a_WHITESPACE_label_is_skipped_not_kept_blank(self):
        # `plan_report` has no empty-label guard (match() refuses "" itself), so
        # a blank one would reach the lexicon and be refused there — one wasted
        # slot decision per report rather than none.
        self.assertEqual(shortcut_relay.decode([[1, 0x16, "  \t "]]), ())

    def test_EXTRA_trailing_fields_are_tolerated(self):
        # A newer forwarder may append a field; an older receiver must read the
        # three it knows rather than refusing the entry.
        out = shortcut_relay.decode([[1, 0x16, "Save", "something-new"]])
        self.assertEqual((out[0].mods, out[0].hid, out[0].label), (1, 0x16, "Save"))


class RelaySourceTest(unittest.TestCase):
    """The FORWARDER's side, which `forwarder.py` itself cannot test.

    That module imports pywinctl at load time, so a test of it is permanently
    skipped in the documented environment — which reads as coverage. The parts
    that matter therefore live in `RelaySource`: the three-state answer, the
    in-flight guard, and the privacy gate.
    """

    def _source(self, shortcuts=(), reason=None, allowed=None, on_ready=None):
        self.harvested = []
        self.spawned = []
        return shortcut_relay.RelaySource(
            logging.getLogger("test.relaysource"),
            harvest=lambda app: (self.harvested.append(app), shortcuts)[1],
            reason=lambda: reason, allowed=allowed, on_ready=on_ready,
            spawn=lambda fn, name: self.spawned.append(fn))

    def test_the_FIRST_ask_never_blocks_and_answers_NONE(self):
        """⚠️ The reason this is a queue at all: the caller is the window poll,
        and the work behind it is a tree walk charging a D-Bus round trip per
        node. A synchronous answer stalls every focus change by seconds."""
        src = self._source(shortcuts=[sc()])
        self.assertIsNone(src.shortcuts_for("gimp"))
        self.assertEqual(self.harvested, [])            # nothing ran inline
        self.assertEqual(len(self.spawned), 1)

    def test_the_answer_arrives_ENCODED(self):
        src = self._source(shortcuts=[sc(label="Save")])
        src.shortcuts_for("gimp")
        self.spawned[0]()
        self.assertEqual(src.shortcuts_for("gimp"), [[1, 0x16, "Save"]])

    def test_an_EMPTY_harvest_is_an_ANSWER_not_a_retry(self):
        # ⚠️ The distinction the whole relay rests on: `[]` stops the receiver
        # asking, None keeps it asking. Most applications expose nothing, so
        # this is the common case, not an edge one.
        src = self._source(shortcuts=[])
        src.shortcuts_for("gedit")
        self.spawned[0]()
        self.assertEqual(src.shortcuts_for("gedit"), [])

    def test_an_app_is_harvested_ONCE_not_once_per_report(self):
        # The receiver asks on every report until it has an answer, so without
        # the in-flight guard a 15 s harvest starts dozens of tree walks.
        src = self._source(shortcuts=[sc()])
        for _ in range(20):
            src.shortcuts_for("gimp")
        self.assertEqual(len(self.spawned), 1)

    def test_a_RAISING_harvest_costs_an_empty_answer_and_nothing_else(self):
        src = shortcut_relay.RelaySource(
            logging.getLogger("test.relaysource"),
            harvest=lambda app: 1 / 0, reason=lambda: None,
            allowed=lambda: True,
            spawn=lambda fn, name: self.__dict__.setdefault("fn", fn))
        src.shortcuts_for("gimp")
        self.fn()
        # Answered, so the receiver stops asking rather than re-triggering a
        # harvest that raises on every single report.
        self.assertEqual(src.shortcuts_for("gimp"), [])

    def test_NO_BACKEND_answers_empty_rather_than_retrying_forever(self):
        src = self._source(reason="this virtualenv cannot see PyGObject")
        src.shortcuts_for("gimp")
        self.spawned[0]()
        self.assertEqual(src.shortcuts_for("gimp"), [])
        self.assertEqual(self.harvested, [])

    def test_the_SETTING_being_off_reads_no_tree_at_all(self):
        # Off on either machine means no application's accessibility tree is
        # touched anywhere. The receiver gates its ASK on its own copy; this is
        # the other half, on the machine where the reading would happen.
        src = self._source(shortcuts=[sc()], allowed=lambda: False)
        self.assertEqual(src.shortcuts_for("gimp"), [])
        self.assertEqual(self.spawned, [])

    def test_a_READY_callback_fires_only_when_there_is_something_to_send(self):
        # It nudges the heartbeat so the answer goes out now instead of up to
        # 15 s later; firing on an empty harvest would buy a report that says
        # nothing.
        ready = []
        src = self._source(shortcuts=[], on_ready=ready.append)
        src.shortcuts_for("gedit")
        self.spawned[0]()
        self.assertEqual(ready, [])
        src = self._source(shortcuts=[sc()], on_ready=ready.append)
        src.shortcuts_for("gimp")
        self.spawned[0]()
        self.assertEqual(ready, ["gimp"])

    def test_a_RAISING_ready_callback_never_reaches_the_EXCEPTHOOK(self):
        # An escape reaches threading.excepthook, which this app routes into
        # crash_log.txt — so a failing observer would put a spurious crash in
        # every later problem report.
        src = self._source(shortcuts=[sc()], on_ready=lambda app: 1 / 0)
        src.shortcuts_for("gimp")
        self.spawned[0]()                     # must not raise
        self.assertEqual(src.shortcuts_for("gimp"), [[1, 0x16, "Save"]])

    def test_an_EMPTY_name_is_not_harvested(self):
        src = self._source(shortcuts=[sc()])
        self.assertIsNone(src.shortcuts_for(""))
        self.assertEqual(self.spawned, [])


class ForwarderWiringTest(unittest.TestCase):
    """`forwarder.py` cannot be imported here, so pin what it must call."""

    def test_the_forwarder_calls_RelaySource_the_way_it_is_defined(self):
        import inspect
        inspect.signature(shortcut_relay.RelaySource.__init__).bind(
            None, logging.getLogger("x"), on_ready=lambda name: None)
        inspect.signature(shortcut_relay.RelaySource.shortcuts_for).bind(
            None, "gimp")

class DisabledHarvestIsNotCachedTest(unittest.TestCase):
    """⚠️ The SWITCH is read before the CACHE.

    It used to be the other way round, with the disabled answer written into
    the cache as `[]`. Turning `shortcut_icons_enabled` back on then did nothing
    for every app visited while it was off: the cache answered first, and
    nothing on the FORWARDER clears it — the settings hook that would is on the
    host, a different machine. It took a restart (Greptile, #240)."""

    def _source(self, allowed):
        return shortcut_relay.RelaySource(
            logging.getLogger("test.relay"),
            allowed=lambda: allowed[0],
            spawn=lambda fn, name: None)          # never harvest in a test

    def test_re_enabling_MID_SESSION_takes_effect(self):
        allowed = [False]
        src = self._source(allowed)
        self.assertEqual(src.shortcuts_for("gimp"), [])   # visited while off
        allowed[0] = True
        # On again: the answer must become "not yet" (a harvest is due), never
        # the [] cached while it was off.
        self.assertIsNone(src.shortcuts_for("gimp"))

    def test_a_disabled_answer_is_NOT_written_to_the_cache(self):
        allowed = [False]
        src = self._source(allowed)
        src.shortcuts_for("gimp")
        self.assertEqual(dict(src._cache), {})

    def test_a_REAL_answer_is_still_cached(self):
        """The control: without it the two above pass for a source that caches
        nothing at all, which would re-harvest on every window report."""
        allowed = [True]
        src = self._source(allowed)
        src._cache["gimp"] = [[1, 22, "Save"]]
        self.assertEqual(src.shortcuts_for("gimp"), [[1, 22, "Save"]])


class RelayThreadReleaseTest(unittest.TestCase):
    """⚠️ Each relay harvest runs on its own thread, and on Windows the backend
    builds COM state there. The thread must release it before it ends, as the
    keyboard-side fetcher does (CodeRabbit, #264)."""

    def _run_on_default_thread(self, source):
        """Run one harvest and JOIN its thread before returning.

        ⚠️ `_run` fills the cache BEFORE it releases the backend, so waiting
        for the cached answer let the test leave its `patch` block while the
        worker was still about to call `release_thread` -- a race that
        passes almost always and fails for no visible reason (CodeRabbit,
        #264). Joining the thread keeps the patches in force to the end."""
        threads = []

        def spawn(fn, name):
            # Same shape as RelaySource._thread, but keeps the handle.
            t = threading.Thread(target=fn, name=name, daemon=True)
            threads.append(t)
            t.start()

        source._spawn = spawn
        self.assertIsNone(source.shortcuts_for("gedit"))
        self.assertEqual(len(threads), 1)
        threads[0].join(3)
        self.assertFalse(threads[0].is_alive(), "relay harvest never finished")
        self.assertIsNotNone(source.shortcuts_for("gedit"))

    def test_the_REAL_backend_is_released_ON_the_harvest_thread(self):
        from polyhost.services import shortcut_source
        released = []
        with patch.object(shortcut_source, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_source, "harvest", return_value=[]), \
             patch.object(shortcut_source, "release_thread",
                          side_effect=lambda: released.append(
                              threading.current_thread().name)):
            self._run_on_default_thread(
                shortcut_relay.RelaySource(Mock(), allowed=lambda: True))
        self.assertEqual(released, ["poly-fwd-shortcuts"])

    def test_a_RAISING_harvest_still_releases(self):
        from polyhost.services import shortcut_source
        released = []
        with patch.object(shortcut_source, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_source, "harvest",
                          side_effect=RuntimeError("boom")), \
             patch.object(shortcut_source, "release_thread",
                          side_effect=lambda: released.append(1)):
            self._run_on_default_thread(
                shortcut_relay.RelaySource(Mock(), allowed=lambda: True))
        self.assertEqual(released, [1])

    def test_an_INJECTED_harvest_releases_nothing(self):
        from polyhost.services import shortcut_source
        with patch.object(shortcut_source, "release_thread") as release:
            self._run_on_default_thread(shortcut_relay.RelaySource(
                Mock(), harvest=lambda app: [], reason=lambda: None,
                allowed=lambda: True))
        release.assert_not_called()


if __name__ == "__main__":
    unittest.main()
