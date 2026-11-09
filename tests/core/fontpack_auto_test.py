"""Tests for PolyCore's font-pack auto-flash orchestration
(`_maybe_auto_flash_fontpack` / `_fontpack_autocheck_job`).

The pure decisions live in services/fontpack_bundle + device/hid_fontpack
(tested there); these cover the wiring: gating on the setting, the once-per-process
flash guard, flashing only the stale bundles (per-bundle versions vs the shipped
manifest), and the emitted events. PolyCore pulls in the full device stack, so the
suite skips if those deps are absent."""
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from polyhost.core import events

try:
    from polyhost.core.poly_core import PolyCore
    _HAVE_CORE = True
except Exception:   # noqa: BLE001 — heavy optional deps (numpy/PIL/pvlib/…)
    _HAVE_CORE = False


def _fake_core(auto=True, in_progress=False, device_versions=None, failed=None,
               pipe_port=None, protocol=27):
    """Minimal stand-in exposing exactly what the two methods touch. ``pipe_port``
    is what pipe_port_for_update() answers: the bundle pass hands it to every
    flash, None meaning HID (no pipe, or dev_force_hid_link on)."""
    settings = {"fontpack_auto_flash": auto, "fontpack_path": ""}
    submitted = []
    emitted = []
    core = types.SimpleNamespace(
        poly_settings=types.SimpleNamespace(get=lambda k: settings[k]),
        worker=types.SimpleNamespace(submit=lambda name, fn: submitted.append((name, fn))),
        keeb=types.SimpleNamespace(hid=object(), fontpack_bundle_versions=device_versions or {},
                                   protocol_version=protocol),
        log=types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        emit=lambda name, payload: emitted.append((name, payload)),
        _fontpack_flash_in_progress=in_progress,
        _fontpack_failed=dict(failed or {}),
        pipe_port_for_update=lambda: pipe_port,
    )
    # The real implementations, bound to the stand-in — these are what the tests
    # below exercise; only _maybe_auto_flash_fontpack's submit is stubbed.
    core._fontpack_flash_bundles_job = lambda cancel, **kw: PolyCore._fontpack_flash_bundles_job(
        core, cancel, **kw)
    core._verify_flashed_bundle = lambda b, st, m: PolyCore._verify_flashed_bundle(core, b, st, m)
    core._emit_fontpack_summary = lambda *a, **kw: PolyCore._emit_fontpack_summary(core, *a, **kw)
    core._autocheck = lambda cancel: PolyCore._fontpack_autocheck_job(core, cancel)
    core._bundle_fits_device = lambda b: PolyCore._bundle_fits_device(core, b)
    # The bundle list without the emoji search dictionary: these tests patch
    # load_bundle_manifest and count bundles. TestEmojiSearchDictionary below
    # covers the real _bundle_manifest().
    core._bundle_manifest = lambda: __import__(
        "polyhost.services.fontpack_bundle", fromlist=["x"]).load_bundle_manifest()
    core._fontpack_autocheck_job = lambda cancel: None
    core._fontpack_stale_notice_job = lambda cancel: None
    core._submitted, core._emitted = submitted, emitted
    return core


# Two shipped bundles: symbol (slot 0, v2) and emoji (slot 5, v3).
_MANIFEST = {"layout_version": 1, "bundles": [
    {"id": "symbol", "index": 0, "content_version": 2, "file": "symbol.plyf", "path": "/x/symbol.plyf"},
    {"id": "emoji",  "index": 5, "content_version": 3, "file": "emoji.plyf",  "path": "/x/emoji.plyf"},
]}


_BIG_ICONS = {"id": "icons", "index": 8, "kind": "icons", "content_version": 5,
              "size": 416008, "file": "icons.plyi", "path": "/x/icons.plyi"}


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestIconSlotGate(unittest.TestCase):
    """A library over 256 KB goes only to firmware with the 512 KB slot (v27)."""

    def _flashed(self, protocol):
        core = _fake_core(device_versions={8: 4}, protocol=protocol)
        manifest = {"layout_version": 3, "bundles": [dict(_BIG_ICONS)]}
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=manifest), \
             patch("polyhost.device.hid_fontpack.flash_fontpack",
                   return_value=(True, "ok", "ok")) as ff:
            PolyCore._fontpack_flash_bundles_job(core, types.SimpleNamespace(is_set=lambda: False))
        return ff.call_count

    def test_a_large_library_waits_for_protocol_27(self):
        self.assertEqual(self._flashed(26), 0)
        self.assertEqual(self._flashed(27), 1)

    def test_a_library_that_fits_256_kb_is_not_gated(self):
        core = _fake_core(protocol=20)
        self.assertTrue(PolyCore._bundle_fits_device(core, dict(_BIG_ICONS, size=0x40000)))
        self.assertTrue(PolyCore._bundle_fits_device(core, {"id": "emoji", "size": 10**6}))
        self.assertFalse(PolyCore._bundle_fits_device(core, _BIG_ICONS))

    def test_an_unread_protocol_holds_a_large_library_without_device_io(self):
        """The status snapshot calls the gate, so it reads the cached protocol
        and never asks the keyboard; unread means too old."""
        core = _fake_core(protocol=None)
        core.keeb.supports = lambda f: self.fail("the gate must not query the device")
        self.assertFalse(PolyCore._bundle_fits_device(core, _BIG_ICONS))


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestMaybeAutoFlash(unittest.TestCase):

    def test_disabled_setting_queues_only_the_stale_notice(self):
        core = _fake_core(auto=False)
        PolyCore._maybe_auto_flash_fontpack(core)
        self.assertEqual([n for n, _fn in core._submitted], ["fontpack_stale_notice"])

    def test_enabled_submits_worker_job(self):
        core = _fake_core(auto=True)
        PolyCore._maybe_auto_flash_fontpack(core)
        self.assertEqual(len(core._submitted), 1)
        self.assertEqual(core._submitted[0][0], "fontpack_autocheck")


@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestStaleNoticeWithAutoFlashOff(unittest.TestCase):
    """Auto Flash off: flash nothing, but say which bundles are behind."""

    def _run(self, device_versions):
        core = _fake_core(auto=False, device_versions=device_versions)
        core.fontpack_bundle_status = lambda: PolyCore.fontpack_bundle_status(core)
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest",
                   return_value=_MANIFEST), \
             patch("polyhost.device.hid_fontpack.flash_fontpack") as ff:
            PolyCore._fontpack_stale_notice_job(core, None)
        self.assertFalse(ff.called, "the notice must never flash")
        return core

    def test_stale_bundles_are_named_in_one_event(self):
        core = self._run({0: 1, 5: 3})
        self.assertEqual(core._emitted, [(events.FONTPACK_STALE, {"bundles": ["symbol"]})])

    def test_up_to_date_emits_nothing(self):
        core = self._run({0: 2, 5: 3})
        self.assertEqual(core._emitted, [])

    def test_status_reports_the_setting(self):
        core = _fake_core(auto=False, device_versions={0: 2, 5: 3})
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest",
                   return_value=_MANIFEST):
            ok, info = PolyCore.fontpack_bundle_status(core)
        self.assertTrue(ok)
        self.assertIs(info["auto_flash"], False)


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

    def test_every_bundle_flash_takes_the_update_port(self):
        # The pass asks pipe_port_for_update() per bundle: the probed port when
        # there is one, None (HID) when the developer setting forces HID.
        core = _fake_core(device_versions={}, pipe_port="/dev/ttyACM0")
        ff = self._run(core, _MANIFEST)
        self.assertEqual([c.kwargs["pipe_port"] for c in ff.call_args_list],
                         ["/dev/ttyACM0", "/dev/ttyACM0"])
        core = _fake_core(device_versions={}, pipe_port=None)
        ff = self._run(core, _MANIFEST)
        self.assertEqual([c.kwargs["pipe_port"] for c in ff.call_args_list], [None, None])

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

    def test_a_remembered_failure_is_NOT_retried_on_a_keyboard_without_its_slot(self):
        """CodeRabbit on #291: a keyboard flashed back to protocol 19 no longer
        lists slot 8, and the retry list skipped the slot check the stale list
        applies, so icons.plyi was re-sent (and refused) on every connect."""
        manifest = {"layout_version": 2, "bundles": _MANIFEST["bundles"] + [
            {"id": "icons", "index": 8, "content_version": 1, "kind": "icons",
             "file": "icons.plyi", "path": "/x/icons.plyi"}]}
        core = _fake_core(device_versions={0: 2, 5: 3}, failed={8: "rejected"})
        ff = self._run(core, manifest)
        ff.assert_not_called()

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
        # ...but it stays QUEUED for the next pass: the version block only proves the
        # MASTER stored it, and the firmware cannot distinguish a lost slave ACK from
        # an explicit slave refusal (both are SYNC_CRC32_ERR over the bridge), so
        # trusting it could leave the halves rendering different glyph sets.
        self.assertEqual(set(core._fontpack_failed), {0})

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



@unittest.skipUnless(_HAVE_CORE, "PolyCore deps not installed")
class TestEmojiSearchDictionary(unittest.TestCase):
    """The selected emoji search dictionary rides the bundle passes as slot 9."""

    def _core(self, selected="de", device_versions=None, user_file=""):
        core = _fake_core(device_versions=device_versions)
        settings = {"fontpack_auto_flash": True, "fontpack_path": "", "emoji_search_dict": selected,
                    "emoji_search_dict_file": user_file}
        core.poly_settings = types.SimpleNamespace(get=lambda k: settings.get(k))
        core._bundle_manifest = lambda: PolyCore._bundle_manifest(core)
        return core

    def test_selected_dictionary_is_slot_9(self):
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
            m = PolyCore._bundle_manifest(self._core("de"))
        d = [b for b in m["bundles"] if b["index"] == 9]
        self.assertEqual(len(d), 1)
        self.assertEqual((d[0]["kind"], d[0]["dict_id"]), ("emojidict", "de"))
        self.assertEqual(d[0]["content_version"], (1 << 8) | 1)      # de is dictionary 1
        self.assertEqual(len(m["bundles"]), len(_MANIFEST["bundles"]) + 1)

    def test_switching_to_a_lower_number_is_stale(self):
        # The keyboard holds de (number 1); English is number 0, so ">" would miss it.
        core = self._core("en", device_versions={0: 2, 5: 3, 9: (1 << 8) | 1})
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST), \
             patch("polyhost.device.hid_fontpack.flash_fontpack",
                   return_value=(True, "ok", "ok")) as ff:
            PolyCore._fontpack_flash_bundles_job(core, None, auto=True)
        self.assertEqual([c.kwargs["bundle_id"] for c in ff.call_args_list], [9])

    def test_no_slot_9_flashes_no_dictionary(self):
        core = self._core("de", device_versions={0: 2, 5: 3})      # firmware before layout v4
        with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST), \
             patch("polyhost.device.hid_fontpack.flash_fontpack") as ff:
            PolyCore._fontpack_flash_bundles_job(core, None, auto=True)
        self.assertFalse(ff.called)

    def test_status_names_the_dictionary_on_the_keyboard(self):
        core = self._core("ru", device_versions={9: (1 << 8) | 1})
        ok, st = PolyCore.emoji_search_status(core)
        self.assertTrue(ok and st["shipped"] and st["supported"])
        self.assertEqual(st["selected"], "ru")
        self.assertEqual(st["device"], {"id": "de", "revision": 1, "user": False})
        self.assertEqual((st["file"], st["file_error"]), ("", ""))
        self.assertEqual(st["dictionaries"][0]["id"], "en")

    def _user_file(self, tmp):
        """The shipped German dictionary, unpacked, as a user's own file."""
        from polyhost.services import emojidict
        m = emojidict.load_manifest()
        path = os.path.join(tmp, "mine.plyd")
        with open(emojidict.unpacked_path(m, emojidict.find(m, "de"), Path(tmp)), "rb") as f, \
                open(path, "wb") as out:
            out.write(f.read())
        return path

    def test_user_file_is_slot_9(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._user_file(tmp)
            with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST):
                m = PolyCore._bundle_manifest(self._core("en", user_file=path))
        d = [b for b in m["bundles"] if b["index"] == 9]
        self.assertEqual([(b["dict_id"], b["path"]) for b in d], [("file", path)])

    def test_unusable_user_file_flashes_nothing_to_slot_9(self):
        # Replacing the slot with a shipped dictionary would discard the user's own.
        with tempfile.TemporaryDirectory() as tmp:
            core = self._core("en", device_versions={0: 2, 5: 3, 9: (1 << 8) | 0xFF},
                              user_file=os.path.join(tmp, "missing.plyd"))
            with patch("polyhost.services.fontpack_bundle.load_bundle_manifest", return_value=_MANIFEST), \
                 patch("polyhost.device.hid_fontpack.flash_fontpack") as ff:
                PolyCore._fontpack_flash_bundles_job(core, None, auto=True)
                ok, st = PolyCore.emoji_search_status(core)
        self.assertFalse(ff.called)
        self.assertIn("cannot read", st["file_error"])
        self.assertTrue(st["device"]["user"])

    def _choose_core(self, user_file=""):
        store = {"emoji_search_dict": "en", "emoji_search_dict_file": user_file}
        calls = []
        core = types.SimpleNamespace(
            poly_settings=types.SimpleNamespace(get_all=lambda: dict(store),
                                                set_all=lambda a, source="": store.update(a) or True),
            note_settings_changed=lambda keys: calls.append(("changed", tuple(keys))),
            _has_emojidict_slot=lambda: True,
            flash_fontpack_bundle=lambda b: calls.append(("flash", b)) or (True, "queued"))
        return core, store, calls

    def test_choose_a_file_then_the_same_file_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.realpath(self._user_file(tmp))
            core, store, calls = self._choose_core()
            self.assertEqual(PolyCore.emoji_search_choose(core, path=path), (True, path))
            self.assertEqual(store["emoji_search_dict_file"], path)
            self.assertEqual(calls[-1][0], "changed")
            # Same file again: its version did not change, so flash it by force.
            self.assertEqual(PolyCore.emoji_search_choose(core, path=path), (True, "queued"))
            self.assertEqual(calls[-1], ("flash", "emojidict"))

    def test_choose_refuses_a_file_that_is_not_a_dictionary(self):
        from polyhost.device import hid_fontpack
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.plyd")
            with open(path, "wb") as f:
                f.write(hid_fontpack.build_empty_pack())
            core, store, calls = self._choose_core()
            ok, msg = PolyCore.emoji_search_choose(core, path=path)
        self.assertFalse(ok)
        self.assertIn("not an emoji search dictionary", msg)
        self.assertEqual((store["emoji_search_dict_file"], calls), ("", []))

    def test_choosing_a_shipped_id_stops_using_the_file(self):
        core, store, calls = self._choose_core(user_file="/x/mine.plyd")
        self.assertEqual(PolyCore.emoji_search_choose(core, dict_id="ru"), (True, "ru"))
        self.assertEqual((store["emoji_search_dict"], store["emoji_search_dict_file"]), ("ru", ""))
        self.assertFalse(PolyCore.emoji_search_choose(core, dict_id="xx")[0])

    def test_choosing_a_dictionary_flashes_it(self):
        calls = []
        core = types.SimpleNamespace(
            _BRIGHTNESS_SETTING_KEYS=PolyCore._BRIGHTNESS_SETTING_KEYS,
            _GENERIC_ICON_SETTING_KEYS=PolyCore._GENERIC_ICON_SETTING_KEYS,
            _fw_actions_allowed=lambda: True,
            sync_fontpack=lambda force=False: calls.append(force),
            keeb=types.SimpleNamespace(fontpack_bundle_versions={0: 2}),
            poly_settings=types.SimpleNamespace(get=lambda k: None))
        core._has_emojidict_slot = lambda: PolyCore._has_emojidict_slot(core)
        PolyCore.note_settings_changed(core, ["emoji_search_dict"])
        self.assertEqual(calls, [], "no slot 9: the pass would flash only other bundles")
        core.keeb.fontpack_bundle_versions = {0: 2, 9: 0}
        PolyCore.note_settings_changed(core, ["emoji_search_dict"])
        self.assertEqual(calls, [False])
        PolyCore.note_settings_changed(core, ["emoji_search_dict_file"])
        self.assertEqual(calls, [False, False])
        PolyCore.note_settings_changed(core, ["fontpack_auto_flash"])
        self.assertEqual(calls, [False, False], "other settings must not flash it")


if __name__ == "__main__":
    unittest.main()
