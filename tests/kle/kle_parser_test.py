import unittest

from polyhost.kle.kle_praser import parse_kle


class TestParseKle(unittest.TestCase):

    def test_empty_input_returns_zeros_and_empty_dict(self):
        rows, cols, km = parse_kle([])
        self.assertEqual(rows, 0)
        self.assertEqual(cols, 0)
        self.assertEqual(km, {})

    def test_single_key_at_origin(self):
        rows, cols, km = parse_kle([["0,0"]])
        self.assertEqual(rows, 1)
        self.assertEqual(cols, 1)
        self.assertIn("0,0", km)
        key = km["0,0"]
        self.assertEqual(key["x"], 0.0)
        self.assertEqual(key["y"], 0.0)
        self.assertEqual(key["w"], 1.0)
        self.assertEqual(key["h"], 1.0)
        self.assertEqual(key["row"], 0)
        self.assertEqual(key["col"], 0)

    def test_two_keys_in_one_row_have_consecutive_x_positions(self):
        _, _, km = parse_kle([["0,0", "0,1"]])
        self.assertEqual(km["0,0"]["x"], 0.0)
        self.assertEqual(km["0,1"]["x"], 1.0)

    def test_two_rows_produce_correct_row_and_col_counts(self):
        rows, cols, km = parse_kle([
            ["0,0", "0,1"],
            ["1,0", "1,1"],
        ])
        self.assertEqual(rows, 2)
        self.assertEqual(cols, 2)

    def test_second_row_y_advances_by_one(self):
        _, _, km = parse_kle([
            ["0,0"],
            ["1,0"],
        ])
        self.assertEqual(km["0,0"]["y"], 0.0)
        self.assertEqual(km["1,0"]["y"], 1.0)

    def test_wide_key_advances_x_by_width(self):
        _, _, km = parse_kle([[{"w": 2}, "0,0", "0,1"]])
        self.assertEqual(km["0,0"]["w"], 2.0)
        self.assertEqual(km["0,0"]["x"], 0.0)
        # second key starts after the 2-unit wide first key
        self.assertEqual(km["0,1"]["x"], 2.0)
        self.assertEqual(km["0,1"]["w"], 1.0)  # width resets after each key

    def test_tall_key_has_correct_height(self):
        _, _, km = parse_kle([[{"h": 2}, "0,0"]])
        self.assertEqual(km["0,0"]["h"], 2.0)

    def test_x_offset_shifts_key_position(self):
        _, _, km = parse_kle([[{"x": 1.5}, "0,0"]])
        self.assertEqual(km["0,0"]["x"], 1.5)

    def test_y_offset_shifts_key_position(self):
        _, _, km = parse_kle([[{"y": 0.5}, "0,0"]])
        self.assertEqual(km["0,0"]["y"], 0.5)

    def test_rotation_is_stored_on_key(self):
        _, _, km = parse_kle([[{"r": 45, "rx": 2.0, "ry": 1.0}, "0,0"]])
        key = km["0,0"]
        self.assertEqual(key["r"], 45.0)
        self.assertEqual(key["rx"], 2.0)
        self.assertEqual(key["ry"], 1.0)

    def test_rotation_origin_sets_cursor(self):
        # rx/ry reset the cursor to the rotation origin
        _, _, km = parse_kle([[{"rx": 3.0, "ry": 2.0}, "0,0"]])
        self.assertEqual(km["0,0"]["x"], 3.0)
        self.assertEqual(km["0,0"]["y"], 2.0)

    def test_metadata_row_with_name_key_is_skipped(self):
        # KLE metadata objects have a 'name' property; they must not appear in output
        rows, cols, km = parse_kle([{"name": "Test Layout"}, ["0,0"]])
        self.assertEqual(len(km), 1)
        self.assertIn("0,0", km)

    def test_row_col_fields_match_label(self):
        _, _, km = parse_kle([["2,5"]])
        self.assertEqual(km["2,5"]["row"], 2)
        self.assertEqual(km["2,5"]["col"], 5)

    def test_max_row_and_col_are_tracked_correctly(self):
        rows, cols, km = parse_kle([
            ["0,0", "0,3"],
            ["2,0", "2,7"],
        ])
        self.assertEqual(rows, 3)   # max row index 2 → 3 rows
        self.assertEqual(cols, 8)   # max col index 7 → 8 cols

    def test_no_rotation_y_advances_between_rows(self):
        _, _, km = parse_kle([
            ["0,0"],
            ["1,0"],
            ["2,0"],
        ])
        self.assertEqual(km["0,0"]["y"], 0.0)
        self.assertEqual(km["1,0"]["y"], 1.0)
        self.assertEqual(km["2,0"]["y"], 2.0)


if __name__ == '__main__':
    unittest.main()
