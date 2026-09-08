"""Tests for PolyCore's unicode-input-method push and its WinCompose settle watcher.

The mode is normally pushed once per connect, so installing (or quitting)
WinCompose mid-session needs an explicit re-push — that backs both the tray's
post-install refresh and `polyctl unicode-mode`.

The settle watcher covers the case the once-per-connect push gets WRONG: at logon
autostart brings PolyKybdHost up before WinCompose, so the connect-time probe finds
no wincompose.exe and pushes plain Windows for the rest of the session.
"""
import threading
import time
import types
import unittest
from unittest.mock import patch

from polyhost.input.unicode_input import InputMethod

try:
    from polyhost.core.poly_core import PolyCore
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 — heavy optional deps (numpy/PIL/pvlib/…)
    _HAVE_CORE = False


def _fake_core(send_mode=True, device_result=(True, "ok")):
    """Minimal stand-in exposing exactly what refresh_unicode_mode touches."""
    settings = {"unicode_send_composition_mode": send_mode}
    calls = []

    def _device_call(name, fn):
        calls.append(name)
        return device_result

    core = types.SimpleNamespace(
        poly_settings=types.SimpleNamespace(get=lambda k: settings[k]),
        keeb=types.SimpleNamespace(set_unicode_mode=lambda m: (True, "ok")),
        log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        _device_call=_device_call,
    )
    core._calls = calls
    return core


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class RefreshUnicodeModeTest(unittest.TestCase):

    def test_pushes_the_detected_mode(self):
        core = _fake_core()
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.WinCompose):
            ok, payload = PolyCore.refresh_unicode_mode(core)
        self.assertTrue(ok)
        self.assertEqual(payload, {"mode": "WinCompose"})
        self.assertEqual(core._calls, ["set_unicode_mode"])

    def test_respects_the_disabled_setting(self):
        """Users who turned the composition-mode push off must not get one here."""
        core = _fake_core(send_mode=False)
        ok, msg = PolyCore.refresh_unicode_mode(core)
        self.assertFalse(ok)
        self.assertIn("disabled", msg)
        self.assertEqual(core._calls, [])

    def test_device_failure_is_reported_verbatim(self):
        core = _fake_core(device_result=(False, "no PolyKybd present"))
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.Windows):
            ok, msg = PolyCore.refresh_unicode_mode(core)
        self.assertFalse(ok)
        self.assertEqual(msg, "no PolyKybd present")

    def test_a_successful_push_is_recorded_for_the_watcher(self):
        """The watcher dedupes against this, so the refresh has to keep it current."""
        core = _fake_core()
        core._last_pushed_unicode_mode = InputMethod.Windows
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.WinCompose):
            PolyCore.refresh_unicode_mode(core)
        self.assertEqual(core._last_pushed_unicode_mode, InputMethod.WinCompose)

    def test_a_failed_push_is_NOT_recorded(self):
        """Recording a mode the keyboard never took would make the watcher dedupe
        against it and never retry — the failure would become permanent."""
        core = _fake_core(device_result=(False, "no PolyKybd present"))
        core._last_pushed_unicode_mode = InputMethod.Windows
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=InputMethod.WinCompose):
            PolyCore.refresh_unicode_mode(core)
        self.assertEqual(core._last_pushed_unicode_mode, InputMethod.Windows)


def _watcher_core(modes, send_mode=True):
    """Stand-in for the settle watcher: `modes` is consumed one probe at a time."""
    pushed = []
    probes = []
    seq = list(modes)

    def _push(mode):
        core._last_pushed_unicode_mode = mode
        pushed.append(mode)
        return True

    core = types.SimpleNamespace(
        WINCOMPOSE_SETTLE_INTERVAL=0.001,
        _wincompose_stop=threading.Event(),
        # A real (short) deadline, not inf: a regression that fails to stop on
        # WinCompose must FAIL this suite, not hang it.
        _wincompose_deadline=time.monotonic() + 1.0,
        _last_pushed_unicode_mode=InputMethod.Windows,
        poly_settings=types.SimpleNamespace(
            get=lambda k: {"unicode_send_composition_mode": send_mode}[k]),
        log=types.SimpleNamespace(info=lambda *a, **k: None,
                                  debug=lambda *a, **k: None),
        _push_unicode_mode=_push,
    )
    core._pushed = pushed
    core._probes = probes

    def _probe():
        probes.append(1)
        return seq.pop(0) if seq else InputMethod.Windows

    core._probe = _probe
    return core


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class WinComposeSettleTest(unittest.TestCase):
    """The startup race: the connect-time probe ran before WinCompose was up."""

    def _run(self, core, probe=None):
        # A loop that lost its exit conditions would otherwise HANG the suite
        # rather than fail it — the deadline test in particular drives exactly
        # that mutation. The timer bounds every case; the assertions below still
        # distinguish "returned on its own" from "was stopped".
        guard = threading.Timer(3.0, core._wincompose_stop.set)
        guard.start()
        try:
            with patch("polyhost.input.unicode_input.get_input_method",
                       side_effect=probe or (lambda: core._probe())):
                PolyCore._wincompose_settle_loop(core)
        finally:
            guard.cancel()

    def test_pushes_when_wincompose_appears_late(self):
        core = _watcher_core([InputMethod.Windows, InputMethod.WinCompose])
        self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])

    def test_stops_once_wincompose_is_seen(self):
        """It must not keep spawning TASKLIST for the rest of the window — and it
        must not re-push the same mode. The list is longer than the loop should
        consume, so a runaway loop shows up as extra pushes."""
        core = _watcher_core([InputMethod.WinCompose] + [InputMethod.Windows] * 5)
        self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])

    def test_the_deadline_ends_it_when_wincompose_never_starts(self):
        """WinCompose simply not installed: the loop must terminate on its own.

        Asserted as ZERO probes, not as an empty push list: with the deadline
        already expired the loop must return before spawning a single TASKLIST,
        whereas "nothing was pushed" is also true of a loop that never stops."""
        core = _watcher_core([InputMethod.Windows] * 50)
        core._wincompose_deadline = 0.0    # already expired
        self._run(core)
        self.assertEqual(core._probes, [])
        self.assertEqual(core._pushed, [])

    def test_respects_the_disabled_setting(self):
        core = _watcher_core([InputMethod.WinCompose], send_mode=False)
        self._run(core)
        self.assertEqual(core._pushed, [])

    def test_a_probe_failure_does_not_kill_the_watcher(self):
        """TASKLIST can fail transiently; the next probe must still get its turn."""
        core = _watcher_core([InputMethod.Windows, InputMethod.WinCompose])
        calls = []

        def _probe():
            calls.append(1)
            if len(calls) == 1:
                raise OSError("TASKLIST unavailable")
            return core._probe()

        self._run(core, probe=_probe)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class PushUnicodeModeTest(unittest.TestCase):

    def _core(self):
        submitted = []
        core = types.SimpleNamespace(
            _last_pushed_unicode_mode=None,
            log=types.SimpleNamespace(info=lambda *a, **k: None),
            worker=types.SimpleNamespace(
                submit=lambda name, fn: submitted.append(name)),
        )
        core._submitted = submitted
        return core

    def test_pushes_a_new_mode(self):
        core = self._core()
        self.assertTrue(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual(core._submitted, ["set_unicode_mode"])
        self.assertEqual(core._last_pushed_unicode_mode, InputMethod.WinCompose)

    def test_dedupes_an_unchanged_mode(self):
        """The watcher probes every few seconds — it must not re-send each time."""
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self.assertFalse(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual(core._submitted, ["set_unicode_mode"])


if __name__ == "__main__":
    unittest.main()
