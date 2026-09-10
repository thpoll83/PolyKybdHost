"""OverlayHandler.handle_active_window — redundant re-enable / re-disable suppression.

The handler downgrades a same-app ENABLE (overlays already on, nothing
resent) to NONE so the keyboard isn't asked to redo a blocking slave
bridge-sync + full refresh on every window-title change, and symmetrically
downgrades a DISABLE while overlays are already off (a no-overlay window
whose title keeps ticking, e.g. a terminal spinner). Genuine transitions
(a real enable after a disable, or vice-versa) still go through, and a
device call that fails is re-armed by PolyCore via note_overlay_state so
the redundant-command guard doesn't swallow the retry.

active_window imports pywinctl/Xlib at module load, which needs a display,
so this skips in a headless/CI environment and runs on a real desktop.
"""
import unittest

try:
    from polyhost.handler.active_window import OverlayHandler
    from polyhost.handler.common import OverlayCommand
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - headless/no-display env
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TestReEnableSuppression(unittest.TestCase):

    def _handler(self):
        # Empty mapping is enough — we drive the decision via _decide_active_window.
        return OverlayHandler({})

    def test_redundant_enable_downgraded_to_none(self):
        h = self._handler()
        # First match for an app: OFF_ON sends + enables.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        data, cmd = h.handle_active_window(0, 0)
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        self.assertTrue(h.overlays_enabled)
        # Same app, only the title changed: matcher returns ENABLE, but overlays
        # are already on → suppressed to NONE (no device traffic).
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        data, cmd = h.handle_active_window(0, 0)
        self.assertEqual(cmd, OverlayCommand.NONE)
        self.assertIsNone(data)
        self.assertTrue(h.overlays_enabled)

    def test_first_disable_is_a_real_transition(self):
        h = self._handler()
        # Overlays on (a mapped app), then switch to an unmapped window: the
        # DISABLE is a genuine on->off transition and must fire.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        self.assertTrue(h.overlays_enabled)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)

    def test_redundant_disable_downgraded_to_none(self):
        h = self._handler()
        # A no-overlay window whose TITLE keeps changing resolves to DISABLE on
        # every poll. Overlays start off (fresh handler), so the very first and
        # every subsequent DISABLE is redundant -> downgraded to NONE (no traffic,
        # no full keycap re-render). This is the terminal-spinner-in-title case.
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        for _ in range(3):
            data, cmd = h.handle_active_window(0, 0)
            self.assertEqual(cmd, OverlayCommand.NONE)
            self.assertIsNone(data)
            self.assertFalse(h.overlays_enabled)

    def test_enable_after_disable_is_not_suppressed(self):
        h = self._handler()
        # Establish overlays-on, then a real DISABLE, then ENABLE must fire.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)
        # Back to a mapped app after an unmapped window: re-enable must fire.
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)

    def test_failed_disable_rearm_retries(self):
        h = self._handler()
        # Overlays on, then a real DISABLE (on->off) fires and marks off.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)
        # PolyCore's overlay job saw the device DISABLE fail and re-armed the
        # handler back to the pre-command state. The next poll's DISABLE must
        # NOT be suppressed — it retries until the device confirms.
        h.note_overlay_state(True)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)

    def test_failed_enable_rearm_retries(self):
        h = self._handler()
        # A real ENABLE (off->on) fires and marks on.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)
        # Device ENABLE failed -> re-armed to "disabled"; next ENABLE retries.
        h.note_overlay_state(False)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)

    def test_force_resend_clears_enabled_state(self):
        h = self._handler()
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        self.assertTrue(h.overlays_enabled)
        # A reconnect resets the device's overlays; the next enable must not be
        # suppressed.
        h.force_resend()
        self.assertFalse(h.overlays_enabled)



@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TestInvalidateWindowCache(unittest.TestCase):
    """Re-evaluating the focused window, and when that is not enough.

    ⚠️ THE FIELD BUG (2026-09-10, "so far nothing"): a program icon that
    finishes downloading while its app is STILL focused matches the same entry,
    so `try_to_match_window` returns ENABLE, which `_is_redundant_overlay_cmd`
    drops because overlays are already on. Nothing is re-sent, and the mark that
    just arrived does not reach the keycap until the user switches away and
    back. Measured: a Chrome mark resolved 0.8 s into the send that had gone
    without it and appeared four minutes later, on the third activation.
    """

    TITLE = "Some Page - Chrome"

    def _handler(self):
        # ⚠️ Match against `handler.mapping["chrome"]`, not the dict passed in:
        # `annotate` returns a COPY carrying the precomputed `flags` list, and
        # `find_matching_entry` indexes that key unconditionally.
        handler = OverlayHandler({"chrome": {"overlay": ["x.png"]}})
        handler.title = self.TITLE
        return handler

    def _match(self, handler):
        return handler.try_to_match_window("chrome", handler.mapping["chrome"])[1]

    def _next_poll(self, handler):
        """What the poll does after an invalidation: re-read the window.

        `invalidate_window_cache` drops the cached title precisely so
        `local_win_changed` trips, and the poll then calls `set_win` before
        matching -- so a test that matches on the dropped title is asking the
        matcher a question the real flow never asks.
        """
        handler.title = self.TITLE
        return self._match(handler)

    def test_a_re_match_of_the_SAME_entry_is_only_an_ENABLE(self):
        # The premise the bug rests on, pinned so the rest of this class cannot
        # pass for the wrong reason.
        h = self._handler()
        self.assertEqual(self._match(h), OverlayCommand.OFF_ON)
        self.assertEqual(self._match(h), OverlayCommand.ENABLE)

    def test_the_PLAIN_invalidation_does_NOT_resend_the_same_entry(self):
        # Correct for a browser URL change, which matches a DIFFERENT entry --
        # and the reason the icon case needed its own flag rather than a
        # widening of this one.
        h = self._handler()
        self._match(h)
        h.invalidate_window_cache()
        self.assertEqual(self._next_poll(h), OverlayCommand.ENABLE)

    def test_resend_same_entry_turns_that_back_into_a_full_OFF_ON(self):
        h = self._handler()
        self._match(h)
        h.invalidate_window_cache(resend_same_entry=True)
        self.assertEqual(self._next_poll(h), OverlayCommand.OFF_ON)

    def test_the_resulting_ENABLE_really_IS_swallowed_by_the_guard(self):
        # The second half of the bug: ENABLE is not merely weaker than OFF_ON,
        # it reaches the device as nothing at all.
        h = self._handler()
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.ENABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.NONE)

    def test_BOTH_forms_drop_the_cached_window_so_the_next_poll_re_evaluates(self):
        for resend in (False, True):
            with self.subTest(resend_same_entry=resend):
                h = self._handler()
                h.handle = 1234
                h.invalidate_window_cache(resend_same_entry=resend)
                self.assertIsNone(h.title)
                self.assertIsNone(h.handle)

    def test_NEITHER_form_re_arms_the_accept_time_debounce(self):
        # `force_resend` does, deliberately. Here the window is already focused
        # and has already cleared the debounce, so re-arming it would just delay
        # the re-send by another accept window -- which for the icon case is the
        # very latency the flag exists to remove.
        for resend in (False, True):
            with self.subTest(resend_same_entry=resend):
                h = self._handler()
                h.last_update_msec = 999
                h.invalidate_window_cache(resend_same_entry=resend)
                self.assertEqual(h.last_update_msec, 999)



@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TestMarkOnlySendKeepsTheStateHonest(unittest.TestCase):
    """The device-side half of the mark-only branch in `tick_window_tracking`.

    An app with no template of its own gets only its program mark, and the tick
    sends it INSTEAD of issuing the DISABLE the handler asked for. The handler
    has already recorded "overlays off" for that DISABLE, so unless the tick
    corrects it the guard below swallows the next real one.
    """

    def _handler(self):
        return OverlayHandler({})

    def test_an_UNCORRECTED_state_swallows_the_next_real_disable(self):
        # This is the failure, spelled out: nothing here calls
        # note_overlay_state, exactly as the tick did before the fix.
        h = self._handler()
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        # An app with neither template nor mark now asks for a real disable...
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.NONE)

    def test_CORRECTING_it_lets_the_next_real_disable_through(self):
        h = self._handler()
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        h.handle_active_window(0, 0)
        h.note_overlay_state(True)      # what the tick does after sending a mark
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)


if __name__ == "__main__":
    unittest.main()
