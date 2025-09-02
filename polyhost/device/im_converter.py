import logging

import numpy as np
from enum import Enum

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from polyhost.device.keys import KeyCode
from polyhost.device.overlay_data import OverlayData


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
    def __init__(self, settings):
        self.settings = settings
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
                q_image = pixmap.toImage()
                im = np.ndarray((q_image.height(), q_image.width(), 3), buffer=q_image.constBits(),
                                   strides=[q_image.bytesPerLine(), 3, 1], dtype=np.uint8)
                [b, g, r] = np.dsplit(im, im.shape[-1])
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                # plt.imshow(self.image[Modifier.SHIFT])
                # plt.show()
                self.log.debug_detailed("Loaded 3 channels from %s: %dx%d", filename, self.w, self.h)
            else:
                q_image = pixmap.toImage()
                b = q_image.bits()
                b.setsize(q_image.width() * q_image.height() * 4)

                im = np.ndarray((q_image.height(), q_image.width(), 4), buffer=b,
                                strides=[q_image.bytesPerLine(), 4, 1], dtype=np.uint8)
                [b, g, r, a] = np.dsplit(im, im.shape[-1])
                self.image[key_a] = np.array(a, dtype=bool)
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.log.debug_detailed("Loaded 4 channels from %s: %dx%d", filename, self.w, self.h)
        else:
            if not pixmap.hasAlphaChannel():
                q_image = pixmap.toImage()
                im = np.ndarray((q_image.height(), q_image.width(), 3), buffer=q_image.constBits(),
                                   strides=[q_image.bytesPerLine(), 3, 1], dtype=np.uint8)
            else:
                q_image = pixmap.toImage()
                b = q_image.bits()
                b.setsize(q_image.width() * q_image.height() * 4)

                im = np.ndarray((q_image.height(), q_image.width(), 4), buffer=b,
                                strides=[q_image.bytesPerLine(), 4, 1], dtype=np.uint8)
            # convert the image to b/w
            self.image[Modifier.NO_MOD] = np.array(np.dot(im[..., :3], [0.2989 / 255, 0.5870 / 255, 0.1140 / 255]),
                                                   dtype=bool)
            
            self.log.debug("Loaded %s: %dx%d", filename, self.w, self.h)
            
        #not supported for now
        if Modifier.GUI_KEY in self.image:
            self.image.pop(Modifier.GUI_KEY)

        return True

    # noinspection PyPep8Naming
    @property
    @staticmethod
    def NUM_OVERLAYS_X(self):
        return 10

    # noinspection PyPep8Naming
    @property
    @staticmethod
    def NUM_OVERLAYS_Y(self):
        return 9

    def extract_overlays(self, modifier=Modifier.NO_MOD):
        # we expect 10x9 images each having 72x40px
        if self.w < self.settings.OVERLAY_RES_X * self.NUM_OVERLAYS_X or self.h < self.settings.OVERLAY_RES_Y * self.NUM_OVERLAYS_Y:
            self.log.error("Image too small")
            return None
        if modifier in self.image:
            overlays = {}
            keycode = KeyCode.KC_A.value
            for y in range(0, self.NUM_OVERLAYS_Y):
                for x in range(0, self.NUM_OVERLAYS_X):
                    top_x = x * self.settings.OVERLAY_RES_X
                    top_y = y * self.settings.OVERLAY_RES_Y
                    bottom_x = top_x + self.settings.OVERLAY_RES_X
                    bottom_y = top_y + self.settings.OVERLAY_RES_Y
                    key_slice = self.image[modifier][top_y:bottom_y, top_x:bottom_x]
                    if key_slice.any():
                        overlays[keycode] = OverlayData(self.settings, key_slice)

                    keycode += 1
                    if keycode == KeyCode.KC_KP_SLASH.value:        # skip keypad keycodes
                        keycode = KeyCode.KC_NONUS_BACKSLASH.value  # KC_NONUS_BACKSLASH
                    if keycode == KeyCode.KC_KB_POWER.value:        # skip media keys etc.
                        keycode = KeyCode.KC_LEFT_CTRL.value        # KC_LEFT_CTRL
            self.log.debug_detailed("Image data for modifier %s overlay prepared.", modifier)
            return overlays
        else:
            #self.log.info("No image data for modifier %s present.", modifier)
            return None
