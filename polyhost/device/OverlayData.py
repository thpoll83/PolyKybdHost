import numpy as np

from device import RleCompression

def find_roi_rectangle(image):
    rows = np.any(image, axis=1)
    cols = np.any(image, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return None
    
    top, bottom = np.where(rows == 1)[0][[0, -1]]
    left, right = np.where(cols == 1)[0][[0, -1]]
    
    return (int(top), int(left), int(bottom), int(right))

class OverlayData():
    def __init__(self, image):
        self.all_bytes = np.packbits(image, axis=None).tobytes()
        self.compressed_bytes = RleCompression.compress(self.all_bytes)
        self.roi = find_roi_rectangle(image)
        self.top, self.left, self.bottom, self.right = self.roi
        roi_image = image[self.top:self.bottom, self.left:self.right]
        self.roi_bytes = np.packbits(roi_image, axis=None).tobytes()
        self.compressed_roi_bytes = RleCompression.compress(self.roi_bytes)
