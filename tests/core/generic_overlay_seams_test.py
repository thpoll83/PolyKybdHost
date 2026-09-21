"""The four seams between the generic path and everything it asks.

Each was **0% covered** and each is a place where a wrong answer produces a
plausible board rather than an error: an empty template list blanks the keycaps
a fill was meant to preserve, a forwarded window resolved against the local
machine draws the wrong app's mark, an all-black mask becomes a converter that
uploads nothing, and a build-time renderer that falls back instead of raising
emits the OLD artwork under a diff that reads "nothing changed".
"""

import importlib.util
import os
import unittest
from unittest.mock import MagicMock

import numpy as np

from polyhost.core.poly_core import PolyCore

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TemplateFileListTest(unittest.TestCase):
    """`PolyCore._template_files` — the list the gap fill sends ahead of its own."""

    def test_NO_overlay_data_is_an_EMPTY_tuple_not_a_None_that_crashes(self):
        """The fill branch calls this unconditionally, so "no data" has to be a
        value `list(...)` accepts rather than something the send trips over."""
        handler = MagicMock()
        handler.get_overlay_data.return_value = None
        self.assertEqual(PolyCore._template_files(handler), ())

    def test_a_SINGLE_name_is_wrapped_rather_than_walked_as_CHARACTERS(self):
        """⚠️ `get_overlay_data` answers a bare string for a one-file entry, and
        iterating a string yields letters -- which would send one bogus path per
        character and blank the board."""
        handler = MagicMock()
        handler.get_overlay_data.return_value = "gimp_template.mods.png"
        files = PolyCore._template_files(handler)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith("gimp_template.mods.png"))
        self.assertTrue(os.path.isabs(files[0]) or os.sep in files[0],
                        "the name must be resolved to a path, not passed raw")

    def test_a_LIST_keeps_its_ORDER(self):
        """The primary file must stay ahead of the combo one: `send_overlays_mru`
        walks the list in order and an earlier source claims its keys first."""
        handler = MagicMock()
        handler.get_overlay_data.return_value = ["a.mods.png", "a.combo.mods.png"]
        files = PolyCore._template_files(handler)
        self.assertEqual([os.path.basename(f) for f in files],
                         ["a.mods.png", "a.combo.mods.png"])



class SyntheticConverterTest(unittest.TestCase):
    """`shortcut_converter` — what an unusable mask becomes."""

    def _converter(self, keys):
        from polyhost.device.device_settings import DeviceSettings
        from polyhost.device.synthetic_overlay import shortcut_converter
        return shortcut_converter(DeviceSettings(), keys)

    def test_an_ALL_BLACK_mask_yields_NO_converter(self):
        """⚠️ Not an empty one. A converter with no overlays would be sent, take
        a pool slot and a mapping entry, and draw nothing -- so the keycap would
        lose whatever the template had put there, in exchange for blank."""
        dark = np.zeros((40, 72), dtype=bool)
        self.assertIsNone(self._converter({(0, 4): dark}))

    def test_an_UNKNOWN_modifier_value_is_SKIPPED_not_raised(self):
        """The keys come from the fetcher's plan, which is built from an app's
        own accelerators -- attacker-shaped on the relay path."""
        lit = np.zeros((40, 72), dtype=bool)
        lit[10:20, 10:20] = True
        self.assertIsNone(self._converter({(999, 4): lit}))

    def test_a_LIT_mask_DOES_yield_a_converter(self):
        """The control: without this the two above pass for a function that
        always returns None."""
        lit = np.zeros((40, 72), dtype=bool)
        lit[10:20, 10:20] = True
        self.assertIsNotNone(self._converter({(0, 4): lit}))


class SharedConceptMaskTest(unittest.TestCase):
    """The generator's build-time renderer — it must RAISE, never fall back."""

    def setUp(self):
        path = os.path.join(REPO, "scripts", "generate_app_overlays.py")
        spec = importlib.util.spec_from_file_location("_gen_shared", path)
        self.gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gen)

    def test_an_UNREACHABLE_catalog_RAISES_rather_than_returning_None(self):
        """⚠️ The rule with the sharpest failure behind it. A silent fall-back
        would emit the OLD artwork, so the regenerated tree would be identical
        and the diff would read "nothing changed" -- the worst outcome available
        to a build script, because it is indistinguishable from success."""
        import polyhost.services.icon_catalog as ic
        real_font, real_table = ic.fetch_subset, ic.load_codepoints
        ic.fetch_subset = lambda *a, **k: None
        ic.load_codepoints = lambda *a, **k: {}
        try:
            with self.assertRaises(RuntimeError) as caught:
                self.gen.shared_concept_mask("copy")
            self.assertIn("copy", str(caught.exception),
                          "the error must name the concept that could not be drawn")
        finally:
            ic.fetch_subset, ic.load_codepoints = real_font, real_table

    def test_a_concept_with_NO_icon_name_is_a_quiet_None(self):
        """Distinct from the raise: nothing to draw is not a failure to draw."""
        import polyhost.services.shortcut_icons as si
        real = si.icon_for
        si.icon_for = lambda concept: ""
        try:
            self.assertEqual(self.gen.shared_concept_mask("copy"), (None, ""))
        finally:
            si.icon_for = real


if __name__ == "__main__":
    unittest.main()
