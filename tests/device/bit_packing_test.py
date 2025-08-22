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

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)