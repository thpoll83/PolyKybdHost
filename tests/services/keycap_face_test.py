"""The per-application keycap face (services/keycap_face.py) and its tick hook."""
import json
import os
import tempfile
import types
import unittest

from polyhost.device.command_ids import GlyphPlacement, GlyphScript
from polyhost.services.keycap_face import KeycapFace, wanted_face

C64KEYS = GlyphScript.C64KEYS.value
TOP_LEFT = GlyphPlacement.TOP_LEFT.value


class _Keyboard:
    """The four PolyKybd calls, on a keyboard that starts on Tengwar, centred."""

    def __init__(self, script=1, place=0, protocol26=True, readable=True,
                 place_readable=True, place_writable=True):
        self.script, self.place = script, place
        self.protocol26, self.readable = protocol26, readable
        self.place_readable, self.place_writable = place_readable, place_writable
        self.writes = []

    def get_glyph_script(self):
        return (True, self.script) if self.readable else (False, 0)

    def set_glyph_script(self, v):
        self.writes.append(("script", v))
        self.script = v
        return True, ""

    def get_glyph_placement(self):
        return (True, self.place) if self.protocol26 and self.place_readable else (False, 0)

    def set_glyph_placement(self, v):
        if not self.protocol26:
            return False, "too old"
        if not self.place_writable:
            return False, "no reply"
        self.writes.append(("place", v))
        self.place = v
        return True, ""


class WantedFaceTest(unittest.TestCase):

    def test_names_and_spellings(self):
        self.assertEqual(wanted_face({"glyph_script": "c64keys", "glyph_script_position": "top-left"}),
                         (C64KEYS, TOP_LEFT))
        self.assertEqual(wanted_face({"glyph_script": "IBMVGA"}), (GlyphScript.IBMVGA.value, None))
        self.assertEqual(wanted_face({"glyph_script_position": "top_left"}), (None, TOP_LEFT))
        self.assertEqual(wanted_face({"glyph_script_position": "center"}), (None, 0))

    def test_an_entry_without_the_keys_asks_for_nothing(self):
        self.assertIsNone(wanted_face({"overlay": "x.png"}))
        self.assertIsNone(wanted_face(None))
        self.assertIsNone(wanted_face("not a dict"))

    def test_unknown_values_are_ignored(self):
        self.assertIsNone(wanted_face({"glyph_script": "klingon"}))
        self.assertEqual(wanted_face({"glyph_script": "amiga", "glyph_script_position": "middle"}),
                         (GlyphScript.AMIGA.value, None))


class KeycapFaceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "cfg", "keycap_face_restore.json")

    def test_override_then_restore(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        self.assertEqual((kb.script, kb.place), (C64KEYS, TOP_LEFT))
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"script": 1, "place": 0})
        face.apply(None, kb)
        self.assertEqual((kb.script, kb.place), (1, 0))
        self.assertFalse(os.path.exists(self.path))
        self.assertIsNone(face.remembered)

    def test_the_same_face_again_writes_nothing(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        n = len(kb.writes)
        face.apply((C64KEYS, TOP_LEFT), kb)
        face.apply(None, kb)
        face.apply(None, kb)
        self.assertEqual(len(kb.writes), n + 2)     # one restore: script + placement

    def test_switching_between_two_overridden_apps_keeps_the_users_face(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        face.apply((GlyphScript.AMIGA.value, None), kb)
        self.assertEqual(face.remembered, (1, 0))   # not the C64 face
        # The Amiga entry leaves the placement alone: the user's centre, not C64's top-left.
        self.assertEqual((kb.script, kb.place), (GlyphScript.AMIGA.value, 0))
        face.apply(None, kb)
        self.assertEqual((kb.script, kb.place), (1, 0))

    def test_a_new_host_restores_a_face_left_by_one_that_stopped(self):
        kb = _Keyboard()
        KeycapFace(self.path).apply((C64KEYS, TOP_LEFT), kb)    # host stops here
        later = KeycapFace(self.path)
        self.assertEqual(later.remembered, (1, 0))
        later.restore(kb)
        self.assertEqual((kb.script, kb.place), (1, 0))
        self.assertFalse(os.path.exists(self.path))

    def test_a_hand_picked_face_is_the_one_restored(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        face.note_user_choice(script=GlyphScript.RUNES.value)
        face.apply(None, kb)
        self.assertEqual((kb.script, kb.place), (GlyphScript.RUNES.value, 0))

    def test_a_hand_picked_face_without_an_override_remembers_nothing(self):
        face = KeycapFace(self.path)
        face.note_user_choice(script=3)
        self.assertIsNone(face.remembered)
        self.assertFalse(os.path.exists(self.path))

    def test_older_firmware_gets_the_script_only(self):
        kb, face = _Keyboard(protocol26=False), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        self.assertEqual(kb.writes, [("script", C64KEYS)])
        face.apply(None, kb)
        self.assertEqual(kb.script, 1)

    def test_a_placement_that_could_not_be_read_is_never_written(self):
        kb, face = _Keyboard(place_readable=False), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        self.assertEqual(kb.writes, [("script", C64KEYS)])   # the restore could not undo it
        face.apply(None, kb)
        self.assertEqual((kb.script, kb.place), (1, 0))

    def test_a_failed_placement_restore_keeps_the_record(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        kb.place_writable = False
        face.apply(None, kb)
        self.assertEqual(face.remembered, (1, 0))     # kept for the next connect
        self.assertTrue(os.path.exists(self.path))
        kb.place_writable = True
        KeycapFace(self.path).restore(kb)
        self.assertEqual((kb.script, kb.place), (1, 0))
        self.assertFalse(os.path.exists(self.path))

    def test_after_close_a_queued_face_does_nothing(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        face.close()
        face.restore(kb)                               # shutdown's restore jumps the queue
        face.apply((GlyphScript.AMIGA.value, None), kb)  # a job queued before it
        self.assertEqual((kb.script, kb.place), (1, 0))
        self.assertFalse(os.path.exists(self.path))

    def test_an_unreadable_keyboard_is_left_alone(self):
        kb, face = _Keyboard(readable=False), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        self.assertEqual(kb.writes, [])
        face.apply((C64KEYS, TOP_LEFT), kb)          # and not retried every tick
        self.assertEqual(kb.writes, [])

    def test_after_a_disconnect_the_face_is_sent_again(self):
        kb, face = _Keyboard(), KeycapFace(self.path)
        face.apply((C64KEYS, TOP_LEFT), kb)
        face.note_disconnected()
        kb.script, kb.place = 1, 0                    # a different board, or a reset
        face.apply((C64KEYS, TOP_LEFT), kb)
        self.assertEqual((kb.script, kb.place), (C64KEYS, TOP_LEFT))
        self.assertEqual(face.remembered, (1, 0))     # the first remembered face stays


class TrackKeycapFaceTest(unittest.TestCase):
    """PolyCore._track_keycap_face queues work only when the wanted face changes."""

    def _core(self):
        from polyhost.core import poly_core
        applied = []
        core = types.SimpleNamespace(
            log=None, submitted=[], jobs=[], applied=applied, keeb="the keyboard",
            _keycap_face=types.SimpleNamespace(apply=lambda w, dev: applied.append((w, dev))),
            _keycap_face_sent=poly_core._NOT_SENT,
            _keycap_face_entry_seen=None, _keycap_face_wanted=None)

        def submit(name, fn, coalesce_key=None):
            core.submitted.append(name)
            core.jobs.append((fn, coalesce_key))
        core.worker = types.SimpleNamespace(submit=submit)
        core.track = lambda handler: poly_core.PolyCore._track_keycap_face(core, handler)
        return core

    def test_the_job_applies_the_face_to_the_keyboard(self):
        core = self._core()
        core.track(types.SimpleNamespace(current_entry={"glyph_script": "c64keys"}))
        core.track(types.SimpleNamespace(current_entry={"overlay": "o.png"}))
        self.assertEqual([k for _, k in core.jobs], ["keycap_face", "keycap_face"])
        for fn, _ in core.jobs:
            fn(None)
        self.assertEqual(core.applied, [((C64KEYS, None), "the keyboard"),
                                        (None, "the keyboard")])

    def test_a_forwarded_window_uses_the_forwarded_match(self):
        core = self._core()
        wrapper = {"remote": True}
        handler = types.SimpleNamespace(
            current_entry=wrapper, is_remote_mapping_entry=lambda: True,
            remote_handler=types.SimpleNamespace(current_entry={"glyph_script": "amiga"}))
        core.track(handler)
        core.jobs[0][0](None)
        self.assertEqual(core.applied, [((GlyphScript.AMIGA.value, None), "the keyboard")])

    def test_one_submit_per_change(self):
        core = self._core()
        vice = {"overlay": "v.png", "glyph_script": "c64keys"}
        other = {"overlay": "o.png"}
        for entry in (vice, vice, vice, other, other, None, vice):
            core.track(types.SimpleNamespace(current_entry=entry))
        # vice -> face, other -> restore (None), None -> same None, vice -> face again
        self.assertEqual(core.submitted, ["keycap_face", "keycap_face", "keycap_face"])


if __name__ == "__main__":
    unittest.main()
