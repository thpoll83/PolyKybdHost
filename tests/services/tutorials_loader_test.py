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
        self.assertIn("midi-layer", found)
        self.assertIn("brightness", found)
        for t in found.values():
            self.assertIn(t.category, loader.CATEGORIES)
            self.assertIn("en", t.title)
            self.assertFalse(t.user)

    def test_the_custom_keycodes_resolve(self):
        # PolyKybd's own keycodes come from legends.json, not keycodes.h.
        brightness = loader.load_all()[0]["brightness"]
        points = [s.point for s in brightness.steps if s.point]
        self.assertIn(Point("keycode", 0x7E1D), points)       # KC_DAUTO
        self.assertIn(Point("keycode", 0x5207), points)       # TO(7)


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

    def test_waits(self):
        self.assertEqual(parse_script(_step(wait={"seconds": 3})).steps[0].wait,
                         Wait("seconds", 3.0))
        self.assertEqual(parse_script(_step(wait={"layer": "MIDI"})).steps[0].wait,
                         Wait("layer", "MIDI"))
        self.assertEqual(parse_script(_step(wait={"press": "KC_ESC"})).steps[0].wait,
                         Wait("press", 0x29))

    def test_refusals(self):
        bad = {
            "unknown top field": _script(colour="red"),
            "unknown step field": _step(spotlight={"keys": []}),
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
