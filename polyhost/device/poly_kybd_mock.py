import logging
import os
import time

from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_sim import OverlayFirmwareSim, display_flat_idx


class PolyKybdMock:
    """
    PolyKybd for Testing
    """

    def __init__(self, settings, version, lang = "enUS", langs = "enUsdeAtkoKrfrFritItesEs"):
        self.settings = settings
        self.log = logging.getLogger('PolyHost')
        self.all_languages = list()
        self.version = version
        self.sw_version_num = [int(x) for x in version.split(".")]
        self.lang = lang
        self.langs = langs
        self.hid_image_sends: int = 0
        self.hid_mapping_sends: int = 0
        self.last_mapping: dict = {}
        self._sim = OverlayFirmwareSim()

    def connect(self):
        return True

    def query_id(self):
        return True, "PolyKybdMockID"

    def query_version_info(self):
        return True, self.version

    def get_name(self):
        return "PolyKybdMock"

    def get_sw_version(self):
        return self.version

    def get_sw_version_number(self):
        """Get the software version number in as 3 ints: major, minor, patch"""
        return self.sw_version_num

    def get_hw_version(self):
        return self.version

    def reset_overlay_mapping(self):
        self.log.info("Reset Overlay Mapping...")
        self._sim.reset_mapping()
        return True, ""

    def reset_overlays_and_usage(self):
        self.log.info("Reset Overlays AND Usage...")
        self._sim.reset_all()
        return True, ""

    def reset_overlay_usage(self):
        self.log.info("Reset Overlay Usage...")
        self._sim.reset_usage()
        return True, ""

    def reset_overlays(self):
        self.log.info("Reset Overlays...")
        self._sim._store.clear()
        return True, ""

    def enable_overlays(self):
        return True, ""

    def disable_overlays(self):
        return True, ""

    def set_brightness(self, brightness):
        return True, ""

    def press_and_release_key(self, keycode, duration):
        return True, ""

    def press_key(self, keycode):
        return True, ""

    def release_key(self, keycode):
        return True, ""

    def set_idle(self, idle):
        return True, ""

    def query_current_lang(self):
        return True, self.lang

    def enumerate_lang(self):
        return True, self.langs

    def get_lang_list(self):
        return split_by_n_chars(self.langs, 4)

    def get_current_lang(self):
        return self.lang

    def change_language(self, lang):
        self.lang = lang
        return True, lang

    def set_overlay_masking(self, set_all):
        return True, f"{set_all}"

    def send_overlay_mapping(self, from_to: dict) -> tuple[bool, str]:
        self.hid_mapping_sends += 1
        self.last_mapping = from_to
        self._sim.apply_mapping(from_to)
        return True, "Mapping sent"

    def send_overlay(self, filename, on_off=True):
        self.log.info("Send Overlay '%s'...", filename)
        converter = ImageConverter(self.settings)
        if not converter:
            return False, f"Invalid file '{filename}'."

        if not converter.open(filename):
            return False, f"Unable to read '{filename}'."

        counter = 0
        all_keys = ""
        for modifier in Modifier:
            overlaymap = converter.extract_overlays(modifier)
            #it is okay if there is no overlay for a modifier
            if overlaymap:
                self.log.debug_detailed("Sending overlays for modifier %s.", modifier)
                if on_off and counter == 0:
                    self.log.debug("Disable overlays...")
                    self.disable_overlays()
                for keycode, overlay_data in overlaymap.items():
                    self.send_smallest_overlay(keycode, modifier, overlaymap)
                all_keys_for_mod = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                self.log.debug_detailed("Overlays for keycodes %s have been sent.", all_keys_for_mod)
                all_keys += f"(Mod: {modifier}/{modifier.value} {all_keys_for_mod})"
                counter += 1

        if on_off and counter > 0:
            self.log.debug("Enable overlays...")
            self.enable_overlays()

        return True, f"{counter} overlays sent {all_keys}."

    def send_overlays(self, filenames):
        overlay_counter = 0
        key_counter = 0
        hid_msg_counter = 0
        enabled = False

        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            converter = ImageConverter(self.settings)
            if not converter:
                self.log.warning("Invalid file %s", filename)
                return False

            if not converter.open(filename):
                self.log.warning("Unable to read %s", filename)
                return False

            for modifier in Modifier:
                overlay_map = converter.extract_overlays(modifier)
                # it is okay if there is no overlay for a modifier
                if overlay_map:
                    self.log.info(f"Sending overlays for modifier {modifier}.")

                    # Send ESC first
                    if not enabled and modifier == Modifier.NO_MOD:
                        if KeyCode.KC_ESCAPE.value in overlay_map.keys():
                            hid_msg_counter += self.send_smallest_overlay(
                                KeyCode.KC_ESCAPE.value, modifier, overlay_map)
                            overlay_map.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True
                            key_counter += 1

                    for keycode in overlay_map:
                        hid_msg_counter += self.send_smallest_overlay(keycode, modifier, overlay_map)
                        key_counter += 1

                    all_keys = ", ".join(f"{key:#02x}" for key in overlay_map.keys())
                    self.log.info(f"Overlays for keycodes {all_keys} have been sent.")
                    overlay_counter += 1

                    time.sleep(0.2)

        self.log.info(f"{overlay_counter} overlays with {key_counter} keys sent ({hid_msg_counter} hid messages).")
        if not enabled:
            self.enable_overlays()
        return True

    def send_overlays_mru(self, filenames: list, cache) -> bool:
        display_to_pool: dict[int, int] = {}

        with cache.batch():
            for filename in filenames:
                self.log.info("Send Overlay MRU (mock) '%s'...", filename)
                converter = ImageConverter(self.settings)
                if not converter.open(filename):
                    self.log.warning("Unable to read %s", filename)
                    return False

                for modifier in Modifier:
                    overlay_map = converter.extract_overlays(modifier)
                    if not overlay_map:
                        continue

                    for keycode, overlay_data in overlay_map.items():
                        content_key = (os.path.basename(filename), modifier.value, keycode)
                        pool_slot, is_hit = cache.get_or_allocate(content_key, filename, overlay_data.all_bytes)

                        if not is_hit:
                            pool_kc, pool_mod = cache.pool_slot_to_firmware_address(pool_slot)
                            self.hid_image_sends += self.send_smallest_overlay(
                                pool_kc, pool_mod, {pool_kc: overlay_data})

                        disp_idx = cache.display_flat_idx(keycode, modifier)
                        display_to_pool[disp_idx] = pool_slot

        self.reset_overlay_usage()
        self.send_overlay_mapping(display_to_pool)
        self.enable_overlays()
        return True

    def send_smallest_overlay(self, keycode: int, modifier: Modifier, mapping: dict) -> int:
        ov = mapping[keycode]
        pool_slot = display_flat_idx(keycode, modifier)
        self._sim.store_image(pool_slot, ov.all_bytes)
        return min(ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs)

    # ── inspection helpers ──────────────────────────────────────────────────

    def get_display_bitmap(self, keycode: int, modifier: Modifier) -> bytes | None:
        """Return the 360-byte bitmap shown at (keycode, modifier), or None if blank."""
        return self._sim.get_display_bitmap(keycode, modifier)

    def get_display_image(self, keycode: int, modifier: Modifier) -> "np.ndarray | None":
        """Return the 72×40 bool numpy array shown at (keycode, modifier), or None."""
        return self._sim.get_display_image(keycode, modifier)

    def save_overlay_as_png(self, keycode: int, modifier: Modifier, path: str) -> bool:
        """Save the overlay at (keycode, modifier) as a PNG file for visual inspection."""
        return self._sim.save_as_png(keycode, modifier, path)

    def read_serial(self):
        return None

    def get_console_output(self):
        return None

    def execute_commands(self, command_list):
        for cmd_str in command_list:
            cmd_str = cmd_str.strip()
            end = cmd_str.find(" ")
            cmd = cmd_str[:end] if end != -1 else cmd_str
            try:
                match cmd:
                    case "wait":
                        time.sleep(float(cmd_str[end + 1:]))
                    case "press":
                        self.press_key(int(cmd_str[end + 1:], 0))
                    case "release":
                        self.release_key(int(cmd_str[end + 1:], 0))
                    case "overlay":
                        params = cmd_str[end + 1:]
                        end = params.find(" ")
                        cmd = params[:end] if end != -1 else params
                        match cmd:
                            case "send":
                                self.send_overlay(params[end + 1:])
                            case "reset":
                                self.reset_overlays()
                            case "reset-usage":
                                self.reset_overlay_usage()
                            case "reset-mapping":
                                self.reset_overlay_mapping()
                            case _:
                                self.log.warning(f"Unknown overlay command '{cmd}' from '{cmd_str}'")
                    case _:
                        self.log.warning(f"Unknown command '{cmd_str}'")
            except Exception as e:
                self.log.error(f"Couldn't not execute '{cmd_str}': {e}")

    def get_default_layer(self) -> tuple[bool, int]:
        return True, 0

    def set_dynamic_keycode(self, layer: int, row: int, col: int, keycode: int):
        self.log.info("set_dynamic_keycode layer=%d row=%d col=%d keycode=0x%04x", layer, row, col, keycode)
        return True, ""

    def set_unicode_mode(self, mode):
        self.log.info(f"Setting unicode mode to %d", mode.value)
