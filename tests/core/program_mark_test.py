"""The generic program mark: when PolyCore draws an app's own icon on ESC.

A template overlay draws a real icon on every shortcut key. Where no template
covers the focused application, this puts at least that application's own mark
on the board. Template always wins, so these pin the branch that decides.
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


def make_core(*, app=("gimp", None), mask=None, slug="si:gimp"):
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
    core.poly_settings = MagicMock()
    core.poly_settings.get.side_effect = lambda k: False
    from polyhost.input.unicode_input import get_host_os
    core._last_pushed_os = get_host_os().value
    core._program_mark_on_device = None
    core._app_icons = MagicMock()
    core._app_icons.overlay_for.return_value = (mask, slug)
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

    def test_a_template_send_FORGETS_the_mark_on_the_device(self):
        # ⚠️ The template re-programs the whole pool, so the mark is gone with
        # it. Without clearing this, switching template-app -> generic-app ->
        # template-app -> generic-app would skip the second generic send.
        core = make_core(mask=_mask())
        _tick(core)                                        # generic mark sent
        self.assertEqual(core._program_mark_on_device, "si:gimp")
        _tick(core, data="x.mods.png", cmd=OverlayCommand.OFF_ON)
        self.assertIsNone(core._program_mark_on_device)


class GenericMarkTest(unittest.TestCase):

    def test_no_template_and_a_mask_QUEUES_the_mark(self):
        core = make_core(mask=_mask())
        _tick(core)
        self.assertEqual(core.worker.submit.call_args.args[0], "overlay")
        self.assertEqual(core.worker.submit.call_args.kwargs["coalesce_key"],
                         "overlay")
        self.assertEqual(core._program_mark_on_device, "si:gimp")

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
        self.assertEqual(core._program_mark_on_device, "si:inkscape")

    def test_NO_mask_yet_sends_nothing_and_claims_nothing(self):
        # First sighting: the fetch was queued, nothing is drawable yet. The
        # tick after it resolves is what sends — no callback races the focus.
        core = make_core(mask=None)
        _tick(core)
        core.worker.submit.assert_not_called()
        self.assertIsNone(core._program_mark_on_device)

    def test_an_app_we_cannot_NAME_is_skipped(self):
        core = make_core(app=(None, None), mask=_mask())
        _tick(core)
        core._app_icons.overlay_for.assert_not_called()


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
        self.assertIsNone(core._program_mark_on_device)

    def test_a_RAISING_send_forgets_the_mark_and_warns(self):
        core = make_core(mask=_mask())
        events = []
        core.subscribe(lambda n, p: events.append(n))
        _tick(core)
        entry = core.device_mgr.all_entries[0]
        entry.device.send_overlays_mru.side_effect = RuntimeError("boom")
        core.worker.submit.call_args.args[1](threading.Event())
        self.assertIsNone(core._program_mark_on_device)
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
