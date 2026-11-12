"""The first-time MIDI guide (services/midi_guide.py) and its tick hook."""
import json
import os
import tempfile
import types
import unittest

from polyhost.services.midi_guide import (SeenPrograms, find_path, is_midi_entry,
                                          layer_target, midi_layer, program_key, run_guide)

ROWS, COLS = 10, 8
TRNS = 0x0001
MO, TO, OSL = 0x5220, 0x5200, 0x5280
BASE, FL, UL, ML = 4, 5, 7, 8


def _keymap(layers=9):
    return [TRNS] * (layers * ROWS * COLS)


def _put(buf, layer, row, col, kc):
    buf[(layer * ROWS + row) * COLS + col] = kc


def _default_split72():
    """The layer keys of the default split72 keymap that matter here."""
    buf = _keymap()
    for base in range(5):
        _put(buf, base, 2, 0, MO + FL)        # Fn
    _put(buf, FL, 0, 0, OSL + UL)
    _put(buf, FL, 0, 6, TO + UL)
    _put(buf, FL, 7, 7, TO + ML)              # above the right Shift
    _put(buf, UL, 5, 1, TO + ML)              # the clef on the utility layer
    _put(buf, FL, 8, 0, TO + 6)               # Num
    return buf


class LayerTargetTest(unittest.TestCase):
    def test_layer_keys(self):
        self.assertEqual(layer_target(MO + 5), 5)
        self.assertEqual(layer_target(TO + 8), 8)
        self.assertEqual(layer_target(OSL + 7), 7)
        self.assertEqual(layer_target(0x5260 + 3), 3)    # TG
        self.assertEqual(layer_target(0x52C0 + 2), 2)    # TT
        self.assertEqual(layer_target(0x4504), 5)        # LT(5, KC_A)
        self.assertEqual(layer_target(0x50A2), 5)        # LM(5, MOD_LSFT)

    def test_other_keys(self):
        for kc in (0x0004, TRNS, 0x5240 + 3, 0x52E0 + 3, 0x52A0 + 1, 0x7700):  # A, ___, DF, PDF, OSM, macro
            self.assertIsNone(layer_target(kc), hex(kc))


class FindPathTest(unittest.TestCase):
    def test_default_keymap_is_fn_then_the_key_above_right_shift(self):
        self.assertEqual(find_path(_default_split72(), ROWS, COLS, BASE, ML),
                         [(2, 0, BASE), (7, 7, FL)])

    def test_every_base_layer(self):
        for base in range(5):
            self.assertEqual(find_path(_default_split72(), ROWS, COLS, base, ML),
                             [(2, 0, base), (7, 7, FL)])

    def test_without_the_fn_key_it_goes_through_the_utility_layer(self):
        buf = _default_split72()
        _put(buf, FL, 7, 7, TRNS)          # a board whose user cleared it
        self.assertEqual(find_path(buf, ROWS, COLS, BASE, ML),
                         [(2, 0, BASE), (0, 0, FL), (5, 1, UL)])

    def test_a_remapped_midi_key_on_the_base_layer_is_one_step(self):
        buf = _default_split72()
        _put(buf, BASE, 3, 3, TO + ML)
        self.assertEqual(find_path(buf, ROWS, COLS, BASE, ML), [(3, 3, BASE)])

    def test_a_step_never_goes_down(self):
        buf = _keymap()
        _put(buf, BASE, 0, 0, MO + 1)      # a lower layer: the ring could never advance
        _put(buf, 1, 0, 1, TO + ML)
        self.assertIsNone(find_path(buf, ROWS, COLS, BASE, ML))

    def test_no_path_or_bad_input(self):
        self.assertIsNone(find_path(_keymap(), ROWS, COLS, BASE, ML))
        self.assertIsNone(find_path(None, ROWS, COLS, BASE, ML))
        self.assertIsNone(find_path(_default_split72(), ROWS, COLS, ML, ML))
        self.assertIsNone(find_path(_default_split72(), ROWS, COLS, 12, ML))

    def test_at_most_four_steps(self):
        buf = _keymap(layers=10)
        for layer in range(4, 9):          # 4 -> 5 -> 6 -> 7 -> 8 -> 9: five steps
            _put(buf, layer, 0, layer % COLS, MO + layer + 1)
        self.assertIsNone(find_path(buf, ROWS, COLS, 4, 9))
        self.assertEqual(len(find_path(buf, ROWS, COLS, 4, 8)), 4)


class EntryTest(unittest.TestCase):
    def test_is_midi_entry(self):
        self.assertTrue(is_midi_entry({"overlay": "x.png", "midi": True}))
        self.assertFalse(is_midi_entry({"overlay": "x.png"}))
        self.assertFalse(is_midi_entry({"midi": "yes"}))
        self.assertFalse(is_midi_entry(None))

    def test_no_web_midi_in_safari(self):
        web = {"overlay": [], "url": "^https://x", "midi": True}
        self.assertTrue(is_midi_entry(web, "chrome"))
        self.assertFalse(is_midi_entry(web, "safari"))
        self.assertFalse(is_midi_entry(web, "Safari Technology Preview"))
        self.assertTrue(is_midi_entry({"midi": True}, "safari"))   # not a web page

    def test_program_key(self):
        self.assertEqual(program_key("Bitwig Studio", {"midi": True}), "bitwig studio")
        web = {"midi": True, "url": "^https://signal"}
        self.assertEqual(program_key("chrome", web, "https://www.Example.com/app?x=1"),
                         "web:example.com")
        self.assertEqual(program_key("chrome", web), "chrome")   # no URL known
        self.assertIsNone(program_key(None, {"midi": True}))

    def test_midi_layer(self):
        self.assertEqual(midi_layer(["Qwerty", "Fn", "MIDI"]), 2)
        self.assertIsNone(midi_layer(["Qwerty", "Fn"]))
        self.assertIsNone(midi_layer(None))


class SeenProgramsTest(unittest.TestCase):
    def test_persists_and_clears(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            seen = SeenPrograms(path)
            self.assertFalse(seen.has("bitwig studio"))
            seen.add("bitwig studio")
            self.assertTrue(SeenPrograms(path).has("bitwig studio"))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), ["bitwig studio"])
            seen.clear()
            self.assertFalse(SeenPrograms(path).has("bitwig studio"))

    def test_an_unreadable_file_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "seen.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertFalse(SeenPrograms(path).has("x"))


class _Keyboard:
    def __init__(self, supports=True, names=("Q", "S", "C", "N", "W", "Fn", "Num", "Util", "MIDI"),
                 base=BASE, buffer=None, guide=(True, "ok")):
        self._supports, self.names, self.base = supports, list(names), base
        self.buffer = _default_split72() if buffer is None else buffer
        self.guide, self.calls = guide, []
        self.device_settings = types.SimpleNamespace(MATRIX_ROWS=ROWS, MATRIX_COLUMNS=COLS)

    def supports(self, feature):
        return self._supports and feature == "key_guide"

    def get_layer_names(self):
        return True, self.names

    def get_default_layer(self):
        return True, self.base

    def get_dynamic_buffer(self):
        return True, self.buffer

    def key_guide(self, *args):
        self.calls.append(args)
        return self.guide

    def key_attention_cancel(self):
        self.calls.append("cancel")
        return True, "ok"


class RunGuideTest(unittest.TestCase):
    def test_sends_the_path(self):
        kb = _Keyboard()
        self.assertEqual(run_guide(kb), (True, "ok"))
        self.assertEqual(kb.calls, [([(2, 0, BASE), (7, 7, FL)], ML, 12, 2500)])

    def test_refusals(self):
        for kb, words in ((_Keyboard(supports=False), "too old"),
                          (_Keyboard(names=("Q", "Fn")), "no MIDI layer"),
                          (_Keyboard(buffer=_keymap()), "No key path")):
            ok, msg = run_guide(kb)
            self.assertFalse(ok)
            self.assertIn(words, msg)
            self.assertEqual(kb.calls, [])


class TrackMidiGuideTest(unittest.TestCase):
    """PolyCore._track_midi_guide: once per program, cancelled when it leaves."""

    def _core(self, protocol=34, seen_path=None):
        from polyhost.core import poly_core
        kb = _Keyboard()
        kb.protocol_version = protocol
        core = types.SimpleNamespace(
            log=types.SimpleNamespace(info=lambda *a: None), jobs=[], keeb=kb,
            _midi_seen=SeenPrograms(seen_path), _midi_guide_key=None,
            _midi_guide_owner=None, safe_mode=False, coalesce={})

        def submit(name, fn, coalesce_key=None):
            core.jobs.append((name, fn))
            core.coalesce[name] = coalesce_key
        core.worker = types.SimpleNamespace(submit=submit)
        core._run_midi_guide = lambda key: poly_core.PolyCore._run_midi_guide(core, key)
        core.track = lambda handler: poly_core.PolyCore._track_midi_guide(core, handler)

        def run_jobs():
            names = [n for n, _ in core.jobs]
            for _, fn in core.jobs:
                fn(None)
            core.jobs.clear()
            return names
        core.run_jobs = run_jobs
        return core

    @staticmethod
    def _window(app, entry, url=None):
        return types.SimpleNamespace(current_entry=entry, app_name=app, current_url=url)

    def test_once_per_program(self):
        core = self._core()
        bitwig = self._window("bitwig studio", {"overlay": "b.png", "midi": True})
        core.track(bitwig)
        core.track(bitwig)                       # a still window queues nothing
        self.assertEqual(core.run_jobs(), ["midi_guide"])
        self.assertEqual(len(core.keeb.calls), 1)
        core.track(self._window("explorer", {"overlay": "e.png"}))
        self.assertEqual(core.run_jobs(), ["midi_guide_cancel"])
        core.track(bitwig)                       # seen: no second guide
        self.assertEqual(core.run_jobs(), [])
        core.track(self._window("lmms", {"overlay": "l.png", "midi": True}))
        self.assertEqual(core.run_jobs(), ["midi_guide"])

    def test_no_cancel_when_nothing_was_started(self):
        core = self._core()
        core.track(self._window("explorer", {"overlay": "e.png"}))
        core.track(self._window("notepad", {"overlay": "n.png"}))
        self.assertEqual(core.run_jobs(), [])

    def test_old_firmware_gets_nothing(self):
        core = self._core(protocol=33)
        core.track(self._window("bitwig studio", {"midi": True}))
        self.assertEqual(core.run_jobs(), [])

    def test_a_refused_guide_runs_again_next_time(self):
        core = self._core()
        core.keeb.guide = (False, "refused")
        bitwig = self._window("bitwig studio", {"midi": True})
        core.track(bitwig)
        core.run_jobs()
        self.assertIsNone(core._midi_guide_owner)
        core.track(self._window("explorer", {}))
        self.assertEqual(core.run_jobs(), [])    # nothing to cancel
        core.keeb.guide = (True, "ok")
        core.track(bitwig)
        self.assertEqual(core.run_jobs(), ["midi_guide"])

    def test_cancel_and_guide_do_not_coalesce(self):
        core = self._core()
        core.track(self._window("bitwig studio", {"midi": True}))
        core.run_jobs()
        core.track(self._window("lmms", {"midi": True}))   # A -> B: cancel A, guide B
        self.assertEqual([n for n, _ in core.jobs], ["midi_guide_cancel", "midi_guide"])
        self.assertNotEqual(core.coalesce["midi_guide_cancel"], core.coalesce["midi_guide"])

    def test_an_ended_guide_is_not_cancelled(self):
        core = self._core()
        core.track(self._window("bitwig studio", {"midi": True}))
        core.run_jobs()
        key, _ = core._midi_guide_owner
        core._midi_guide_owner = (key, 0.0)                 # its ripples ran out
        core.track(self._window("explorer", {}))
        self.assertEqual(core.run_jobs(), [])               # a later polyctl attention stays

    def test_a_stale_job_does_nothing(self):
        core = self._core()
        core.track(self._window("bitwig studio", {"midi": True}))
        core._midi_guide_key = "explorer"                   # focus moved before it ran
        core.run_jobs()
        self.assertEqual(core.keeb.calls, [])
        self.assertFalse(core._midi_seen.has("bitwig studio"))

    def test_focus_leaving_during_the_request_cancels_it(self):
        core = self._core()
        core.track(self._window("bitwig studio", {"midi": True}))
        real = core.keeb.key_guide

        def leave_while_sending(*args):
            core._midi_guide_key = None                     # the tick moved on meanwhile
            return real(*args)
        core.keeb.key_guide = leave_while_sending
        core.run_jobs()
        self.assertEqual(core.keeb.calls[-1], "cancel")
        self.assertIsNone(core._midi_guide_owner)

    def test_a_failed_guide_keeps_another_guides_owner(self):
        core = self._core()
        core.track(self._window("bitwig studio", {"midi": True}))
        core.run_jobs()
        owner = core._midi_guide_owner
        core.keeb.guide = (False, "refused")
        core._midi_guide_key = "lmms"
        core._run_midi_guide("lmms")
        self.assertEqual(core._midi_guide_owner, owner)

    def test_manual_guide_is_refused_in_restricted_mode(self):
        from polyhost.core import poly_core
        core = types.SimpleNamespace(safe_mode=True, _midi_seen=SeenPrograms(None),
                                     _device_call=lambda *a: self.fail("device call"))
        ok, msg = poly_core.PolyCore.midi_guide(core, reset=True)
        self.assertFalse(ok)
        self.assertEqual(msg, poly_core.SAFE_MODE_REFUSAL)

    def test_a_web_page_counts_by_host(self):
        core = self._core()
        entry = {"midi": True, "url": "^https://onlinesequencer"}
        core.track(self._window("chrome", entry, "https://onlinesequencer.net/"))
        core.run_jobs()
        self.assertTrue(core._midi_seen.has("web:onlinesequencer.net"))
        self.assertFalse(core._midi_seen.has("chrome"))

    def test_a_forwarded_window_uses_the_remote_entry(self):
        core = self._core()
        remote = types.SimpleNamespace(current_entry={"midi": True}, name="ardour8",
                                       current_url=None)
        handler = types.SimpleNamespace(current_entry={"remote": True}, app_name="forwarder",
                                        current_url=None, remote_handler=remote,
                                        is_remote_mapping_entry=lambda: True)
        core.track(handler)
        core.run_jobs()
        self.assertTrue(core._midi_seen.has("ardour8"))


if __name__ == "__main__":
    unittest.main()
