"""The committed slicer binding files are what gen_slicer_bindings.py writes
from keys.yaml, so a table edit cannot ship without regenerating them."""

import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "gen_slicer_bindings",
    Path(__file__).resolve().parents[2] / "polyhost/res/overlay_sources/slicers/gen_slicer_bindings.py")
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


class CommittedBindingsTest(unittest.TestCase):

    def test_every_binding_file_is_what_the_generator_writes(self):
        keys = gen.load_keys()
        for name in gen.SETS:
            with self.subTest(name):
                path = gen.HERE / f"bindings_{name}.yaml"
                self.assertEqual(path.read_text(encoding="utf-8"), gen.render(name, keys),
                                 "run python polyhost/res/overlay_sources/slicers/gen_slicer_bindings.py")


if __name__ == "__main__":
    unittest.main()
