"""Properties of the tutorial script loader (services/tutorials/loader.py).

A user puts their own scripts in ``<config dir>/tutorials/``. A file that cannot be
used is reported as a ScriptError, which ``load_all`` lists next to the scripts
that load; any other exception stops the whole listing."""
import os
import tempfile
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.tutorials import loader
from polyhost.services.tutorials.loader import Point, ScriptError, Step, Wait

load_profile()

# What yaml.safe_load can give: scalars, lists, and maps whose keys are any
# hashable scalar (`1: x`, `null: x`, `yes: x`).
KEY = st.one_of(st.text(max_size=8), st.integers(-3, 3), st.none(), st.booleans(), st.floats())
SCALAR = st.one_of(st.none(), st.booleans(), st.integers(-2, 0x10002), st.floats(),
                   st.text(max_size=10), st.sampled_from(
                       ["KC_A", "kc_esc", "OSL(3)", "OSL(99)", "MO(1)", "next", "MIDI", " ",
                        "KC_DAUTO", "LCTL(KC_C)", "S(KC_1)", "0x7E00"]),
                   st.sampled_from([0, 0.0, -0.0, -1, 0xFFFF, 0x10000, 0x1F, 0x20]))
YAMLISH = st.recursive(SCALAR, lambda inner: st.lists(inner, max_size=3)
                       | st.dictionaries(KEY, inner, max_size=3), max_leaves=10)

# Not st.integers(0, 9) == 0: Hypothesis draws the low end of a range often.
ONE_IN_TEN = st.sampled_from([False] * 9 + [True])
STEP_FIELD = st.sampled_from(sorted(loader._STEP_KEYS))
POINT = st.one_of(YAMLISH, st.sampled_from([
    {"keycode": 0x10000}, {"keycode": -1}, {"keycode": True}, {"keycode": "OSL(32)"},
    {"key": [0, -1]}, {"key": [0, True]}, {"key": [1, 2, 3]}, {"layer_key": ""}]),
    st.dictionaries(st.sampled_from(sorted(loader._POINT_KINDS)
                                                           + ["layer"]), YAMLISH,
                                           min_size=1, max_size=2))
STEP_VALUE = {
    "say": st.one_of(YAMLISH, st.lists(st.text(max_size=12), min_size=1, max_size=3)),
    "text": YAMLISH,
    "point": POINT,
    "guide_to_layer": YAMLISH,
    "spotlight": st.one_of(YAMLISH, st.lists(POINT, max_size=3)),
    "reveal": st.one_of(YAMLISH, st.fixed_dictionaries({"from": POINT})),
    "wait": st.one_of(YAMLISH, st.sampled_from([
        {"seconds": 0}, {"seconds": -1}, {"seconds": 0.0}, {"seconds": "2"},
        {"press": 0x10000}, {"press": -1}, {"key": {"key": [-1, 0]}}, {"layer": " "}]),
        st.dictionaries(st.sampled_from(sorted(loader._WAIT_KINDS)),
                                               st.one_of(YAMLISH, POINT), min_size=1,
                                               max_size=1)),
}


@st.composite
def near_scripts(draw):
    # Half of the scripts have a valid header, so their steps are what is tested.
    valid = draw(st.booleans())
    raw = {"id": "demo" if valid else draw(st.one_of(st.sampled_from(["a-1", "Bad", "-x"]),
                                                     YAMLISH)),
           "category": "other" if valid else draw(st.one_of(st.sampled_from(loader.CATEGORIES),
                                                            YAMLISH)),
           "title": "T" if valid else draw(st.one_of(st.text(max_size=8), YAMLISH)),
           "steps": draw(st.lists(near_steps(), min_size=1, max_size=3) if valid else
                         st.one_of(st.lists(st.one_of(near_steps(), YAMLISH), max_size=3),
                                   YAMLISH))}
    for key in () if valid else draw(st.lists(st.sampled_from(sorted(loader._SCRIPT_KEYS)),
                                              max_size=2)):
        raw.pop(key, None)
    if draw(st.booleans()):
        raw["summary"] = draw(YAMLISH)
    if draw(st.booleans()):
        raw["min_protocol"] = draw(st.integers(-5, 99)) if valid else draw(YAMLISH)
    if not valid and draw(ONE_IN_TEN):
        raw[draw(KEY)] = draw(YAMLISH)
    return raw


# A valid step, generated with the Step it must parse to.
LAYER = st.text("ABCMIDFnu", min_size=1, max_size=6)
VALID_POINT = st.one_of(
    st.integers(0, 0xFFFF).map(lambda v: ({"keycode": v}, Point("keycode", v))),
    LAYER.map(lambda n: ({"layer_key": " " + n}, Point("layer_key", n))),
    st.tuples(st.integers(0, 9), st.integers(0, 15)).map(
        lambda rc: ({"key": list(rc)}, Point("key", rc))))
VALID_WAIT = st.one_of(
    st.just(("next", Wait("next"))),
    st.floats(0.01, 1e6).map(lambda s: ({"seconds": s}, Wait("seconds", s))),
    st.integers(1, 600).map(lambda s: ({"seconds": s}, Wait("seconds", float(s)))),
    st.tuples(st.sampled_from(["layer", "leave"]), LAYER).map(
        lambda kv: ({kv[0]: kv[1]}, Wait(kv[0], kv[1]))),
    st.integers(0, 0xFFFF).map(lambda v: ({"press": v}, Wait("press", v))),
    VALID_POINT.map(lambda p: ({"key": p[0]}, Wait("key", p[1]))))
SAY_LINE = st.text("abcdefghij XYZ.!", min_size=1, max_size=9)


@st.composite
def valid_steps(draw):
    raw, want = {}, {}
    if draw(st.booleans()):
        lines = draw(st.lists(SAY_LINE, min_size=1, max_size=2))
        raw["say"] = lines[0] if len(lines) == 1 and draw(st.booleans()) else lines
        want["say"] = tuple(lines)
    if draw(st.booleans()):
        text = draw(st.dictionaries(st.sampled_from(["en", "de", "pt-BR"]),
                                    st.text(max_size=8), min_size=1))
        raw["text"], want["text"] = text, text
    ring = draw(st.sampled_from(["point", "guide", None]))
    if ring == "point":
        raw["point"], want["point"] = draw(VALID_POINT)
    elif ring == "guide":
        name = draw(LAYER)
        raw["guide_to_layer"], want["guide_to_layer"] = name + "  ", name
    if draw(st.booleans()):
        items = draw(st.lists(st.one_of(VALID_POINT, LAYER.map(
            lambda n: ({"layer": n}, Point("layer", n)))), max_size=3))
        raw["spotlight"] = [r for r, _ in items]
        want["spotlight"] = tuple(p for _, p in items)
    if draw(st.booleans()):
        r, p = draw(VALID_POINT)
        raw["reveal"], want["reveal"] = {"from": r}, p
    if draw(st.booleans()):
        raw["wait"], want["wait"] = draw(VALID_WAIT)
    return raw, Step(**want)


@st.composite
def near_steps(draw):
    """A valid step with, most of the time, one field changed to junk or one
    unknown field added: each refusal is then tested on its own."""
    step, _ = draw(valid_steps())
    if draw(st.sampled_from([True] * 4 + [False])):
        field = draw(STEP_FIELD)
        step[field] = draw(STEP_VALUE[field])
    if draw(ONE_IN_TEN):
        step[draw(KEY)] = draw(YAMLISH)        # an unknown field, maybe not a string
    return step


class TutorialScriptFuzzTest(unittest.TestCase):
    @given(st.one_of(YAMLISH, near_scripts()))
    def test_parse_raises_only_script_error(self, raw):
        try:
            t = loader.parse_script(raw)
        except ScriptError:
            return
        self.assertTrue(loader._ID.fullmatch(t.id))
        self.assertIn(t.category, loader.CATEGORIES)
        self.assertGreaterEqual(t.min_protocol, loader.BASE_PROTOCOL)
        self.assertTrue(t.steps)
        for step in t.steps:
            self.assertFalse(step.point is not None and step.guide_to_layer is not None)
            self.assertTrue(all(0x20 <= ord(c) <= 0x7E for line in step.say for c in line))
            points = [step.point, step.reveal, *(step.spotlight or ())]
            if step.wait.kind == "seconds":
                self.assertGreater(step.wait.value, 0)
            elif step.wait.kind == "press":
                self.assertTrue(0 <= step.wait.value <= 0xFFFF)
            elif step.wait.kind == "key":
                points.append(step.wait.value)
            for point in filter(None, points):
                if point.kind == "keycode":
                    self.assertTrue(0 <= point.value <= 0xFFFF)
                elif point.kind == "key":
                    self.assertTrue(all(type(n) is int and n >= 0 for n in point.value))
                else:
                    self.assertTrue(point.value and point.value == point.value.strip())

    @given(st.sampled_from(["demo", "x", "a-b-9"]), st.sampled_from(loader.CATEGORIES),
           st.integers(-5, 99), st.lists(valid_steps(), min_size=1, max_size=4))
    def test_a_valid_script_parses_to_its_model(self, tid, category, min_protocol, steps):
        raw = {"id": tid, "category": category, "title": {"en": "T", "de": "U"},
               "min_protocol": min_protocol, "steps": [r for r, _ in steps]}
        t = loader.parse_script(raw)
        self.assertEqual((t.id, t.category, t.title, t.summary, t.min_protocol),
                         (tid, category, {"en": "T", "de": "U"}, {},
                          max(loader.BASE_PROTOCOL, min_protocol)))
        self.assertEqual(t.steps, tuple(s for _, s in steps))


YAML_TEXT = st.lists(st.sampled_from(
    ["id: demo\n", "category: other\n", "title: T\n", "steps:\n", "  - say: Hi\n",
     "  - wait: {seconds: 2}\n", "  - 1: x\n", "  - {? [a]: b}\n", "a: 2001-13-01\n",
     "b: 2001-01-01\n", "x: &a [*a]\n", "!!python/object:os.system x\n", ": : :\n",
     "\t", "- ", "{", "[", "'", "\"\\x\"\n", "y: !!binary 'a'\n", "z: !!int x\n",
     "\ufeff", "\x00", "%YAML 9.9\n---\n"]), max_size=8).map("".join)


class TutorialFileFuzzTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "t.yaml")

    def tearDown(self):
        self._dir.cleanup()

    @given(st.one_of(YAML_TEXT, st.text(max_size=40)))
    def test_load_file_raises_only_script_error(self, text):
        with open(self.path, "w", encoding="utf-8", errors="surrogatepass") as fh:
            fh.write(text)
        try:
            loader.load_file(self.path, user=True)
        except ScriptError:
            pass  # a documented refusal; any other exception fails the test
        found, errors = loader.load_all(shipped_dir="", user_directory=self._dir.name)
        self.assertEqual(len(found) + len(errors), 1)


if __name__ == "__main__":
    unittest.main()
