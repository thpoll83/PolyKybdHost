"""board.json (the firmware's base layer) and the KLE (the geometry) describe
the same 74 keys -- the board view and the mock's seeded keymap join on that."""
import unittest

from polyhost.services import board_layout


class BoardLayoutTest(unittest.TestCase):

    def test_every_kle_key_has_a_base_layer_entry(self):
        keys = board_layout.physical_keys()
        self.assertEqual(len(keys), 74)
        board = board_layout.load_board()
        exported = {tuple(k["matrix"]) for k in board["keys"]}
        self.assertEqual({(k["row"], k["col"]) for k in keys}, exported)

    def test_the_base_layer_is_the_keymap_not_the_labels(self):
        codes = board_layout.base_keycodes()
        self.assertEqual(codes[(0, 0)], 0x29)       # KC_ESCAPE
        self.assertEqual(codes[(1, 1)], 0x14)       # KC_Q
        # Only modifier macros stay unresolved, and none of them carries an overlay.
        unresolved = [k["token"] for k in board_layout.load_board()["keys"] if k["keycode"] is None]
        self.assertEqual(unresolved, ["KC_HYPR"])

    def test_a_missing_export_is_none_not_a_crash(self):
        import pathlib
        self.assertIsNone(board_layout.load_board(pathlib.Path("/nonexistent/board.json")))
        self.assertEqual(board_layout.base_keycodes(pathlib.Path("/nonexistent/board.json")), {})


if __name__ == "__main__":
    unittest.main()
