"""Every template that draws a concept must draw the SAME BYTES.

⚠️ This is what makes a concept cost ONE pool slot board-wide instead of one
per application. `overlay_cache.get_or_allocate` dedupes by content --

    if bytes_data is not None and bytes_data in self._bytes_to_slot:

-- so two templates whose Copy differs by a single pixel occupy two slots and
re-upload on every switch between them, while identical bytes are a free hit.
Measured over the committed artwork: the 29 concepts the templates name were
drawn **84** different ways before the shared renderer and **33** after, the
four extras being the bindings that deliberately opt out.

⚠️ IT CANNOT BE ACHIEVED BY TUNING GEOMETRY, which is why the fix was one
renderer rather than two agreeing ones. The same Fluent `save` through cairosvg
and through FreeType agrees on 2799 of 2880 pixels and differs on 81, all
stroke-edge antialiasing landing on opposite sides of the 1-bit threshold.

⚠️ The survey asks the GENERATOR which bindings share (`concept_to_share`)
rather than re-deriving it. A second copy of that rule would drift the moment
either moved and nothing would go red -- the test would simply survey a
different set than the generator writes, which is agreement by construction in
the one place it must not be.

This runs OFFLINE against the COMMITTED artwork, deliberately: the drift it
guards against is somebody regenerating one app without the others, or editing
a PNG by hand, and neither needs a network to detect. The other half of the
contract -- that a template cell equals what the running app renders -- needs
the icon font and so is checked by the generator itself.
"""

import glob
import hashlib
import importlib.util
import os
import unittest

import numpy as np
import yaml
from PIL import Image

from polyhost.device.keys import KeyCode

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = os.path.join(REPO, "polyhost", "res", "overlay_sources")
OVERLAYS = os.path.join(REPO, "polyhost", "res", "overlays")
CELL_W, CELL_H = 72, 40
CTRL_CHANNEL = 0                      # R, per the overlay spec


def _generator():
    """`scripts/` is not a package, so import the module by path."""
    path = os.path.join(REPO, "scripts", "generate_app_overlays.py")
    spec = importlib.util.spec_from_file_location("_gen_app_overlays", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cell(arr, keycode):
    """The 72x40 Ctrl-channel cell for one keycode, as `im_converter` slices it."""
    index = keycode - KeyCode.KC_A.value
    row, col = divmod(index, 10)
    block = arr[row * CELL_H:(row + 1) * CELL_H,
                col * CELL_W:(col + 1) * CELL_W, CTRL_CHANNEL]
    return block > 127


def _shared_cells():
    """{concept: {sha: [app, ...]}} over every Ctrl-only binding that SHARES."""
    gen = _generator()
    out = {}
    for path in sorted(glob.glob(os.path.join(SOURCES, "*", "bindings.yaml"))):
        app = os.path.basename(os.path.dirname(path))
        with open(path, encoding="utf-8") as fh:
            spec = yaml.safe_load(fh) or {}
        png = os.path.join(OVERLAYS, "%s.mods.png" % spec.get("output", ""))
        if not os.path.exists(png):
            continue
        arr = np.asarray(Image.open(png).convert("RGBA"))
        for binding in (spec.get("bindings") or []):
            if [str(m).upper() for m in (binding.get("mods") or [])] != ["CTRL"]:
                continue
            concept = gen.concept_to_share(binding)
            if not concept:
                continue
            try:
                keycode = getattr(KeyCode, "KC_%s" % str(binding["key"]).upper()).value
            except (AttributeError, KeyError):
                continue
            mask = _cell(arr, keycode)
            if not mask.any():
                continue
            digest = hashlib.sha256(mask.tobytes()).hexdigest()
            out.setdefault(concept, {}).setdefault(digest, []).append(app)
    return out


class TemplatesAgreeOnAConceptTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.shared = _shared_cells()

    def test_the_fixture_actually_found_artwork(self):
        """⚠️ Without this the whole class passes vacuously — a renamed output
        or a moved directory makes every loop below iterate nothing, and an
        empty survey is indistinguishable from perfect agreement."""
        self.assertGreater(len(self.shared), 10, "no shared cells surveyed")
        self.assertGreater(sum(len(v) for apps in self.shared.values()
                               for v in apps.values()), 100)

    def test_a_concept_is_ONE_drawing_across_every_template(self):
        offenders = {c: {d[:8]: apps for d, apps in v.items()}
                     for c, v in self.shared.items() if len(v) > 1}
        self.assertEqual(
            offenders, {},
            "each of these concepts is drawn more than one way, so it takes "
            "one pool slot PER DRAWING and re-uploads on every app switch. "
            "Re-run scripts/generate_app_overlays.py for the apps listed.")

    def test_at_least_one_concept_is_shared_by_SEVERAL_apps(self):
        """The property the dedupe pays off on — a concept only one app draws
        would satisfy the test above trivially."""
        widest = max(len(apps) for v in self.shared.values() for apps in v.values())
        self.assertGreaterEqual(widest, 5)


class WhichBindingsShareTest(unittest.TestCase):
    """The predicate itself, since the survey above can only see its verdict."""

    def setUp(self):
        self.gen = _generator()

    def test_a_label_that_NAMES_the_concept_shares(self):
        self.assertEqual(self.gen.concept_to_share({"label": "Copy"}), "copy")
        self.assertEqual(self.gen.concept_to_share({"label": "Bookmarks"}),
                         "bookmark")            # spelling fold, so a plural lands

    def test_a_label_that_merely_FOLDS_to_a_concept_does_NOT(self):
        """⚠️ The whole reason this predicate is narrower than `match()`.
        `match()` answers "what icon beats a text label", which is a different
        question from "is this the same picture somebody already drew"."""
        for label in ("Copy merged", "Duplicate line", "Go to definition",
                      "New folder", "Clear screen", "Close HTML tag"):
            self.assertEqual(self.gen.concept_to_share({"label": label}), "",
                             "%r must keep its own artwork" % label)

    def test_shared_false_opts_out(self):
        self.assertEqual(
            self.gen.concept_to_share({"label": "Copy", "shared": False}), "")

    def test_an_explicit_GEOMETRY_key_opts_out(self):
        """The shared renderer owns the placement, so it cannot honour one made
        by hand — and ignoring it would discard somebody's decision."""
        for key, value in (("region", [72, 40]), ("anchor", "center"),
                           ("margin", 0), ("fit", "stretch"),
                           ("threshold", 150), ("mode", "luma")):
            self.assertEqual(
                self.gen.concept_to_share({"label": "Copy", key: value}), "",
                "%r must opt out of sharing" % key)


if __name__ == "__main__":
    unittest.main()
