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
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

try:
    from polyhost.handler.active_window import (
        OverlayHandler, _handle_identifies,
        frontmost_app as aw_frontmost_app,
    )
    from polyhost.handler.common import OverlayCommand
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - headless/no-display env
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TestCoveredByTemplate(unittest.TestCase):
    """What the generic fall-back asks before standing down."""

    def _handler(self):
        return OverlayHandler({})

    def _entry(self, *, overlay=True, remote=False):
        from polyhost.handler.common import FLAGS, Flags
        from polyhost.handler.active_window import OVERLAY
        flags = [False] * len(Flags)
        flags[Flags.HAS_OVERLAY.value] = overlay
        flags[Flags.HAS_REMOTE.value] = remote
        entry = {FLAGS: flags}
        if overlay:
            entry[OVERLAY] = ["gimp.mods.png"]
        return entry

    def test_a_matched_overlay_entry_COVERS_the_window(self):
        h = self._handler()
        h.current_entry = self._entry()
        self.assertTrue(h.covered_by_template())

    def test_nothing_matched_covers_NOTHING(self):
        h = self._handler()
        h.current_entry = None
        h.remote_handler.has_overlay = lambda: False
        self.assertFalse(h.covered_by_template())

    def test_a_matched_entry_with_NO_overlay_covers_nothing(self):
        # A mapping entry can match on title alone and carry no overlay set, so
        # `current_entry` being truthy is NOT the question -- which is why this
        # is answered from `get_overlay_data()` rather than from that attribute.
        h = self._handler()
        h.current_entry = self._entry(overlay=False)
        h.remote_handler.has_overlay = lambda: False
        self.assertFalse(h.covered_by_template())

    def test_it_survives_the_tick_that_reports_NO_change(self):
        # ⚠️ The regression this exists for. `handle_active_window` returns the
        # filenames only on the tick the window CHANGES; the caller must still be
        # able to learn, on every tick after that, that a template is live.
        h = self._handler()
        h._decide_active_window = lambda *a: (["gimp.mods.png"], OverlayCommand.OFF_ON)
        h.current_entry = self._entry()
        data, cmd = h.handle_active_window(0, 0)
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        h._decide_active_window = lambda *a: (None, OverlayCommand.NONE)
        data, cmd = h.handle_active_window(0, 0)
        self.assertIsNone(data)                     # the tell the caller used
        self.assertTrue(h.covered_by_template())    # the tell it should use


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
class FocusedAppTest(unittest.TestCase):
    """`OverlayHandler.focused_app` — name and identity from ONE place."""

    def _handler(self):
        handler = OverlayHandler.__new__(OverlayHandler)
        handler.app_name = "gimp"
        handler.remote_handler = None
        return handler

    def test_a_LOCAL_window_answers_its_own_name_and_NO_identity(self):
        handler = self._handler()
        handler.is_remote_mapping_entry = lambda: False
        self.assertEqual(handler.focused_app(), ("gimp", None))

    def test_a_FORWARDED_window_answers_the_REMOTE_name_and_its_identity(self):
        """⚠️ The whole point of the seam: the app runs on the other machine, so
        the local `app_name` names the wrong thing. Answering it would draw the
        forwarder's own window mark on a forwarded app."""
        remote = MagicMock()
        remote.name = "Code.exe"
        remote.forwarded_identity.return_value = "IDENTITY"
        handler = self._handler()
        handler.remote_handler = remote
        handler.is_remote_mapping_entry = lambda: True
        self.assertEqual(handler.focused_app(), ("Code.exe", "IDENTITY"))
        remote.forwarded_identity.assert_called_once_with("Code.exe")

    def test_a_FORWARDED_window_with_NO_name_yet_answers_NOTHING(self):
        """⚠️ Not the local name as a fallback. A report can arrive before the
        name does, and falling back would draw the wrong app's mark for one
        tick -- which the signature would then latch as already sent."""
        remote = MagicMock()
        remote.name = None
        handler = self._handler()
        handler.remote_handler = remote
        handler.is_remote_mapping_entry = lambda: True
        self.assertEqual(handler.focused_app(), (None, None))


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class MacOSTupleHandleTest(unittest.TestCase):
    """⚠️ The window handle is an OPAQUE TOKEN, not a number.

    It is an int HWND on Windows and an int id on the Linux reporters, but on
    macOS pywinctl's `MacOSWindow.getHandle()` returns a **tuple**
    `(app, window number)`. `log_win` formatted it with `%d`, which raises
    `TypeError: %d format: a real number is required, not tuple` -- and that
    line sits inside the `try` whose `except` logs "Failed retrieving active
    window", so the whole poll bailed out and every Mac reported **no active
    window at all, forever**: no overlays and no per-app language switch, from
    a cosmetic log line (field, 2026-09-21).

    Nothing compares or arithmetics the handle -- it is only ever tested for
    equality -- so there was never a reason to demand a number of it.
    """

    @staticmethod
    def _win(handle):
        win = MagicMock()
        win.title = "Safari"
        win.getHandle.return_value = handle
        return win

    def _poll(self, handle):
        """Two ticks: the first notices the change, the second accepts it.

        ⚠️ Patched by STRING target, not `patch.object` on an imported
        module. Importing `polyhost.handler.active_window` here as well as
        `from`-importing it at the top gives one module two import forms, which
        CodeQL flags (`py/import-and-import-from`) -- a shape this repo has
        been caught by before. A string target needs no second import.
        """
        handler = OverlayHandler({})          # empty mapping: stop after log_win
        win = self._win(handle)
        mod = "polyhost.handler.active_window"
        with patch(mod + ".pwc.getActiveWindow", return_value=win), \
             patch(mod + ".app_name_for", return_value="Safari"), \
             self.assertLogs(handler.log, level="INFO") as captured:
            handler._decide_active_window(10, 5)
            handler._decide_active_window(10, 5)
        return captured.output

    def test_a_TUPLE_handle_still_reports_the_active_window(self):
        lines = self._poll((1234, 5))
        self.assertTrue(any("Active App Changed" in l for l in lines), lines)
        self.assertFalse(any("Failed retrieving active window" in l for l in lines),
                         lines)

    def test_an_INT_handle_is_unchanged(self):
        lines = self._poll(98765)
        self.assertTrue(any("Active App Changed" in l for l in lines), lines)
        self.assertTrue(any("98765" in l for l in lines), lines)


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class FocusedPidTest(unittest.TestCase):
    """The pid the OS-icon route needs, and the one case it must NOT give."""

    def _handler(self, pid=1234, raises=False, remote=False):
        h = OverlayHandler({})
        h.win = MagicMock()
        if raises:
            h.win.getPID.side_effect = OSError("gone")
        else:
            h.win.getPID.return_value = pid
        h.is_remote_mapping_entry = lambda: remote
        h.remote_handler = MagicMock() if remote else None
        return h

    def test_a_LOCAL_window_answers_its_pid(self):
        self.assertEqual(self._handler().focused_pid(), 1234)

    def test_a_FORWARDED_window_answers_NOTHING(self):
        """⚠️ The app runs on the other machine, so a local pid names an
        unrelated process -- and the identity travelling with the report is the
        right answer there."""
        self.assertIsNone(self._handler(remote=True).focused_pid())

    def test_NO_window_answers_nothing(self):
        h = self._handler()
        h.win = None
        self.assertIsNone(h.focused_pid())

    def test_a_RAISING_backend_does_not_take_the_overlay_send_with_it(self):
        self.assertIsNone(self._handler(raises=True).focused_pid())


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class LosingTheWindowTest(unittest.TestCase):
    """What happens when the backend stops reporting a window at all.

    ⚠️ Field, 2026-09-21: switching to an application the window handler could
    not see left the PREVIOUS app's mark on ESC and its shortcut icons on the
    board. Two separate causes, one symptom, both pinned here.
    """

    @staticmethod
    def _win():
        win = MagicMock()
        win.title = "Terminal"
        win.getHandle.return_value = (1234, 5)
        return win

    def _handler_on_an_app(self):
        """A handler that has accepted a window and named its app.

        ⚠️ A NON-EMPTY mapping, and it has to be: `app_name` is assigned inside
        `if self.mapping:`, so with `{}` it is never set at all and "the
        handler stopped naming the app" passes whether or not the clear
        exists. Caught by the regained-window test below, which is the only one
        of the four that can fail on a vacuous fixture.
        """
        handler = OverlayHandler({"someotherapp": {}})   # present, never matches
        mod = "polyhost.handler.active_window"
        with patch(mod + ".pwc.getActiveWindow", return_value=self._win()), \
             patch(mod + ".app_name_for", return_value="Terminal"):
            handler._decide_active_window(10, 5)
            handler._decide_active_window(10, 5)
        return handler

    def _lose_the_window(self, handler):
        """⚠️ `frontmost_app` is patched to answer NOTHING, deliberately.

        Losing the window no longer means losing the app -- a windowless app the
        OS can still name is drawn from the name alone (see
        `AWindowlessAppIsStillAnAppTest`). These four cases are about the other
        half, where nothing knows what is focused, and off macOS they would pass
        for the wrong reason: `frontmost_app` returns `(None, None)` on any
        non-Darwin host, so the premise would be the test machine's platform
        rather than anything this file asserts.
        """
        mod = "polyhost.handler.active_window"
        with patch(mod + ".pwc.getActiveWindow", return_value=None), \
             patch(mod + ".frontmost_app", return_value=(None, None)):
            return handler._decide_active_window(10, 5)

    def test_the_handler_stops_NAMING_the_app_it_can_no_longer_see(self):
        """`focused_app()` drives the generic overlays, so a stale name is the
        host re-affirming the icons of an app the user has already left."""
        handler = self._handler_on_an_app()
        self.assertEqual(handler.win.title, "Terminal")
        self._lose_the_window(handler)
        self.assertEqual(handler.focused_app(), (None, None))

    def test_losing_the_window_DISABLES_even_with_no_template_active(self):
        """⚠️ The guard was `if self.current_entry` -- "was a HAND-MADE overlay
        set on the board?". A generically-drawn app has none, so the board kept
        drawing it."""
        handler = self._handler_on_an_app()
        self.assertIsNone(handler.current_entry)
        _, cmd = self._lose_the_window(handler)
        self.assertEqual(cmd, OverlayCommand.DISABLE)

    def test_it_costs_NOTHING_when_the_board_is_already_blank(self):
        """`_is_redundant_overlay_cmd` is what makes the unconditional DISABLE
        safe: with overlays already off it is dropped before the bridge-sync."""
        handler = self._handler_on_an_app()
        handler.overlays_enabled = False
        with patch("polyhost.handler.active_window.pwc.getActiveWindow",
                   return_value=None):
            _, cmd = handler.handle_active_window(10, 5)
        self.assertEqual(cmd, OverlayCommand.NONE)

    def test_a_REGAINED_window_names_its_app_again(self):
        """The clear must not be a one-way door."""
        handler = self._handler_on_an_app()
        self._lose_the_window(handler)
        mod = "polyhost.handler.active_window"
        with patch(mod + ".pwc.getActiveWindow", return_value=self._win()), \
             patch(mod + ".app_name_for", return_value="Terminal"):
            handler._decide_active_window(10, 5)
            handler._decide_active_window(10, 5)
        self.assertEqual(handler.focused_app(), ("terminal", None))


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AnUntitledWindowStillNamesItsAppTest(unittest.TestCase):
    """⚠️ On macOS an untitled window identifies NOTHING, so two different
    apps look identical to the change test.

    `MacOSWindow.getHandle()` derives the handle FROM the title: it returns
    `("", "")` whenever `title` is empty, and `title` is empty for every window
    `System Events` reports no `AXTitle` for. The change test compared handle and
    title only, so switching between two such applications was not a change at
    all -- the previous app's mark and its 48 shortcut icons stayed on the
    keycaps and NOTHING was logged, which is the worst shape a bug can take: the
    user reports "it is not even in the log" and there is nothing to act on
    (field, 2026-09-21: VS Code, Maps and Chess in a row).

    The app name is what tells them apart, and on macOS `getAppName()` is a
    cached attribute read rather than another AppleScript round trip.
    """

    @staticmethod
    def _win(app, title, handle):
        win = MagicMock()
        win.title = title
        win.getHandle.return_value = handle
        win.getAppName.return_value = app
        return win

    def _switch(self, first, second):
        """Focus `first`, then `second`; return the app names that got reported.

        Two ticks per window: the first notices `prev_win` moved and rearms the
        accept timer, the second accepts it. Patched by STRING target so the
        module is not imported a second way (`py/import-and-import-from`).
        """
        handler = OverlayHandler({})          # empty mapping: stop after log_win
        mod = "polyhost.handler.active_window"
        seen = []
        with self.assertLogs(handler.log, level="INFO") as captured:
            for win in (first, first, second, second):
                with patch(mod + ".pwc.getActiveWindow", return_value=win), \
                     patch(mod + ".app_name_for",
                           side_effect=lambda w: w.getAppName()):
                    handler._decide_active_window(10, 5)
        for line in captured.output:
            if "Active App Changed" in line:
                seen.append(line.split('"')[1])
        return seen

    def test_two_UNTITLED_apps_in_a_row_are_both_reported(self):
        chess = self._win("Chess", "", ("", ""))
        maps = self._win("Maps", "", ("", ""))
        self.assertEqual(self._switch(chess, maps), ["Chess", "Maps"])

    def test_the_SAME_untitled_app_is_still_reported_once(self):
        # The fix must not turn every poll into a change: that would re-send the
        # whole generic set, and `_maybe_send_generic_overlays` runs each tick.
        chess = self._win("Chess", "", ("", ""))
        self.assertEqual(self._switch(chess, chess), ["Chess"])

    def test_a_TITLED_window_keeps_using_its_handle(self):
        # The opposite mistake, and the reason the fallback is CONDITIONAL:
        # the app name must not replace a handle that works. Two windows of one
        # app sharing a title -- two untitled Notepads, both "Untitled - Notepad"
        # -- are told apart by the handle and by nothing else, so substituting
        # the app name here would merge them into one window that never changes.
        a = self._win("Notepad", "Untitled - Notepad", 4321)
        b = self._win("Notepad", "Untitled - Notepad", 8765)
        self.assertEqual(self._switch(a, b), ["Notepad", "Notepad"])

    def test_handle_identifies_answers_for_each_backend(self):
        self.assertTrue(_handle_identifies(98765))            # Windows HWND
        self.assertTrue(_handle_identifies(("Safari", "Docs")))  # macOS, titled
        self.assertFalse(_handle_identifies(("", "")))        # macOS, untitled
        self.assertFalse(_handle_identifies(None))


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AWindowlessAppIsStillAnAppTest(unittest.TestCase):
    """⚠️ NO WINDOW IS NOT NO APPLICATION.

    `pywinctl.getActiveWindow()` returns None for some macOS applications --
    measured on Photos, Notes and Freeform, while Chess, Maps and Terminal on
    the same desktop answered normally (field, 2026-09-21). The handler treated
    that as "nothing is focused" and blanked the board, but the overlay path
    never needed the window: it needs the app's NAME and PID, which
    `NSWorkspace` knows without one.

    What is genuinely lost is the TITLE, so a template entry that matches on one
    cannot be evaluated -- hence the DISABLE these tests also pin. The generic
    path draws; the template path correctly stands down.
    """

    MOD = "polyhost.handler.active_window"

    def _tick(self, handler, app, times=1):
        """Poll `times` with no window while `app` = (name, pid) is frontmost."""
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=None), \
             patch(self.MOD + ".frontmost_app", return_value=app):
            for _ in range(times):
                out = handler._decide_active_window(10, 5)
        return out

    def test_the_app_is_NAMED_even_with_no_window(self):
        handler = OverlayHandler({})
        self._tick(handler, ("Photos", 4242))
        self.assertEqual(handler.focused_app(), ("photos", None))

    def test_the_PID_survives_too(self):
        # Without it the OS icon and the macOS AX harvest are both unreachable,
        # so the app would be named and still draw nothing.
        handler = OverlayHandler({})
        self._tick(handler, ("Photos", 4242))
        self.assertEqual(handler.focused_pid(), 4242)

    def test_it_DISABLES_so_a_stale_template_cannot_survive(self):
        handler = OverlayHandler({})
        _, cmd = self._tick(handler, ("Photos", 4242))
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertIsNone(handler.current_entry)

    def test_switching_between_two_WINDOWLESS_apps_is_noticed(self):
        # Both are invisible to the backend, so the handle/title test that tells
        # ordinary windows apart has nothing to compare -- the name is all there
        # is, and without it Notes would keep showing Photos' icons.
        handler = OverlayHandler({})
        self._tick(handler, ("Photos", 4242))
        self._tick(handler, ("Notes", 77))
        self.assertEqual(handler.focused_app(), ("notes", None))
        self.assertEqual(handler.focused_pid(), 77)

    def test_the_SAME_windowless_app_does_not_refire_every_tick(self):
        # `_maybe_send_generic_overlays` runs on every tick, so a DISABLE per
        # tick would blank the board it has just drawn, forever.
        handler = OverlayHandler({})
        with self.assertLogs(handler.log, level="INFO") as caught:
            self._tick(handler, ("Photos", 4242), times=4)
        lines = [l for l in caught.output if "No active window" in l]
        self.assertEqual(len(lines), 1, caught.output)
        self.assertIn("Photos", lines[0])

    def test_regaining_a_real_window_CLEARS_the_windowless_identity(self):
        # The two are alternatives. A leftover windowless name would outrank
        # nothing here, but it would answer for a forwarded window and for the
        # next app the backend can see.
        handler = OverlayHandler({})
        self._tick(handler, ("Photos", 4242))
        win = MagicMock()
        win.title = "Terminal"
        win.getHandle.return_value = (1234, 5)
        win.getAppName.return_value = "Terminal"
        win.getPID.return_value = 5          # the pid, NOT the handle's tail
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=win), \
             patch(self.MOD + ".app_name_for", return_value="Terminal"):
            handler._decide_active_window(10, 5)
            handler._decide_active_window(10, 5)
        self.assertIsNone(handler.windowless_app)
        self.assertIsNone(handler.windowless_pid)
        self.assertEqual(handler.focused_pid(), 5)

    def test_an_app_the_OS_cannot_name_either_is_still_NOTHING(self):
        handler = OverlayHandler({})
        _, cmd = self._tick(handler, (None, None))
        self.assertEqual(handler.focused_app(), (None, None))
        self.assertIsNone(handler.focused_pid())
        # NONE, not DISABLE: nothing was ever drawn, so there is nothing to take
        # off the board. `LosingTheWindowTest` covers the transition that does
        # need one.
        self.assertEqual(cmd, OverlayCommand.NONE)

    def test_LOSING_a_windowless_app_to_nothing_disables(self):
        handler = OverlayHandler({})
        self._tick(handler, ("Photos", 4242))
        _, cmd = self._tick(handler, (None, None))
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertEqual(handler.focused_app(), (None, None))

    def test_frontmost_app_answers_nothing_off_macOS(self):
        """It is macOS-only on purpose: the other backends do not have this
        failure mode, and a second opinion about which app is focused is a way
        for two answers to disagree.

        ⚠\ufe0f A working `AppKit` is injected, and without it this test passes
        for the wrong reason -- on a Linux host the import fails anyway, so the
        platform guard could be deleted outright and nothing would notice
        (measured: that mutation escaped until the fake was added). The fake is
        what makes the guard the only thing answering.
        """
        appkit = types.ModuleType("AppKit")
        app = MagicMock()
        app.localizedName.return_value = "Photos"
        app.processIdentifier.return_value = 4242
        appkit.NSWorkspace = MagicMock()
        appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication \
            .return_value = app
        with patch(self.MOD + ".platform.system", return_value="Linux"), \
             patch.dict(sys.modules, {"AppKit": appkit}):
            self.assertEqual(aw_frontmost_app(), (None, None))

    def test_frontmost_app_really_reads_the_name_AND_the_pid(self):
        """⚠\ufe0f Every other test here patches `frontmost_app` itself, so none of
        them can see what the real one returns -- a fake that implements the
        contract cannot test it. Measured: dropping the pid from the real
        function escaped the whole sweep until this case existed.

        `AppKit` is injected into `sys.modules` because the import is INSIDE the
        function (it must be: this module is imported on Linux too).
        """
        appkit = types.ModuleType("AppKit")
        app = MagicMock()
        app.localizedName.return_value = "Photos"
        app.processIdentifier.return_value = 4242
        appkit.NSWorkspace = MagicMock()
        appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication \
            .return_value = app
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch.dict(sys.modules, {"AppKit": appkit}):
            self.assertEqual(aw_frontmost_app(), ("Photos", 4242))

    def test_frontmost_app_answers_nothing_when_no_app_is_frontmost(self):
        appkit = types.ModuleType("AppKit")
        appkit.NSWorkspace = MagicMock()
        appkit.NSWorkspace.sharedWorkspace.return_value.frontmostApplication \
            .return_value = None
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch.dict(sys.modules, {"AppKit": appkit}):
            self.assertEqual(aw_frontmost_app(), (None, None))

    def test_frontmost_app_never_raises(self):
        with patch(self.MOD + ".platform.system", side_effect=RuntimeError("nope")):
            self.assertEqual(aw_frontmost_app(), (None, None))


if __name__ == "__main__":
    unittest.main()
