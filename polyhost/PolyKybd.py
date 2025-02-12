import logging
import re
import time
from enum import Enum

import numpy as np

import HidHelper
import ImageConverter


class Cmd(Enum):
    GET_ID = 6
    GET_LANG = 7
    GET_LANG_LIST = 8
    CHANGE_LANG = 9
    SEND_OVERLAY = 10
    OVERLAY_FLAGS_ON = 11
    OVERLAY_FLAGS_OFF = 12
    SET_BRIGHTNESS = 13
    KEYPRESS = 14
    IDLE_STATE = 15


class MaskFlag(Enum):
    LEFT_TOP = 2
    LEFT_BOTTOM = 4
    RIGHT_TOP = 8
    RIGHT_BOTTOM = 16

def compose_cmd_str(cmd, text):
    b = bytearray.fromhex(f"09{cmd.value:02x}3a")
    b.extend(text.encode())
    return b
    
def compose_cmd(cmd, extra1=None, extra2=None, extra3=None):
    if extra3 is not None:
        return bytearray.fromhex(f"09{cmd.value:02x}3a{extra1:02x}{extra2:02x}{extra3:02x}")
    elif extra2 is not None:
        return bytearray.fromhex(f"09{cmd.value:02x}3a{extra1:02x}{extra2:02x}")
    elif extra1 is not None:
        return bytearray.fromhex(f"09{cmd.value:02x}3a{extra1:02x}")
    else:
        return bytearray.fromhex(f"09{cmd.value:02x}")


def split_by_n_chars(text, n):
    return [text[i:i+n] for i in range(0, len(text), n)]



class PolyKybd():
    """
    Communication to PolyKybd
    """

    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.all_languages = list()
        self.hid = None

    def get_log_handler(self):
        return self.log

    def connect(self):
        # Connect to Keeb
        if not self.hid:
            self.hid = HidHelper.HidHelper(0x2021, 0x2007)
        else:
            result, msg = self.query_id()
            if not result:
                self.log.debug("Reconnecting to PolyKybd...")
                try:
                    self.hid = HidHelper.HidHelper(0x2021, 0x2007)
                except Exception as e:
                    self.log.warning(f"Could not reconnect: {e}")
                    return False
        return self.hid.interface_aquired()

    def query_id(self):
        try:
            result, msg = self.hid.send_and_read(compose_cmd(Cmd.GET_ID), 1000)
            return result, msg if not result else msg[3:]
        except Exception as e:
            return False, f"Exception: {e}"

    def query_version_info(self):
        result, msg = self.query_id()
        if not result:
            return False, msg
        try:
            match = re.search(r"(?P<name>.+)\W(?P<sw>\d\.\d\.\d)\WHW(?P<hw>\w*)", msg)
            if match:
                self.name = match.group("name")
                self.sw_version = match.group("sw")
                self.hw_version = match.group("hw")
                return True, msg
            else:
                self.log.warning(f"Could not match version string: {msg}")
                return False, "Could not match version string. Please update firmware."
        except Exception as e:
            self.log.warning(f"Exception matching version string '{msg}':\n{e}")
            return False, "Could not match version string. Please update firmware."

    def get_name(self):
        return self.name

    def get_sw_version(self):
        return self.sw_version

    def get_hw_version(self):
        return self.hw_version

    def reset_overlays(self):
        self.log.info("Reset Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x20))

    def enable_overlays(self):
        self.log.info("Enable Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x01))

    def disable_overlays(self):
        self.log.info("Disable Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_OFF, 0x01))

    def set_brightness(self, brightness):
        self.log.info(f"Setting Display Brightness to {brightness}...")
        return self.hid.send(compose_cmd(Cmd.SET_BRIGHTNESS, int(np.clip(brightness, 0, 50))))

    def press_and_release_key(self, keycode, duration):
        self.log.info(f"Pressing {keycode} for {duration} sec...")
        result, msg = self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255))
        if result:
            # for now, it is fine to block this thread
            time.sleep(duration)
            return self.hid.send(compose_cmd(Cmd.KEYRELEASE, keycode >> 8, keycode & 255))
        else:
            return result, msg

    def press_key(self, keycode):
        self.log.info(f"Pressing {keycode}...")
        return self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))

    def release_key(self, keycode):
        self.log.info(f"Releasing {keycode}...")
        return self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))

    def set_idle(self, idle):
        self.log.debug(f"Setting idle state to {idle}...")
        return self.hid.send(compose_cmd(Cmd.IDLE_STATE, 1 if idle else 0))

    def query_current_lang(self):
        self.log.debug("Query Languages...")

        result, msg = self.hid.send_and_read(compose_cmd(Cmd.GET_LANG), 100)
        if result:
            self.current_lang = msg[3:]
            return True, self.current_lang
        else:
            return False, "Could not read reply from PolyKybd"

    def enumerate_lang(self):
        self.log.debug("Enumerate Languages...")
        result, msg = self.query_current_lang()
        if not result:
            return False, msg
        
        result, reply = self.hid.send_and_read(compose_cmd(Cmd.GET_LANG_LIST), 100)

        if not result:
            return False, "Could not receive language list."
        lang_str = ""
        while result and len(reply) > 3:
            lang_str = f"{lang_str}{reply[3:]}"
            result, reply = self.hid.read(100)

        self.all_languages = split_by_n_chars(lang_str, 4)
        return True, lang_str

    def get_lang_list(self):
        return self.all_languages

    def get_current_lang(self):
        return self.current_lang

    def change_language(self, lang):
        """
        Send command to change the language to the specified index
        :param lang: 4 letter str which must be in the list of languages.
        :return:
            - result (:py:class:`bool`) True on successful language change.
            - lang_code (:py:class:`str`) The 4 letter language code as str in use.
        """
        if lang not in self.all_languages:
            return False, f"Language '{lang}' not present on PolyKybd"

        result, msg = self.hid.send_and_read(compose_cmd_str(Cmd.CHANGE_LANG, lang), 100)
        if not result:
            return False, f"Could not change to {lang} ({msg})"

        self.log.info(f"Language changed to {lang} ({msg}).")
        return True, lang

    def set_overlay_masking(self, flags, set):
        cmd = Cmd.OVERLAY_FLAGS_ON if set else Cmd.OVERLAY_FLAGS_OFF
        return self.hid.send(compose_cmd(cmd, 0x1e))

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
        lock = None
        for modifier in ImageConverter.Modifier:
            overlaymap = converter.extract_overlays(modifier)
            #it is okay if there is no overlay for a modifier
            if overlaymap:
                self.log.debug(f"Sending overlays for modifier {modifier}.")
                if on_off and counter == 0:
                    self.disable_overlays()
                for keycode in overlaymap:
                    bmp = overlaymap[keycode]
                    for i in range(0, NUM_MSGS):
                        self.log.debug(f"Sending msg {i + 1} of {NUM_MSGS}.")
                        cmd = compose_cmd(Cmd.SEND_OVERLAY, keycode, modifier.value, i)
                        data = cmd + bmp[i * BYTES_PER_MSG:(i + 1) * BYTES_PER_MSG]
                        result, msg, lock = self.hid.send_multiple(data, lock)
                        if not result:
                            return False, f"Error sending overlay message {i + 1}/{NUM_MSGS} ({msg})"
                all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                self.log.debug(f"Overlays for keycodes {all_keys} have been sent.")
                counter = counter + 1
        if lock:
            lock.release()

        if on_off and counter > 0:
            # self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x1e))
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
