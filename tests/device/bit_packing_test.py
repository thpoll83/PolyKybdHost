import unittest

from polyhost.device.bit_packing import pack_dict_10_bit, unpack_bytes_to_dict


def print_as_c_array(data: bytearray, name: str = "my_array", line_width: int = 16):
    """
    Prints a bytearray formatted as a C-style array of unsigned chars.

    Args:
        data: The input bytearray.
        name: The desired name for the C array variable.
        line_width: The number of bytes to print per line for readability.
    """
    # Start the C array declaration, including the size
    print(f"unsigned char {name}[{len(data)}] = {{")

    # Iterate over the bytearray in chunks of 'line_width'
    for i in range(0, len(data), line_width):
        # Get the current chunk of bytes
        chunk = data[i:i + line_width]

        # Format each byte in the chunk as a 0x-prefixed, two-digit hex string
        # Example: 10 becomes '0x0a', 255 becomes '0xff'
        hex_values = [f"0x{byte:02x}" for byte in chunk]

        # Join the hex values with commas and add indentation for readability
        line = "  " + ", ".join(hex_values)

        # Add a trailing comma if it's not the last line of the array
        if i + line_width < len(data):
            line += ","

        print(line)

    # Close the C array declaration
    print("};")

class TestBitPacking(unittest.TestCase):

    def test_packing_and_unpacking(self):
        """Tests a typical dictionary can be packed and unpacked correctly."""
        original_dict = {1: 1023, 1022: 2, 512: 511, 0: 0, 345: 876}
        packed = pack_dict_10_bit(original_dict)
        # We need to know the original order of keys to unpack correctly
        ordered_keys = list(original_dict.keys())
        unpacked = unpack_bytes_to_dict(packed, len(original_dict))

        # Reorder the unpacked dictionary to match original for comparison
        reordered_unpacked = {k: unpacked[k] for k in ordered_keys}
        self.assertEqual(original_dict, reordered_unpacked)

    def test_empty_dictionary(self):
        """Tests that an empty dictionary results in an empty bytearray."""
        original_dict = {}
        packed = pack_dict_10_bit(original_dict)
        self.assertEqual(packed, bytearray())
        unpacked = unpack_bytes_to_dict(packed, 0)
        self.assertEqual(unpacked, {})

    def test_single_pair(self):
        """Tests a dictionary with a single key-value pair."""
        original_dict = {123: 456}
        packed = pack_dict_10_bit(original_dict)
        unpacked = unpack_bytes_to_dict(packed, 1)
        self.assertEqual(original_dict, unpacked)

    def test_max_values(self):
        """Tests that the maximum 10-bit values are handled correctly."""
        original_dict = {1023: 1023}
        packed = pack_dict_10_bit(original_dict)
        unpacked = unpack_bytes_to_dict(packed, 1)
        self.assertEqual(original_dict, unpacked)

    def test_zero_values(self):
        """Tests that zero values are handled correctly."""
        original_dict = {0: 0}
        packed = pack_dict_10_bit(original_dict)
        unpacked = unpack_bytes_to_dict(packed, 1)
        self.assertEqual(original_dict, unpacked)

    def test_value_truncation(self):
        """Tests that values larger than 1023 are truncated."""
        # 1024 in binary is 10000000000 (11 bits). The LSB 10 bits are all 0.
        # 1025 in binary is 10000000001. The LSB 10 bits are just 1.
        original_dict = {1024: 1025}
        expected_after_truncation = {0: 1}
        packed = pack_dict_10_bit(original_dict)
        unpacked = unpack_bytes_to_dict(packed, 1)
        self.assertEqual(expected_after_truncation, unpacked)

    def test_twelve_pairs(self):
        """Tests a dictionary with 12 pairs to check handling of multiple bytes."""
        original_dict = {i: 1023 - i for i in range(12)}
        packed = pack_dict_10_bit(original_dict)

        print_as_c_array(packed, "test")

        # Verification of byte length: 12 pairs * 20 bits/pair = 240 bits. 240 / 8 = 30 bytes.
        self.assertEqual(len(packed), 30)

        unpacked = unpack_bytes_to_dict(packed, len(original_dict))
        self.assertEqual(original_dict, unpacked)

class TestVariableWidthPacking(unittest.TestCase):
    """The width-parameterised codec + the report planner (protocol v12+).

    ⚠️ The packer must stay the exact inverse of the firmware's
    set_packed_overlay_mapping()/pack_map_value() pair (fill_overlay.c) — verify
    any change by round-tripping, never by eye.
    """

    def test_round_trip_at_every_width(self):
        from polyhost.device.bit_packing import pack_values, values_per_report
        for width in range(8, 17):
            for data_bytes in (60, 61, 62):
                with self.subTest(width=width, data_bytes=data_bytes):
                    n = values_per_report(data_bytes, width)
                    mask = (1 << width) - 1
                    vals = [(i * 2654435761 >> 7) & mask for i in range(n)]
                    buf = pack_values(vals, data_bytes, width)
                    self.assertEqual(len(buf), data_bytes,
                                     "packing must not grow the buffer")
                    got = unpack_bytes_to_dict(buf, n // 2, width)
                    expected = {vals[i * 2]: vals[i * 2 + 1] for i in range(n // 2)}
                    self.assertEqual(got, expected)

    def test_min_width_never_below_eight(self):
        from polyhost.device.bit_packing import min_width, pair_width
        self.assertEqual(min_width(0), 8)
        self.assertEqual(min_width(255), 8)
        self.assertEqual(min_width(256), 9)
        self.assertEqual(min_width(1023), 10)
        self.assertEqual(min_width(1024), 11)
        self.assertEqual(min_width(1439), 11)   # highest flat index (90*15+89)
        # A pair needs whichever half is wider.
        self.assertEqual(pair_width(1, 600), 10)
        self.assertEqual(pair_width(1400, 1), 11)

    def test_eleven_bits_covers_the_whole_index_space(self):
        """12+ is never needed: max from is 1439 < 2048, max to is 599."""
        from polyhost.device.bit_packing import pair_width
        self.assertEqual(pair_width(90 * 15 + 89, 599), 11)

    def test_pack_report_fills_every_slot(self):
        """No slot may be left zero — the firmware would read it as 0 -> 0."""
        from polyhost.device.bit_packing import pack_report, pairs_per_report
        data_bytes, width = 61, 10
        buf = pack_report([(5, 7)], data_bytes, width)
        decoded = unpack_bytes_to_dict(buf, pairs_per_report(data_bytes, width), width)
        # Padding repeats the last pair, so the only mapping present is 5 -> 7 —
        # and crucially NOT the spurious 0 -> 0 a zero fill would decode as.
        self.assertEqual(decoded, {5: 7})

    def test_plan_covers_every_pair_exactly_once(self):
        from polyhost.device.bit_packing import plan_mapping_reports, pairs_per_report
        mapping = {i: (i * 7) % 600 for i in range(0, 1440, 3)}
        reports = plan_mapping_reports(mapping, 61)
        seen = []
        for width, pairs in reports:
            self.assertLessEqual(len(pairs), pairs_per_report(61, width))
            for f, t in pairs:
                # A pair may ride a WIDER report, never a narrower one.
                self.assertLessEqual(max(f.bit_length(), t.bit_length(), 8), width)
                seen.append((f, t))
        self.assertEqual(sorted(seen), sorted(mapping.items()))

    def test_plan_does_not_force_narrow_pairs_up_to_the_widest(self):
        from polyhost.device.bit_packing import plan_mapping_reports
        mapping = {i: i for i in range(40)}      # all 8-bit
        mapping[1400] = 5                        # one 11-bit outlier
        widths = [w for w, _ in plan_mapping_reports(mapping, 61)]
        self.assertIn(11, widths)
        self.assertIn(8, widths)

    def test_plan_of_empty_mapping_is_empty(self):
        from polyhost.device.bit_packing import plan_mapping_reports
        self.assertEqual(plan_mapping_reports({}, 61), [])


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
