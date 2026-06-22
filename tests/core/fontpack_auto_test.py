"""Tests for PolyCore's font-pack auto-flash orchestration
(`_maybe_auto_flash_fontpack` / `_fontpack_autocheck_job`).

The pure decisions live in services/fontpack_bundle + device/hid_fontpack
(tested there); these cover the wiring: gating on the setting, the once-per-process
flash guard, flashing only the stale bundles (per-bundle versions vs the shipped
manifest), and the emitted events. PolyCore pulls in the full device stack, so the
suite skips if those deps are absent."""
import types
import unittest
from unittest.mock import patch

try:
    from polyhost.core.poly_core import PolyCore
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 — heavy optional deps (numpy/PIL/pvlib/…)
    _HAVE_CORE = False


def _fake_core(auto=True, in_progress=False, device_versions=None):
    """Minimal stand-in exposing exactly what the two methods touch."""
    settings = {"fontpack_auto_flash": auto, "fontpack_path": ""}
    submitted = []
    emitted = []
    core = types.SimpleNamespace(
        poly_settings=types.SimpleNamespace(get=lambda k: settings[k]),
        worker=types.SimpleNamespace(submit=lambda name, fn: submitted.append((name, fn))),
        keeb=types.SimpleNamespace(hid=object(), fontpack_bundle_versions=device_versions or {}),
        log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        emit=lambda name, payload: emitted.append((name, payload)),
        _fontpack_flash_in_progress=in_progress,
    )
    core._fontpack_autocheck_job = lambda cancel: None
    core._submitted, core._emitted = submitted, emitted
    return core


# Two shipped bundles: symbol (slot 0, v2) and emoji (slot 5, v3).
_MANIFEST = {"layout_version": 1, "bundles": [
    {"id": "symbol", "index": 0, "content_version": 2, "file": "symbol.plyf", "path": "/x/symbol.plyf"},
    {"id": "emoji",  "index": 5, "content_version": 3, "file": "emoji.plyf",  "path": "/x/emoji.plyf"},
]}


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

    def _run(self, core, manifest, flash_result=(True, "ok")):
        cancel = types.SimpleNamespace(is_set=lambda: False)
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=manifest), \
             patch("polyhost.device.hid_fontpack.flash_fontpack",
                   return_value=flash_result) as ff:
            PolyCore._fontpack_autocheck_job(core, cancel)
        return ff

    def test_no_manifest_is_inert(self):
        core = _fake_core()
        ff = self._run(core, None)
        ff.assert_not_called()
        self.assertEqual(core._emitted, [])

    def test_up_to_date_does_not_flash(self):
        # Device already at/above every shipped version → nothing to do.
        core = _fake_core(device_versions={0: 2, 5: 3})
        ff = self._run(core, _MANIFEST)
        ff.assert_not_called()
        self.assertFalse(core._fontpack_flash_in_progress)

    def test_only_stale_bundles_flashed(self):
        # symbol up to date (v2), emoji behind (v1 < v3) and missing handled as 0.
        core = _fake_core(device_versions={0: 2, 5: 1})
        ff = self._run(core, _MANIFEST)
        ff.assert_called_once()
        # flashed emoji to slot 5
        _, kwargs = ff.call_args
        self.assertEqual(kwargs["bundle_id"], 5)
        # Guard is cleared once the run completes, so the next reconnect re-checks.
        self.assertFalse(core._fontpack_flash_in_progress)
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"]
        self.assertEqual(len(done), 1)
        self.assertTrue(done[0][1]["ok"] and done[0][1]["auto"])

    def test_missing_versions_flash_all(self):
        # Empty version map (pre-pack device or absent bundles) → flash both.
        core = _fake_core(device_versions={})
        ff = self._run(core, _MANIFEST)
        self.assertEqual(ff.call_count, 2)
        self.assertEqual([c.kwargs["bundle_id"] for c in ff.call_args_list], [0, 5])

    def test_flash_failure_stops_and_reports(self):
        core = _fake_core(device_versions={})
        ff = self._run(core, _MANIFEST, flash_result=(False, "CRC mismatch"))
        ff.assert_called_once()       # stops after the first failure
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"]
        self.assertEqual(len(done), 1)
        self.assertFalse(done[0][1]["ok"])

    def test_in_progress_blocks_concurrent_flash(self):
        # A flash is already running (e.g. the connection flapped) → don't double-flash.
        core = _fake_core(in_progress=True, device_versions={})
        ff = self._run(core, _MANIFEST)
        ff.assert_not_called()


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestManualBundleOps(unittest.TestCase):
    """The manual (polyctl) bundle ops: status, force-flash one, sync-all."""

    def test_bundle_status_marks_stale(self):
        core = _fake_core(device_versions={0: 2, 5: 1})
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
            ok, payload = PolyCore.fontpack_bundle_status(core)
        self.assertTrue(ok and payload["shipped"])
        by_id = {b["id"]: b for b in payload["bundles"]}
        self.assertFalse(by_id["symbol"]["stale"])      # device v2 == shipped v2
        self.assertTrue(by_id["emoji"]["stale"])        # device v1 < shipped v3

    def test_bundle_status_no_manifest(self):
        core = _fake_core()
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=None):
            ok, payload = PolyCore.fontpack_bundle_status(core)
        self.assertTrue(ok)
        self.assertFalse(payload["shipped"])

    def test_flash_bundle_resolves_id_to_slot(self):
        core = _fake_core()
        core._fw_actions_allowed = lambda: True
        core._find_bundle = PolyCore._find_bundle
        captured = {}
        core.flash_fontpack = lambda path, bundle_id=0: captured.update(path=path, bundle_id=bundle_id) or (True, {"queued": True})
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
            ok, _ = PolyCore.flash_fontpack_bundle(core, "emoji")
        self.assertTrue(ok)
        self.assertEqual(captured["bundle_id"], 5)
        self.assertEqual(captured["path"], "/x/emoji.plyf")

    def test_flash_bundle_unknown(self):
        core = _fake_core()
        core._fw_actions_allowed = lambda: True
        core._find_bundle = PolyCore._find_bundle
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
            ok, msg = PolyCore.flash_fontpack_bundle(core, "nope")
        self.assertFalse(ok)
        self.assertIn("Unknown bundle", msg)

    def test_sync_submits_job(self):
        core = _fake_core()
        core._fw_actions_allowed = lambda: True
        ok, payload = PolyCore.sync_fontpack(core)
        self.assertTrue(ok and payload["queued"])
        self.assertEqual(core._submitted[0][0], "fontpack_sync")


if __name__ == "__main__":
    unittest.main()
