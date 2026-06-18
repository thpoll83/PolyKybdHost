"""Tests for PolyCore's font-pack auto-flash orchestration
(`_maybe_auto_flash_fontpack` / `_fontpack_autocheck_job`).

The pure decision lives in services/fontpack_bundle (tested there); these tests
cover the wiring: gating on the setting, the once-per-process flash guard, the
cheap-status-read-every-connect behaviour, and the emitted events. PolyCore
pulls in the full device stack, so the suite skips if those deps are absent."""
import types
import unittest
from unittest.mock import patch

try:
    from polyhost.core.poly_core import PolyCore
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 — heavy optional deps (numpy/PIL/pvlib/…)
    _HAVE_CORE = False


def _fake_core(auto=True, attempted=False, fontpack_path=""):
    """Minimal stand-in exposing exactly what the two methods touch."""
    settings = {"fontpack_auto_flash": auto, "fontpack_path": fontpack_path}
    submitted = []
    emitted = []
    core = types.SimpleNamespace(
        poly_settings=types.SimpleNamespace(get=lambda k: settings[k]),
        worker=types.SimpleNamespace(submit=lambda name, fn: submitted.append((name, fn))),
        keeb=types.SimpleNamespace(hid=object()),
        log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        emit=lambda name, payload: emitted.append((name, payload)),
        _fontpack_auto_attempted=attempted,
    )
    # _maybe_auto_flash_fontpack submits self._fontpack_autocheck_job by reference.
    core._fontpack_autocheck_job = lambda cancel: None
    core._submitted, core._emitted = submitted, emitted
    return core


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestMaybeAutoFlash(unittest.TestCase):

    def test_disabled_setting_submits_nothing(self):
        core = _fake_core(auto=False)
        PolyCore._maybe_auto_flash_fontpack(core)
        self.assertEqual(core._submitted, [])

    def test_enabled_submits_worker_job(self):
        core = _fake_core(auto=True)
        PolyCore._maybe_auto_flash_fontpack(core)
        self.assertEqual(len(core._submitted), 1)
        self.assertEqual(core._submitted[0][0], "fontpack_autocheck")


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestAutocheckJob(unittest.TestCase):

    def _run(self, core, bundled, status, decide):
        cancel = types.SimpleNamespace(is_set=lambda: False)
        with patch("polyhost.services.fontpack_bundle.bundled_pack_info", return_value=bundled), \
             patch("polyhost.services.fontpack_bundle.decide_auto_flash", return_value=decide), \
             patch("polyhost.device.hid_fontpack.get_fontpack_status", return_value=status) as gs, \
             patch("polyhost.device.hid_fontpack.flash_fontpack",
                   return_value=(True, "loaded v7")) as ff:
            PolyCore._fontpack_autocheck_job(core, cancel)
        return gs, ff

    def test_no_bundled_pack_is_inert(self):
        core = _fake_core()
        gs, ff = self._run(core, (None, None), (True, {}), (False, "x"))
        gs.assert_not_called()
        ff.assert_not_called()
        self.assertEqual(core._emitted, [])

    def test_up_to_date_reads_status_but_does_not_flash(self):
        core = _fake_core()
        binfo = {"abi_version": 1, "content_version": 7}
        gs, ff = self._run(core, ("/p.plyf", binfo),
                           (True, {"present": True, "abi": 1, "content_version": 7}),
                           (False, "up to date"))
        gs.assert_called_once()      # cheap status read on every connect
        ff.assert_not_called()       # but no flash
        self.assertFalse(core._fontpack_auto_attempted)

    def test_stale_flashes_once_and_sets_guard(self):
        core = _fake_core()
        binfo = {"abi_version": 1, "content_version": 7}
        gs, ff = self._run(core, ("/p.plyf", binfo),
                           (True, {"present": True, "abi": 1, "content_version": 5}),
                           (True, "older"))
        ff.assert_called_once()
        self.assertTrue(core._fontpack_auto_attempted)
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"]
        self.assertEqual(len(done), 1)
        self.assertTrue(done[0][1]["ok"])
        self.assertTrue(done[0][1]["auto"])

    def test_guard_blocks_second_auto_flash(self):
        core = _fake_core(attempted=True)
        binfo = {"abi_version": 1, "content_version": 7}
        gs, ff = self._run(core, ("/p.plyf", binfo),
                           (True, {"present": False, "abi": 1, "content_version": 0}),
                           (True, "no font pack"))
        ff.assert_not_called()       # already attempted this process — no auto-retry


if __name__ == "__main__":
    unittest.main()
