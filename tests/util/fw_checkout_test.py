"""fw_checkout finds firmware files in both qmk_firmware layouts.

The 2026-11 firmware move put the root sources into folders (keymap/, modes/, ...)
and base/fonts into fonts/. A host run against either checkout must find the same
files, and must not mistake the generator directory fonts/ of the old layout for
the header directory.
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
        want = _touch(self.pk, "keymap/poly_keymap.c")
        _touch(self.pk, "fonts/gfxfont.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keymap/poly_keymap.c"), want)
        self.assertEqual(fw_checkout.font_dir(self.pk), os.path.join(self.pk, "fonts"))

    def test_layout_before_the_move(self):
        want = _touch(self.pk, "poly_keymap.c")
        _touch(self.pk, "base/fonts/gfxfont.h")
        _touch(self.pk, "fonts/fonts.yaml")          # the generator dir exists too
        self.assertEqual(fw_checkout.fw_file(self.pk, "keymap/poly_keymap.c"), want)
        self.assertEqual(fw_checkout.font_dir(self.pk),
                         os.path.join(self.pk, "base", "fonts"))

    def test_current_path_takes_priority(self):
        # The current layout keeps forwarding headers at the root for old keymaps;
        # the lookup must return the real header in keymap/, not the forwarder.
        want = _touch(self.pk, "keymap/keycode_helper.h")
        _touch(self.pk, "keycode_helper.h")
        self.assertEqual(fw_checkout.fw_file(self.pk, "keymap/keycode_helper.h"), want)

    def test_missing_file_reports_the_current_path(self):
        self.assertEqual(fw_checkout.fw_file(self.pk, "modes/midi_legend.c"),
                         os.path.join(self.pk, "modes", "midi_legend.c"))
        self.assertEqual(fw_checkout.font_dir(self.pk), os.path.join(self.pk, "fonts"))

    def test_unlisted_file_is_joined_unchanged(self):
        self.assertEqual(fw_checkout.fw_file(self.pk, "lang/named_glyphs.h"),
                         os.path.join(self.pk, "lang", "named_glyphs.h"))


if __name__ == "__main__":
    unittest.main()
