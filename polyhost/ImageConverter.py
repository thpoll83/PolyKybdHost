import logging

import numpy as np
from enum import Enum

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage

class Modifier(Enum):
    NO_MOD = 0
    CTRL = 1
    SHIFT = 2
    CTRL_SHIFT = 3
    ALT = 4
    CTRL_ALT = 5
    ALT_SHIFT = 6
    # CTRL_ALT_SHIFT = 7 #not supported for now
    GUI_KEY = 8

class ImageConverter:
    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.h = 0
        self.w = 0
        self.image = {}

    def open(self, filename):
        pixmap = QPixmap()
        try:
            pixmap.load(filename, "", Qt.NoFormatConversion)
            self.w = pixmap.width()
            self.h = pixmap.height()
        except:
            self.log.warning("Couldn't read overlay")
            return False

        if ".mods." in filename:
            if ".combo.mods." in filename:
                key_a = Modifier.GUI_KEY
                key_r = Modifier.CTRL_SHIFT
                key_g = Modifier.CTRL_ALT
                key_b = Modifier.ALT_SHIFT
            else:
                key_a = Modifier.NO_MOD
                key_r = Modifier.CTRL
                key_g = Modifier.ALT
                key_b = Modifier.SHIFT
            if not pixmap.hasAlphaChannel():
                qimage = pixmap.toImage()
                im = np.ndarray((qimage.height(), qimage.width(), 3), buffer=qimage.constBits(),
                                   strides=[qimage.bytesPerLine(), 3, 1], dtype=np.uint8)
                [b, g, r] = np.dsplit(im, im.shape[-1])
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                # plt.imshow(self.image[Modifier.SHIFT])
                # plt.show()
                self.log.info(f"Loaded 3 channels from {filename}: {self.w}x{self.h}")
            else:
                qimage = pixmap.toImage()
                b = qimage.bits()
                b.setsize(qimage.width() * qimage.height() * 4)

                im = np.ndarray((qimage.height(), qimage.width(), 4), buffer=b,
                                strides=[qimage.bytesPerLine(), 4, 1], dtype=np.uint8)
                [b, g, r, a] = np.dsplit(im, im.shape[-1])
                self.image[key_a] = np.array(a, dtype=bool)
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.log.debug(f"Loaded 4 channels from {filename}: {self.w}x{self.h}")
        else:
            if not pixmap.hasAlphaChannel():
                qimage = pixmap.toImage()
                im = np.ndarray((qimage.height(), qimage.width(), 3), buffer=qimage.constBits(),
                                   strides=[qimage.bytesPerLine(), 3, 1], dtype=np.uint8)
            else:
                qimage = pixmap.toImage()
                b = qimage.bits()
                b.setsize(qimage.width() * qimage.height() * 4)

                im = np.ndarray((qimage.height(), qimage.width(), 4), buffer=b,
                                strides=[qimage.bytesPerLine(), 4, 1], dtype=np.uint8)
            # convert the image to b/w
            self.image[Modifier.NO_MOD] = np.array(np.dot(im[..., :3], [0.2989 / 255, 0.5870 / 255, 0.1140 / 255]),
                                                   dtype=bool)
            # plt.imshow(self.image[Modifier.NO_MOD])
            # plt.show()
            self.log.debug(f"Loaded {filename}: {self.w}x{self.h}")

        #not supported for now
        if Modifier.GUI_KEY in self.image:
            self.image.pop(Modifier.GUI_KEY)

        return True

    def extract_overlays(self, modifier=Modifier.NO_MOD):
        # we expect 10x9 images each having 72x40px
        if self.w < 72 * 10 or self.h < 40 * 9:
            self.log.error("Image too small")
            return None
        if modifier in self.image:
            overlays = {}
            keycode = 4  # KC_A
            for y in range(0, 9):
                for x in range(0, 10):
                    topx = x * 72
                    topy = y * 40
                    bottomx = (x + 1) * 72
                    bottomy = (y + 1) * 40
                    key_slice = self.image[modifier][topy:bottomy, topx:bottomx]
                    if key_slice.any():
                        overlays[keycode] = np.packbits(key_slice, axis=None).tobytes()

                    keycode = keycode + 1
                    if keycode == 84:  # skip keypad keycodes
                        keycode = 100  # KC_NONUS_BACKSLASH
                    if keycode == 102:  # skip media keys etc.
                        keycode = 224  # KC_LEFT_CTRL
            self.log.debug(f"Image data for modifier {modifier} overlay prepared.")
            return overlays
        else:
            #self.log.info(f"No image data for modifier {modifier} present.")
            return None
