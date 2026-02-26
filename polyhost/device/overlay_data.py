import math
import numpy as np

from polyhost.util.rle_util import rle_compress


def find_roi_rectangle(image):
    """ Find the region of interest - the rectangle in the image containing all set pixels"""
    rows = np.any(image, axis=1)
    cols = np.any(image, axis=0)

    if not np.any(rows) or not np.any(cols):
        return None

    top, bottom = np.where(rows == 1)[0][[0, -1]]
    left, right = np.where(cols == 1)[0][[0, -1]]

    return int(top), int(left), int(bottom), int(right)


class OverlayData:
    """ Container for all overlay data package variations: plain, compressed, region-of-interest, compressed region-of-interest """

    def __init__(self, settings, image, debug_dump_byte_buffers=False):
        self.settings = settings

        self.all_bytes = np.packbits(image, axis=None).tobytes()

        self.roi = find_roi_rectangle(image)
        self.top, self.left, self.bottom, self.right = self.roi
        self.bottom += 1
        self.right += 1
        roi = image[self.top: self.bottom, self.left: self.right]
        self.compressed_bytes = rle_compress(self.all_bytes)

        self.roi_bytes = np.packbits(roi, axis=None).tobytes()
        self.compressed_roi_bytes = rle_compress(self.roi_bytes)

        # we can skip empty data packets as for plain transfer every packet has a number and the buffer are erased before
        self.all_msgs = self.helper_calc_overlay_bytes(self.all_bytes)
        self.compressed_msgs = math.ceil(
            (len(self.compressed_bytes)+self.settings.OVERLAY_CMD_BYTES_COMPRESSED_ONCE)/self.settings.MAX_PAYLOAD_BYTES_PER_REPORT)
        self.roi_msgs = math.ceil(
            (len(self.roi_bytes)+self.settings.OVERLAY_CMD_BYTES_ROI_ONCE)/self.settings.MAX_PAYLOAD_BYTES_PER_REPORT)
        self.compressed_roi_msgs = math.ceil(
            (len(self.compressed_roi_bytes)+self.settings.OVERLAY_CMD_BYTES_ROI_ONCE)/self.settings.MAX_PAYLOAD_BYTES_PER_REPORT)

        # w = self.right - self.left
        # h = self.bottom - self.top
        # plt.imshow(image)
        # plt.gca().add_patch(plt.Rectangle((self.top, self.left), w, h,
        #                               edgecolor='red',
        #                               facecolor='none',
        #                               lw=2))
        # plt.show()

        if debug_dump_byte_buffers:
            print("uint8_t all[] = {")
            print(", ".join(hex(b) for b in self.all_bytes))
            print("};")
            print(
                f"uint8_t roi_y = {self.top}, roi_x = {self.left}, roi_yy = {self.bottom}, roi_xx = {self.right};")
            print("uint8_t roi[] = {")
            print(", ".join(hex(b) for b in self.roi_bytes))
            print("};")
            print("uint8_t croi[] = {")
            print(", ".join(hex(b) for b in self.compressed_roi_bytes))
            print("};")

    def helper_calc_overlay_bytes(self, all_bytes, skip_empty=True):
        """ Checks each overlay data packet for empty ones and deducts from the overall number """
        if not skip_empty:
            return self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT

        msg_cnt = 0
        for msg_num in range(0, self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT):
            start = msg_num * self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            stop = start + self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            data = all_bytes[start:stop]
            if all(b == 0 for b in data):
                continue
            msg_cnt += 1

        return msg_cnt
