import unittest

from polyhost.util.math_util import find_nearest, natural_divisors


# Assuming the provided functions are in the same file or imported
# from the respective module

class TestMathFunctions(unittest.TestCase):

    def test_natural_divisors(self):
        # Test for a prime number
        self.assertEqual(natural_divisors(7), [1, 7], "Prime numbers should only have 1 and itself as divisors")
        
        # Test for a composite number
        self.assertEqual(natural_divisors(12), [1, 2, 3, 4, 6, 12], "12 should have divisors [1, 2, 3, 4, 6, 12]")
        
        # Test for 1
        self.assertEqual(natural_divisors(1), [1], "1 should only have itself as a divisor")
        
        # Test for a perfect square
        self.assertEqual(natural_divisors(16), [1, 2, 4, 8, 16], "16 should have divisors [1, 2, 4, 8, 16]")
        
        # Test for a large number
        self.assertEqual(natural_divisors(28), [1, 2, 4, 7, 14, 28], "28 should have divisors [1, 2, 4, 7, 14, 28]")

    def test_find_nearest(self):
        # Test for a number in the middle of the array
        self.assertEqual(find_nearest(5, [1, 2, 4, 6, 8]), 4, "Nearest number not over 5 should be 4")
        
        # Test for a number larger than all elements in the array
        self.assertEqual(find_nearest(10, [1, 2, 4, 6, 8]), 8, "Nearest number not over 10 should be 8")
        
        # Test for a number smaller than all elements in the array
        self.assertEqual(find_nearest(0, [1, 2, 4, 6, 8]), 1, "Nearest number not over 0 should be 1 (default to smallest)")
        
        # Test for an exact match
        self.assertEqual(find_nearest(6, [1, 2, 4, 6, 8]), 6, "Nearest number not over 6 should be 6 (exact match)")
        
        # Test for a single-element array
        self.assertEqual(find_nearest(5, [3]), 3, "Nearest number not over 5 should be 3 in a single-element array")
        
        # Test for edge case where array is empty
        with self.assertRaises(IndexError):
            find_nearest(5, [])

if __name__ == '__main__':
    unittest.main()
