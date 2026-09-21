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
from polyhost.handler.common import OverlayCommand


def _mask():
    m = np.zeros((38, 38), dtype=bool)
    m[8:30, 8:30] = True
    return m


def make_core(*, app=("gimp", None), mask=None, slug="si:gimp", shortcuts=None):
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
    core.poly_settings.get.side_effect = lambda k: False
    # `note_settings_changed(None)` -- what the in-process dialog sends -- runs
    # the brightness branch first, so the fixture has to mirror that too.
    core.sunlight = MagicMock()
    from polyhost.input.unicode_input import get_host_os
    core._last_pushed_os = get_host_os().value
    core._generic_on_device = None
    core._told_no_remote_shortcuts = set()
    core._app_icons = MagicMock()
    core._app_icons.overlay_for.return_value = (mask, slug)
    core._shortcut_icons = MagicMock()
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
        core = make_core(mask=_mask())
        _tick(core)                                        # generic mark sent
        self.assertEqual(core._generic_on_device[0], "si:gimp")
        _tick(core, data="x.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertIsNone(core._generic_on_device)


class TemplatePriorityTest(unittest.TestCase):
    """A hand-made overlay set wins, and it has to keep winning after tick 1."""

    def test_the_generic_set_does_NOT_overwrite_a_live_template(self):
        # ⚠️ The regression, reported from hardware as "icons where we have
        # overlays take priority, which is not the case right now". The template
        # arrives on the tick the window changes; on EVERY tick after that
        # `handle_active_window` answers (None, NONE) for the same window, so the
        # old `else` branch fired, `send_overlays_mru` reset the mapping the
        # template had just committed, and the hand-made keycaps went blank about
        # a second after appearing.
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core, data="gimp_template.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertEqual(core.worker.submit.call_count, 1)      # the template
        for _ in range(5):
            _tick(core)                                         # same window
        self.assertEqual(core.worker.submit.call_count, 1)      # and nothing else

    def test_it_is_asked_the_HANDLER_not_the_returned_data(self):
        # The data is the tell that a template was JUST SENT; the handler is the
        # only thing that knows one is STILL ACTIVE.
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)                       # no data, no command, template active
        core.worker.submit.assert_not_called()

    def test_leaving_a_templated_app_hands_the_board_BACK_to_the_generic_set(self):
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)
        core.worker.submit.assert_not_called()
        core.overlay_handler.covered_by_template.return_value = False
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_covered_window_costs_NO_fetch_at_all(self):
        # Not merely "sends nothing": a template-covered app must not walk
        # another process's accessibility tree either.
        core = make_core(mask=_mask(), shortcuts=_sc())
        core.overlay_handler.covered_by_template.return_value = True
        _tick(core)
        core._app_icons.overlay_for.assert_not_called()
        core._shortcut_icons.overlays_for.assert_not_called()


class GenericMarkTest(unittest.TestCase):

    def test_no_template_and_a_mask_QUEUES_the_mark(self):
        core = make_core(mask=_mask())
        _tick(core)
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"],
                         "overlay")
        self.assertEqual(core._generic_on_device[0], "si:gimp")

    def test_it_emits_THINKING_like_any_other_overlay_send(self):
        core = make_core(mask=_mask())
        events = []
        core.subscribe(lambda n, p: events.append((n, p)))
        _tick(core)
        self.assertIn(("overlay_activity", {"state": "thinking"}), events)

    def test_the_SAME_app_is_not_resent_every_tick(self):
        # The tick runs continuously; only a change may cost a transfer.
        core = make_core(mask=_mask())
        for _ in range(5):
            _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_DIFFERENT_app_is_sent(self):
        core = make_core(mask=_mask())
        _tick(core)
        core._app_icons.overlay_for.return_value = (_mask(), "si:inkscape")
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 2)
        self.assertEqual(core._generic_on_device[0], "si:inkscape")

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
        # The harvest is slow and runs off the tick, so the first sighting of an
        # app resolves the mark and nothing else. The pass after the tree walk
        # finishes has to send again, or the icons appear only the SECOND time
        # you focus the application.
        core = make_core(mask=_mask(), shortcuts={})
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 1)
        core._shortcut_icons.overlays_for.return_value = _sc()
        _tick(core)
        self.assertEqual(core.worker.submit.call_count, 2)

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
        core._app_icons.forget.assert_called_once()

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

    def test_the_MARK_still_goes_out_while_the_relay_is_in_flight(self):
        # The mark works because the forwarder resolves the identity and relays
        # it. Losing the mark while waiting for shortcuts would be a regression.
        core = self._remote(relayed=None, mask=_mask())
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        names = core.device_mgr.all_entries[0].device.send_overlays_mru.call_args.args[0]
        self.assertEqual(names, ["@prog:si:gimp"])

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
        core._shortcut_icons.overlays_for.assert_called_once_with("gimp")


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


class FailurePathTest(unittest.TestCase):

    def test_a_CANCELLED_send_forgets_the_mark_so_it_can_be_retried(self):
        # ⚠️ The slug is recorded BEFORE the send, so a superseded job has to put
        # it back — otherwise the app is permanently believed to be marked and
        # never gets one.
        core = make_core(mask=_mask())
        _tick(core)
        job = core.worker.submit.call_args.args[1]
        cancel = threading.Event()
        cancel.set()
        job(cancel)
        self.assertIsNone(core._generic_on_device)

    def test_a_RAISING_send_forgets_the_mark_and_warns(self):
        core = make_core(mask=_mask())
        events = []
        core.subscribe(lambda n, p: events.append(n))
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.worker.submit.call_args.args[1](threading.Event())
        self.assertIsNone(core._generic_on_device)
        self.assertIn("overlay_warning", events)

    def test_the_send_names_the_SYNTHETIC_source(self):
        core = make_core(mask=_mask())
        _tick(core)
        core.worker.submit.call_args.args[1](threading.Event())
        entry = core.device_mgr.all_entries[0]
        args, kwargs = entry.device.send_overlays_mru.call_args
        self.assertEqual(args[0], ["@prog:si:gimp"])
        self.assertIn("@prog:si:gimp", kwargs["synthetic"])


if __name__ == "__main__":
    unittest.main()
