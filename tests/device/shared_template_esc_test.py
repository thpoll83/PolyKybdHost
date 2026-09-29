"""A template shared by several apps must leave ESC to each one's own mark.

Chrome, Chromium, Brave, Edge, Vivaldi, Opera and Arc share `chrome_template`
because Chromium browsers share their shortcuts. The template used to carry the
Chrome logo on ESC in all eight of its variants, bare ESC included. The program
mark stands down on any key a template draws, so every other browser in that
entry showed CHROME on plain ESC and its own mark only under chords such as
Ctrl+GUI+ESC (hardware round, 2026-09-29, Edge).

With ESC left blank, each browser's own mark -- Chrome's too -- takes the key on
all sixteen variants.

The JetBrains template had the same fault: a "JB" logo on ESC in twelve
variants across its three files, so IDEA, PyCharm, CLion and the rest all
showed the family logo instead of their own mark.
"""

import logging
import unittest
from pathlib import Path

import yaml

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"


def _needs_pil(case):
    try:
        import numpy             # noqa: F401
        from PIL import Image    # noqa: F401
    except Exception:
        case.skipTest("Pillow/numpy not installed")


class _SharedTemplateLeavesEsc:
    """Mixin: `ANCHOR` names the mapping entry, `SHARED` must all share it."""

    ANCHOR = ""
    SHARED: set = set()
    FILES = 0

    def setUp(self):
        _needs_pil(self)
        mapping = yaml.safe_load(
            (RES / "overlay-mapping.poly.yaml").read_text(encoding="utf-8"))
        self.key, self.entry = next(
            (k, v) for k, v in mapping.items()
            if self.ANCHOR in [n.strip() for n in str(k).split(",")])

    def test_the_entry_is_shared_by_more_than_one_app(self):
        """The premise: if the anchor app ever gets an entry of its own, a logo
        on its template's ESC is harmless again and this test can go."""
        names = {n.strip() for n in self.key.split(",")}
        self.assertTrue(self.SHARED <= names, names)

    def test_no_ESC_variant_in_the_shared_template(self):
        from polyhost.device.im_converter import ImageConverter
        logger = logging.getLogger("PolyHost")
        self.addCleanup(logger.setLevel, logger.level)
        logger.setLevel(logging.ERROR)
        esc = KeyCode.KC_ESCAPE.value
        overlays = self.entry["overlay"]
        self.assertEqual(self.FILES, len(overlays), overlays)
        for name in overlays:
            conv = ImageConverter(DeviceSettings())
            self.assertIsNot(conv.open(str(RES / "overlays" / name)), False, name)
            for mod in Modifier:
                with self.subTest(file=name, modifier=mod.name):
                    self.assertNotIn(esc, conv.extract_overlays(mod) or {})


class ChromiumTemplateLeavesEscTest(_SharedTemplateLeavesEsc, unittest.TestCase):
    ANCHOR = "chrome"
    SHARED = {"msedge", "brave", "vivaldi"}
    FILES = 2


class JetBrainsTemplateLeavesEscTest(_SharedTemplateLeavesEsc, unittest.TestCase):
    ANCHOR = "clion64"
    SHARED = {"idea64", "pycharm64", "webstorm64", "rider64"}
    FILES = 3

if __name__ == "__main__":
    unittest.main()
