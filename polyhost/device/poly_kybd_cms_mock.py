import logging
import time

from polyhost.device.cmd_composer import split_by_n_chars
from polyhost.device.im_converter import Modifier, ImageConverter
from polyhost.device.keys import KeyCode


class PolyKybdMock:
    """
    PolyKybd for Testing
    """

    def __init__(self, version, lang = "enUS", langs = "enUsdeAtkoKO"):
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

    def reset_overlays(self):
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
        self.log.info(f"Send Overlay '{filename}'...")
        converter = ImageConverter()
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
                counter = counter + 1

        if on_off and counter > 0:
            self.enable_overlays()
        return True, f"{counter} overlays sent."

    def send_overlays(self, filenames, allow_compressed):
        overlay_counter = 0
        hid_msg_counter = 0
        enabled = False
        if type(filenames) is not list:
            filenames = [filenames]
        
        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            converter = ImageConverter()
            if not converter:
                return False, f"Invalid file '{filename}'."

            if not converter.open(filename):
                return False, f"Unable to read '{filename}'."

            for modifier in Modifier:
                overlaymap = converter.extract_overlays(modifier)
                # it is okay if there is no overlay for a modifier
                if overlaymap:
                    self.log.debug(f"Sending overlays for modifier {modifier}.")

                    # Send ESC first
                    if not enabled and modifier == Modifier.NO_MOD:
                        if KeyCode.KC_ESCAPE.value in overlaymap.keys():
                            # if allow_compressed:
                            #     hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode_compressed(KeyCode.KC_ESCAPE.value, modifier, overlaymap)
                            # else:
                            #     hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode(KeyCode.KC_ESCAPE.value, modifier, overlaymap)
                            overlaymap.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True

                    all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                    self.log.debug(f"Overlays for keycodes {all_keys} have been sent.")
                    overlay_counter = overlay_counter + 1

        self.log.info(f"{overlay_counter} overlays sent ({hid_msg_counter} hid messages).")
        if not enabled:
            self.enable_overlays()
        return True, "Overlays sent."
    
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
                            case _:
                                self.log.warning(f"Unknown overlay command '{cmd}' from '{cmd_str}'")
                    case _:
                        self.log.warning(f"Unknown command '{cmd_str}'")
            except Exception as e:
                self.log.error(f"Couldn't not execute '{cmd_str}': {e}")
