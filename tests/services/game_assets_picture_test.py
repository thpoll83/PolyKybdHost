"""The icon picker's renderer in Python (game_assets/picture.py) against the
page's JavaScript (tools/icon_picker_template.html).

The expected values were produced by running these inputs through the page in
Chromium (its renderDither / renderPixel / renderVector / renderWord / place
and seeded()): a SHA-256 prefix of the 72x40 cell and its lit-pixel count. A
change to either side must keep them equal, or the keyboard stops showing what
the page showed. Regenerate the pins from the page, never from this module.
"""
import hashlib
import unittest

import numpy as np

from polyhost.services.game_assets import picture

def palette():
    return np.array([[(i * 7) % 256, (i * 13) % 256, (i * 29) % 256] for i in range(256)], np.uint8)


def source_picture():
    yy, xx = np.mgrid[0:24, 0:32]
    f = np.full((24, 32), 100, np.uint8)
    f[0], f[-1], f[:, 0], f[:, -1] = 15, 15, 15, 15
    blob = ((xx - 16) / 10.0) ** 2 + ((yy - 12) / 7.0) ** 2 <= 1
    f[blob] = (40 + (xx * 3 + yy * 5) % 90)[blob]
    f[3, 3] = 60                                   # a stray pixel the cut drops
    return f


def silhouette():
    yy, xx = np.mgrid[0:30, 0:40]
    a = np.where(((xx - 20) / 18.0) ** 2 + ((yy - 15) / 13.0) ** 2 <= 1, 255, 0).astype(np.uint8)
    a[10:20, 5:12] = 0
    return a


def font():
    g = {c: np.array([[3, 3, 3, 0], [3, 1, 2, 0], [3, 1 if c % 2 else 2, 2, 0], [0, 3, 0, 0]], np.uint8)
         for c in range(32, 127)}
    return 4, g


D = {"engine": "dither", "cut": True, "frame": 1, "lo": 5, "hi": 95, "gamma": 1.0, "curve": 0.3, "sharpen": 1.0,
     "floor": 0.15, "outline": True, "mirror": False}
PICTURES = {
    "levels": dict(D, mode="levels"),
    "fs": dict(D, mode="fs", gamma=0.6, curve=0.6, sharpen=1.5),
    "bayer": dict(D, mode="bayer", cut=False, outline=False, lo=19, hi=100, gamma=0.5, curve=0, sharpen=0, floor=0),
    "threshold": dict(D, mode="threshold", thr=0.52, mirror=True, valign="centre"),
    "pixel_nonzero": {"engine": "pixel", "lit": "nonzero", "scale": 0},
    "pixel_darker": {"engine": "pixel", "lit": "darker", "pct": 45, "scale": 1, "valign": "bottom"},
    "pixel_edge": {"engine": "pixel", "lit": "edge+bright", "scale": 0, "mirror": True},
    "pixel_smooth": {"engine": "pixel", "lit": "darker", "pct": 53, "crop": [2, 3], "smooth_w": 72, "valign": "bottom"},
}
VECTORS = {
    "relief": {"relief": True, "depth": 0.08, "azimuth": 225, "elevation": 42, "ambient": 0.35, "falloff": 0.45,
               "grain": 1.0, "seed": 1, "flat": 0.6, "mode": "fs", "lo": 3, "hi": 97, "gamma": 1.0, "curve": 0.0,
               "sharpen": 0.0, "floor": 0.15, "outline": True, "valign": "bottom"},
    "flat": {"relief": False, "flat": 0.6, "mode": "levels", "lo": 3, "hi": 97, "gamma": 1.0, "curve": 0.0,
             "sharpen": 0.0, "floor": 0.15, "outline": True},
}
WORDS = {"word": {"text": "Ab c", "body": True, "shade": True, "outline": False, "gap": 1, "scale": 2, "valign": "bottom"}}
REGION = (48, 40)


PINS = {
    "levels": "1fe7ca0b3bc64238:725",
    "fs": "d05871e191978ae0:842",
    "bayer": "a7971823ed82cc6f:289",
    "threshold": "b19f5125f52093aa:713",
    "pixel_nonzero": "fb60c3364a3c7318:768",
    "pixel_darker": "b743beae2e7df025:45",
    "pixel_edge": "309f111818fa79a4:281",
    "pixel_smooth": "e5ca9e5ffbf5d2b6:304",
    "relief": "5a21f1f3a5937b58:824",
    "flat": "140b8c148f05ee28:1115",
    "word": "bc8359db81168b7d:64"
}
MULBERRY_SEED_1 = [0.9659740590135758, 1.1231041937508899, -0.04922786278570801]


def cell(mask, region=REGION):
    """`mask` (region-sized) in the 72x40 cell, as the page's place() with
    anchor right and no margin."""
    out = np.zeros((40, 72), bool)
    out[(40 - region[1]) // 2:(40 - region[1]) // 2 + mask.shape[0], 72 - region[0]:72 - region[0] + mask.shape[1]] = mask
    return out


def pin(m):
    bits = "".join("1" if v else "0" for v in m.reshape(-1))
    return hashlib.sha256(bits.encode()).hexdigest()[:16] + ":" + str(bits.count("1"))


class PictureTest(unittest.TestCase):

    def test_pictures_match_the_page(self):
        for name, p in PICTURES.items():
            with self.subTest(name):
                self.assertEqual(pin(cell(picture.picture(source_picture(), palette(), p, REGION))), PINS[name])

    def test_vectors_match_the_page(self):
        for name, p in VECTORS.items():
            with self.subTest(name):
                self.assertEqual(pin(cell(picture.vector(silhouette(), p, REGION))), PINS[name])

    def test_words_match_the_page(self):
        for name, p in WORDS.items():
            with self.subTest(name):
                self.assertEqual(pin(picture.word(font(), p, (72, 40))), PINS[name])

    def test_the_grain_generator_matches_the_page(self):
        rnd = picture._mulberry(1)
        self.assertEqual([rnd(), rnd(), rnd()], MULBERRY_SEED_1)

    def test_an_unknown_mode_or_rule_is_refused(self):
        with self.assertRaises(ValueError):
            picture.picture(source_picture(), palette(), dict(PICTURES["levels"], mode="halftone"), REGION)
        with self.assertRaises(ValueError):
            picture.picture(source_picture(), palette(), {"engine": "pixel", "lit": "glow"}, REGION)


if __name__ == "__main__":
    unittest.main()
