import unittest
from unittest.mock import MagicMock

from polyhost.device.cmd_composer import (
    compose_cmd_str, compose_cmd, compose_roi_header, expect
)
from polyhost.device.keys import Modifier


class TestUtilityFunctions(unittest.TestCase):
    def setUp(self):
        # Create a mock command object with a value attribute
        self.mock_cmd = MagicMock()
        self.mock_cmd.value = 0x01  # Example command value

    def test_compose_cmd_str(self):
        result = compose_cmd_str(self.mock_cmd, "test")
        expected = bytearray.fromhex("0901") + b"test"
        self.assertEqual(result, expected)

    def test_compose_cmd_no_extra(self):
        result = compose_cmd(self.mock_cmd)
        expected = bytearray.fromhex("0901")
        self.assertEqual(result, expected)

    def test_compose_cmd_with_extra(self):
        result = compose_cmd(self.mock_cmd, 0x02, 0x03, 0x04)
        expected = bytearray.fromhex("0901020304")
        self.assertEqual(result, expected)

    def test_compose_roi_header_uncompressed(self):
        overlay = MagicMock()
        overlay.top = 0x03
        overlay.bottom = 0x0A
        overlay.left = 0x1F
        overlay.right = 0x2A

        result = compose_roi_header(self.mock_cmd, 0x10, Modifier.CTRL_ALT, overlay, compressed=False)
        expected = bytearray(b'\x09\x01\x10\x05\x2b\x1f\x2a')
        self.assertEqual(result, expected)

    def test_compose_roi_header_compressed(self):
        # Updated overlay parameters
        overlay = MagicMock()
        overlay.top = 0x05
        overlay.bottom = 0x0C
        overlay.left = 0x2F
        overlay.right = 0x3B

        result = compose_roi_header(self.mock_cmd, 0x20, Modifier.GUI_KEY, overlay, compressed=True)
        expected = bytearray(b'\x09\x01\x20\x18\x31\x2f\xbb')
        self.assertEqual(result, expected)

    def test_expect(self):
        result = expect(self.mock_cmd)
        expected = "P" + chr(self.mock_cmd.value)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
