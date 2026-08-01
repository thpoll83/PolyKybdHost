import logging

from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_data import OverlayData

# numpy and PIL are imported lazily inside open() (the only place they're used).
# Both are heavy cold imports and im_converter sits on the daemon's startup
# import chain (poly_kybd), but conversion only runs on the HID worker thread
# when an overlay is actually loaded — so deferring the import speeds startup.

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
        import numpy as np
        from PIL import Image
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
            # Channel -> modifier variant. ⚠️ ".combo.mods." and ".extra.mods." both
            # CONTAIN ".mods.", so they must be tested before the plain form.
            if ".combo.mods." in filename:
                # Pairs, plus GUI in alpha.
                key_a, key_r = Modifier.GUI_KEY, Modifier.CTRL_SHIFT
                key_g, key_b = Modifier.CTRL_ALT, Modifier.ALT_SHIFT
            elif ".extra.mods." in filename:
                # Third tier: what is left after the singles and the pairs. Only R
                # is assigned today (CTRL_ALT_SHIFT, variant 7). G/B/A are RESERVED
                # for the GUI pairs the firmware earmarks (GUI+CTRL / GUI+ALT /
                # GUI+SHIFT -> variants 9/10/11, config.h NUM_VARIATIONS_WITH_MAP).
                # CTRL_ALT_SHIFT lives in R rather than A on purpose: a 3-channel
                # PNG drops alpha entirely below, which would silently lose it.
                key_r = Modifier.CTRL_ALT_SHIFT
                key_a = key_g = key_b = None
            else:
                # Singles, plus the unmodified layer in alpha.
                key_a, key_r = Modifier.NO_MOD, Modifier.CTRL
                key_g, key_b = Modifier.ALT, Modifier.SHIFT
            if not has_alpha:
                [b, g, r] = np.dsplit(im, im.shape[-1])
                channels = ((key_r, r), (key_g, g), (key_b, b))
                self.log.debug_detailed("Loaded 3 channels from %s: %dx%d", filename, self.w, self.h)
            else:
                [b, g, r, a] = np.dsplit(im, im.shape[-1])
                channels = ((key_a, a), (key_r, r), (key_g, g), (key_b, b))
                self.log.debug_detailed("Loaded 4 channels from %s: %dx%d", filename, self.w, self.h)
            for key, plane in channels:
                if key is not None:            # reserved channel — nothing maps to it yet
                    self.image[key] = np.array(plane, dtype=bool)
        else:
            # convert the image to b/w
            self.image[Modifier.NO_MOD] = np.array(np.dot(im[..., :3], [0.2989 / 255, 0.5870 / 255, 0.1140 / 255]),
                                                   dtype=bool)

            self.log.debug("Loaded %s: %dx%d", filename, self.w, self.h)

        # GUI overlays used to be dropped here ("not supported for now") even though
        # the .combo.mods. alpha channel carries them, the firmware addresses variant
        # 8 (adjust_overlay_idx_to_mod -> idx + NUM_OVERLAYS*8) and overlay_map[] has
        # always had entries for it — so they simply never reached the keyboard. They
        # are sent now. Cost is nil: every shipped template's GUI content is the one
        # Esc app-marker cell, byte-identical to its other variants, so the cache
        # dedups it onto a single pool slot.

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
