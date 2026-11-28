"""The shape-list renderer for drawn keys (services/key_drawing.py)."""
import unittest

import numpy as np

from polyhost.services import key_drawing as kd


class RenderTest(unittest.TestCase):

    def test_each_shape_draws(self):
        for shape in ({"rect": [2, 2, 10, 10], "fill": True},
                      {"ellipse": [10, 5, 20, 20]},
                      {"line": [0, 0, 71, 39], "width": 2},
                      {"polygon": [[5, 5], [30, 5], [15, 30]], "fill": True},
                      {"text": "F5", "at": [36, 20], "size": 18, "align": "center"},
                      {"icon": "concept:material:content_copy"},
                      {"bitmap": ["#.#", ".#."], "at": [3, 3], "scale": 2}):
            mask, notes = kd.render([shape])
            self.assertEqual(mask.shape, (40, 72))
            self.assertTrue(mask.any(), shape)
            self.assertEqual(notes, [])

    def test_a_filled_rect_is_exact(self):
        mask, _ = kd.render([{"rect": [10, 5, 4, 3], "fill": True}])
        self.assertEqual(kd.ink_box(mask), (10, 5, 4, 3))
        self.assertEqual(int(mask.sum()), 12)

    def test_erase_cuts_into_what_is_below(self):
        mask, _ = kd.render([{"rect": [0, 0, 72, 40], "fill": True},
                             {"rect": [10, 10, 5, 5], "fill": True, "erase": True}])
        self.assertFalse(mask[10:15, 10:15].any())
        self.assertEqual(int(mask.sum()), 72 * 40 - 25)

    def test_a_bitmap_is_pixel_exact_and_scaled(self):
        mask, _ = kd.render([{"bitmap": ["#.", ".#"], "at": [1, 1], "scale": 2}])
        expected = np.zeros((40, 72), dtype=bool)
        expected[1:3, 1:3] = expected[3:5, 3:5] = True
        np.testing.assert_array_equal(mask, expected)

    def test_an_icon_without_at_equals_its_library_frame(self):
        # So the keyboard can draw it from its own flash.
        mask, _ = kd.render([{"icon": "concept:material:content_copy"}])
        np.testing.assert_array_equal(mask, kd.icon_mask("concept:material:content_copy"))

    def test_an_icon_with_at_moves_its_ink(self):
        mask, _ = kd.render([{"icon": "concept:material:content_copy", "at": [0, 0]}])
        box = kd.ink_box(mask)
        self.assertEqual(box[:2], (0, 0))
        self.assertEqual(box[2:], kd.ink_box(kd.icon_mask("concept:material:content_copy"))[2:])

    def test_a_shape_outside_the_key_is_noted(self):
        _mask, notes = kd.render([{"rect": [100, 100, 3, 3]}])
        self.assertEqual(len(notes), 1)

    def test_refusals(self):
        for shapes in ([], None, "rect", [{"rect": [0, 0, 0, 5]}], [{"rect": [0, 0, 5]}],
                       [{"rect": [0, 0, 5, 5], "line": [0, 0, 1, 1]}], [{"circle": [1, 2, 3]}],
                       [{"rect": [0, 0, 5, 5], "colour": "red"}], [{"rect": [0, 0, 5, 5], "fill": 1}],
                       [{"rect": [True, 0, 5, 5]}], [{"line": [0, 0, 5, 5], "width": 11}],
                       [{"text": "Ωmega"}], [{"text": ""}], [{"text": "x" * 65}],
                       [{"text": "a", "size": 41}], [{"text": "a", "align": "top"}],
                       [{"text": "a", "align": []}],
                       [{"icon": "no:such:icon"}], [{"bitmap": ["#x"]}], [{"bitmap": ["#"] * 41}],
                       [{"bitmap": ["#"], "scale": 5}], [{"polygon": [[0, 0], [1, 1]]}],
                       [{"rect": [0, 0, 1, 1]}] * 201):
            with self.assertRaises(kd.DrawingError, msg=repr(shapes)[:80]):
                kd.render(shapes)

    def test_find_icons(self):
        hits = kd.find_icons("content copy")
        self.assertIn("concept:material:content_copy", [h["name"] for h in hits])
        self.assertTrue(all(len(h["size"]) == 2 for h in hits))
        self.assertEqual(kd.find_icons(""), [])
        self.assertLessEqual(len(kd.find_icons("concept")), 20)


if __name__ == "__main__":
    unittest.main()
