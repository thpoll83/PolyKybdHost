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


def _fake_core(auto=True, in_progress=False, device_versions=None, failed=None):
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
        _fontpack_failed=dict(failed or {}),
    )
    # The real implementations, bound to the stand-in — these are what the tests
    # below exercise; only _maybe_auto_flash_fontpack's submit is stubbed.
    core._fontpack_flash_bundles_job = lambda cancel, **kw: PolyCore._fontpack_flash_bundles_job(
        core, cancel, **kw)
    core._verify_flashed_bundle = lambda b, st, m: PolyCore._verify_flashed_bundle(core, b, st, m)
    core._emit_fontpack_summary = lambda *a: PolyCore._emit_fontpack_summary(core, *a)
    core._autocheck = lambda cancel: PolyCore._fontpack_autocheck_job(core, cancel)
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

    def _run(self, core, manifest, flash_result=(True, "ok", "ok"), side_effect=None, **kw):
        cancel = types.SimpleNamespace(is_set=lambda: False)
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=manifest), \
             patch("polyhost.device.hid_fontpack.flash_fontpack",
                   return_value=flash_result, side_effect=side_effect) as ff:
            if kw:
                PolyCore._fontpack_flash_bundles_job(core, cancel, **kw)
            else:
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

    def test_one_failure_does_not_abort_the_remaining_bundles(self):
        # ⚠️ This inverts the old contract, which returned after the first failure.
        # In the field that cost SIX good bundles a flash because the first one
        # (symbol) failed (2026-08-17) — one bundle's failure says nothing about the
        # next one's, so the pass continues and reports everything at the end.
        core = _fake_core(device_versions={})
        ff = self._run(core, _MANIFEST,
                       side_effect=[(False, "rejected", "rejected"), (True, "ok", "ok")])
        self.assertEqual(ff.call_count, 2)
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"]
        self.assertEqual(len(done), 1)
        self.assertFalse(done[0][1]["ok"])          # a failure still fails the run
        self.assertIn("symbol", done[0][1]["msg"])  # ...and is named
        self.assertIn("emoji", done[0][1]["msg"])   # ...alongside what did land

    def test_a_hard_failure_is_remembered_for_the_next_pass(self):
        # A 'rejected' bundle is never verified against the device (the keyboard said
        # it refused the data), so it lands in the retry set.
        core = _fake_core(device_versions={})
        self._run(core, _MANIFEST, flash_result=(False, "rejected", "rejected"))
        self.assertEqual(set(core._fontpack_failed), {0, 5})

    def test_a_remembered_failure_is_reflashed_even_when_the_version_reads_current(self):
        # THE FIELD BUG: the device reports the shipped version (the data landed and
        # only the COMMIT ACK was lost), so decide_stale_bundles says "nothing to do"
        # — but the previous attempt was reported as failed, so it must be retried.
        core = _fake_core(device_versions={0: 2, 5: 3}, failed={0: "COMMIT failed"})
        ff = self._run(core, _MANIFEST)
        ff.assert_called_once()
        self.assertEqual(ff.call_args.kwargs["bundle_id"], 0)
        self.assertEqual(core._fontpack_failed, {})   # cleared once it succeeds

    def test_lost_ack_is_verified_against_the_device_and_not_a_failure(self):
        # 'slave-unconfirmed' + the device now reporting the shipped version = the
        # data is stored; report it as done-with-a-caveat instead of a failure, and
        # do NOT queue a pointless re-flash of tens of KB.
        core = _fake_core(device_versions={0: 0, 5: 3})   # only symbol is behind

        def _query_id():
            # What the keyboard reports after the "failed" flash: the bundle is there.
            core.keeb.fontpack_bundle_versions = {0: 2, 5: 3}
            return True, "PolyKybd"
        core.keeb.query_id = _query_id
        ff = self._run(core, _MANIFEST,
                       flash_result=(False, "COMMIT incomplete", "slave-unconfirmed"))
        ff.assert_called_once()
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"][0][1]
        self.assertTrue(done["ok"])
        self.assertIn("Unconfirmed", done["msg"])
        self.assertIn("other half", done["msg"])
        self.assertEqual(core._fontpack_failed, {})

    def test_verification_that_still_reads_behind_stays_a_failure(self):
        core = _fake_core(device_versions={0: 0, 5: 3})
        core.keeb.query_id = lambda: (True, "PolyKybd")   # version block unchanged
        self._run(core, _MANIFEST,
                  flash_result=(False, "COMMIT incomplete", "slave-unconfirmed"))
        done = [e for e in core._emitted if e[0] == "fontpack_flash_done"][0][1]
        self.assertFalse(done["ok"])
        self.assertEqual(set(core._fontpack_failed), {0})

    def test_force_all_flashes_every_bundle_regardless_of_version(self):
        core = _fake_core(device_versions={0: 2, 5: 3})    # everything up to date
        ff = self._run(core, _MANIFEST, force_all=True)
        self.assertEqual([c.kwargs["bundle_id"] for c in ff.call_args_list], [0, 5])

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
        self.assertFalse(by_id["symbol"]["retry"])
        self.assertEqual(payload["failed"], [])

    def test_bundle_status_reports_a_bundle_needing_a_retry(self):
        # Up to date by version, but the last flash failed — the UI needs to see this
        # or it renders "up to date" over a bundle that never took.
        core = _fake_core(device_versions={0: 2, 5: 3}, failed={0: "COMMIT failed"})
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
            ok, payload = PolyCore.fontpack_bundle_status(core)
        by_id = {b["id"]: b for b in payload["bundles"]}
        self.assertFalse(by_id["symbol"]["stale"])
        self.assertTrue(by_id["symbol"]["retry"])
        self.assertEqual(by_id["symbol"]["last_error"], "COMMIT failed")
        self.assertEqual(payload["failed"], ["symbol"])

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
