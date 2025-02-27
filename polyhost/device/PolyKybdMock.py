import logging
import time

from device import ImageConverter
from device.PolyKybd import split_by_n_chars


class PolyKybdMock():
    """
    PolyKybd for Testing
    """

    def __init__(self, version, lang = "enUS", langs = "enUsdeAtkoKO"):
        self.log = logging.getLogger('PolyHost')
        self.all_languages = list()
        self.version = version
        self.lang = lang
        self.langs = langs

    def connect(self):
        return True

    def query_id(self):
        return True, "PolyKybdMock.py"

    def query_version_info(self):
        return True, self.version

    def get_name(self):
        return "PolyKybdMock"

    def get_sw_version(self):
        return self.version

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

    def set_overlay_masking(self, flags, set):
        return True, ""

    def send_overlay(self, filename, on_off=True):
        self.log.info(f"Send Overlay '{filename}'...")
        converter = ImageConverter.ImageConverter()
        if not converter:
            return False, f"Invalid file '{filename}'."

        if not converter.open(filename):
            return False, f"Unable to read '{filename}'."

        BYTES_PER_MSG = 24
        BYTES_PER_OVERLAY = int(72 * 40) / 8  # 360
        NUM_MSGS = int(BYTES_PER_OVERLAY / BYTES_PER_MSG)  # 360/24 = 15
        self.log.debug(f"BYTES_PER_MSG: {BYTES_PER_MSG}, BYTES_PER_OVERLAY: {BYTES_PER_OVERLAY}, NUM_MSGS: {NUM_MSGS}")

        counter = 0
        for modifier in ImageConverter.Modifier:
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
