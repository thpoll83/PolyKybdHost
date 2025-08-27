import unittest

from polyhost.util.dict_util import split_dict, split_by_n_chars


# Unit Test Class
class TestDictUtil(unittest.TestCase):
    def test_split_exact_chunk(self):
        """Test when the dictionary splits evenly into chunks."""
        input_dict = {chr(97 + i): i for i in range(24)}  # {'a': 0, 'b': 1, ..., 'x': 23}
        result = split_dict(input_dict, max_keys=12)
        self.assertEqual(len(result), 2)  # Should create 2 dictionaries
        self.assertEqual(len(result[0]), 12)  # Each dictionary should have 12 keys
        self.assertEqual(len(result[1]), 12)

    def test_split_with_remainder(self):
        """Test when the dictionary has a remainder."""
        input_dict = {chr(97 + i): i for i in range(25)}  # {'a': 0, 'b': 1, ..., 'y': 24}
        result = split_dict(input_dict, max_keys=12)
        self.assertEqual(len(result), 3)  # Should create 3 dictionaries
        self.assertEqual(len(result[0]), 12)  # First dictionary should have 12 keys
        self.assertEqual(len(result[1]), 12)  # Second dictionary should have 12 keys
        self.assertEqual(len(result[2]), 1)   # Last dictionary should have 1 key

    def test_empty_dict(self):
        """Test splitting an empty dictionary."""
        input_dict = {}
        result = split_dict(input_dict, max_keys=12)
        self.assertEqual(result, [])  # Should return an empty list

    def test_single_chunk(self):
        """Test when the dictionary fits within one chunk."""
        input_dict = {chr(97 + i): i for i in range(10)}  # {'a': 0, ..., 'j': 9}
        result = split_dict(input_dict, max_keys=12)
        self.assertEqual(len(result), 1)  # Should create 1 dictionary
        self.assertEqual(len(result[0]), 10)  # The dictionary should have 10 keys

    def test_large_max_keys(self):
        """Test when max_keys is larger than the dictionary size."""
        input_dict = {chr(97 + i): i for i in range(10)}  # {'a': 0, ..., 'j': 9}
        result = split_dict(input_dict, max_keys=20)
        self.assertEqual(len(result), 1)  # Should create 1 dictionary
        self.assertEqual(len(result[0]), 10)  # The dictionary should have 10 keys

    def test_large_dict_with_arbitrary_keys(self):
        """Test splitting a dictionary with 200 arbitrary integer keys and values."""
        input_dict = {i: i * 2 for i in range(1, 201)}  # {1: 2, 2: 4, ..., 200: 400}
        result = split_dict(input_dict, max_keys=12)
        
        # Verify the number of resulting dictionaries
        self.assertEqual(len(result), 17)  # 200 entries divided by 12 keys per chunk = 17 chunks
        
        # Verify that all chunks have at most 12 keys
        self.assertTrue(all(len(d) <= 12 for d in result))
        
        # Verify that all keys and values are present in the split dictionaries
        reconstructed_dict = {}
        for d in result:
            reconstructed_dict.update(d)
        
        self.assertEqual(reconstructed_dict, input_dict)  # Ensure all keys and values match
        
    def test_split_by_n_chars(self):
        result = split_by_n_chars("abcdefghij", 3)
        expected = ["abc", "def", "ghi", "j"]
        self.assertEqual(result, expected)

        # Test with exact division
        result = split_by_n_chars("abcdef", 2)
        expected = ["ab", "cd", "ef"]
        self.assertEqual(result, expected)

        # Test with n larger than text length
        result = split_by_n_chars("abc", 5)
        expected = ["abc"]
        self.assertEqual(result, expected)

if __name__ == "__main__":
    unittest.main()
