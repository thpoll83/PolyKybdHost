import math
import numpy as np

from device import RleCompression

# overlay constants
MAX_DATA_PER_MSG = 30
PLAIN_OVERLAY_BYTES_PER_MSG = 24
BYTES_PER_OVERLAY = int(72 * 40) / 8  # 360
NUM_PLAIN_OVERLAY_MSGS = int(BYTES_PER_OVERLAY / PLAIN_OVERLAY_BYTES_PER_MSG)  # 360/24 = 15

def find_roi_rectangle(image):
    rows = np.any(image, axis=1)
    cols = np.any(image, axis=0)

    if not np.any(rows) or not np.any(cols):
        return None

    top, bottom = np.where(rows == 1)[0][[0, -1]]
    left, right = np.where(cols == 1)[0][[0, -1]]

    return int(top), int(left), int(bottom), int(right)

def helper_calc_overlay_bytes(all_bytes, skip_empty=True):
    msg_cnt = 0
    for msg_num in range(0, NUM_PLAIN_OVERLAY_MSGS):
        data = all_bytes[msg_num * PLAIN_OVERLAY_BYTES_PER_MSG:(msg_num + 1) * PLAIN_OVERLAY_BYTES_PER_MSG]
        if skip_empty and all(b == 0 for b in data):
            continue
        msg_cnt = msg_cnt + 1

    return msg_cnt
class OverlayData:
    def __init__(self, image):
        self.all_bytes = np.packbits(image, axis=None).tobytes()
        
        self.roi = find_roi_rectangle(image)
        self.top, self.left, self.bottom, self.right = self.roi
        roi_image = image[self.top : self.bottom, self.left : self.right]
        self.compressed_bytes = RleCompression.compress(self.all_bytes)
        
        self.roi_bytes = np.packbits(roi_image, axis=None).tobytes()
        self.compressed_roi_bytes = RleCompression.compress(self.roi_bytes)
        
        self.all_msgs = helper_calc_overlay_bytes(self.all_bytes)
        self.compressed_msgs = math.ceil((len(self.compressed_bytes)+2)/MAX_DATA_PER_MSG)
        self.roi_msg_msgs = math.ceil((len(self.roi_bytes)+5)/MAX_DATA_PER_MSG)
        self.compressed_roi_msgs = math.ceil((len(self.compressed_roi_bytes)+5)/MAX_DATA_PER_MSG)
        
        # print(f"All: {len(self.all_bytes)}")
        # print(", ".join(hex(b) for b in self.all_bytes))
        # print(f"Roi: {len(self.roi_bytes)} - {self.top}, {self.left}, {self.bottom}, {self.right}")
        # print(", ".join(hex(b) for b in self.roi_bytes))
        # print(f"Compressed Roi: {len(self.compressed_roi_bytes)}")
        # print(", ".join(hex(b) for b in self.compressed_roi_bytes))
    

