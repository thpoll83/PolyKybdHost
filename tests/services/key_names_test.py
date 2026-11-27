"""The frozen key-name table (res/key_positions.yaml) and the key references the
MCP tools take. Plan: docs/mcp-server-plan.md -> Identifying a key."""
import json
import unittest

from polyhost.kle.kle_praser import parse_kle
from polyhost.services import board_layout
from polyhost.services.key_names import KeyRefError, load_table
from polyhost.services.keycode_text import parse_keycode


class KeyTableTest(unittest.TestCase):

    def setUp(self):
        self.t = load_table("split72")

    def test_74_names_each_kle_row_col_exactly_once(self):
        _, _, matrix = parse_kle(json.loads(board_layout.KLE_JSON.read_text(encoding="utf-8")))
        kle = [(k["row"], k["col"]) for k in matrix.values()]
        self.assertEqual(len(kle), 74)
        self.assertEqual(len(self.t.by_name), 74)
        self.assertEqual(sorted(self.t.by_name.values()), sorted(kle))

    def test_both_halves_have_the_same_names(self):
        left = {n[2:] for n in self.t.by_name if n.startswith("L:")}
        right = {n[2:] for n in self.t.by_name if n.startswith("R:")}
        self.assertEqual(len(left), 37)
        self.assertEqual(left, right)

    def test_known_keys(self):
        # Esc, Tab below it, the AI key, and the keys over the expansion ports.
        self.assertEqual(self.t.by_name["L:1.1"], (0, 0))
        self.assertEqual(self.t.by_name["L:1.2"], (1, 0))
        self.assertEqual(self.t.by_name["R:1.1"], (5, 7))
        self.assertEqual(self.t.by_name["L:8.3"], (3, 7))
        self.assertEqual(self.t.by_name["R:8.3"], (8, 0))

    def test_no_display_is_the_two_expansion_port_keys(self):
        # The same two keys as kb_layout_dialog.NO_DISPLAY_MATRIX.
        self.assertEqual({self.t.by_name[n] for n in self.t.no_display}, {(3, 7), (8, 0)})

    def test_thumb_keys(self):
        expected = {f"{h}:{xy}" for h in "LR" for xy in ("6.5", "7.4", "7.5", "8.4", "8.5")}
        self.assertEqual(self.t.thumb, expected)

    def test_every_alias_resolves_to_its_canonical_name(self):
        for name in self.t.by_name:
            half, rest = name.split(":")
            x, y = rest.split(".")
            other = "R" if half == "L" else "L"
            alias = f"{other}:{17 - int(x)}.{y}"
            self.assertEqual(self.t.canonical(alias), name, alias)
            self.assertEqual(self.t.canonical(name.lower()), name)

    def test_an_alias_of_an_empty_place_is_an_error(self):
        for text in ("L:12.5", "R:12.5", "L:9.1", "L:9.2"):
            with self.assertRaises(KeyRefError, msg=text):
                self.t.canonical(text)

    def test_a_place_with_no_key_and_a_bad_name_are_errors(self):
        for text in ("L:5.5", "L:0.1", "L:17.1", "L:1.6", "X:1.1", "L1.1", ""):
            with self.assertRaises(KeyRefError, msg=text):
                self.t.canonical(text)


class KeyReferenceTest(unittest.TestCase):

    def setUp(self):
        self.t = load_table("split72")
        self.base = {pos: 0 for pos in self.t.by_pos}
        self.base[(0, 0)] = parse_keycode("KC_ESC")
        self.base[(4, 4)] = parse_keycode("KC_SPC")
        self.base[(9, 3)] = parse_keycode("KC_SPC")

    def resolve(self, ref):
        return self.t.resolve(ref, self.base, parse_keycode)

    def test_name_alias_and_matrix_references(self):
        self.assertEqual(self.resolve("L:1.1"), "L:1.1")
        self.assertEqual(self.resolve("L:9.4"), "R:8.4")
        self.assertEqual(self.resolve({"row": 5, "col": 7}), "R:1.1")

    def test_a_base_reference_finds_the_one_key(self):
        self.assertEqual(self.resolve({"base": "KC_ESC"}), "L:1.1")
        self.assertEqual(self.resolve({"base": "esc"}), "L:1.1")

    def test_a_base_keycode_on_two_keys_is_an_error_that_lists_both(self):
        with self.assertRaises(KeyRefError) as ctx:
            self.resolve({"base": "KC_SPC"})
        self.assertIn("L:6.5", str(ctx.exception))
        self.assertIn("R:6.5", str(ctx.exception))

    def test_a_base_keycode_on_no_key_is_an_error(self):
        with self.assertRaises(KeyRefError):
            self.resolve({"base": "KC_Q"})

    def test_bad_references(self):
        for ref in ({"row": 0, "col": 7},  # (0, 7) is no key
                    {"row": True, "col": 0}, {"row": "1", "col": 0},
                    {"base": "KC_NOT_A_KEY"}, {"row": 1}, {}, 5, None, ["L:1.1"]):
            with self.assertRaises(KeyRefError, msg=repr(ref)):
                self.resolve(ref)


class GridTest(unittest.TestCase):

    def test_the_grid_draws_every_key_in_its_place(self):
        t = load_table("split72")
        text = t.grid(lambda n: "%d,%d" % t.by_name[n])
        lines = text.splitlines()
        self.assertEqual(len(lines), 7)  # header, rule, five rows
        self.assertIn("2,0 2,1 2,2 2,3 2,4 2,5 2,6 3,7 | 8,0 7,1", lines[4])
        self.assertIn("4,3  .  4,4", lines[6])
        for pos in t.by_pos:
            self.assertIn("%d,%d" % pos, text)


if __name__ == "__main__":
    unittest.main()
