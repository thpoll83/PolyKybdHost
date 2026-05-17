import unittest
from unittest.mock import MagicMock

from polyhost.device.cmd_composer import (
    compose_cmd_str, compose_cmd, compose_roi_header, expect
)
from polyhost.device.command_ids import HidId
from polyhost.device.keys import Modifier

P = HidId.ID_POLYKYBD.value  # protocol prefix byte


class TestUtilityFunctions(unittest.TestCase):
    def setUp(self):
        # Create a mock command object with a value attribute
        self.mock_cmd = MagicMock()
        self.mock_cmd.value = 0x01  # Example command value

    def test_compose_cmd_str(self):
        result = compose_cmd_str(self.mock_cmd, "test")
        expected = bytearray([P, 0x01]) + b"test"
        self.assertEqual(result, expected)

    def test_compose_cmd_no_extra(self):
        result = compose_cmd(self.mock_cmd)
        expected = bytearray([P, 0x01])
        self.assertEqual(result, expected)

    def test_compose_cmd_with_extra(self):
        result = compose_cmd(self.mock_cmd, 0x02, 0x03, 0x04)
        expected = bytearray([P, 0x01, 0x02, 0x03, 0x04])
        self.assertEqual(result, expected)

    def test_compose_roi_header_uncompressed(self):
        overlay = MagicMock()
        overlay.top = 0x03
        overlay.bottom = 0x0A
        overlay.left = 0x1F
        overlay.right = 0x2A

        result = compose_roi_header(self.mock_cmd, 0x10, Modifier.CTRL_ALT, overlay, compressed=False)
        expected = bytearray([P, 0x01, 0x10, 0x05, 0x2b, 0x1f, 0x2a])
        self.assertEqual(result, expected)

    def test_compose_roi_header_compressed(self):
        overlay = MagicMock()
        overlay.top = 0x05
        overlay.bottom = 0x0C
        overlay.left = 0x2F
        overlay.right = 0x3B

        result = compose_roi_header(self.mock_cmd, 0x20, Modifier.GUI_KEY, overlay, compressed=True)
        expected = bytearray([P, 0x01, 0x20, 0x18, 0x31, 0x2f, 0xbb])
        self.assertEqual(result, expected)

    def test_expect(self):
        result = expect(self.mock_cmd)
        expected = "P" + chr(self.mock_cmd.value)
        self.assertEqual(result, bytearray(expected, encoding="utf-8"))


if __name__ == '__main__':
    unittest.main()
