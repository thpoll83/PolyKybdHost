"""fw_checkout finds firmware files in all three qmk_firmware layouts.

The firmware moved its sources twice in 2026-11: first out of the
keyboards/polykybd root into folders (keymap/, modes/, ...) and base/fonts into
fonts/, then into groups (keymap/ -> keys_com/, modes/ -> features/modes/,
hid/ -> lib/hid/, system/ -> lib/system/, layers.h -> keys_com/layers.h). A host
run against any of these checkouts must find the same files, and must not
mistake the generator directory fonts/ of the first layout for the header
directory.
"""
import os
import tempfile
import unittest

from polyhost.util import fw_checkout


def _touch(root, rel):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("")
    return path


class FwCheckoutTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pk = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_current_layout(self):
        want = _touch(self.pk, "keys_com/poly_keymap.c")
        _touch(self.pk, "fonts/gfxfont.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keys_com/poly_keymap.c"), want)
        self.assertEqual(fw_checkout.font_dir(self.pk), os.path.join(self.pk, "fonts"))

    def test_layout_with_folders_before_the_groups(self):
        for cur, old in (("keys_com/poly_keymap.c", "keymap/poly_keymap.c"),
                         ("features/modes/midi_legend.c", "modes/midi_legend.c"),
                         ("lib/hid/hid_com.c", "hid/hid_com.c"),
                         ("lib/system/state.h", "system/state.h")):
            want = _touch(self.pk, old)
            self.assertEqual(fw_checkout.fw_file(self.pk, cur), want, cur)

    def test_layout_before_the_first_move(self):
        want = _touch(self.pk, "poly_keymap.c")
        _touch(self.pk, "base/fonts/gfxfont.h")
        _touch(self.pk, "fonts/fonts.yaml")          # the generator dir exists too
        self.assertEqual(fw_checkout.fw_file(self.pk, "keys_com/poly_keymap.c"), want)
        self.assertEqual(fw_checkout.font_dir(self.pk),
                         os.path.join(self.pk, "base", "fonts"))

    def test_layers_h_at_the_root_in_both_older_layouts(self):
        want = _touch(self.pk, "layers.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keys_com/layers.h"), want)

    def test_newer_older_path_takes_priority(self):
        # A checkout of the folder layout still had the root forwarding headers;
        # the lookup must return the real header in keymap/, not the forwarder.
        want = _touch(self.pk, "keymap/keycode_helper.h")
        _touch(self.pk, "keycode_helper.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keys_com/keycode_helper.h"), want)

    def test_current_path_takes_priority(self):
        want = _touch(self.pk, "keys_com/keycode_helper.h")
        _touch(self.pk, "keymap/keycode_helper.h")
        _touch(self.pk, "keycode_helper.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keys_com/keycode_helper.h"), want)

    def test_missing_file_reports_the_current_path(self):
        self.assertEqual(fw_checkout.fw_file(self.pk, "features/modes/midi_legend.c"),
                         os.path.join(self.pk, "features/modes/midi_legend.c"))
        self.assertEqual(fw_checkout.font_dir(self.pk), os.path.join(self.pk, "fonts"))

    def test_language_layer_in_both_older_layouts(self):
        # tools/lang_layer_demo.py reads both files through fw_file.
        for layout in ("", "keymap/"):
            with self.subTest(layout=layout or "root"), tempfile.TemporaryDirectory() as pk:
                for name in ("lang_layer.c", "lang_layer.h"):
                    want = _touch(pk, layout + name)
                    self.assertEqual(fw_checkout.fw_file(pk, "keys_com/" + name), want)

    def test_unlisted_file_is_joined_unchanged(self):
        self.assertEqual(fw_checkout.fw_file(self.pk, "lang/named_glyphs.h"),
                         os.path.join(self.pk, "lang/named_glyphs.h"))


if __name__ == "__main__":
    unittest.main()
