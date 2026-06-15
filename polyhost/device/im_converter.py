import logging

import numpy as np

from PIL import Image

from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_data import OverlayData

class ImageConverter:
    def __init__(self, device_settings):
        self.device_settings = device_settings
        self.log = logging.getLogger('PolyHost')
        self.h = 0
        self.w = 0
        self.image = {}
        self._num_x = 10
        self._num_y = 9

    def open(self, filename):
        # Pillow decode (Qt-free: this runs on the non-Qt HID worker thread).
        # We normalise to an (H, W, depth) uint8 array with the SAME channel
        # order the old QImage path produced, so the extracted overlay bytes
        # stay byte-identical (gated by tests/device/im_converter_golden_test).
        #
        # The legacy path converted to little-endian ARGB32 when the source
        # had an alpha channel (byte order B,G,R,A) and to RGB888 (R,G,B)
        # otherwise. It used QImage.hasAlphaChannel() to choose. Pillow modes
        # with alpha are RGBA / LA / PA and palettes carrying transparency, so
        # we mirror that test and build the channels in B,G,R[,A] order to
        # match the ARGB32 byte layout the downstream code expects.
        try:
            with Image.open(filename) as pil_image:
                pil_image.load()
                src_mode = pil_image.mode
                has_alpha = (
                    "A" in src_mode
                    or "transparency" in pil_image.info
                )
                if has_alpha:
                    rgba = pil_image.convert("RGBA")
                    rgb_arr = np.asarray(rgba, dtype=np.uint8)  # R,G,B,A
                    # Reorder to B,G,R,A to match QImage Format_ARGB32 bytes.
                    im = rgb_arr[..., [2, 1, 0, 3]]
                    depth = 4
                else:
                    rgb = pil_image.convert("RGB")
                    rgb_arr = np.asarray(rgb, dtype=np.uint8)  # R,G,B
                    # RGB888 in the old path was R,G,B order.
                    im = rgb_arr
                    depth = 3
                self.w = im.shape[1]
                self.h = im.shape[0]
        except Exception as e:
            self.log.warning("Couldn't read overlay: %s", e)
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
            if not has_alpha:
                [b, g, r] = np.dsplit(im, im.shape[-1])
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.log.debug_detailed("Loaded 3 channels from %s: %dx%d", filename, self.w, self.h)
            else:
                [b, g, r, a] = np.dsplit(im, im.shape[-1])
                self.image[key_a] = np.array(a, dtype=bool)
                self.image[key_r] = np.array(r, dtype=bool)
                self.image[key_g] = np.array(g, dtype=bool)
                self.image[key_b] = np.array(b, dtype=bool)
                self.log.debug_detailed("Loaded 4 channels from %s: %dx%d", filename, self.w, self.h)
        else:
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
    def NUM_OVERLAYS_X(self):
        return self._num_x

    # noinspection PyPep8Naming
    @property
    def NUM_OVERLAYS_Y(self):
        return self._num_y

    def extract_overlays(self, modifier=Modifier.NO_MOD):
        # we expect 10x9 images each having 72x40px
        if self.w < self.device_settings.OVERLAY_RES_X * self.NUM_OVERLAYS_X or self.h < self.device_settings.OVERLAY_RES_Y * self.NUM_OVERLAYS_Y:
            self.log.error("Image too small")
            return None
        if modifier in self.image:
            overlays = {}
            keycode = KeyCode.KC_A.value
            for y in range(0, self.NUM_OVERLAYS_Y):
                for x in range(0, self.NUM_OVERLAYS_X):
                    top_x = x * self.device_settings.OVERLAY_RES_X
                    top_y = y * self.device_settings.OVERLAY_RES_Y
                    bottom_x = top_x + self.device_settings.OVERLAY_RES_X
                    bottom_y = top_y + self.device_settings.OVERLAY_RES_Y
                    key_slice = self.image[modifier][top_y:bottom_y, top_x:bottom_x]
                    if key_slice.any():
                        try:
                            overlays[keycode] = OverlayData(self.device_settings, key_slice)
                        except ValueError:
                            self.log.warning("Skipping empty overlay for keycode 0x%x", keycode)
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
