"""services/tutorials/loader: the YAML tutorial scripts (docs/tutorials-plan.md)."""
import os
import tempfile
import unittest

from polyhost.services.tutorials import loader
from polyhost.services.tutorials.loader import Point, ScriptError, Wait, parse_script


def _script(**over):
    raw = {"id": "demo", "category": "layers", "title": "Demo",
           "steps": [{"say": ["Hold Fn"], "wait": "next"}]}
    raw.update(over)
    return raw


def _step(**fields):
    return _script(steps=[fields])


class ShippedScriptsTest(unittest.TestCase):
    def test_every_shipped_script_loads(self):
        found, errors = loader.load_all()
        self.assertEqual(errors, [])
        for tid in ("midi-layer", "brightness", "accents", "rgb-lighting", "emoji-search",
                    "keyboard-language", "base-layouts", "record-macro"):
            self.assertIn(tid, found)
        for t in found.values():
            self.assertIn(t.category, loader.CATEGORIES)
            self.assertIn("en", t.title)
            self.assertFalse(t.user)

    def test_the_custom_keycodes_resolve(self):
        # PolyKybd's own keycodes come from legends.json, not keycodes.h.
        brightness = loader.load_all()[0]["brightness"]
        points = [s.point for s in brightness.steps if s.point]
        self.assertIn(Point("keycode", 0x7E1D), points)       # KC_DAUTO
        self.assertIn(Point("keycode", 0x7E08), points)       # KC_BASE
        # The Utility layer is entered with the layer guide, which takes the TO key.
        self.assertEqual(brightness.steps[0].guide_to_layer, "Utility")


class ParseTest(unittest.TestCase):
    def test_a_minimal_script(self):
        t = parse_script(_script())
        self.assertEqual(t.id, "demo")
        self.assertEqual(t.title, {"en": "Demo"})
        self.assertEqual(t.min_protocol, loader.BASE_PROTOCOL)
        self.assertEqual(t.steps[0].say, ("Hold Fn",))
        self.assertEqual(t.steps[0].wait, Wait("next"))

    def test_min_protocol_is_never_below_the_ring(self):
        self.assertEqual(parse_script(_script(min_protocol=2)).min_protocol, 32)
        self.assertEqual(parse_script(_script(min_protocol=35)).min_protocol, 35)

    def test_translated_texts(self):
        t = parse_script(_script(title={"en": "Demo", "de": "Vorführung"}))
        self.assertEqual(t.title["de"], "Vorführung")

    def test_points(self):
        self.assertEqual(parse_script(_step(point={"keycode": "KC_A"})).steps[0].point,
                         Point("keycode", 4))
        self.assertEqual(parse_script(_step(point={"keycode": 0x29})).steps[0].point,
                         Point("keycode", 0x29))
        self.assertEqual(parse_script(_step(point={"layer_key": " Fn "})).steps[0].point,
                         Point("layer_key", "Fn"))
        self.assertEqual(parse_script(_step(point={"key": [2, 3]})).steps[0].point,
                         Point("key", (2, 3)))

    def test_spotlight_and_reveal(self):
        step = parse_script(_step(spotlight=[{"keycode": "KC_A"}, {"layer": "MIDI"},
                                             {"key": [1, 2]}, {"layer_key": "Fn"}],
                                  reveal={"from": {"key": [3, 4]}})).steps[0]
        self.assertEqual(step.spotlight, (Point("keycode", 4), Point("layer", "MIDI"),
                                          Point("key", (1, 2)), Point("layer_key", "Fn")))
        self.assertEqual(step.reveal, Point("key", (3, 4)))
        self.assertEqual(parse_script(_step(spotlight=[])).steps[0].spotlight, ())
        self.assertIsNone(parse_script(_step(say="x")).steps[0].spotlight)

    def test_say_width_is_measured_in_the_status_face(self):
        # Measured with the shipped face: 'W' is 14 px, 'i' 4 px.
        self.assertEqual(loader.say_width("Hold Fn"), 53)
        self.assertEqual(loader.say_width("Min 1/4 1/2 3/4 Max"), 143)
        parse_script(_step(say=["i" * 29, "i" * 30]))          # 59 bytes, narrow
        with self.assertRaises(ScriptError):
            parse_script(_step(say=["W" * 10]))                  # 10 x 14 px > 128

    def test_waits(self):
        self.assertEqual(parse_script(_step(wait={"seconds": 3})).steps[0].wait,
                         Wait("seconds", 3.0))
        self.assertEqual(parse_script(_step(wait={"layer": "MIDI"})).steps[0].wait,
                         Wait("layer", "MIDI"))
        self.assertEqual(parse_script(_step(wait={"press": "KC_ESC"})).steps[0].wait,
                         Wait("press", 0x29))
        self.assertEqual(parse_script(_step(wait={"key": {"keycode": "KC_ESC"}})).steps[0].wait,
                         Wait("key", Point("keycode", 0x29)))
        self.assertEqual(parse_script(_step(wait={"leave": "Language"})).steps[0].wait,
                         Wait("leave", "Language"))

    def test_emoji_mode(self):
        self.assertTrue(parse_script(_step(emoji_mode="search")).steps[0].emoji_mode)
        self.assertFalse(parse_script(_step(emoji_mode="tab")).steps[0].emoji_mode)
        self.assertIsNone(parse_script(_step()).steps[0].emoji_mode)
        # A script with an emoji_mode step needs protocol 37, whatever it declares.
        self.assertEqual(parse_script(_step(emoji_mode="search")).min_protocol, 37)
        self.assertEqual(parse_script(_step()).min_protocol, loader.BASE_PROTOCOL)
        for bad in ("on", ["search"], {"mode": "search"}, True):
            with self.assertRaises(ScriptError):
                parse_script(_step(emoji_mode=bad))

    def test_one_shot_layer_keycode(self):
        self.assertEqual(parse_script(_step(point={"keycode": "OSL(7)"})).steps[0].point,
                         Point("keycode", 0x5287))
        with self.assertRaises(ScriptError):
            parse_script(_step(point={"keycode": "OSL(32)"}))

    def test_refusals(self):
        bad = {
            "unknown top field": _script(colour="red"),
            "unknown step field": _step(colour="red"),
            "spotlight not a list": _step(spotlight={"keys": []}),
            "a spotlight item that is no key": _step(spotlight=[{"row": 1}]),
            "reveal without from": _step(reveal={"keycode": "KC_A"}),
            "reveal from a layer": _step(reveal={"from": {"layer": "MIDI"}}),
            "the old keycode wait": _step(wait={"keycode": "KC_A"}),
            "a line wider than the panel": _step(say=["Min 1/4 1/2 3/4 Max"]),
            "two lines over 59 bytes": _step(say=["i" * 30, "i" * 30]),
            "a typo in wait": _step(wait="nxt"),
            "two wait kinds": _step(wait={"seconds": 1, "layer": "Fn"}),
            "seconds not above 0": _step(wait={"seconds": 0}),
            "seconds as bool": _step(wait={"seconds": True}),
            "missing id": {k: v for k, v in _script().items() if k != "id"},
            "upper-case id": _script(id="Demo"),
            "unknown category": _script(category="games"),
            "no steps": _script(steps=[]),
            "a step that is no map": _script(steps=["Hold Fn"]),
            "three say lines": _step(say=["a", "b", "c"]),
            "non-ASCII on the OLED": _step(say=["Größe"]),
            "unknown keycode": _step(point={"keycode": "KC_NOPE"}),
            "keycode out of range": _step(point={"keycode": 0x10000}),
            "a key with one number": _step(point={"key": [1]}),
            "a negative key": _step(point={"key": [-1, 0]}),
            "point and guide": _step(point={"key": [0, 0]}, guide_to_layer="MIDI"),
            "empty layer name": _step(guide_to_layer=" "),
            "text not a string": _step(text=3),
            "min_protocol not a number": _script(min_protocol="35"),
            "not a map": ["id"],
        }
        for why, raw in bad.items():
            with self.subTest(why), self.assertRaises(ScriptError):
                parse_script(raw)

    def test_the_error_names_the_step(self):
        with self.assertRaises(ScriptError) as cm:
            parse_script(_script(steps=[{"say": "ok"}, {"wait": "nxt"}]))
        self.assertIn("steps[1].wait", str(cm.exception))


class FixedLayersTest(unittest.TestCase):
    """The layers the keyboard compiles in, from the shipped preview export."""

    def test_split72(self):
        fixed = loader.fixed_layers(10, 8)
        self.assertEqual(fixed["stored"], 9)
        self.assertEqual([name for name, _cells in fixed["layers"]],
                         ["Settings", "Language", "Intl", "Emoji"])
        cells = dict(fixed["layers"])
        self.assertEqual(cells["Settings"][(5, 4)], 0x7E11)     # KC_RGB_TOG
        self.assertEqual(cells["Emoji"][(1, 0)], 0x7E26)        # KC_EMJ_MODE
        self.assertEqual(cells["Intl"][(4, 1)], 0x7E23)         # KC_LAT_REMAP
        # LSLOT(0): a key with a function and no keycode the export can name.
        self.assertEqual(cells["Language"][(1, 1)], loader.FIXED_UNRESOLVED)

    def test_another_matrix_gets_none(self):
        self.assertIsNone(loader.fixed_layers(8, 6))


class PickTextTest(unittest.TestCase):
    def test_fallbacks(self):
        texts = {"en": "Hello", "de": "Hallo", "pt": "Olá"}
        self.assertEqual(loader.pick_text(texts, "de"), "Hallo")
        self.assertEqual(loader.pick_text(texts, "pt-BR"), "Olá")
        self.assertEqual(loader.pick_text(texts, "fr"), "Hello")
        self.assertEqual(loader.pick_text(texts, None), "Hello")
        self.assertEqual(loader.pick_text({"de": "Hallo"}, "fr"), "Hallo")
        self.assertEqual(loader.pick_text({}, "de"), "")


class LoadAllTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.shipped = os.path.join(self._tmp.name, "shipped")
        self.user = os.path.join(self._tmp.name, "user")
        os.makedirs(self.shipped)
        os.makedirs(self.user)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, directory, name, text):
        with open(os.path.join(directory, name), "w", encoding="utf-8") as f:
            f.write(text)

    def _yaml(self, tid, title):
        return f"id: {tid}\ncategory: other\ntitle: {title}\nsteps:\n  - say: Hi\n"

    def test_a_user_script_replaces_a_shipped_one(self):
        self._write(self.shipped, "a.yaml", self._yaml("a", "Shipped"))
        self._write(self.user, "a.yaml", self._yaml("a", "Mine"))
        found, errors = loader.load_all(self.shipped, self.user)
        self.assertEqual(errors, [])
        self.assertEqual(found["a"].title, {"en": "Mine"})
        self.assertTrue(found["a"].user)

    def test_errors_are_listed_and_the_rest_loads(self):
        self._write(self.user, "good.yml", self._yaml("good", "Good"))
        self._write(self.user, "bad.yaml", "id: [unclosed\n")
        self._write(self.user, "typo.yaml", self._yaml("typo", "T") + "    wait: nxt\n")
        self._write(self.user, "notes.txt", "not a script")
        self._write(self.user, ".hidden.yaml", "garbage: [")
        found, errors = loader.load_all(self.shipped, self.user)
        self.assertEqual(sorted(found), ["good"])
        self.assertEqual(sorted(os.path.basename(e["path"]) for e in errors),
                         ["bad.yaml", "typo.yaml"])

    def test_the_same_id_twice_in_one_folder(self):
        self._write(self.user, "1.yaml", self._yaml("a", "First"))
        self._write(self.user, "2.yaml", self._yaml("a", "Second"))
        found, errors = loader.load_all(self.shipped, self.user)
        self.assertEqual(found["a"].title, {"en": "First"})
        self.assertEqual(len(errors), 1)
        self.assertIn("2.yaml", errors[0]["path"])

    def test_a_missing_folder_is_empty(self):
        found, errors = loader.load_all(os.path.join(self.shipped, "nope"), None)
        self.assertEqual((found, errors), ({}, []))


if __name__ == "__main__":
    unittest.main()
