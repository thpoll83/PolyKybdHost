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
import logging
import os
import subprocess
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

try:
    from polyhost.handler.active_window import (
        OverlayHandler, _handle_identifies,
        focused_app_pid as aw_focused_app_pid,
        frontmost_app as aw_frontmost_app,
        _AX_FOCUSED_APPLICATION, _FRONTMOST_SCRIPT,
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

    def test_a_forwarder_overlay_covers_a_REMOTE_entry(self):
        h = self._handler()
        h.current_entry = self._entry(overlay=False, remote=True)
        h.remote_handler.has_overlay = lambda: True
        h.remote_handler.get_overlay_data = lambda: ["jetbrains_linux_template.mods.png"]
        self.assertTrue(h.covered_by_template())
        self.assertEqual(h.get_overlay_data(), ["jetbrains_linux_template.mods.png"])

    def test_a_STALE_forwarder_overlay_covers_no_LOCAL_window(self):
        # ⚠️ The forwarder still reports CLion after the local focus moved to
        # the taskbar. That report must not cover a window no entry matched,
        # or the core re-sends CLion's template there (field, 2026-09-30).
        h = self._handler()
        h.current_entry = None
        h.remote_handler.has_overlay = lambda: True
        h.remote_handler.get_overlay_data = lambda: ["jetbrains_linux_template.mods.png"]
        self.assertFalse(h.covered_by_template())
        self.assertIsNone(h.get_overlay_data())

    def test_nor_a_LOCAL_entry_with_no_overlay(self):
        h = self._handler()
        h.current_entry = self._entry(overlay=False)
        h.remote_handler.has_overlay = lambda: True
        h.remote_handler.get_overlay_data = lambda: ["jetbrains_linux_template.mods.png"]
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
class FocusedTitleTest(unittest.TestCase):
    """The title the shortcut harvest re-harvests on (shortcut_fetcher)."""

    def _handler(self, title="Untitled - Kate", remote=False):
        h = OverlayHandler({})
        h.win = MagicMock()
        h.title = title
        h.is_remote_mapping_entry = lambda: remote
        h.remote_handler = MagicMock() if remote else None
        return h

    def test_a_LOCAL_window_answers_its_title(self):
        self.assertEqual(self._handler().focused_title(), "Untitled - Kate")

    def test_a_BYTES_title_is_decoded(self):
        """Some backends hand back bytes (the log prints b'...')."""
        self.assertEqual(self._handler(title="Welcome \u2014 Kate".encode()).focused_title(),
                         "Welcome \u2014 Kate")

    def test_a_FORWARDED_window_answers_NOTHING(self):
        """Its shortcuts are harvested on the other machine."""
        self.assertIsNone(self._handler(remote=True).focused_title())

    def test_NO_window_answers_nothing(self):
        h = self._handler()
        h.win = None
        self.assertIsNone(h.focused_title())

    def test_an_EMPTY_title_answers_nothing(self):
        self.assertIsNone(self._handler(title="").focused_title())


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class FocusedHandleTest(unittest.TestCase):
    """The window the Windows shortcut harvest reads (2026-10-15: a read
    queued for Zoom ran on Chrome)."""

    def _handler(self, handle=198342, remote=False, raises=False):
        h = OverlayHandler({})
        h.win = MagicMock()
        if raises:
            h.win.getHandle.side_effect = RuntimeError("gone")
        else:
            h.win.getHandle.return_value = handle
        h.is_remote_mapping_entry = lambda: remote
        h.remote_handler = MagicMock() if remote else None
        return h

    def on(self, system):
        return patch("polyhost.handler.active_window.platform.system",
                     return_value=system)

    def test_a_LOCAL_window_on_Windows_answers_its_handle(self):
        with self.on("Windows"):
            self.assertEqual(self._handler().focused_handle(), 198342)

    def test_OTHER_platforms_answer_nothing(self):
        """macOS derives the handle from the title; it names no window."""
        for system in ("Darwin", "Linux"):
            with self.on(system):
                self.assertIsNone(self._handler().focused_handle(), system)

    def test_a_FORWARDED_window_answers_nothing(self):
        with self.on("Windows"):
            self.assertIsNone(self._handler(remote=True).focused_handle())

    def test_NO_window_and_a_RAISING_backend_answer_nothing(self):
        with self.on("Windows"):
            h = self._handler()
            h.win = None
            self.assertIsNone(h.focused_handle())
            self.assertIsNone(self._handler(raises=True).focused_handle())


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

    What is genuinely lost is the TITLE, so an entry that MATCHES on one cannot
    be evaluated and must fail -- but an entry that declares none is fine, and
    those are evaluated here (`title_known=False`; see
    `TheWindowlessBranchStillMatchesATemplateTest`). The DISABLE these tests
    pin is the empty-mapping case: nothing matched, so the generic path draws
    and the template path stands down.
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

    @staticmethod
    def _osascript(stdout):
        """Stand in for the `osascript` subprocess `frontmost_app` shells out to."""
        return MagicMock(return_value=MagicMock(stdout=stdout))

    def test_frontmost_app_reads_the_name_AND_the_pid(self):
        """⚠\ufe0f Every other test here patches `frontmost_app` itself, so none of
        them can see what the real one returns -- a fake that implements the
        contract cannot test it. Measured: dropping the pid from the real
        function escaped the whole sweep until this case existed."""
        run = self._osascript("4242\nPhotos\n")
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), ("Photos", 4242))

    def test_it_asks_SYSTEM_EVENTS_rather_than_the_AppKit_property(self):
        """⚠\ufe0f The regression this function exists to prevent, pinned at the
        one place it is visible: WHICH source is asked.

        `NSWorkspace.frontmostApplication` is one line of Python away and is
        STALE off the main thread -- twice now. The shortcut fetcher read
        `Safari` for nine consecutive harvests over three minutes; this function
        froze on `QuickTime Player`, so switching to Activity Monitor drew
        QuickTime's mark and its shortcuts and logged nothing, because the name
        never changed. A wrong app is worse than no app.

        Asserting the RESULT cannot catch that -- a stale read returns a
        perfectly well-formed name. Only the source can be asserted, so this
        test reads the command and the script."""
        run = self._osascript("1\nPhotos\n")
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            aw_frontmost_app()
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "osascript", argv)
        script = run.call_args.kwargs["input"]
        self.assertIn("System Events", script)
        self.assertIn("frontmost is true", script)

    def test_the_SCRIPT_and_the_PARSER_agree_on_the_order(self):
        """\u26a0\ufe0f The script and the parser are two halves of one contract and
        only the parser is under test -- every case here fakes the subprocess
        OUTPUT, so swapping the two values inside the AppleScript escapes the
        whole sweep. Measured: it did.

        The pid leads because a process name may contain anything, spaces
        included ("Activity Monitor", "QuickTime Player"); the pid is digits and
        ends at the first newline. Reversed, every two-word app would lose its
        tail -- and every one-word app would still pass.
        """
        ret = [l for l in _FRONTMOST_SCRIPT.splitlines()
               if l.strip().startswith("return ")]
        self.assertEqual(len(ret), 1, ret)
        self.assertLess(ret[0].index("procID"), ret[0].index("procName"), ret[0])

    def test_a_process_name_containing_SPACES_survives(self):
        # "QuickTime Player", "Activity Monitor", "Visual Studio Code" -- the pid
        # leads for exactly this reason, so the name is whatever is left.
        run = self._osascript("77\nActivity Monitor\n")
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), ("Activity Monitor", 77))

    def test_a_name_with_NO_usable_pid_is_still_a_name(self):
        # 0 is the AppleScript's own unresolved default, never a real pid. The
        # pid only reaches the OS icon and the AX harvest; the name alone still
        # picks a template and drives the lexicon.
        run = self._osascript("0\nPhotos\n")
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), ("Photos", None))

    def test_frontmost_app_answers_nothing_when_no_app_is_frontmost(self):
        # The AppleScript's own `try` leaves the defaults in place, so an empty
        # name is how "could not resolve" arrives -- not an exception.
        run = self._osascript("0\n\n")
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), (None, None))

    def test_frontmost_app_answers_nothing_off_macOS(self):
        """It is macOS-only on purpose: the other backends do not have this
        failure mode, and a second opinion about which app is focused is a way
        for two answers to disagree.

        ⚠\ufe0f A WORKING osascript is faked, and without it this test passes for
        the wrong reason -- on a Linux host the command is absent anyway, so the
        platform guard could be deleted outright and nothing would notice."""
        run = self._osascript("4242\nPhotos\n")
        with patch(self.MOD + ".platform.system", return_value="Linux"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), (None, None))
        run.assert_not_called()

    def test_frontmost_app_never_raises(self):
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run",
                   side_effect=RuntimeError("osascript is unwell")):
            self.assertEqual(aw_frontmost_app(), (None, None))

    def test_a_HUNG_osascript_does_not_hang_the_tick(self):
        # The window tick is a ~600 ms loop. An unbounded wait here would stop
        # the board following the focus at all, which is worse than the fault
        # this function exists to work around.
        run = MagicMock(side_effect=subprocess.TimeoutExpired("osascript", 2.0))
        with patch(self.MOD + ".platform.system", return_value="Darwin"), \
             patch(self.MOD + ".subprocess.run", run):
            self.assertEqual(aw_frontmost_app(), (None, None))
        self.assertIsNotNone(run.call_args.kwargs.get("timeout"))


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class PolyHostsOwnWindowTest(unittest.TestCase):
    """PolyHost runs as `python -m polyhost`, so its windows arrive named after
    the interpreter. They are renamed `polyhost`, which is what draws the
    PolyKybd mark on ESC instead of the Python logo."""

    MOD = "polyhost.handler.active_window"

    def _focus(self, pid, app="python3"):
        # A non-empty mapping: `app_name` is only derived when there is one.
        handler = OverlayHandler({"someapp": {}})
        win = MagicMock()
        win.title = "PolyKybd Settings"
        win.getHandle.return_value = 777
        win.getPID.return_value = pid
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=win), \
             patch(self.MOD + ".app_name_for", return_value=app):
            handler._decide_active_window(10, 5)
            handler._decide_active_window(10, 5)
        return handler

    def test_a_polyhost_window_is_named_polyhost(self):
        handler = self._focus(os.getpid())
        self.assertEqual(handler.focused_app(), ("polyhost", None))

    def test_another_python_window_keeps_the_interpreter_name(self):
        with patch("polyhost.handler.own_process.process_argv",
                   return_value=["python3", "other.py"]):
            handler = self._focus(os.getpid() + 1)
        self.assertEqual(handler.focused_app(), ("python3", None))

    def test_macOS_own_front_window_skips_pywinctl(self):
        """System Events cannot see our window on macOS (it answered
        Terminal), so the window-server answer takes over."""
        handler = OverlayHandler({})
        with patch(self.MOD + ".own_front_app", return_value=("polyhost", 4242)), \
             patch(self.MOD + ".pwc.getActiveWindow") as get_active, \
             patch(self.MOD + ".frontmost_app") as frontmost:
            handler._decide_active_window(10, 5)
        get_active.assert_not_called()
        frontmost.assert_not_called()
        self.assertEqual(handler.focused_app(), ("polyhost", None))
        self.assertEqual(handler.focused_pid(), 4242)

    def test_a_windowless_polyhost_is_named_polyhost_too(self):
        handler = OverlayHandler({})
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=None), \
             patch(self.MOD + ".frontmost_app",
                   return_value=("Python", os.getpid())):
            handler._decide_active_window(10, 5)
        self.assertEqual(handler.focused_app(), ("polyhost", None))


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AMatchWithNothingToDrawDisablesTest(unittest.TestCase):
    """⚠️ A mapped window with no overlay must not leave the last app's keycaps up.

    Field, 2026-09-30: NoMachine's connection chooser matches the `remote:`
    entry `nxplayer`, but no forwarder had reported, so the match returned
    OFF_ON with no data. Nothing was sent, and Chrome's overlays stayed on the
    board while the chooser was in front.
    """

    MAPPING = {
        "nxplayer": {"remote": True, "title": " - NoMachine$"},
        "notepad": {"overlay": "notepad_template.mods.png"},
    }

    @staticmethod
    def _win(app, title, handle):
        win = MagicMock()
        win.title = title
        win.getHandle.return_value = handle
        win.getAppName.return_value = app
        return win

    def _focus(self, handler, win):
        """Two ticks: the first rearms the accept timer, the second decides."""
        mod = "polyhost.handler.active_window"
        with patch(mod + ".pwc.getActiveWindow", return_value=win), \
             patch(mod + ".app_name_for", side_effect=lambda w: w.getAppName()):
            handler._decide_active_window(10, 5)
            return handler._decide_active_window(10, 5)

    def test_a_remote_entry_with_NO_forwarder_report_DISABLES(self):
        handler = OverlayHandler(self.MAPPING)
        self.addCleanup(handler.close)
        data, cmd = self._focus(handler, self._win("nxplayer", "myhost - NoMachine", 11))
        self.assertIsNone(data)
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        # Still the current entry, so a later forwarder report switches through
        # the remote branch; not the LAST entry, so coming back is a full OFF_ON.
        self.assertTrue(handler.is_remote_mapping_entry())
        self.assertIsNone(handler.last_entry)

    def test_a_template_entry_still_switches_with_its_files(self):
        handler = OverlayHandler(self.MAPPING)
        self.addCleanup(handler.close)
        data, cmd = self._focus(handler, self._win("notepad", "a.txt", 12))
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        self.assertIn("notepad_template.mods.png", data)


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class NoMachineChooserIsNotASessionTest(unittest.TestCase):
    """The SHIPPED `nxplayer` entry matches a session window only.

    On Windows a NoMachine session window is titled `<host> - NoMachine`; the
    connection chooser is titled `NoMachine` alone. The old `.*NoMachine.*`
    made the chooser a remote session (field, 2026-09-30).
    """

    def _handler(self):
        import pathlib
        import yaml
        res = pathlib.Path(__file__).resolve().parents[2] / "polyhost" / "res"
        with open(res / "overlay-mapping.poly.yaml", encoding="utf-8") as f:
            shipped = yaml.safe_load(f)
        handler = OverlayHandler({"nxplayer": shipped["nxplayer"]})
        self.addCleanup(handler.close)
        return handler

    def _focus(self, handler, title):
        return AMatchWithNothingToDrawDisablesTest._focus(
            self, handler,
            AMatchWithNothingToDrawDisablesTest._win("nxplayer", title, 21))

    def test_a_SESSION_window_is_the_remote_entry(self):
        handler = self._handler()
        self._focus(handler, "myhost - NoMachine")
        self.assertTrue(handler.is_remote_mapping_entry())

    def test_the_connection_CHOOSER_is_not(self):
        handler = self._handler()
        data, cmd = self._focus(handler, "NoMachine")
        self.assertFalse(handler.is_remote_mapping_entry())
        self.assertEqual(cmd, OverlayCommand.DISABLE)



@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TheAcceptTimerCountsREALTimeTest(unittest.TestCase):
    """⚠️ It used to add the NOMINAL cycle whatever the tick really cost.

    Accepting a switch takes six ticks: the tick that notices the window moved
    resets the timer to 0, then five 250 ms steps carry it past the 1000 ms
    threshold. At the stated cycle that is 3 s. On macOS a tick measured
    **2.30 s median** -- pywinctl spends two `osascript` processes per
    `getActiveWindow()` -- so the same six ticks were 15.3 s of uninterrupted
    focus, and every app the user left sooner never reached the keyboard at
    all. The field bundle of 2026-10-16 has 132 slow-tick warnings across 42
    minutes with not one app-identity line between them.

    The nominal cycle stays the FLOOR, because the tests here drive the loop
    with no delay at all and would otherwise accumulate nothing.
    """

    @staticmethod
    def _win(app):
        win = MagicMock()
        win.title = ""
        win.getHandle.return_value = ("", "")
        win.getAppName.return_value = app
        return win

    def _switches_after(self, clock):
        """Ticks spent before a switch to a second app is reported."""
        handler = OverlayHandler({})
        mod = "polyhost.handler.active_window"
        first, second = self._win("Chess"), self._win("Maps")
        with patch(mod + ".time.monotonic", side_effect=clock), \
             patch(mod + ".app_name_for", side_effect=lambda w: w.getAppName()), \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + "._IS_MACOS", False):
            with patch(mod + ".pwc.getActiveWindow", return_value=first):
                for _ in range(8):
                    handler._decide_active_window(250, 1000)
            with patch(mod + ".pwc.getActiveWindow", return_value=second), \
                 self.assertLogs(handler.log, level="INFO") as captured:
                for ticks in range(1, 9):
                    handler._decide_active_window(250, 1000)
                    if any("Active App Changed: \"Maps\"" in line
                           for line in captured.output):
                        return ticks
        return None

    def test_a_SLOW_tick_accepts_the_switch_in_two_ticks(self):
        # 2.5 s per tick, the measured macOS cost: one tick is already past the
        # 1000 ms threshold, so the switch lands on the tick after the reset.
        clock = (n * 2.5 for n in range(1000))
        self.assertEqual(self._switches_after(lambda: next(clock)), 2)

    def test_the_NOMINAL_cycle_is_still_the_floor(self):
        # A caller that ticks faster than it says it does keeps the old count,
        # which is what every other test in this file relies on.
        self.assertEqual(self._switches_after(lambda: 100.0), 6)


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TheMacOSTickSkipsTheAppleScriptQueryTest(unittest.TestCase):
    """The Accessibility early-out: is the same application still in front?

    `pywinctl.getActiveWindow()` costs two `osascript` processes on macOS and
    ran on every tick for ever. `active_window.focused_app_pid()` answers the
    same question with one in-process `AXFocusedApplication` read, so a
    settled board costs nothing.

    ⚠️ A pid does not change when a window RETITLES, so each condition below
    is load-bearing: the skip must not survive a retitle the overlay match
    depends on.
    """

    MAPPING = {
        "finder": {"overlay": "finder.png"},
        "google chrome": {"titles-contains": {"github": {"overlay": "gh.png"}}},
    }

    def _settled(self, app="finder", pid=4321):
        """A handler that already resolved `app`, as a settled board has."""
        handler = OverlayHandler(dict(self.MAPPING))
        win = MagicMock()
        win.getPID.return_value = pid
        handler.set_win(win, "", app.title())
        handler.app_name = app
        handler._macos_front = pid
        handler._macos_resolved = True
        return handler

    @staticmethod
    def _gate(handler, identity):
        mod = "polyhost.handler.active_window"
        with patch(mod + ".focused_app_pid", return_value=identity):
            return handler._macos_can_skip_tick()

    def test_an_UNCHANGED_front_app_skips_the_query(self):
        handler = self._settled()
        self.assertTrue(self._gate(handler, 4321))

    def test_a_CHANGED_front_app_spends_the_query(self):
        handler = self._settled()
        self.assertFalse(self._gate(handler, 9999))

    def test_an_entry_matching_on_TITLES_never_skips(self):
        # Chrome's overlay is keyed on `titles-contains`, and a tab switch
        # retitles the window without moving the topmost window at all. 14 of
        # the 69 shipped entries are like this.
        handler = self._settled(app="google chrome")
        self.assertFalse(self._gate(handler, 4321))

    def test_an_UNRESOLVED_identity_spends_the_query(self):
        # ⚠️ The starvation case. A changed identity clears the marker, and the
        # window branch sets it only once its accept timer matures -- so the
        # debounce ticks must keep querying. Without the marker a switch could
        # be skipped into limbo: the identity is already the new app's while
        # the handler still believes the old one is focused.
        handler = self._settled()
        self.assertFalse(self._gate(handler, 9999))   # clears it
        self.assertFalse(self._gate(handler, 9999))   # still owed

    def test_it_never_asks_pywinctl_for_the_PID(self):
        # `window_pid` is `MacOSWindow.getPID()`, one more `osascript` through a
        # shell. A cross-check there would have cost most of the saving.
        handler = self._settled()
        handler.win.getPID.reset_mock()
        self.assertTrue(self._gate(handler, 4321))
        handler.win.getPID.assert_not_called()

    def test_an_UNGRANTED_accessibility_read_spends_the_query(self):
        # None is never "unchanged", so a machine with no grant behaves
        # exactly as it did before the detector existed.
        handler = self._settled()
        self.assertFalse(self._gate(handler, None))
        self.assertFalse(self._gate(handler, None))

    def test_NONE_stays_unskippable_even_after_a_resolve(self):
        # ⚠️ The `front is None` guard, and the one mutation that survived
        # without this test. Comparing None to a stored None reads "unchanged",
        # so once the full path had marked anything resolved, a machine with no
        # Accessibility grant would skip EVERY tick from then on and the
        # keyboard would never follow the active app again.
        handler = self._settled()
        self.assertFalse(self._gate(handler, None))   # stores None
        handler._macos_resolved = True                # the full path resolved
        self.assertFalse(self._gate(handler, None))

    def test_the_FIRST_tick_of_a_session_spends_the_query(self):
        # No identity and no marker yet, so there is no belief to confirm.
        handler = OverlayHandler(dict(self.MAPPING))
        self.assertFalse(self._gate(handler, 4321))

    def test_a_resolved_tick_ARMS_the_skip_for_the_next_one(self):
        # The window branch sets the marker where it commits to a window, so a
        # real tick followed by an unchanged identity costs nothing.
        handler = OverlayHandler(dict(self.MAPPING))
        win = MagicMock()
        win.title = ""
        win.getHandle.return_value = ("", "")
        win.getAppName.return_value = "Finder"
        mod = "polyhost.handler.active_window"
        with patch(mod + "._IS_MACOS", True), \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + ".app_name_for", return_value="Finder"), \
             patch(mod + ".focused_app_pid", return_value=4321), \
             patch(mod + ".pwc.getActiveWindow", return_value=win) as query:
            for _ in range(8):
                handler._decide_active_window(250, 1000)
        # Six ticks to accept the window, then the rest skip.
        self.assertEqual(query.call_count, 6)

    def test_a_skipped_tick_does_NOT_call_getActiveWindow(self):
        handler = self._settled()
        mod = "polyhost.handler.active_window"
        with patch(mod + "._IS_MACOS", True), \
             patch(mod + ".focused_app_pid", return_value=4321), \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + ".pwc.getActiveWindow") as query:
            data, cmd = handler._decide_active_window(250, 1000)
        query.assert_not_called()
        self.assertIsNone(data)
        self.assertEqual(cmd, OverlayCommand.NONE)

    def test_OTHER_platforms_never_consult_it(self):
        handler = self._settled()
        mod = "polyhost.handler.active_window"
        with patch(mod + "._IS_MACOS", False), \
             patch(mod + ".focused_app_pid") as quartz, \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + ".pwc.getActiveWindow", return_value=None):
            handler._decide_active_window(250, 1000)
        quartz.assert_not_called()


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class LoggingTheWindowCostsNoExtraAppleScriptTest(unittest.TestCase):
    """⚠️ `log_win` used to RE-READ the window it was logging.

    It called `self.win.title` and `self.win.getHandle()` again, and on macOS
    each is an `osascript` subprocess -- `getHandle()` reads `title` inside
    itself, so the log line alone was three AppleScript round trips of the
    seven a changed tick spent. The caller already holds both values.
    """

    def test_the_tick_reads_title_and_handle_ONCE_each(self):
        # ⚠️ `title` is a PropertyMock, not an attribute. Assigning
        # `win.title = "Notes"` counts no reads, so the handle count was the
        # only thing asserted and a regression that re-read `win.title` --
        # which is what this test exists to catch, since each read is an
        # `osascript` on macOS -- passed (Revix, #397).
        win = MagicMock()
        title = PropertyMock(return_value="Notes")
        type(win).title = title
        win.getHandle.return_value = ("Notes", "Notes")
        win.getAppName.return_value = "Notes"
        handler = OverlayHandler({})
        mod = "polyhost.handler.active_window"
        with patch(mod + "._IS_MACOS", False), \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + ".app_name_for", return_value="Notes"), \
             patch(mod + ".pwc.getActiveWindow", return_value=win):
            for _ in range(6):
                handler._decide_active_window(250, 1000)
        self.assertEqual(win.getHandle.call_count, 1, "handle read more than once")
        self.assertEqual(title.call_count, 1, "title read more than once")

    def test_the_title_is_logged_as_TEXT_not_as_a_bytes_repr(self):
        # `title.encode('utf-8')` rendered an empty title as `b''` and a real
        # one as `b'NoMachine Software Update'`, so a bundle reader had to work
        # out that the quoting was the log's own.
        handler = OverlayHandler({})
        handler.win = MagicMock()
        with self.assertLogs(handler.log, level="INFO") as captured:
            handler.log_win("nxrunner", "NoMachine Software Update", ("", ""))
        self.assertIn('Title: "NoMachine Software Update"', captured.output[0])
        self.assertNotIn("b'", captured.output[0])


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TheFocusDetectorTest(unittest.TestCase):
    """`focused_app_pid()` — the one call a skipped macOS tick makes.

    ⚠️ Two cheaper or more obvious sources were rejected, and the reasons are
    the point of this class: the Quartz window list answers about a WINDOW, so
    activating an app whose windows are all minimized would never move it and
    the switch would be skipped indefinitely; and
    `NSWorkspace.frontmostApplication` reads stale off the main thread, which
    this project has measured wrong twice.
    """

    def _read(self, err=0, app=object(), pid_err=0, pid=4321, macos=True):
        mod = "polyhost.handler.active_window"
        api = (MagicMock(return_value="systemwide"),
               MagicMock(return_value=(err, app)),
               MagicMock(return_value=(pid_err, pid)))
        with patch(mod + "._IS_MACOS", macos), \
             patch(mod + "._ax_system_wide_api", return_value=api) as factory:
            return aw_focused_app_pid(), api, factory

    def test_it_answers_the_focused_application_pid(self):
        found, api, _ = self._read()
        self.assertEqual(found, 4321)
        api[1].assert_called_once_with("systemwide", _AX_FOCUSED_APPLICATION, None)

    def test_it_asks_for_the_FOCUSED_APPLICATION_not_a_window(self):
        # A window attribute would miss an app activated with every window
        # minimized, and the skip would then never end.
        self.assertEqual(_AX_FOCUSED_APPLICATION, "AXFocusedApplication")

    def test_an_AX_ERROR_answers_NOTHING(self):
        # -25211 is kAXErrorAPIDisabled: no Accessibility grant.
        self.assertIsNone(self._read(err=-25211, app=None)[0])

    def test_a_FAILED_pid_read_answers_NOTHING(self):
        self.assertIsNone(self._read(pid_err=-25200)[0])

    def test_pid_ZERO_answers_NOTHING(self):
        # 0 is never a real application pid, and reads as falsy downstream.
        self.assertIsNone(self._read(pid=0)[0])

    def test_OTHER_platforms_never_import_pyobjc(self):
        found, _, factory = self._read(macos=False)
        self.assertIsNone(found)
        factory.assert_not_called()

    def test_a_RAISING_read_answers_NOTHING(self):
        mod = "polyhost.handler.active_window"
        with patch(mod + "._IS_MACOS", True), \
             patch(mod + "._ax_system_wide_api",
                   side_effect=ImportError("no pyobjc")):
            self.assertIsNone(aw_focused_app_pid())

    def test_a_BROKEN_detector_says_so_ONCE(self):
        """⚠️ Silence here would hide the fix reverting itself.

        A pyobjc upgrade or an AX rename returns the tick to querying pywinctl
        every time, and the only symptom would be the multi-second switch lag
        coming back with nothing in the log (Revix, #397). Once per process,
        not per tick: a tick logs ~150 times an hour.
        """
        mod = "polyhost.handler.active_window"
        with patch(mod + "._AX_FAILED_ONCE", False), \
             patch(mod + "._IS_MACOS", True), \
             patch(mod + "._ax_system_wide_api",
                   side_effect=RuntimeError("AX gone")):
            with self.assertLogs("PolyHost", level="WARNING") as captured:
                for _ in range(3):
                    self.assertIsNone(aw_focused_app_pid())
        self.assertEqual(len(captured.output), 1, captured.output)
        self.assertIn("not a missing Accessibility grant", captured.output[0])

    def test_a_MISSING_grant_stays_quiet(self):
        # -25211 is kAXErrorAPIDisabled: a normal state on an ungranted
        # machine, and not something to warn about every start.
        mod = "polyhost.handler.active_window"
        api = (MagicMock(return_value="sw"),
               MagicMock(return_value=(-25211, None)),
               MagicMock())
        with patch(mod + "._AX_FAILED_ONCE", False), \
             patch(mod + "._IS_MACOS", True), \
             patch(mod + "._ax_system_wide_api", return_value=api):
            logger = logging.getLogger("PolyHost")
            with patch.object(logger, "warning") as warn:
                self.assertIsNone(aw_focused_app_pid())
        warn.assert_not_called()


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TheWindowlessBranchStillMatchesATemplateTest(unittest.TestCase):
    """An app pywinctl cannot see still gets its hand-made artwork.

    ⚠️ **The branch used to skip the template path wholesale**, on the premise
    that no window means no title means no match. True only of the entries that
    MATCH on a title. VS Code's own `os: macos:` branch carries three templates
    and deliberately no `title:` -- a macOS window title does not name the app
    -- and it was never once evaluated: the keycaps stayed blank while the log
    said "no template covers it" (field, 2026-10-16).
    """

    MOD = "polyhost.handler.active_window"

    def _tick(self, mapping, app=("Code", 909), times=1):
        # ⚠️ ONE tick by default. This branch has no debounce of its own -- it
        # acts on the first tick that reaches it -- so a second tick finds
        # nothing changed and answers NONE, which would mask the decision.
        handler = OverlayHandler(mapping)
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=None), \
             patch(self.MOD + ".own_front_app", return_value=None), \
             patch(self.MOD + ".frontmost_app", return_value=app):
            for _ in range(times):
                out = handler._decide_active_window(10, 5)
        return handler, out

    def test_an_APP_NAME_only_entry_is_drawn(self):
        handler, (data, cmd) = self._tick({"code": {"overlay": "vscode.png"}})
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        self.assertIsNotNone(data)
        self.assertEqual(handler.current_entry["overlay"], "vscode.png")

    def test_a_TITLE_constrained_entry_is_NOT_drawn(self):
        # The false positive the flag exists to prevent: with no title there is
        # nothing to test the constraint against, so it fails.
        handler, (data, cmd) = self._tick(
            {"code": {"overlay": "vscode.png", "title": ".* Visual Studio Code"}})
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertIsNone(data)
        self.assertIsNone(handler.current_entry)

    def test_an_app_with_NO_entry_still_disables_for_the_generic_path(self):
        handler, (data, cmd) = self._tick({"other": {"overlay": "x.png"}})
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertEqual(handler.focused_app()[0], "code")

    def test_the_matched_app_name_is_the_one_the_generic_path_asks_about(self):
        # `app_name` is why that field exists: "no template covers this app"
        # and "draw a generic mark for it" must mean the same application.
        handler, _ = self._tick({"code": {"overlay": "vscode.png"}})
        self.assertEqual(handler.app_name, "code")

    def test_a_match_with_NOTHING_to_draw_does_not_keep_the_last_app_up(self):
        # Same rule as the window branch: `last_entry` is dropped so returning
        # is a full OFF_ON, never an ENABLE of another app's mapping.
        handler, (data, cmd) = self._tick({"code": {"remote": "1.2.3.4"}})
        self.assertIsNone(data)
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertIsNone(handler.last_entry)

    def _real_mapping_tick(self, os_type):
        """The reported case, end to end, on the SHIPPED mapping.

        ⚠️ A matcher-level probe is not enough here: the handler supplies the
        OS itself (`_active_os`), and that is what decides which branch of
        `code:` is judged. The first version of this fix looked correct at the
        matcher and still answered DISABLE through the handler, because the
        test machine resolved to Linux.
        """
        import yaml
        # ⚠️ Patched by STRING target, not via a second `import ... as module`:
        # CodeQL flags a module imported with both `import` and `import from`
        # (py/import-and-import-from), and this file already uses the
        # `from ... import` form at the top.
        mod = "polyhost.handler.active_window"
        with open("polyhost/res/overlay-mapping.poly.yaml", encoding="utf-8") as fh:
            handler = OverlayHandler(yaml.safe_load(fh))
        with patch(mod + ".pwc.getActiveWindow", return_value=None), \
             patch(mod + ".own_front_app", return_value=None), \
             patch(mod + ".frontmost_app", return_value=("Code", 909)), \
             patch(mod + ".OverlayHandler._active_os", lambda s: os_type):
            data, cmd = handler._decide_active_window(250, 1000)
        return handler, data, cmd

    def test_VS_CODE_gets_its_mac_templates_with_no_window(self):
        from polyhost.device.command_ids import OsType
        handler, data, cmd = self._real_mapping_tick(OsType.MACOS)
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        self.assertIsNotNone(data, "the reported failure: nothing drawn for 'code'")
        self.assertTrue(
            any("vscode_mac_template" in f for f in handler.current_entry["overlay"]),
            handler.current_entry.get("overlay"))

    def test_VS_CODE_on_LINUX_still_needs_its_title(self):
        # The same entry's `linux:` branch DOES declare
        # `title: .* Visual Studio Code`, so with no window it must not fire --
        # the per-OS half of the same rule.
        from polyhost.device.command_ids import OsType
        handler, data, cmd = self._real_mapping_tick(OsType.LINUX)
        self.assertEqual(cmd, OverlayCommand.DISABLE)
        self.assertIsNone(data)
        self.assertIsNone(handler.current_entry)


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TheSkipMustNotSWALLOWAForcedRefreshTest(unittest.TestCase):
    """⚠️ Every reset that exists to force a re-match must disarm the skip.

    The skip answers "the same app is in front, so nothing changed" -- true of
    the OS, and irrelevant to a caller that has just thrown away what the
    handler knew. `force_resend()` runs after a device reconnect, when the
    keyboard's overlays have been cleared; `invalidate_window_cache()` runs
    when a browser SPA navigates without retitling. Both ask for a re-match on
    the next tick, and the skip would have returned before either reached the
    window query -- leaving a cleared keyboard blank until the user switched
    apps (Greptile P1 and CodeRabbit, independently, #397).
    """

    MOD = "polyhost.handler.active_window"

    def _settled_on_finder(self):
        handler = OverlayHandler({})
        win = MagicMock()
        handler.set_win(win, "", "Finder")
        handler.app_name = "finder"
        handler._macos_front = 4321
        handler._macos_resolved = True
        return handler

    def _ticks_the_query(self, handler):
        """Did the next tick reach `pwc.getActiveWindow()`?"""
        with patch(self.MOD + "._IS_MACOS", True), \
             patch(self.MOD + ".focused_app_pid", return_value=4321), \
             patch(self.MOD + ".own_front_app", return_value=None), \
             patch(self.MOD + ".pwc.getActiveWindow", return_value=None) as query:
            handler._decide_active_window(250, 1000)
        return query.called

    def test_the_skip_is_armed_to_begin_with(self):
        # Guards the premise of the two tests below.
        self.assertFalse(self._ticks_the_query(self._settled_on_finder()))

    def test_force_resend_disarms_it(self):
        handler = self._settled_on_finder()
        handler.force_resend()
        self.assertTrue(self._ticks_the_query(handler),
                        "the OFF_ON force_resend asked for never ran")

    def test_invalidate_window_cache_disarms_it(self):
        handler = self._settled_on_finder()
        handler.invalidate_window_cache()
        self.assertTrue(self._ticks_the_query(handler),
                        "the new URL was never re-matched")


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AWindowlessAppNeverArmsTheSkipTest(unittest.TestCase):
    """⚠️ A pid does not change when an app GAINS a window.

    The windowless branch used to arm the skip, which made the state
    permanent: the user opens or restores a window in the same app, the pid is
    unchanged, so every later tick returned before the query and the window was
    never seen -- and with it the app's title, its template and its harvest
    (Greptile P1, #397). The branch is reached precisely when there is
    something still to find, so it is the one place the skip must not arm.
    """

    MOD = "polyhost.handler.active_window"

    def test_a_window_APPEARING_is_noticed(self):
        handler = OverlayHandler({})
        win = MagicMock()
        win.title = "main.py"
        win.getHandle.return_value = ("Code", "main.py")
        win.getAppName.return_value = "Code"
        with patch(self.MOD + "._IS_MACOS", True), \
             patch(self.MOD + ".focused_app_pid", return_value=909), \
             patch(self.MOD + ".own_front_app", return_value=None), \
             patch(self.MOD + ".frontmost_app", return_value=("Code", 909)), \
             patch(self.MOD + ".app_name_for", return_value="Code"):
            # No window: the app is named from the OS.
            with patch(self.MOD + ".pwc.getActiveWindow", return_value=None):
                handler._decide_active_window(250, 1000)
            self.assertEqual(handler.focused_app()[0], "code")
            # Same app, same pid -- and now it has a window.
            with patch(self.MOD + ".pwc.getActiveWindow", return_value=win) as query:
                for _ in range(8):
                    handler._decide_active_window(250, 1000)
        self.assertTrue(query.called, "the window was never looked for again")
        self.assertEqual(handler.title, "main.py")


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AWindowTitleCannotSPLITALogRecordTest(unittest.TestCase):
    """⚠️ A window title is attacker-influenceable: a web page picks it.

    Logging it as text rather than as a bytes repr -- which is the readability
    fix this PR made -- also stopped escaping control characters, so a title
    carrying a newline could forge an extra log line and split one app-change
    record in a support bundle (Greptile P2, #397). Ordinary Unicode must stay
    readable; only the control characters are escaped.
    """

    def test_a_NEWLINE_in_a_title_does_not_start_a_new_line(self):
        handler = OverlayHandler({})
        handler.win = MagicMock()
        with self.assertLogs(handler.log, level="INFO") as captured:
            handler.log_win("evil", "real title\nINFO    forged line", ("", ""))
        self.assertEqual(len(captured.output), 1)
        self.assertNotIn("\n", captured.output[0])
        self.assertIn("\\n", captured.output[0])

    def test_a_CARRIAGE_RETURN_and_a_TAB_are_escaped_too(self):
        handler = OverlayHandler({})
        handler.win = MagicMock()
        with self.assertLogs(handler.log, level="INFO") as captured:
            handler.log_win("app", "a\rb\tc", 1)
        self.assertIn("a\\rb\\tc", captured.output[0])

    def test_ORDINARY_unicode_stays_readable(self):
        # The reason this is not `.encode('utf-8')`: that mangled every
        # non-ASCII title into \xNN escapes.
        handler = OverlayHandler({})
        handler.win = MagicMock()
        with self.assertLogs(handler.log, level="INFO") as captured:
            handler.log_win("app", "Dokument – Übersicht 日本語", 1)
        self.assertIn("Dokument – Übersicht 日本語", captured.output[0])


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class AWindowlessAppMustNotInheritTheLastURLTest(unittest.TestCase):
    """⚠️ `try_to_match_window` reads `self.current_url`, not an argument.

    `set_win()` cleared `win`, `title`, `handle` and `app_name` but not
    `current_url`, so the windowless match ran against whatever tab the
    PREVIOUS window had reported. With `title_known=False` a `urls-contains`
    branch is still live, so a browser web-app's overlay could be drawn for a
    completely different, windowless application (Revix, #397).

    ⚠️ Revix also named why the other tests miss it: they all start from a
    clean handler, where `current_url` is already None. This one does not.
    """

    MOD = "polyhost.handler.active_window"

    MAPPING = {
        # Shaped like the shipped browser entries: a default overlay plus a
        # per-site branch keyed on the URL.
        "photos": {"overlay": "photos.png",
                   "urls-contains": {"mail.google.com": {"overlay": "gmail.png"}}},
    }

    def test_a_STALE_url_does_not_pick_a_web_app_overlay(self):
        handler = OverlayHandler(dict(self.MAPPING))
        # The previous window was a browser on Gmail.
        handler.current_url = "https://mail.google.com/u/0"
        with patch(self.MOD + ".pwc.getActiveWindow", return_value=None), \
             patch(self.MOD + ".own_front_app", return_value=None), \
             patch(self.MOD + ".frontmost_app", return_value=("Photos", 11)):
            handler._decide_active_window(250, 1000)
        self.assertIsNone(handler.current_url,
                          "the last window's tab outlived its window")
        self.assertEqual(handler.current_entry["overlay"], "photos.png",
                         "Gmail's overlay was drawn for Photos")


if __name__ == "__main__":
    unittest.main()
