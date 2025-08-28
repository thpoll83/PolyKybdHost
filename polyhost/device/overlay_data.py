import math
import numpy as np

from polyhost.util.rle_util import rel_compress
from polyhost.util.math_util import find_nearest, natural_divisors



# overlay constants
REPORT_LENGTH = 32
COMMAND_BYTES = 2

OVERLAY_COMMAND_BYTES = 3
COMPRESSED_OVERLAY_COMMAND_BYTES = 2
ROI_OVERLAY_COMMAND_BYTES = 5

MAX_DATA_PER_MSG = REPORT_LENGTH - COMMAND_BYTES
BYTES_PER_OVERLAY = int(72 * 40) / 8  # 360
PLAIN_OVERLAY_BYTES_PER_MSG = find_nearest(MAX_DATA_PER_MSG, natural_divisors(BYTES_PER_OVERLAY))
NUM_PLAIN_OVERLAY_MSGS = int(BYTES_PER_OVERLAY / PLAIN_OVERLAY_BYTES_PER_MSG)  # 360/24 = 15

def find_roi_rectangle(image):
    """ Find the region of interest - the rectangle in the image containing all set pixels"""
    rows = np.any(image, axis=1)
    cols = np.any(image, axis=0)

    if not np.any(rows) or not np.any(cols):
        return None

    top, bottom = np.where(rows == 1)[0][[0, -1]]
    left, right = np.where(cols == 1)[0][[0, -1]]

    return int(top), int(left), int(bottom), int(right)

def helper_calc_overlay_bytes(all_bytes, skip_empty=True):
    """ Checks each overlay data packet for empty ones and deducts from the overall number """
    if not skip_empty:
        return NUM_PLAIN_OVERLAY_MSGS

    msg_cnt = 0
    for msg_num in range(0, NUM_PLAIN_OVERLAY_MSGS):
        data = all_bytes[msg_num * PLAIN_OVERLAY_BYTES_PER_MSG:(msg_num + 1) * PLAIN_OVERLAY_BYTES_PER_MSG]
        if all(b == 0 for b in data):
            continue
        msg_cnt += 1

    return msg_cnt

class OverlayData:
    """ Container for all overlay data package variations: plain, compressed, region-of-interest, compressed region-of-interest """

    def __init__(self, image):
        self.all_bytes = np.packbits(image, axis=None).tobytes()

        self.roi = find_roi_rectangle(image)
        self.top, self.left, self.bottom, self.right = self.roi
        self.bottom+=1
        self.right+=1
        roi = image[self.top: self.bottom, self.left: self.right]
        self.compressed_bytes = rel_compress(self.all_bytes)

        self.roi_bytes = np.packbits(roi, axis=None).tobytes()
        self.compressed_roi_bytes = rel_compress(self.roi_bytes)

        self.all_msgs = helper_calc_overlay_bytes(self.all_bytes) # we can skip empty data packets as for plain transfer every packet has a number and the buffer are erased before
        self.compressed_msgs = math.ceil((len(self.compressed_bytes)+COMPRESSED_OVERLAY_COMMAND_BYTES)/MAX_DATA_PER_MSG)
        self.roi_msgs = math.ceil((len(self.roi_bytes)+ROI_OVERLAY_COMMAND_BYTES)/MAX_DATA_PER_MSG)
        self.compressed_roi_msgs = math.ceil((len(self.compressed_roi_bytes)+ROI_OVERLAY_COMMAND_BYTES)/MAX_DATA_PER_MSG)

        # w = self.right - self.left
        # h = self.bottom - self.top
        # plt.imshow(image)
        # plt.gca().add_patch(plt.Rectangle((self.top, self.left), w, h,
        #                               edgecolor='red',
        #                               facecolor='none',
        #                               lw=2))
        # plt.show()

        # print("uint8_t all[] = {")
        # print(", ".join(hex(b) for b in self.all_bytes))
        # print("};")
        # print(f"uint8_t roi_y = {self.top}, roi_x = {self.left}, roi_yy = {self.bottom}, roi_xx = {self.right};")
        # print("uint8_t roi[] = {")
        # print(", ".join(hex(b) for b in self.roi_bytes))
        # print("};")
        # print("uint8_t croi[] = {")
        # print(", ".join(hex(b) for b in self.compressed_roi_bytes))
        # print("};")

