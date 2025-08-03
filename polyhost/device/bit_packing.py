import math
import unittest


def pack_dict_10_bit(data_dict: dict[int, int]) -> bytearray:
    """
    Packs a dictionary of integers into a compact bytearray with no wasted bits.

    This function treats the output as a continuous stream of bits. It concatenates
    the 10-bit representation of each key and value into a single large integer,
    which is then converted to bytes. This is highly space-efficient, with at
    most 7 bits of padding at the very end of the bytearray.

    Args:
        data_dict: A dictionary where keys and values are integers.
                   Values exceeding 10 bits (0-1023) will be truncated.

    Returns:
        A bytearray containing the tightly packed key-value pairs.
    """
    if not data_dict:
        return bytearray()

    packed_int = 0
    num_pairs = len(data_dict)

    # Mask to get the 10 least significant bits (2^10 - 1)
    mask = 0x3FF

    # Concatenate all key-value pairs into one large integer
    for key, value in data_dict.items():
        # Shift the existing bits to make room for the new 20-bit pair
        packed_int <<= 20
        # Combine the 10-bit key and 10-bit value
        pair_as_20_bits = ((key & mask) << 10) | (value & mask)
        # Add the new pair to the large integer
        packed_int |= pair_as_20_bits

    # Calculate the number of bytes required to store all the bits
    total_bits = num_pairs * 20
    num_bytes = math.ceil(total_bits / 8)

    # Convert the large integer to a bytearray
    return bytearray(packed_int.to_bytes(num_bytes, 'big'))


def unpack_bytes_to_dict(packed_data: bytes, num_pairs: int) -> dict[int, int]:
    """
    Unpacks a bytearray created by pack_dict_10_bit back into a dictionary.

    Args:
        packed_data: A bytearray of tightly packed 10-bit key-value pairs.
        num_pairs: The number of key-value pairs that were packed.

    Returns:
        The reconstructed dictionary.
    """
    if not packed_data or num_pairs == 0:
        return {}

    # Convert the entire bytearray back to a single integer
    packed_int = int.from_bytes(packed_data, 'big')

    unpacked_dict = {}

    # Masks to extract the 10-bit key and value from a 20-bit chunk
    value_mask = 0x3FF  # Extracts the last 10 bits
    key_mask = 0xFFC00  # Extracts the first 10 bits

    # Extract each 20-bit pair from the right (LSB side)
    for _ in range(num_pairs):
        pair_as_20_bits = packed_int & 0xFFFFF  # Get the last 20 bits

        key = (pair_as_20_bits & key_mask) >> 10
        value = pair_as_20_bits & value_mask

        unpacked_dict[key] = value

        # Shift the integer to the right to process the next pair
        packed_int >>= 20

    return unpacked_dict


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

        # Verification of byte length: 12 pairs * 20 bits/pair = 240 bits. 240 / 8 = 30 bytes.
        self.assertEqual(len(packed), 30)

        unpacked = unpack_bytes_to_dict(packed, len(original_dict))
        self.assertEqual(original_dict, unpacked)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)