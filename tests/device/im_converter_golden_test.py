"""Golden byte-equality test gating the QImage -> Pillow rewrite of ImageConverter.

The reference implementation below is a verbatim copy of the original QImage
decode path that lived in ``polyhost/device/im_converter.py`` before the Pillow
rewrite (phase H0a of the headless-core plan). For every shipped overlay
fixture we decode it both ways and assert that the *complete* extracted
``OverlayData`` output is byte-identical for every ``Modifier`` -- if it isn't,
every keycap on real hardware would render differently.

The reference path imports PyQt5; the main suite runs with Qt available. A
QApplication is not required for QImage decoding. The suite convention is to set
``QT_QPA_PLATFORM=offscreen`` anyway.
"""

import glob
import os
import unittest

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import Modifier
# Installs logging.Logger.debug_detailed used by ImageConverter.
from polyhost.util import log_util  # noqa: F401


OVERLAY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "polyhost", "res", "overlays",
)


def _reference_open(converter, filename):
    """Original QImage-based ImageConverter.open(), copied verbatim.

    Populates ``converter.image`` / ``converter.w`` / ``converter.h`` exactly as
    the pre-Pillow code did, so the rest of ImageConverter (extract_overlays)
    runs unchanged against the reference array.
    """
    from PyQt5.QtGui import QImage

    q_image = QImage()
    if not q_image.load(filename):
        return False
    converter.w = q_image.width()
    converter.h = q_image.height()

    has_alpha = q_image.hasAlphaChannel()
    q_image = q_image.convertToFormat(
        QImage.Format_ARGB32 if has_alpha else QImage.Format_RGB888)
    depth = 4 if has_alpha else 3
    buf = q_image.constBits()
    buf.setsize(q_image.bytesPerLine() * q_image.height())
    im = np.ndarray((q_image.height(), q_image.width(), depth), buffer=buf,
                    strides=[q_image.bytesPerLine(), depth, 1], dtype=np.uint8)

    if ".mods." in filename:
        if ".combo.mods." in filename:
            key_a = Modifier.GUI_KEY
            key_r = Modifier.CTRL_SHIFT
            key_g = Modifier.CTRL_ALT
            key_b = Modifier.ALT_SHIFT
        else:
            key_a = Modifier.NO_MOD
            key_r = Modifier.CTRL
            key_g = Modifier.ALT
            key_b = Modifier.SHIFT
        if not has_alpha:
            [b, g, r] = np.dsplit(im, im.shape[-1])
            converter.image[key_r] = np.array(r, dtype=bool)
            converter.image[key_g] = np.array(g, dtype=bool)
            converter.image[key_b] = np.array(b, dtype=bool)
        else:
            [b, g, r, a] = np.dsplit(im, im.shape[-1])
            converter.image[key_a] = np.array(a, dtype=bool)
            converter.image[key_r] = np.array(r, dtype=bool)
            converter.image[key_g] = np.array(g, dtype=bool)
            converter.image[key_b] = np.array(b, dtype=bool)
    else:
        converter.image[Modifier.NO_MOD] = np.array(
            np.dot(im[..., :3], [0.2989 / 255, 0.5870 / 255, 0.1140 / 255]),
            dtype=bool)

    if Modifier.GUI_KEY in converter.image:
        converter.image.pop(Modifier.GUI_KEY)

    return True


class _ReferenceConverter(ImageConverter):
    """ImageConverter whose open() is the original QImage path."""

    def open(self, filename):  # noqa: A003 - mirror the production signature
        return _reference_open(self, filename)


def _overlaydata_tuple(od):
    return (
        od.all_bytes,
        od.compressed_bytes,
        od.roi_bytes,
        od.compressed_roi_bytes,
        od.roi,
        od.top, od.left, od.bottom, od.right,
    )


class TestImConverterGolden(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.settings = DeviceSettings()
        cls.fixtures = sorted(glob.glob(os.path.join(OVERLAY_DIR, "*.png")))
        assert cls.fixtures, "no overlay fixtures found in %s" % OVERLAY_DIR

    def _all_modifiers_present(self, conv):
        return [m for m in Modifier if m in conv.image]

    def test_fixtures_exist(self):
        # Sanity: we expect the ~15+ shipped overlays.
        self.assertGreaterEqual(len(self.fixtures), 15)

    def test_golden_byte_equality(self):
        for filename in self.fixtures:
            with self.subTest(fixture=os.path.basename(filename)):
                ref = _ReferenceConverter(self.settings)
                new = ImageConverter(self.settings)

                ref_ok = ref.open(filename)
                new_ok = new.open(filename)
                self.assertTrue(ref_ok, "reference open failed: %s" % filename)
                self.assertEqual(
                    ref_ok, new_ok,
                    "open() success differs for %s" % filename)

                self.assertEqual(ref.w, new.w, "width differs: %s" % filename)
                self.assertEqual(ref.h, new.h, "height differs: %s" % filename)

                # Same set of decoded modifier channels.
                self.assertEqual(
                    sorted(m.value for m in ref.image.keys()),
                    sorted(m.value for m in new.image.keys()),
                    "decoded modifier set differs for %s" % filename)

                # The raw boolean channel arrays must match exactly.
                for mod in ref.image.keys():
                    np.testing.assert_array_equal(
                        ref.image[mod], new.image[mod],
                        err_msg="channel %s differs for %s" % (mod, filename))

                # And, crucially, the fully extracted OverlayData per modifier.
                for mod in Modifier:
                    ref_ov = ref.extract_overlays(mod)
                    new_ov = new.extract_overlays(mod)
                    if ref_ov is None:
                        self.assertIsNone(
                            new_ov,
                            "new extract_overlays(%s) should be None for %s"
                            % (mod, filename))
                        continue
                    self.assertIsNotNone(
                        new_ov,
                        "new extract_overlays(%s) unexpectedly None for %s"
                        % (mod, filename))
                    self.assertEqual(
                        sorted(ref_ov.keys()), sorted(new_ov.keys()),
                        "keycode set differs for mod %s of %s" % (mod, filename))
                    for keycode in ref_ov:
                        self.assertEqual(
                            _overlaydata_tuple(ref_ov[keycode]),
                            _overlaydata_tuple(new_ov[keycode]),
                            "OverlayData differs for keycode 0x%x mod %s of %s"
                            % (keycode, mod, filename))


if __name__ == "__main__":
    unittest.main()
