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


class _StopAfter:
    """Stand-in for the watcher's stop Event: records each wait interval and
    ends the loop after `rounds` of them.

    The real loop never returns on its own — that is the point of the design —
    so a test must supply the stop. Doing it by count rather than by wall clock
    keeps the tests deterministic AND means a loop that lost its exit fails
    rather than hanging the suite."""

    def __init__(self, rounds):
        self.rounds = rounds
        self.waits = []

    def wait(self, interval):
        if self.rounds <= 0:
            return True          # stopped; this round does no work
        self.waits.append(interval)
        self.rounds -= 1
        return False

    def set(self):
        self.rounds = -1


def _watcher_core(modes, send_mode=True, connected=True, rounds=None):
    """Stand-in for the watcher: `modes` is consumed one probe at a time."""
    pushed = []
    probes = []
    seq = list(modes)

    def _push(mode):
        core._last_pushed_unicode_mode = mode
        pushed.append(mode)
        return True

    def _probe():
        probes.append(1)
        return seq.pop(0) if seq else InputMethod.Windows

    core = types.SimpleNamespace(
        WINCOMPOSE_FAST_INTERVAL=10,
        WINCOMPOSE_SLOW_INTERVAL=60,
        _wincompose_fast_until=time.monotonic() + 600,
        _wincompose_stop=_StopAfter(len(modes) if rounds is None else rounds),
        _last_pushed_unicode_mode=InputMethod.Windows,
        connected=connected,
        poly_settings=types.SimpleNamespace(
            get=lambda k: {"unicode_send_composition_mode": send_mode}[k]),
        log=types.SimpleNamespace(info=lambda *a, **k: None,
                                  debug=lambda *a, **k: None),
        _push_unicode_mode=_push,
        WINCOMPOSE_FAST_SECONDS=600,
        _started_at=time.monotonic(),
    )
    # The real rule, so the loop is tested against the shipped one.
    core._unicode_mode_is_ambiguous = (
        lambda mode: PolyCore._unicode_mode_is_ambiguous(core, mode))
    core._pushed = pushed
    core._probes = probes
    core._probe = _probe
    return core


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class WinComposeSettleTest(unittest.TestCase):
    """The startup race: the connect-time probe ran before WinCompose was up."""

    def _run(self, core, probe=None):
        with patch("polyhost.input.unicode_input.get_input_method",
                   side_effect=probe or (lambda: core._probe())):
            PolyCore._wincompose_settle_loop(core)

    def test_pushes_when_wincompose_appears_late(self):
        core = _watcher_core([InputMethod.Windows, InputMethod.WinCompose])
        self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])

    def test_KEEPS_watching_after_wincompose_is_seen(self):
        """It must not stop on the state it was waiting for: that would make the
        watch one-directional and miss WinCompose being quit later — which a
        headless daemon has no other way to notice."""
        core = _watcher_core([InputMethod.WinCompose, InputMethod.WinCompose,
                              InputMethod.Windows])
        self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose, InputMethod.Windows])
        self.assertEqual(len(core._probes), 3, "the loop stopped early")

    def test_does_not_re_push_an_unchanged_mode(self):
        core = _watcher_core([InputMethod.WinCompose] * 4)
        self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])

    def test_runs_until_it_is_STOPPED(self):
        """No deadline: WinCompose installed an hour in must still be caught."""
        core = _watcher_core([InputMethod.Windows] * 20, rounds=20)
        self._run(core)
        self.assertEqual(len(core._probes), 20)

    def test_skips_while_the_keyboard_is_DISCONNECTED(self):
        """Nothing to push to, and the post-connect flow re-asserts the mode —
        so probing would only log a failed push once a minute."""
        core = _watcher_core([InputMethod.WinCompose] * 3, connected=False)
        self._run(core)
        self.assertEqual(core._probes, [])
        self.assertEqual(core._pushed, [])

    def test_the_probe_interval_BACKS_OFF_after_the_boot_window(self):
        """10 minutes at 10 s covers the logon race; a permanent watch at that
        rate would be 8,640 TASKLIST spawns a day."""
        core = _watcher_core([InputMethod.Windows] * 3)
        core._wincompose_fast_until = time.monotonic() - 1.0   # window already over
        self._run(core)
        self.assertEqual(set(core._wincompose_stop.waits),
                         {core.WINCOMPOSE_SLOW_INTERVAL})

    def test_the_fast_interval_is_used_inside_the_boot_window(self):
        core = _watcher_core([InputMethod.Windows] * 3)
        self._run(core)
        self.assertEqual(set(core._wincompose_stop.waits),
                         {core.WINCOMPOSE_FAST_INTERVAL})

    def test_a_disabled_setting_is_re_checked_rather_than_ending_the_watch(self):
        """The setting can be turned back on while the app runs, so the loop
        skips the round instead of returning."""
        core = _watcher_core([InputMethod.WinCompose] * 3, send_mode=False)
        self._run(core)
        self.assertEqual(core._pushed, [])
        self.assertEqual(len(core._wincompose_stop.waits), 3,
                         "the loop returned instead of skipping the round")

    def test_a_probe_failure_does_not_kill_the_watcher(self):
        """TASKLIST can fail transiently; the next probe must still get its turn."""
        core = _watcher_core([InputMethod.WinCompose], rounds=2)
        calls = []

        def _probe():
            calls.append(1)
            if len(calls) == 1:
                raise OSError("TASKLIST unavailable")
            return core._probe()

        self._run(core, probe=_probe)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class AmbiguousWindowsModeTest(unittest.TestCase):
    """A plain-Windows reading is an ABSENCE of wincompose.exe, and just after
    logon that is indistinguishable from "it has not started yet"."""

    def _core(self, age=0.0):
        return types.SimpleNamespace(
            WINCOMPOSE_FAST_SECONDS=600,
            _started_at=time.monotonic() - age)

    def _ask(self, core, mode, platform="win32"):
        with patch("polyhost.core.poly_core.sys.platform", platform):
            return PolyCore._unicode_mode_is_ambiguous(core, mode)

    def test_windows_inside_the_logon_window_is_ambiguous(self):
        self.assertTrue(self._ask(self._core(), InputMethod.Windows))

    def test_windows_after_the_logon_window_is_believed(self):
        """Otherwise a machine that simply has no WinCompose could never be
        told the mode at all."""
        self.assertFalse(self._ask(self._core(age=601), InputMethod.Windows))

    def test_wincompose_is_never_ambiguous(self):
        """Seeing the process is a positive observation at any age."""
        self.assertFalse(self._ask(self._core(), InputMethod.WinCompose))

    def test_nothing_is_ambiguous_off_windows(self):
        """get_input_method() is a constant function of sys.platform there, so
        a Linux/Mac reading can never be a race."""
        self.assertFalse(
            self._ask(self._core(), InputMethod.Windows, platform="linux"))

    def test_it_is_measured_from_the_PROCESS_start_not_the_connect(self):
        """WinCompose races the logon, not a replug three hours in — where the
        delay would only postpone the re-assert that catches a DIFFERENT
        keyboard being plugged in."""
        core = self._core(age=3600)
        core._wincompose_fast_until = time.monotonic() + 600   # a fresh connect
        self.assertFalse(self._ask(core, InputMethod.Windows))


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class WatcherHoldsOffTheAmbiguousModeTest(unittest.TestCase):
    """The loop half of the rule above."""

    def _run(self, core):
        with patch("polyhost.input.unicode_input.get_input_method",
                   side_effect=lambda: core._probe()):
            PolyCore._wincompose_settle_loop(core)

    def test_a_windows_reading_is_HELD_during_the_logon_window(self):
        core = _watcher_core([InputMethod.Windows] * 3)
        core._last_pushed_unicode_mode = None      # nothing pushed at connect
        with patch("polyhost.core.poly_core.sys.platform", "win32"):
            self._run(core)
        self.assertEqual(core._pushed, [])
        self.assertEqual(len(core._probes), 3, "it stopped probing")

    def test_it_is_pushed_once_the_window_CLOSES(self):
        """The hold is a delay, not a refusal — a machine without WinCompose
        still gets its mode."""
        core = _watcher_core([InputMethod.Windows] * 2)
        core._last_pushed_unicode_mode = None
        core._started_at = time.monotonic() - 601
        with patch("polyhost.core.poly_core.sys.platform", "win32"):
            self._run(core)
        self.assertEqual(core._pushed, [InputMethod.Windows])

    def test_wincompose_is_pushed_IMMEDIATELY_inside_the_window(self):
        """The hold must not delay the observation it is waiting for."""
        core = _watcher_core([InputMethod.WinCompose])
        core._last_pushed_unicode_mode = None
        with patch("polyhost.core.poly_core.sys.platform", "win32"):
            self._run(core)
        self.assertEqual(core._pushed, [InputMethod.WinCompose])


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class SettingsChangedTest(unittest.TestCase):
    """Turning the setting on mid-session used to do nothing until the next
    reconnect: the watcher is armed in the post-connect flow, and only when the
    setting was already on."""

    def _core(self, send_mode=True, connected=True, ambiguous=False):
        core = types.SimpleNamespace(
            _BRIGHTNESS_SETTING_KEYS=PolyCore._BRIGHTNESS_SETTING_KEYS,
            connected=connected,
            poly_settings=types.SimpleNamespace(
                get=lambda k: {"unicode_send_composition_mode": send_mode}[k]),
            refresh_daylight_brightness=lambda: core._did.append("brightness"),
            _start_wincompose_settle=lambda: core._did.append("watcher"),
            _push_unicode_mode=lambda mode: core._did.append(("push", mode)),
            _unicode_mode_is_ambiguous=lambda mode: ambiguous,
        )
        core._did = []
        core._refresh_unicode_watch = lambda: PolyCore._refresh_unicode_watch(core)
        return core

    def _run(self, core, keys, mode=InputMethod.WinCompose):
        with patch("polyhost.input.unicode_input.get_input_method",
                   return_value=mode):
            PolyCore.note_settings_changed(core, keys)

    def test_enabling_the_setting_ARMS_the_watcher_and_pushes(self):
        core = self._core()
        self._run(core, ["unicode_send_composition_mode"])
        self.assertEqual(core._did,
                         ["watcher", ("push", InputMethod.WinCompose)])

    def test_it_does_nothing_while_the_setting_is_OFF(self):
        core = self._core(send_mode=False)
        self._run(core, ["unicode_send_composition_mode"])
        self.assertEqual(core._did, [])

    def test_a_disconnected_keyboard_arms_the_watcher_but_pushes_NOTHING(self):
        """There is nothing to push to, and the post-connect flow asserts it."""
        core = self._core(connected=False)
        self._run(core, ["unicode_send_composition_mode"])
        self.assertEqual(core._did, ["watcher"])

    def test_an_ambiguous_mode_is_still_HELD(self):
        """Enabling the setting during the logon window must not push the plain
        Windows reading the watcher exists to second-guess."""
        core = self._core(ambiguous=True)
        self._run(core, ["unicode_send_composition_mode"], InputMethod.Windows)
        self.assertEqual(core._did, ["watcher"])

    def test_an_unrelated_key_touches_neither_side_effect(self):
        core = self._core()
        self._run(core, ["ui_theme"])
        self.assertEqual(core._did, [])

    def test_a_brightness_key_still_refreshes_the_daylight_push(self):
        """The pre-existing side effect this hook absorbed."""
        core = self._core()
        key = sorted(PolyCore._BRIGHTNESS_SETTING_KEYS)[0]
        self._run(core, [key])
        self.assertEqual(core._did, ["brightness"])

    def test_None_means_ANY_key_may_have_changed(self):
        """What the in-process settings dialog knows: it writes the file whole."""
        core = self._core()
        self._run(core, None)
        self.assertEqual(core._did,
                         ["brightness", "watcher", ("push", InputMethod.WinCompose)])


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class PushUnicodeModeTest(unittest.TestCase):
    """`submit` only QUEUES the HID command, so the result lands later — these
    pin that a mode counts as pushed only once the keyboard says it took it."""

    def _core(self):
        submitted = []

        def _submit(name, fn, on_done=None):
            submitted.append((name, on_done))

        core = types.SimpleNamespace(
            _last_pushed_unicode_mode=None,
            _queued_unicode_mode=None,
            log=types.SimpleNamespace(info=lambda *a, **k: None,
                                      warning=lambda *a, **k: None),
            worker=types.SimpleNamespace(submit=_submit),
        )
        core._submitted = submitted
        # The push's on_done calls back into the core; bind the REAL method so
        # the confirm/fail bookkeeping under test is the shipped one.
        core._unicode_mode_pushed = (
            lambda mode, result: PolyCore._unicode_mode_pushed(core, mode, result))
        return core

    def _finish(self, core, result):
        """Fire the on_done of the most recent submission, as the worker would."""
        _name, on_done = core._submitted[-1]
        on_done("set_unicode_mode", result)

    def test_pushes_a_new_mode(self):
        core = self._core()
        self.assertTrue(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual([n for n, _ in core._submitted], ["set_unicode_mode"])

    def test_the_mode_is_recorded_only_after_the_device_CONFIRMS(self):
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self.assertIsNone(core._last_pushed_unicode_mode)   # queued, not confirmed
        self._finish(core, (True, "ok"))
        self.assertEqual(core._last_pushed_unicode_mode, InputMethod.WinCompose)

    def test_a_FAILED_push_is_retried_rather_than_deduped(self):
        """The whole point of the watcher is to retry. A push the keyboard
        refused (paused, mid-flash, unplugged) must not suppress the next one."""
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self._finish(core, (False, "suspended"))
        self.assertIsNone(core._last_pushed_unicode_mode)
        self.assertTrue(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual(len(core._submitted), 2)

    def test_an_EXCEPTION_result_counts_as_a_failure(self):
        """The worker catches a raising job and stores the exception as the
        result rather than re-raising, so on_done sees it in place of a tuple."""
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self._finish(core, OSError("device went away"))
        self.assertIsNone(core._last_pushed_unicode_mode)
        self.assertTrue(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))

    def test_dedupes_a_confirmed_mode(self):
        """The watcher probes every few seconds — it must not re-send each time."""
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self._finish(core, (True, "ok"))
        self.assertFalse(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual(len(core._submitted), 1)

    def test_does_not_submit_twice_while_one_is_IN_FLIGHT(self):
        core = self._core()
        PolyCore._push_unicode_mode(core, InputMethod.WinCompose)
        self.assertFalse(PolyCore._push_unicode_mode(core, InputMethod.WinCompose))
        self.assertEqual(len(core._submitted), 1)


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class WinComposeShutdownTest(unittest.TestCase):
    """shutdown() and _start_wincompose_settle race: a reconnect must not be
    able to start a fresh 15-minute watcher after the core has begun stopping."""

    def _core(self):
        return types.SimpleNamespace(
            _wincompose_shutting_down=True,
            _wincompose_lock=threading.Lock(),
            _wincompose_stop=threading.Event(),
            _wincompose_thread=None,
            _wincompose_deadline=0.0,
            _wincompose_fast_until=0.0,
            WINCOMPOSE_SETTLE_SECONDS=900,
            WINCOMPOSE_SETTLE_FAST_SECONDS=120,
        )

    def test_a_reconnect_after_shutdown_does_not_re_arm_the_watcher(self):
        core = self._core()
        core._wincompose_stop.set()          # as shutdown() left it
        with patch("sys.platform", "win32"):
            PolyCore._start_wincompose_settle(core)
        self.assertIsNone(core._wincompose_thread)
        self.assertTrue(core._wincompose_stop.is_set(),
                        "the stop Event was cleared after shutdown")


if __name__ == "__main__":
    unittest.main()
