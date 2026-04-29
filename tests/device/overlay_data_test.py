import unittest

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_data import OverlayData, find_roi_rectangle


class TestFindRoiRectangle(unittest.TestCase):

    def test_empty_image_returns_none(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        self.assertIsNone(find_roi_rectangle(image))

    def test_single_pixel_at_origin(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[0, 0] = 1
        self.assertEqual(find_roi_rectangle(image), (0, 0, 0, 0))

    def test_single_pixel_at_arbitrary_position(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[10, 30] = 1
        self.assertEqual(find_roi_rectangle(image), (10, 30, 10, 30))

    def test_single_pixel_at_bottom_right(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[39, 71] = 1
        self.assertEqual(find_roi_rectangle(image), (39, 71, 39, 71))

    def test_horizontal_line_returns_correct_bounds(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[5, 10:20] = 1
        self.assertEqual(find_roi_rectangle(image), (5, 10, 5, 19))

    def test_vertical_line_returns_correct_bounds(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[5:15, 20] = 1
        self.assertEqual(find_roi_rectangle(image), (5, 20, 14, 20))

    def test_rectangle_returns_tight_bounds(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[5:15, 10:30] = 1
        self.assertEqual(find_roi_rectangle(image), (5, 10, 14, 29))

    def test_full_image_spans_entire_area(self):
        image = np.ones((40, 72), dtype=np.uint8)
        self.assertEqual(find_roi_rectangle(image), (0, 0, 39, 71))

    def test_two_isolated_pixels_span_bounding_box(self):
        image = np.zeros((40, 72), dtype=np.uint8)
        image[2, 5] = 1
        image[20, 60] = 1
        self.assertEqual(find_roi_rectangle(image), (2, 5, 20, 60))


class TestHelperCalcOverlayBytes(unittest.TestCase):

    def setUp(self):
        self.settings = DeviceSettings()
        image = np.zeros((40, 72), dtype=np.uint8)
        image[0, 0] = 1  # single pixel so OverlayData constructor doesn't raise
        self.od = OverlayData(self.settings, image)

    def test_skip_empty_false_always_returns_full_report_count(self):
        all_zeros = bytes(self.settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL)
        result = self.od.helper_calc_overlay_bytes(all_zeros, skip_empty=False)
        self.assertEqual(result, self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)

    def test_all_zero_bytes_with_skip_empty_returns_zero(self):
        all_zeros = bytes(self.settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL)
        self.assertEqual(self.od.helper_calc_overlay_bytes(all_zeros, skip_empty=True), 0)

    def test_single_nonzero_in_first_packet_counts_one(self):
        # only the first byte of 360 is set (pixel at 0,0 → 0x80 in first byte)
        # the remaining 359 bytes are zero, so only report 0 is non-empty
        result = self.od.helper_calc_overlay_bytes(self.od.all_bytes, skip_empty=True)
        self.assertEqual(result, 1)

    def test_all_nonzero_bytes_returns_full_count(self):
        all_ones = bytes([0xFF] * self.settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL)
        result = self.od.helper_calc_overlay_bytes(all_ones, skip_empty=True)
        self.assertEqual(result, self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)

    def test_nonzero_in_last_packet_only_counts_one(self):
        data = bytearray(self.settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL)
        per = self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
        count = self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT
        data[(count - 1) * per] = 0xFF  # set one byte in the last packet
        self.assertEqual(self.od.helper_calc_overlay_bytes(bytes(data), skip_empty=True), 1)

    def test_nonzero_in_first_and_last_packet_counts_two(self):
        data = bytearray(self.settings.OVERLAY_PLAIN_DATA_BYTES_TOTAL)
        per = self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
        count = self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT
        data[0] = 0xFF
        data[(count - 1) * per] = 0xFF
        self.assertEqual(self.od.helper_calc_overlay_bytes(bytes(data), skip_empty=True), 2)


if __name__ == '__main__':
    unittest.main()
