import unittest

from polyhost.keymap.keymap_model import KeymapModel


class TestKeymapModel(unittest.TestCase):

    def setUp(self):
        self.model = KeymapModel(layers=4, rows=10, cols=8)

    def test_all_keycodes_default_to_zero(self):
        for layer in range(4):
            for row in range(10):
                for col in range(8):
                    self.assertEqual(self.model.get_key(layer, row, col), 0x0000)

    def test_current_layer_defaults_to_zero(self):
        self.assertEqual(self.model.current_layer, 0)

    def test_set_and_get_key_roundtrip(self):
        self.model.set_key(0, 3, 5, 0x0028)  # KC_ENTER
        self.assertEqual(self.model.get_key(0, 3, 5), 0x0028)

    def test_different_layers_are_independent(self):
        self.model.set_key(0, 0, 0, 0x0004)  # KC_A on layer 0
        self.model.set_key(1, 0, 0, 0x0005)  # KC_B on layer 1
        self.assertEqual(self.model.get_key(0, 0, 0), 0x0004)
        self.assertEqual(self.model.get_key(1, 0, 0), 0x0005)

    def test_write_does_not_affect_other_cells(self):
        self.model.set_key(2, 5, 3, 0xFFFF)
        # all other cells in same layer untouched
        self.assertEqual(self.model.get_key(2, 5, 2), 0x0000)
        self.assertEqual(self.model.get_key(2, 5, 4), 0x0000)
        self.assertEqual(self.model.get_key(2, 4, 3), 0x0000)
        self.assertEqual(self.model.get_key(2, 6, 3), 0x0000)

    def test_overwrite_key_reflects_new_value(self):
        self.model.set_key(0, 0, 0, 0x0004)
        self.model.set_key(0, 0, 0, 0x0005)
        self.assertEqual(self.model.get_key(0, 0, 0), 0x0005)

    def test_last_layer_row_col_are_accessible(self):
        self.model.set_key(3, 9, 7, 0xABCD)
        self.assertEqual(self.model.get_key(3, 9, 7), 0xABCD)

    def test_single_layer_single_cell(self):
        m = KeymapModel(layers=1, rows=1, cols=1)
        self.assertEqual(m.get_key(0, 0, 0), 0x0000)
        m.set_key(0, 0, 0, 0x1234)
        self.assertEqual(m.get_key(0, 0, 0), 0x1234)

    def test_dimensions_stored_correctly(self):
        self.assertEqual(self.model.layers, 4)
        self.assertEqual(self.model.rows, 10)
        self.assertEqual(self.model.cols, 8)


if __name__ == '__main__':
    unittest.main()
