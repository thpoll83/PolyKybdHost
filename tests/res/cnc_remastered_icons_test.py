"""The C&C Remastered control-group icons keep the placement the review chose.

A unit sits at the top of its 48x40 area, where it covers the Shift symbol the
firmware draws in the top middle of a digit key. The Ctrl plus is in the
lower-right corner. Both come from wz_units.py; a re-render that moved them
would bring the Shift symbol back on top of the units."""
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ICONS = (Path(__file__).resolve().parents[2]
         / "polyhost" / "res" / "overlay_sources" / "cnc_remastered" / "icons")
DIGITS = "1234567890"
PLUS, BAR = 13, 3


def _ink(name: str) -> np.ndarray:
    return np.asarray(Image.open(ICONS / name).convert("RGBA").getchannel("A")) > 127


class CncRemasteredIconsTest(unittest.TestCase):

    def test_every_unit_touches_the_top_edge(self):
        for d in DIGITS:
            with self.subTest(group=d):
                self.assertTrue(_ink(f"group{d}.png")[0].any(),
                                f"group{d}.png does not start at the top row")

    def test_the_ctrl_plus_is_in_the_lower_right_corner(self):
        for d in DIGITS:
            with self.subTest(group=d):
                m = _ink(f"groupnew{d}.png")
                h, w = m.shape
                cy, cx = h - PLUS // 2 - 1, w - PLUS // 2 - 1
                self.assertTrue(m[cy - BAR // 2:cy + BAR // 2 + 1, w - PLUS:w].all())
                self.assertTrue(m[h - PLUS:h, cx - BAR // 2:cx + BAR // 2 + 1].all())
                # Ctrl+digit differs from the digit only around the plus.
                diff = m ^ _ink(f"group{d}.png")
                ys, xs = np.nonzero(diff)
                self.assertGreaterEqual(ys.min(), h - PLUS - 3)
                self.assertGreaterEqual(xs.min(), w - PLUS - 3)


if __name__ == "__main__":
    unittest.main()
