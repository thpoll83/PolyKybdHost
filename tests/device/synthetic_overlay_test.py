"""The duck-typed overlay sources that carry the generic icon fall-back.

`send_overlays_mru` asks a source for `extract_overlays(modifier)` and does not
care whether a file was ever read — which is what lets a fetched icon ride the
whole existing transport (MRU cache, pool allocation, ROI/RLE, mapping commit)
with no firmware change at all. These pin the two rules that carry it: what the
pseudo-filename means, and what a source refuses to build.
"""

import unittest

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import Modifier

KC_S, KC_B = 0x16, 0x05


def settings():
    return DeviceSettings()


def mask(lit=True):
    """A 40x72 boolean frame — the shape OverlayData consumes."""
    m = np.zeros((40, 72), dtype=bool)
    if lit:
        m[10:20, 10:30] = True
    return m


class NamesTest(unittest.TestCase):
    """⚠️ THE NAME IS THE MRU CACHE KEY, so it must identify the CONTENT."""

    def test_a_program_name_carries_the_slug(self):
        """A fixed `@prog` would file GIMP's mark and Inkscape's under one key,
        and the second app focused would get the first one's icon out of the
        pool with no upload and no way to notice."""
        self.assertNotEqual(syn.program_name("gimp"), syn.program_name("inkscape"))

    def test_both_prefixes_read_as_synthetic(self):
        """The core filters on this to keep a source with no converter out of
        the file list — a name it did not recognise would reach
        `ImageConverter.open()` and fail the whole send."""
        self.assertTrue(syn.is_synthetic(syn.program_name("gimp")))
        self.assertTrue(syn.is_synthetic("@sc:save:32lower_left"))
        self.assertTrue(syn.is_shortcut("@sc:save:32lower_left"))
        self.assertFalse(syn.is_shortcut(syn.program_name("gimp")))
        self.assertFalse(syn.is_synthetic("vscode_template.mods.png"))
        self.assertFalse(syn.is_synthetic(""))


class ShortcutConverterTest(unittest.TestCase):

    def test_one_icon_on_several_keys_is_ONE_source(self):
        """The mask does not depend on the key, so rendering it per key would be
        the same pixels in several pool slots."""
        conv = syn.shortcut_converter(
            settings(), {(Modifier.CTRL.value, KC_S): mask(),
                         (Modifier.CTRL.value, KC_B): mask()})
        self.assertEqual(set(conv.extract_overlays(Modifier.CTRL)), {KC_S, KC_B})
        self.assertEqual(len(conv), 2)

    def test_the_harvested_nibble_IS_the_modifier(self):
        """No mapping in between — see the note in shortcut_overlays.plan()."""
        conv = syn.shortcut_converter(
            settings(), {(Modifier.CTRL_SHIFT.value, KC_S): mask()})
        self.assertIsNone(conv.extract_overlays(Modifier.CTRL))
        self.assertEqual(set(conv.extract_overlays(Modifier.CTRL_SHIFT)), {KC_S})

    def test_an_unknown_modifier_value_is_DROPPED_not_guessed(self):
        """16 is outside the nibble and addresses no flat index the firmware
        has, so inventing a variant for it would upload into nowhere."""
        conv = syn.shortcut_converter(settings(), {(16, KC_S): mask(),
                                                   (Modifier.CTRL.value, KC_B): mask()})
        self.assertEqual(len(conv), 1)

    def test_an_ALL_BLACK_mask_is_dropped(self):
        """`OverlayData` refuses one, and an empty overlay would cost a pool slot
        to draw exactly nothing."""
        conv = syn.shortcut_converter(settings(), {(Modifier.CTRL.value, KC_S): mask(lit=False)})
        self.assertIsNone(conv)

    def test_nothing_at_all_is_None_rather_than_an_empty_source(self):
        self.assertIsNone(syn.shortcut_converter(settings(), {}))
        self.assertIsNone(syn.shortcut_converter(settings(), None))

    def test_it_answers_the_two_methods_the_send_loop_calls(self):
        conv = syn.shortcut_converter(settings(), {(Modifier.CTRL.value, KC_S): mask()})
        self.assertTrue(conv.open("@sc:save:32lower_left"))
        self.assertIsNone(conv.extract_overlays(Modifier.ALT))


if __name__ == "__main__":
    unittest.main()
