import unittest
from polyhost.util.rle_util import rle_compress

def rel_decompress(compressed, max_bytes, bit_index=0):
    """
    Decompresses a run-length encoded (RLE) byte stream.

    :param compressed: The compressed byte array.
    :param max_bytes: Maximum number of bytes to decompress.
    :param bit_index: Starting bit index.
    :return: Decompressed byte array.
    """
    dest = bytearray(max_bytes)
    count = 0
    bit_offset = bit_index % 8

    for byte in compressed:
        zeros = byte < 128
        bits = byte if zeros else byte - 128

        for _ in range(bits):
            if count // 8 >= max_bytes:
                return dest

            if zeros:
                dest[count // 8] &= ~(1 << (7 - bit_offset))
            else:
                dest[count // 8] |= (1 << (7 - bit_offset))

            count += 1
            bit_offset += 1

            if bit_offset == 8:
                bit_offset = 0

    return dest


class TestRLECompression(unittest.TestCase):

    def test_compress_decompress(self):
        # Test case 1: Simple alternating bit pattern
        original = bytearray([0b11110000, 0b00001111])  # 8 ones followed by 8 zeros
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input")

        # Test case 2: All zeros
        original = bytearray([0b00000000, 0b00000000])  # 16 zeros
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input")

        # Test case 3: All ones
        original = bytearray([0b11111111, 0b11111111])  # 16 ones
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input")

        # Test case 4: Mixed pattern
        original = bytearray([0b10101010, 0b01010101])  # Alternating ones and zeros
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input")

        # Test case 5: Large input
        original = bytearray([0b11110000] * 100)  # Repeated pattern
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input")

    def test_edge_cases(self):
        # Edge case 1: Empty input
        original = bytearray()
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input for empty input")

        # Edge case 2: Single byte
        original = bytearray([0b11111111])  # Single byte of all ones
        compressed = rle_compress(original)
        decompressed = rel_decompress(compressed, len(original))
        self.assertEqual(original, decompressed, "Decompressed output should match the original input for single byte")

if __name__ == '__main__':
    unittest.main()
