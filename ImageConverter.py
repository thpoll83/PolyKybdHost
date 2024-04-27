import logging

import imageio.v3 as iio
import numpy as np
from enum import Enum


# from matplotlib import pyplot as plt

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
    def __init__(self, filename):
        self.log = logging.getLogger('PolyKybd')
        self.h = 0
        self.w = 0
        self.image = {}
        # try:
        im = iio.imread(filename)
        if ".mods." in filename:
            channels = im.shape[-1]
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
            if channels == 3:
                [b, g, r] = np.dsplit(im, im.shape[-1])
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.h, self.w, _ = self.image[Modifier.NO_MOD].shape
                # plt.imshow(self.image[Modifier.SHIFT])
                # plt.show()
                self.log.info(f"Loaded 3 channels from {filename}: {self.w}x{self.h}")
            elif channels == 4:
                [b, g, r, a] = np.dsplit(im, im.shape[-1])
                self.image[key_a] = np.array(a, dtype=bool)
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.h, self.w, _ = self.image[Modifier.NO_MOD].shape
                # plt.imshow(self.image[Modifier.SHIFT])
                # plt.show()
                self.log.info(f"Loaded 4 channels from {filename}: {self.w}x{self.h}")
            else:
                self.log.error(f"Cannot handle {channels} image channels.")
        else:
            # convert the image to b/w
            self.image[Modifier.NO_MOD] = np.array(np.dot(im[..., :3], [0.2989 / 255, 0.5870 / 255, 0.1140 / 255]),
                                                   dtype=bool)
            self.h, self.w = self.image[Modifier.NO_MOD].shape
            # plt.imshow(self.image[Modifier.NO_MOD])
            # plt.show()
            self.log.info(f"Loaded {filename}: {self.w}x{self.h}")

    # except:
    #    print("Couldn't read overlay")

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
                    slice = self.image[modifier][topy:bottomy, topx:bottomx]
                    if slice.any():
                        overlays[keycode] = np.packbits(slice, axis=None).tobytes()
                        # plt.imshow(slice)
                        # plt.show()

                    keycode = keycode + 1
                    if keycode == 84:  # skip keypad keycodes
                        keycode = 100  # KC_NONUS_BACKSLASH
                    if keycode == 102:  # skip media keys etc.
                        keycode = 224  # KC_LEFT_CTRL
            self.log.info("Image data for overlays prepared.")
            return overlays
        else:
            self.log.info(f"No image data for modifier {modifier} present.")
            return None
