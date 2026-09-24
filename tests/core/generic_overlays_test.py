"""The generic overlay set: the app's mark on ESC plus an icon per shortcut key.

A template overlay draws a real icon on every shortcut key. Where no template
covers the focused application, PolyCore falls back to two generic sources --
that application's own mark, and whatever its accessibility tree could say about
its keyboard shortcuts. Template always wins, so these pin the branch that
decides, and the two halves ship as ONE send because a second
`send_overlays_mru` would reset the mapping the first one committed.
"""
import logging
import threading
import unittest
from unittest.mock import MagicMock

import numpy as np

from polyhost.core.poly_core import PolyCore
from polyhost.settings import DEFAULT_SETTINGS
from polyhost.handler.common import OverlayCommand


def _mask():
    m = np.zeros((38, 38), dtype=bool)
    m[8:30, 8:30] = True
    return m


# ⚠️ ONE key is pinned against its shipped default, and it is not an oversight.
# `note_settings_changed(None)` -- what the in-process dialog sends -- runs EVERY
# branch, so answering the real `unicode_send_composition_mode` starts the
# unicode watcher, which then wants half a dozen instance attributes this file
# has no business fixturing. A file whose subject is generic overlays should not
# carry another subsystem's state; pinning the key that reaches it is the
# narrower lie. Every key this file's subject actually reads answers its default.
_FIXTURE_SETTINGS = {"unicode_send_composition_mode": False}


def make_core(*, app=("gimp", None), mask=None, slug="si:gimp", shortcuts=None,
              settings=None):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.mark")
    core.connected = True
    core.safe_mode = False
    core._observers = []
    core._observers_lock = threading.Lock()
    core.worker = MagicMock()
    core.device_mgr = MagicMock()
    core.keeb = MagicMock()
    core.overlay_handler = MagicMock()
    core.overlay_handler.is_remote_mapping_entry.return_value = False
    core.overlay_handler.focused_app.return_value = app
    # No hand-made overlay set covers this window unless a test says so; a bare
    # MagicMock would answer TRUTHY and silently stand the generic half down.
    core.overlay_handler.covered_by_template.return_value = False
    core.poly_settings = MagicMock()
    # ⚠️ The SHIPPED defaults, not a blanket False. This stub answered False to
    # every key, which silently stood down every feature whose default is True
    # and made the failure read as the feature being broken -- 25 tests in this
    # file reporting "nothing was submitted" the moment a master switch landed,
    # none of them about a switch. Same family as the `covered_by_template`
    # comment below: a stub that answers the wrong CONSTANT is indistinguishable
    # from the code under test being wrong.
    overrides = dict(_FIXTURE_SETTINGS, **(settings or {}))
    core.poly_settings.get.side_effect = (
        lambda k: overrides[k] if k in overrides else DEFAULT_SETTINGS.get(k, False))
    # `note_settings_changed(None)` -- what the in-process dialog sends -- runs
    # the brightness branch first, so the fixture has to mirror that too.
    core.sunlight = MagicMock()
    from polyhost.input.unicode_input import get_host_os
    core._last_pushed_os = get_host_os().value

    core._generic_on_device = None
    core._told_no_remote_shortcuts = set()
    core._told_mark_dropped = set()
    # ⚠️ spec'd, and that is the point rather than tidiness: a bare MagicMock
    # answers ANY attribute, so `_app_icons.forget()` -- a method this fetcher
    # has never had -- passed here while raising AttributeError in the real app
    # and silently stopping every generic-icon setting from taking effect
    # (Greptile, #240). A stub that cannot say "no such method" cannot catch a
    # typo in the name of one.
    from polyhost.services.app_icon_fetcher import AppIconFetcher
    from polyhost.services.shortcut_fetcher import ShortcutIconFetcher
    core._app_icons = MagicMock(spec=AppIconFetcher)
    core._app_icons.overlay_for.return_value = (mask, slug)
    core._shortcut_icons = MagicMock(spec=ShortcutIconFetcher)
    core._shortcut_icons.overlays_for.return_value = shortcuts or {}
    # One device, whose settings the converter is built against.
    entry = MagicMock()
    from polyhost.device.device_settings import DeviceSettings
    entry.device.device_settings = DeviceSettings()
    core.device_mgr.all_entries = [entry]
    return core


def _tick(core, data=None, cmd=OverlayCommand.NONE):
    core.overlay_handler.handle_active_window.return_value = (data, cmd)
    core.tick_window_tracking()


class TemplateWinsTest(unittest.TestCase):

    def test_a_TEMPLATE_match_sends_no_generic_mark(self):
        core = make_core(mask=_mask())
        _tick(core, data="gimp_template.mods.png", cmd=OverlayCommand.OFF_ON)
        core._app_icons.overlay_for.assert_not_called()

    def test_a_template_send_FORGETS_what_is_on_the_device(self):
        # ⚠️ The template re-programs the whole pool, so the generic set is
        # gone with it. Without clearing this, switching template-app -> generic-app ->
        # template-app -> generic-app would skip the second generic send.
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)                                        # generic mark sent
        self.assertEqual(core._generic_on_device[0], "si:gimp")
        _tick(core, data="x.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertIsNone(core._generic_on_device)


OFF = {"generic_overlays_fill_gaps": False}


class TemplatePriorityTest(unittest.TestCase):
    """A hand-made set wins, and it keeps winning after tick 1.

    ⚠️ Scoped to `generic_overlays_fill_gaps: False`, which is a real shipped
    position and not a way to keep old assertions passing: off means a templated
    app shows exactly what its author drew and costs no harvest at all. The ON
    position -- where the two ride ONE send and the template wins per KEY rather
    than per window -- is `TemplateGapFillTest` below. The regression these were
    written for (the generic set overwriting a live template a second after it
    appeared) is impossible in either, for different reasons: here nothing
    generic is sent, there it is the same send.
    """

    def test_the_generic_set_does_NOT_overwrite_a_live_template(self):
        # ⚠️ The regression, reported from hardware as "icons where we have
        # overlays take priority, which is not the case right now". The template
        # arrives on the tick the window changes; on EVERY tick after that
        # `handle_active_window` answers (None, NONE) for the same window, so the
        # old `else` branch fired, `send_overlays_mru` reset the mapping the
        # template had just committed, and the hand-made keycaps went blank about
        # a second after appearing.
        core = make_core(mask=_mask(), shortcuts=_sc(), settings=OFF)
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core, data="gimp_template.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertEqual(core.worker.submit.call_count, 1)      # the template
        for _ in range(5):
            _tick(core)                                         # same window
        self.assertEqual(core.worker.submit.call_count, 1)      # and nothing else

    def test_it_is_asked_the_HANDLER_not_the_returned_data(self):
        # The data is the tell that a template was JUST SENT; the handler is the
        # only thing that knows one is STILL ACTIVE.
        core = make_core(mask=_mask(), shortcuts=_sc(), settings=OFF)
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)                       # no data, no command, template active
        core.worker.submit.assert_not_called()

    def test_leaving_a_templated_app_hands_the_board_BACK_to_the_generic_set(self):
        core = make_core(mask=_mask(), shortcuts=_sc(), settings=OFF)
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)
        core.worker.submit.assert_not_called()
        core.overlay_handler.covered_by_template.return_value = False
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_covered_window_costs_NO_fetch_at_all(self):
        # Not merely "sends nothing": a template-covered app must not walk
        # another process's accessibility tree either.
        core = make_core(mask=_mask(), shortcuts=_sc(), settings=OFF)
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)
        core._app_icons.overlay_for.assert_not_called()
        core._shortcut_icons.overlays_for.assert_not_called()


class GenericMarkTest(unittest.TestCase):

    def test_no_template_and_a_mask_QUEUES_the_mark(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"],
                         "overlay")
        self.assertEqual(core._generic_on_device[0], "si:gimp")

    def test_it_emits_THINKING_like_any_other_overlay_send(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        events = []
        core.subscribe(lambda n, p: events.append((n, p)))
        _tick(core)
        self.assertIn(("overlay_activity", {"state": "thinking"}), events)

    def test_the_SAME_app_is_not_resent_every_tick(self):
        # The tick runs continuously; only a change may cost a transfer.
        core = make_core(mask=_mask(), shortcuts=_sc())
        for _ in range(5):
            _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_DIFFERENT_app_is_sent(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core._app_icons.overlay_for.return_value = (_mask(), "si:inkscape")
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 2)
        self.assertEqual(core._generic_on_device[0], "si:inkscape")

    def test_a_mark_with_NO_shortcuts_is_NOT_drawn(self):
        """⚠️ The mark is CONFIRMATION, not recognition.

        Alone on an otherwise unchanged board it says "this app was
        recognised" and is read as "this app has icons" — a promise the next
        glance disproves. Blank at least says nothing. Reported from hardware:
        *"I see it as confirmation that we have something."*
        """
        core = make_core(mask=_mask(), shortcuts={})
        _tick(core)
        core.worker.submit.assert_not_called()
        self.assertIsNone(core._generic_on_device)

    def test_the_POLYKYBD_mark_on_our_own_window_IS_drawn_alone(self):
        """The one exemption: our logo on our window promises nothing about
        another program, and on macOS our windows expose no shortcuts."""
        from polyhost.services.app_icons import POLYKYBD_SLUG
        core = make_core(app=("polyhost", None), mask=_mask(),
                         slug=POLYKYBD_SLUG, shortcuts={})
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)
        self.assertEqual(core._generic_on_device[0], POLYKYBD_SLUG)

    def test_the_mark_IS_drawn_once_a_single_shortcut_resolves(self):
        """The control. Without it the test above passes for a mark that is
        never drawn at all."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)
        self.assertEqual(core._generic_on_device[0], "si:gimp")

    def test_shortcuts_with_NO_mark_still_send(self):
        """⚠️ The rule is one-directional. Icons without a mark are fine — they
        are the payload; a mark without icons is not, because it is only ever a
        label for them. An app the catalogs do not carry still gets its
        shortcut icons."""
        core = make_core(mask=None, slug=None, shortcuts=_sc())
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_NO_mask_yet_sends_nothing_and_claims_nothing(self):
        # First sighting: the fetch was queued, nothing is drawable yet. The
        # tick after it resolves is what sends — no callback races the focus.
        core = make_core(mask=None)
        _tick(core)
        core.worker.submit.assert_not_called()
        self.assertIsNone(core._generic_on_device)

    def test_an_app_we_cannot_NAME_is_skipped(self):
        core = make_core(app=(None, None), mask=_mask())
        _tick(core)
        core._app_icons.overlay_for.assert_not_called()


def _sc(concept="save", modifier=1, keycode=0x16):
    """One rendered shortcut icon, in the shape `shortcut_overlays.render` makes."""
    return {f"@sc:{concept}:32lower_left": {(modifier, keycode): _mask()}}


class ShortcutIconTest(unittest.TestCase):
    """The second generic source: an icon on every key the app named."""

    def test_shortcut_icons_ride_the_SAME_send_as_the_mark(self):
        # ⚠️ Not a nicety -- `send_overlays_mru` calls `prepare_for_mru_send()`,
        # which RESETS the firmware's whole display->pool mapping and then
        # commits the one it built from the filenames it was given. A second
        # call replaces the first rather than adding to it, so sending the mark
        # and then the icons would leave only the icons and waste the upload.
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)
        core.worker.submit.call_args.args[1](threading.Event())
        entry = core.device_mgr.all_entries[0]
        self.assertEqual(entry.device.send_overlays_mru.call_count, 1)
        names = entry.device.send_overlays_mru.call_args.args[0]
        self.assertEqual(names, ["@prog:si:gimp", "@sc:save:32lower_left"])

    def test_the_MARK_goes_first_so_it_keeps_ESC(self):
        # Both sources are synthetic and `send_overlays_mru` gives an earlier
        # synthetic source the key, so order decides who owns Escape. The mark
        # is the one keycap that means the same thing in every application.
        core = make_core(mask=_mask(),
                         shortcuts=_sc(concept="close", keycode=0x29))   # KC_ESCAPE
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        names = core.device_mgr.all_entries[0].device.send_overlays_mru.call_args.args[0]
        self.assertEqual(names[0], "@prog:si:gimp")

    def test_shortcuts_ALONE_still_send_when_the_app_has_no_mark(self):
        # The two halves are independent: an app whose own icon does not survive
        # 1-bit can still have a readable accessibility tree.
        core = make_core(mask=None, slug=None, shortcuts=_sc())
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        names = core.device_mgr.all_entries[0].device.send_overlays_mru.call_args.args[0]
        self.assertEqual(names, ["@sc:save:32lower_left"])

    def test_NEITHER_half_sends_nothing_and_claims_nothing(self):
        core = make_core(mask=None, slug=None, shortcuts={})
        _tick(core)
        core.worker.submit.assert_not_called()
        self.assertIsNone(core._generic_on_device)

    def test_the_same_app_is_not_resent_every_tick(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        for _ in range(5):
            _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_the_signature_carries_the_KEYS_not_just_the_concepts(self):
        # ⚠️ Two applications routinely resolve the SAME concepts -- Save, Copy,
        # Paste -- while binding them to different chords. A name-only signature
        # would report the second app as already on the device, and its icons
        # would land on the first app's keys or nowhere at all.
        core = make_core(mask=_mask(), shortcuts=_sc(keycode=0x16))
        _tick(core)
        core._shortcut_icons.overlays_for.return_value = _sc(keycode=0x17)
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 2)

    def test_a_shortcut_appearing_LATER_is_sent_without_the_app_changing(self):
        """The harvest is slow and runs off the tick, so the first sighting of
        an app resolves nothing. The pass after the tree walk finishes has to
        send, or the icons appear only the SECOND time you focus the app.

        ⚠️ The first tick now sends NOTHING rather than the mark alone — see
        `_generic_signature`. The property under test is unchanged and is the
        one that matters: a late harvest must not be missed. What moved is that
        the board goes from blank to complete in one step instead of showing a
        mark that promises icons which are not there yet."""
        core = make_core(mask=_mask(), shortcuts={})
        _tick(core)
        core.worker.submit.assert_not_called()
        core._shortcut_icons.overlays_for.return_value = _sc()
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_every_key_of_one_concept_rides_ONE_source(self):
        # The pixels do not depend on the key, so a concept is one pool slot
        # however many chords it lands on -- which is the opposite of the
        # signature rule above and is why they are two different tuples.
        core = make_core(mask=None, slug=None, shortcuts={
            "@sc:save:32lower_left": {(1, 0x16): _mask(), (3, 0x16): _mask()}})
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        call = core.device_mgr.all_entries[0].device.send_overlays_mru.call_args
        self.assertEqual(call.args[0], ["@sc:save:32lower_left"])
        self.assertEqual(len(call.kwargs["synthetic"]["@sc:save:32lower_left"]), 2)

    def test_a_template_match_asks_the_shortcut_fetcher_NOTHING(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core, data="gimp_template.mods.png", cmd=OverlayCommand.OFF_ON)
        core._shortcut_icons.overlays_for.assert_not_called()


class ShutdownTest(unittest.TestCase):

    def test_BOTH_fetcher_threads_are_told_to_stand_down(self):
        # ⚠️ Both are daemon threads, and the shortcut one may be mid-tree-walk
        # over another process. An un-stopped fetcher can resolve an app into a
        # stopped worker after shutdown.
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core._tick_stop = threading.Event()
        core._tick_thread = None
        core._wincompose_lock = threading.Lock()
        try:
            core.shutdown()
        except Exception:
            pass                   # the rest of shutdown() is not under test
        core._app_icons.stop.assert_called_once()
        core._shortcut_icons.stop.assert_called_once()


class SettingsChangeTest(unittest.TestCase):
    """A settings change has to reach BOTH caches and the device signature."""

    def _core(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        return core

    def test_turning_the_feature_off_re_harvests(self):
        core = self._core()
        core.note_settings_changed({"shortcut_icons_enabled"})
        core._shortcut_icons.forget.assert_called_once()
        # ⚠️ `forget_misses`. This line said `forget` and passed against an
        # unspec'd MagicMock, asserting a call to a method the fetcher does not
        # have — the same nonexistent name the code was calling. Two halves of
        # one mistake, agreeing with each other.
        core._app_icons.forget_misses.assert_called_once()

    def test_a_SIZE_change_forgets_what_is_on_the_device(self):
        # ⚠️ The caches alone are not enough. A height change alters the PIXELS
        # while the plan -- and therefore the source names the signature is built
        # from -- may be identical, so the tick would report the new masks as
        # already sent and draw nothing.
        core = self._core()
        self.assertIsNotNone(core._generic_on_device)
        core.note_settings_changed({"shortcut_icon_height"})
        self.assertIsNone(core._generic_on_device)

    def test_an_UNRELATED_setting_costs_no_re_harvest(self):
        core = self._core()
        core.note_settings_changed({"ui_theme"})
        core._shortcut_icons.forget.assert_not_called()
        self.assertIsNotNone(core._generic_on_device)

    def test_a_dialog_that_names_NOTHING_re_harvests(self):
        # `keys=None` is all the in-process dialog knows.
        core = self._core()
        core.note_settings_changed(None)
        core._shortcut_icons.forget.assert_called_once()


class ForwardedShortcutsTest(unittest.TestCase):
    """A forwarded app runs on the OTHER machine, so its tree is read THERE.

    ⚠️ The harvest reads a LOCAL accessibility backend -- AT-SPI here, UI
    Automation on Windows -- so for an app on the other machine it walks the
    wrong tree, finds nothing, and reports "the app exposes no accelerators".
    Measured from a real log: a Windows daemon reported 0 shortcut icons for a
    gnome-terminal whose own machine exposes 16. The forwarder therefore
    harvests and relays the shortcuts as text, exactly as it already relays the
    program mark's identity, and this class pins the three states that relay
    can be in.
    """

    def _remote(self, relayed=None, **kw):
        core = make_core(**kw)
        core.overlay_handler.is_remote_mapping_entry.return_value = True
        core.overlay_handler.remote_handler.forwarded_shortcuts.return_value = relayed
        return core

    def test_nothing_relayed_YET_asks_the_local_backend_NOTHING(self):
        core = self._remote(relayed=None, mask=_mask())
        _tick(core)
        core._shortcut_icons.overlays_for.assert_not_called()

    def test_a_RELAYED_harvest_is_planned_and_rendered_here(self):
        # The division of labour: the other machine harvests, this one decides
        # what each label means and rasters it at this keyboard's height.
        relayed = ({"label": "Save"},)
        core = self._remote(relayed=relayed, mask=_mask())
        _tick(core)
        core._shortcut_icons.overlays_for.assert_called_once_with(
            "gimp", harvested=relayed)

    def test_an_EMPTY_relayed_harvest_is_still_an_ANSWER(self):
        # ⚠️ `()` and None are different and the gap between them is the bug
        # this guards: `()` means the forwarder looked and the app exposes
        # nothing, so it must reach the fetcher (which caches it and says so).
        # Skipping it would leave the core asking on every single tick.
        core = self._remote(relayed=(), mask=_mask())
        _tick(core)
        core._shortcut_icons.overlays_for.assert_called_once_with(
            "gimp", harvested=())

    def test_NOTHING_goes_out_while_the_relay_is_in_flight(self):
        """⚠️ INVERTED on 2026-09-19, and the old reason is worth keeping: this
        asserted the mark went out alone, on the grounds that "losing the mark
        while waiting for shortcuts would be a regression".

        It is not, once the mark's job is understood as CONFIRMATION that the
        rest of the board means something. A forwarded app whose relay has not
        answered has nothing behind the mark, and the two cases the user sees
        are indistinguishable at that moment: a relay still in flight (the icons
        arrive a second later) and a forwarder too old to send them (they never
        do). Showing the mark makes the same promise in both."""
        core = self._remote(relayed=None, mask=_mask())
        _tick(core)
        core.worker.submit.assert_not_called()

    def test_the_mark_and_the_RELAYED_icons_arrive_TOGETHER(self):
        """The other half: once the relay answers, both go in one send."""
        core = self._remote(relayed=[[1, 22, "Save"]], mask=_mask())
        core._shortcut_icons.overlays_for.return_value = _sc()
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        names = core.device_mgr.all_entries[0].device.send_overlays_mru.call_args.args[0]
        self.assertEqual(names[0], "@prog:si:gimp")
        self.assertGreater(len(names), 1, "the icons must ride the same send")

    def test_it_says_WHY_at_INFO_once_per_app(self):
        # Not a failure to debug: this feature decides on its own what to draw
        # on ~20 keycaps, so "it drew nothing" needs a readable reason.
        core = self._remote(relayed=None, mask=_mask())
        with self.assertLogs("test.polycore.mark", level="INFO") as caught:
            for _ in range(4):
                _tick(core)
        said = [m for m in caught.output if "runs on the FORWARDER" in m]
        self.assertEqual(len(said), 1, said)

    def test_a_LOCAL_window_is_still_harvested(self):
        core = make_core(mask=_mask())
        _tick(core)
        # ⚠️ No `harvested=` kwarg: a local app's tree IS readable here, and
        # passing one would route it down the relay path and never look.
        call = core._shortcut_icons.overlays_for.call_args
        self.assertEqual(call.args, ("gimp",))
        self.assertNotIn("harvested", call.kwargs)

    def test_a_LOCAL_window_passes_its_PID_to_the_HARVEST_too(self):
        """⚠️ The same pid the OS-icon route takes. Without it the macOS
        backend harvests whatever NSWorkspace calls frontmost — a value frozen
        on the fetcher's worker thread, measured in the field as every app but
        one refusing with a focus race that had not happened (2026-09-21)."""
        core = make_core(mask=_mask())
        core.overlay_handler.focused_pid.return_value = 4242
        _tick(core)
        self.assertEqual(
            core._shortcut_icons.overlays_for.call_args.kwargs["pid"], 4242)


class ForwardedTest(unittest.TestCase):

    def test_a_FORWARDED_identity_is_passed_to_the_fetcher(self):
        # ⚠️ The whole point of the forwarder transport: the app runs on the
        # other machine, so its identity was resolved there. Re-resolving it
        # here would read the wrong computer's OS — and a Windows keyboard
        # machine has no .desktop entries at all.
        from polyhost.services.os_app_icon import AppIdentity
        ident = AppIdentity(icon=b"PNG", icon_path="/x.png", names=("GIMP",))
        core = make_core(app=("gimp", ident), mask=_mask())
        _tick(core)
        self.assertIs(core._app_icons.overlay_for.call_args.kwargs["identity"],
                      ident)

    def test_a_LOCAL_window_passes_no_identity(self):
        core = make_core(app=("gimp", None), mask=_mask())
        _tick(core)
        self.assertIsNone(core._app_icons.overlay_for.call_args.kwargs["identity"])

    def test_a_DROPPED_mark_says_so_ONCE_at_INFO(self):
        """⚠️ The rule is deliberate — no shortcuts means no send, INCLUDING the
        mark — but it was INVISIBLE from the log. The only INFO line was the
        fetcher announcing a mark it had BUILT (`Program icon for 'terminal':
        os:Terminal.icns`), which is not the same thing as one reaching the
        keyboard, so a blank keycap read as the icon having failed rather than
        having been suppressed on purpose (field, macOS, 2026-09-21).
        """
        core = make_core(app=("terminal", None), mask=_mask())
        core._shortcut_icons.overlays_for.return_value = {}
        with self.assertLogs(core.log, level="INFO") as captured:
            _tick(core)
            _tick(core)                       # the SECOND tick must stay quiet
        dropped = [l for l in captured.output if "Nothing drawn for 'terminal'" in l]
        self.assertEqual(len(dropped), 1, captured.output)
        self.assertIn("not sent on its own", dropped[0])

    def test_an_app_with_NO_mark_at_all_is_not_told(self):
        """The fetchers report their own misses. This line is only for the case
        where something WAS built and then discarded."""
        core = make_core(app=("terminal", None), mask=None)
        core._shortcut_icons.overlays_for.return_value = {}
        core._app_icons.overlay_for.return_value = (None, None)
        with self.assertLogs(core.log, level="INFO") as captured:
            core.log.info("marker")           # assertLogs needs at least one
            _tick(core)
        self.assertFalse([l for l in captured.output if "Nothing drawn" in l],
                         captured.output)

    def test_a_LOCAL_window_passes_its_PID(self):
        """⚠️ The regression that made the OS-icon route DEAD, on every platform.

        `overlay_for(pid=...)` and `os_app_icon.app_identity(pid, ...)` have
        taken a pid all along, and this file's other tests pass one -- but the
        one production caller passed neither it nor an identity for a local
        window. `app_identity` resolves no pid of its own, so every local app
        logged `(OS names: <none>)` and fell through to the catalog, which is
        the half that needs a brand to exist. Measured on macOS, where the
        app's own `.icns` sits in the bundle the pid would have found
        (field, 2026-09-21).
        """
        core = make_core(app=("gimp", None), mask=_mask())
        core.overlay_handler.focused_pid.return_value = 4242
        _tick(core)
        self.assertEqual(core._app_icons.overlay_for.call_args.kwargs["pid"], 4242)


class FailurePathTest(unittest.TestCase):

    def test_a_CANCELLED_send_forgets_the_mark_so_it_can_be_retried(self):
        # ⚠️ The slug is recorded BEFORE the send, so a superseded job has to put
        # it back — otherwise the app is permanently believed to be marked and
        # never gets one.
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        job = core.worker.submit.call_args.args[1]
        cancel = threading.Event()
        cancel.set()
        job(cancel)
        self.assertIsNone(core._generic_on_device)

    def test_a_RAISING_send_forgets_the_mark_and_warns(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        events = []
        core.subscribe(lambda n, p: events.append(n))
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.worker.submit.call_args.args[1](threading.Event())
        self.assertIsNone(core._generic_on_device)
        self.assertIn("overlay_warning", events)

    def test_the_send_names_the_SYNTHETIC_source(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        entry = core.device_mgr.all_entries[0]
        args, kwargs = entry.device.send_overlays_mru.call_args
        self.assertEqual(args[0][0], "@prog:si:gimp")      # the mark keeps ESC
        self.assertIn("@prog:si:gimp", kwargs["synthetic"])
        self.assertLessEqual(set(args[0]), set(kwargs["synthetic"]))




class TemplateGapFillTest(unittest.TestCase):
    """`generic_overlays_fill_gaps` ON: the two ride ONE send.

    ⚠️ The precedence that makes this safe is NOT here -- it is in
    `send_overlays_mru`, which skips a synthetic source on any (modifier,
    keycode) a real one already claimed. What this class pins is the half the
    core owns: that the template files are FOUND, that they go FIRST in the
    list, and that they are found from the handler rather than from what
    `handle_active_window` returned.
    """

    def test_a_covered_window_IS_filled(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_the_TEMPLATE_files_go_FIRST_in_the_send(self):
        """⚠️ Positional, because `send_overlays_mru` walks the list in order and
        a real source claims its keys unconditionally. Last, and a template with
        a baked `program_icon:` would lose ESC to the generic mark — the exact
        inversion of "the hand-made design always wins"."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        sent = entry.device.send_overlays_mru.call_args
        if sent is None:                       # the send runs on the worker
            core.worker.submit.call_args.args[1](threading.Event())
            sent = entry.device.send_overlays_mru.call_args
        filenames, synthetic = sent.args[0], sent.kwargs["synthetic"]
        self.assertTrue(filenames[0].endswith("gimp_template.mods.png"))
        self.assertNotIn(filenames[0], synthetic)
        self.assertLessEqual(set(filenames[1:]), set(synthetic))

    def test_the_file_list_comes_from_the_HANDLER_not_the_returned_data(self):
        """⚠️ The 2026-09-18 field bug, reachable again through a different door.
        `handle_active_window` returns the filenames ONLY on the tick the window
        changes, and the fill runs on the tick the shortcuts resolve — several
        later. Taken from `data` the list would be empty exactly when it matters,
        the synthetic sources would go alone, and `prepare_for_mru_send`'s reset
        would blank every hand-made keycap."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)                            # NO data on this tick
        entry = core.device_mgr.all_entries[0]
        core.worker.submit.call_args.args[1](threading.Event())
        filenames = entry.device.send_overlays_mru.call_args.args[0]
        self.assertTrue(any("gimp_template" in f for f in filenames))

    def test_a_template_with_NOTHING_generic_to_add_is_not_re_sent(self):
        """⚠️ No mark and no shortcuts is not "send the template again" — it is
        already on the device from the change tick, and a send would pay a full
        mapping rebuild to change nothing."""
        core = make_core(mask=None, slug=None, shortcuts={})
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        core.worker.submit.assert_not_called()

    def test_the_signature_separates_two_apps_with_the_SAME_generic_half(self):
        """Same mark, same shortcuts, different template: the second must still
        send, or its template never reaches the device."""
        sig_a = PolyCore._generic_signature("si:gimp", _sc(), ("a.mods.png",))
        sig_b = PolyCore._generic_signature("si:gimp", _sc(), ("b.mods.png",))
        self.assertNotEqual(sig_a, sig_b)


class GenericOverlayMasterSwitchTest(unittest.TestCase):

    def test_OFF_draws_nothing_on_an_app_with_no_template(self):
        core = make_core(mask=_mask(), shortcuts=_sc(),
                         settings={"generic_overlays_enabled": False})
        _tick(core)
        core.worker.submit.assert_not_called()
        core._app_icons.overlay_for.assert_not_called()
        core._shortcut_icons.overlays_for.assert_not_called()

    def test_OFF_also_stops_the_gap_fill(self):
        """⚠️ The master switch is OUTSIDE the fill branch, so it wins whatever
        `fill_gaps` says. A ladder whose lower rung could override the upper one
        would make "turn the whole thing off" untrue."""
        core = make_core(mask=_mask(), shortcuts=_sc(),
                         settings={"generic_overlays_enabled": False,
                                   "generic_overlays_fill_gaps": True})
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        core.worker.submit.assert_not_called()

    def test_OFF_does_not_stop_a_TEMPLATE_send(self):
        """It governs the generic path only — a hand-made overlay is not it."""
        core = make_core(settings={"generic_overlays_enabled": False})
        _tick(core, data="gimp_template.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_BOTH_ship_ON(self):
        """The shipped position, asserted rather than assumed: this is what a
        user gets before touching anything, and the whole feature is invisible
        if either default flips."""
        self.assertIs(DEFAULT_SETTINGS["generic_overlays_enabled"], True)
        self.assertIs(DEFAULT_SETTINGS["generic_overlays_fill_gaps"], True)

    def test_it_drops_the_NEGATIVE_cache_of_the_mark_fetcher(self):
        """⚠️ `forget_misses`, and the name matters. `forget` does not exist on
        `AppIconFetcher`; calling it raised before the two lines after it, so no
        generic-icon setting took effect mid-session at all."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.note_settings_changed({"shortcut_icon_auto_fetch"})
        core._app_icons.forget_misses.assert_called_once_with()
        core._shortcut_icons.forget.assert_called_once_with()

    def test_it_makes_the_BOARD_follow_not_just_the_caches(self):
        """⚠️ Turning a switch OFF means no generic send will happen, so the
        icons already mapped on the keycaps would stay until the next app
        switch — a setting that visibly does nothing. `force_resend` makes the
        next tick re-evaluate the window as if it had changed."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.note_settings_changed({"generic_overlays_enabled"})
        core.overlay_handler.force_resend.assert_called_once_with()

    def test_it_survives_having_NO_window_handler(self):
        """Headless with no display: `overlay_handler` is None and a settings
        change must not raise."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler = None
        core.note_settings_changed({"generic_overlays_enabled"})
        self.assertIsNone(core._generic_on_device)

    def test_TOGGLING_either_one_re_evaluates(self):
        """⚠️ Without this a mid-session flip does nothing until the next app
        switch: the tick reads `_generic_on_device` and reports the set as
        already there. `_forget_generic_overlays` clears exactly that."""
        for key in ("generic_overlays_enabled", "generic_overlays_fill_gaps"):
            with self.subTest(key=key):
                core = make_core(mask=_mask(), shortcuts=_sc())
                core._generic_on_device = ("something", (), ())
                core.note_settings_changed({key})
                self.assertIsNone(core._generic_on_device)




class StaleGenericClearTest(unittest.TestCase):
    """Leaving an app whose generic set IS on the device must clear the keycaps.

    Field report, 2026-09-21, over a forwarder: gnome-terminal relayed 21
    shortcuts and got its generic set, then Calculator and Videos relayed 0 --
    and the terminal's icons stayed on the keycaps in both. Two defects
    compound to produce that, and each is pinned separately below because
    either one alone still leaves a stale board reachable.
    """

    def test_a_generic_send_TELLS_THE_HANDLER_overlays_are_now_on(self):
        """⚠️ THE DESYNC, and it is what actually kept the icons up.

        `send_overlays_mru` ends with `enable_overlays()`, so after any generic
        send the DEVICE is showing overlays -- but the handler's
        `overlays_enabled` was never told, because the generic path is driven by
        no `OverlayCommand` at all. Its `_is_redundant_overlay_cmd` then swallows
        the very DISABLE that would clear them, as already-off. From the first
        generic send onward the handler can never disable overlays again.
        """
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core.overlay_handler.note_overlay_state.assert_called_once_with(True)

    def test_an_app_with_NOTHING_generic_clears_what_the_last_one_left(self):
        """Nothing to draw is not nothing to do: the previous app's icons are
        still mapped, and only a send with an empty source list resets them."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)                                   # terminal: 21 shortcuts
        self.assertIsNotNone(core._generic_on_device)
        core.worker.submit.reset_mock()

        core._app_icons.overlay_for.return_value = (_mask(), "os:calculator")
        core._shortcut_icons.overlays_for.return_value = {}   # calc: none
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1,
                         "the stale set was left on the keycaps")
        self.assertIsNone(core._generic_on_device)

    def test_it_does_NOT_send_when_the_board_is_already_clear(self):
        """The clear is armed by `_generic_on_device`, so an app that resolves
        nothing after another app that resolved nothing costs no HID at all --
        otherwise every tick on an unsupported app queues a reset."""
        core = make_core(mask=_mask(), shortcuts={})
        _tick(core)
        core.worker.submit.assert_not_called()

    def test_a_DISABLE_forgets_what_it_wiped(self):
        """⚠️ Symmetrical to the template send at the OFF_ON branch, and needed
        for the same reason: a DISABLE blanks the board, so a later return to
        the app whose signature we still hold would be deduped away and its
        icons would never come back.
        """
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        self.assertIsNotNone(core._generic_on_device)
        # The master switch off isolates the DISABLE branch: the generic path
        # would otherwise run on the same tick and re-send the very set whose
        # forgetting is under test.
        core.poly_settings.get.side_effect = (
            lambda k: False if k == "generic_overlays_enabled"
            else DEFAULT_SETTINGS.get(k, False))
        _tick(core, cmd=OverlayCommand.DISABLE)
        self.assertIsNone(core._generic_on_device)

    def test_the_fill_case_clears_the_GENERIC_half_and_keeps_the_TEMPLATE(self):
        """⚠️ The clear re-sends the template files rather than an empty list.
        `prepare_for_mru_send()` resets the whole mapping, so clearing with an
        empty list under `fill_gaps` would blank every hand-made keycap -- the
        2026-09-18 field bug, reached through yet another door."""
        core = make_core(mask=_mask(), shortcuts=_sc(),
                         settings={"generic_overlays_fill_gaps": True})
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        self.assertIsNotNone(core._generic_on_device)
        core.worker.submit.reset_mock()

        core._shortcut_icons.overlays_for.return_value = {}
        core._app_icons.overlay_for.return_value = (None, None)
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)
        self.assertIsNone(core._generic_on_device)

        # ⚠️ WHAT is sent, not merely that something was. A clear that passed an
        # empty list would still satisfy the count above while wiping every
        # hand-made keycap -- which is the whole failure this branch exists to
        # avoid, and it escaped the first version of this test.
        core.worker.submit.call_args.args[1](threading.Event())
        entry = core.device_mgr.all_entries[0]
        args, kwargs = entry.device.send_overlays_mru.call_args
        from polyhost.core.poly_core import get_overlay_path
        self.assertEqual(args[0], [get_overlay_path("gimp_template.mods.png")])
        self.assertEqual(kwargs["synthetic"], {})

    def test_the_ordinary_clear_sends_an_empty_list(self):
        """No template, so the reset inside `send_overlays_mru` IS the clear:
        nothing is mapped and no keycap draws."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core.worker.submit.reset_mock()
        core._shortcut_icons.overlays_for.return_value = {}
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        entry = core.device_mgr.all_entries[0]
        args, kwargs = entry.device.send_overlays_mru.call_args
        self.assertEqual(args[0], [])
        self.assertEqual(kwargs["synthetic"], {})

    def test_a_FAILED_clear_is_retried_rather_than_forgotten(self):
        """⚠️ The signature is dropped BEFORE the submit so a tick landing
        mid-flight does not queue a second clear -- so a clear that raises has
        to re-arm it, or the stale icons stay up and nothing will ever try
        again.

        ⚠️ Asserted as "armed", NOT as "the old signature came back". The first
        version of this test pinned the restore itself, which is how the
        partial-clear defect below got written: putting `previous` back is one
        way to arm the retry and it also claims a set is on a keyboard that was
        already cleared. A pinned behaviour is only as good as the reason it
        was pinned."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        events = []
        core.subscribe(lambda n, p: events.append(n))
        _tick(core)
        core._shortcut_icons.overlays_for.return_value = {}
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.worker.submit.call_args.args[1](threading.Event())
        self.assertIsNotNone(core._generic_on_device)     # the retry is armed
        self.assertIn("overlay_warning", events)

        core.worker.submit.reset_mock()
        _tick(core)                                       # …and it fires
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_FAILED_send_re_arms_the_handler_too(self):
        """`prepare_for_mru_send()` clears the firmware's use_overlay bits at the
        very start, so a send that died partway leaves the keycaps blank whether
        or not `enable_overlays()` was reached. The optimistic True recorded at
        submit time has to be taken back, or the handler believes overlays are
        showing and the board and the host disagree from then on."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.overlay_handler.note_overlay_state.reset_mock()
        core.worker.submit.call_args.args[1](threading.Event())
        core.overlay_handler.note_overlay_state.assert_called_once_with(False)

    def test_the_clear_reports_the_state_the_BOARD_is_left_in(self):
        """⚠️ Under `fill_gaps` the clear re-sends the template, so
        `send_overlays_mru`'s trailing `enable_overlays()` leaves overlays ON --
        reporting them off would suppress the DISABLE that leaving this
        application issues, and the template's icons would stay up on the next
        app. With no template nothing is mapped, so off is the truth."""
        core = make_core(mask=_mask(), shortcuts=_sc(),
                         settings={"generic_overlays_fill_gaps": True})
        core.overlay_handler.covered_by_template.return_value = True
        core.overlay_handler.get_overlay_data.return_value = "gimp_template.mods.png"
        _tick(core)
        core._shortcut_icons.overlays_for.return_value = {}
        core._app_icons.overlay_for.return_value = (None, None)
        _tick(core)
        core.overlay_handler.note_overlay_state.reset_mock()
        core.worker.submit.call_args.args[1](threading.Event())
        core.overlay_handler.note_overlay_state.assert_called_once_with(True)

        bare = make_core(mask=_mask(), shortcuts=_sc())
        _tick(bare)
        bare._shortcut_icons.overlays_for.return_value = {}
        _tick(bare)
        bare.overlay_handler.note_overlay_state.reset_mock()
        bare.worker.submit.call_args.args[1](threading.Event())
        bare.overlay_handler.note_overlay_state.assert_called_once_with(False)

    def test_a_PARTIAL_clear_does_not_claim_the_old_set_is_still_up(self):
        """⚠️ TWO KEYBOARDS, and the second one fails after the first cleared.

        Restoring `previous` says "that set is on every device", which is now
        false of the keyboard that DID clear. Switch back to that application
        and the signature matches, the send is skipped, and the cleared
        keyboard stays blank forever while the host believes it is decorated.

        The send path has never had this hazard because it fails to `None` --
        "claim nothing", so the next tick re-sends to everyone and a device
        that already had the set takes it as a cache hit. The clear cannot use
        `None`: that is also what arms it, so the retry would stop. Hence a
        value that is neither -- it never equals a real signature, so a send
        always proceeds, and it is not None, so the clear still retries.
        (Greptile P1, #240.)
        """
        core = make_core(mask=_mask(), shortcuts=_sc())
        second = MagicMock()
        from polyhost.device.device_settings import DeviceSettings
        second.device.device_settings = DeviceSettings()
        core.device_mgr.all_entries.append(second)
        _tick(core)
        signature = core._generic_on_device
        core.worker.submit.call_args.args[1](threading.Event())   # the real send

        core._shortcut_icons.overlays_for.return_value = {}
        _tick(core)
        ok, bad = core.device_mgr.all_entries
        bad.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.worker.submit.call_args.args[1](threading.Event())

        # The first keyboard really was cleared, so the old signature is a lie.
        self.assertNotEqual(core._generic_on_device, signature)
        # ...and the clear is still armed, so the failed device is retried.
        self.assertIsNotNone(core._generic_on_device)

        # The decisive half: going back to that application must SEND again.
        core.worker.submit.reset_mock()
        core._shortcut_icons.overlays_for.return_value = _sc()
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1,
                         "the cleared keyboard would stay blank")

    def test_a_CANCELLED_clear_leaves_the_board_to_whatever_superseded_it(self):
        """A cancel means a template send, another app's set or a DISABLE is
        already on its way, and each of those programs the board and sets the
        handler state itself. Re-arming the signature here would make that
        superseding set look stale and suppress it."""
        core = make_core(mask=_mask(), shortcuts=_sc())
        _tick(core)
        core._shortcut_icons.overlays_for.return_value = {}
        _tick(core)
        cancel = threading.Event()
        cancel.set()
        core.worker.submit.call_args.args[1](cancel)
        self.assertIsNone(core._generic_on_device)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.assert_not_called()


class TitleTickDoesNotFlickerTest(unittest.TestCase):
    """A DISABLE while a generic set is up is left to the generic path.

    Field report, 2026-09-24: an AI agent in a forwarded gnome-terminal spun a
    spinner in the window title once a second. Every frame made the handler
    answer DISABLE (the title changed and no template matches), which blanked
    the board, and the generic path then re-sent the identical set -- so the
    ESC mark flickered on every frame.
    """

    def _core_with_generic_set_up(self, **kw):
        core = make_core(mask=_mask(), shortcuts=_sc(), **kw)
        core.submit_overlay_cmd = MagicMock()
        _tick(core)                                    # the terminal's set
        self.assertIsNotNone(core._generic_on_device)
        core.worker.submit.reset_mock()
        core.overlay_handler.note_overlay_state.reset_mock()
        return core

    def test_a_title_tick_on_the_SAME_app_sends_nothing(self):
        core = self._core_with_generic_set_up()
        before = core._generic_on_device
        for _ in range(5):
            _tick(core, cmd=OverlayCommand.DISABLE)    # spinner frames
        core.submit_overlay_cmd.assert_not_called()
        core.worker.submit.assert_not_called()
        self.assertEqual(core._generic_on_device, before)

    def test_the_handler_is_told_the_board_is_STILL_ON(self):
        # It recorded the DISABLE as sent; left alone, its redundancy guard
        # would believe the board is off and swallow the next real ENABLE.
        core = self._core_with_generic_set_up()
        _tick(core, cmd=OverlayCommand.DISABLE)
        core.overlay_handler.note_overlay_state.assert_called_once_with(True)

    def test_moving_to_an_app_with_NOTHING_generic_still_clears(self):
        core = self._core_with_generic_set_up()
        core._app_icons.overlay_for.return_value = (None, None)
        core._shortcut_icons.overlays_for.return_value = {}
        _tick(core, cmd=OverlayCommand.DISABLE)
        core.submit_overlay_cmd.assert_not_called()
        self.assertEqual(core.worker.submit.call_count, 1, "the clear")
        self.assertIsNone(core._generic_on_device)

    def test_moving_to_an_app_with_a_DIFFERENT_set_sends_it_once(self):
        core = self._core_with_generic_set_up()
        core._app_icons.overlay_for.return_value = (_mask(), "si:inkscape")
        _tick(core, cmd=OverlayCommand.DISABLE)
        core.submit_overlay_cmd.assert_not_called()
        self.assertEqual(core.worker.submit.call_count, 1)
        self.assertEqual(core._generic_on_device[0], "si:inkscape")

    def test_a_board_with_NO_generic_set_still_gets_its_DISABLE(self):
        # Leaving a template-only app: nothing generic is up, so the generic
        # path would not touch the board and the DISABLE is what clears it.
        core = make_core(mask=None, slug=None, shortcuts={})
        core.submit_overlay_cmd = MagicMock()
        _tick(core, cmd=OverlayCommand.DISABLE)
        core.submit_overlay_cmd.assert_called_once_with(OverlayCommand.DISABLE)

    def test_with_the_generic_path_OFF_the_DISABLE_still_goes_out(self):
        core = self._core_with_generic_set_up()
        core.poly_settings.get.side_effect = (
            lambda k: False if k == "generic_overlays_enabled"
            else DEFAULT_SETTINGS.get(k, False))
        _tick(core, cmd=OverlayCommand.DISABLE)
        core.submit_overlay_cmd.assert_called_once_with(OverlayCommand.DISABLE)


if __name__ == "__main__":
    unittest.main()
