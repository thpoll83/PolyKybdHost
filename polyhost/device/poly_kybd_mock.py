import logging
import time

from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.im_converter import Modifier, ImageConverter
from polyhost.device.keys import KeyCode


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
        return True, ""

    def reset_overlays_and_usage(self):
        self.log.info("Reset Overlays AND Usage...")
        return True, ""

    def reset_overlay_usage(self):
        self.log.info("Reset Overlay Usage...")
        return True, ""

    def reset_overlays(self):
        self.log.info("Reset Overlays...")
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

    def send_overlay(self, filename, on_off=True):
        self.log.info("Send Overlay '%s'...", filename)
        converter = ImageConverter(self.settings)
        if not converter:
            return False, f"Invalid file '{filename}'."

        if not converter.open(filename):
            return False, f"Unable to read '{filename}'."

        counter = 0
        for modifier in Modifier:
            overlaymap = converter.extract_overlays(modifier)
            #it is okay if there is no overlay for a modifier
            if overlaymap:
                self.log.debug(f"Sending overlays for modifier {modifier}.")
                if on_off and counter == 0:
                    self.disable_overlays()
                all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                self.log.debug(f"Overlays for keycodes {all_keys} have been sent.")
                counter += 1

        if on_off and counter > 0:
            self.enable_overlays()
        return True, f"{counter} overlays sent."

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
                            hid_msg_counter += self.send_smallest_overlay(KeyCode.KC_ESCAPE.value, overlay_map)
                            overlay_map.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True
                            key_counter += 1

                    for keycode in overlay_map:
                        hid_msg_counter += self.send_smallest_overlay(keycode, overlay_map)
                        key_counter += 1

                    all_keys = ", ".join(f"{key:#02x}" for key in overlay_map.keys())
                    self.log.info(f"Overlays for keycodes {all_keys} have been sent.")
                    overlay_counter += 1

        # self.log.info(f"Sum Plain: {self.stat_plain} Comp: {self.stat_comp} Roi: {self.stat_roi} CRoi: {self.stat_croi} Best: {self.stat_best}")
        self.log.info(f"{overlay_counter} overlays with {key_counter} keys sent ({hid_msg_counter} hid messages).")
        # self.log.info(f"Stats: Plain:{self.stat_plain} C:{self.stat_comp} R:{self.stat_roi} CR:{self.stat_croi} --> {self.stat_best}")
        if not enabled:
            self.enable_overlays()
        return True

    def send_smallest_overlay(self, keycode, mapping: dict):
        ov = mapping[keycode]
        return min(ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs)

    def read_serial(self):
        return None

    def get_console_output(selfself):
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

    def set_unicode_mode(self, value):
        self.log.info(f"Setting unicode mode to %d", value)
