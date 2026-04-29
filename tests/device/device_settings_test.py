import unittest

from polyhost.device.device_settings import DeviceSettings


class TestDeviceSettings(unittest.TestCase):
    def setUp(self):
        self.s = DeviceSettings()

    def test_vid_and_pid(self):
        self.assertEqual(self.s.VID, 0x2021)
        self.assertEqual(self.s.PID, 0x2007)

    def test_matrix_dimensions(self):
        self.assertEqual(self.s.MATRIX_ROWS, 10)
        self.assertEqual(self.s.MATRIX_COLUMNS, 8)
        self.assertEqual(self.s.NUMBER_OF_KEYS, 74)

    def test_overlay_resolution(self):
        self.assertEqual(self.s.OVERLAY_RES_X, 72)
        self.assertEqual(self.s.OVERLAY_RES_Y, 40)

    def test_hid_report_size(self):
        self.assertEqual(self.s.HID_REPORT_SIZE, 64)
        self.assertEqual(self.s.HID_CONSOLE_REPORT_SIZE, 64)

    def test_max_payload_leaves_two_bytes_for_command_headers(self):
        # 64 byte report - 1 VIA byte - 1 PolyKybd byte = 62 bytes payload
        self.assertEqual(self.s.MAX_PAYLOAD_BYTES_PER_REPORT, 62)

    def test_overlay_plain_data_bytes_total(self):
        # 72 * 40 pixels, packed 8 per byte = 360 bytes
        self.assertEqual(self.s.OVERLAY_PLAIN_DATA_BYTES_TOTAL, 360)

    def test_overlay_plain_data_bytes_per_report_divides_total_evenly(self):
        total = self.s.OVERLAY_PLAIN_DATA_BYTES_TOTAL
        per_report = self.s.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
        self.assertEqual(total % per_report, 0)
        self.assertLessEqual(per_report, self.s.MAX_PAYLOAD_BYTES_PER_REPORT)

    def test_overlay_plain_data_report_count(self):
        expected = self.s.OVERLAY_PLAIN_DATA_BYTES_TOTAL // self.s.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
        self.assertEqual(self.s.OVERLAY_PLAIN_DATA_REPORT_COUNT, expected)

    def test_overlay_mapping_indices_per_report(self):
        # indices are 10-bit wide
        expected = self.s.MAX_PAYLOAD_BYTES_PER_REPORT * 8 // 10
        self.assertEqual(self.s.OVERLAY_MAPPING_INDICES_PER_REPORT, expected)

    def test_hid_usage_pages_and_usages(self):
        self.assertEqual(self.s.HID_RAW_USAGE_PAGE, 0xFF61)
        self.assertEqual(self.s.HID_RAW_USAGE, 0x62)
        self.assertEqual(self.s.HID_CONSOLE_USAGE_PAGE, 0xFF31)
        self.assertEqual(self.s.HID_CONSOLE_USAGE, 0x74)

    def test_overlay_command_byte_counts(self):
        self.assertEqual(self.s.OVERLAY_CMD_BYTES_PER_PLAIN_REPORT, 3)
        self.assertEqual(self.s.OVERLAY_CMD_BYTES_COMPRESSED_ONCE, 2)
        self.assertEqual(self.s.OVERLAY_CMD_BYTES_ROI_ONCE, 5)


if __name__ == '__main__':
    unittest.main()
