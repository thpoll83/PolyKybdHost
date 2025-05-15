import logging
import re
import time
from enum import Enum

import numpy as np

from polyhost.device import HidHelper, ImageConverter, OverlayData, CmdHelper
from polyhost.device.Keycodes import KeyCode

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
    START_COMPRESSED_OVERLAY = 16
    SEND_COMPRESSED_OVERLAY = 17
    START_ROI_OVERLAY = 18
    SEND_ROI_OVERLAY = 19


class MaskFlag(Enum):
    LEFT_TOP = 2
    LEFT_BOTTOM = 4
    RIGHT_TOP = 8
    RIGHT_BOTTOM = 16


class PolyKybd:
    """
    Communication to PolyKybd
    """

    def __init__(self):
        self.log = logging.getLogger('PolyHost')
        self.all_languages = list()
        self.current_lang = None
        self.hid = None
        self.name = None
        self.sw_version = None
        self.sw_version_num = None
        self.hw_version = None
        self.stat_plain = 0
        self.stat_comp = 0
        self.stat_roi = 0
        self.stat_croi = 0
        self.stat_best = 0

    def connect(self):
        """Connect to PolyKybd"""
        # Connect to Keeb
        if not self.hid:
            self.hid = HidHelper.HidHelper(0x2021, 0x2007)
        else:
            result, _ = self.query_id()
            if not result:
                self.log.debug("Reconnecting to PolyKybd...")
                try:
                    self.hid = HidHelper.HidHelper(0x2021, 0x2007)
                except HidHelper.hid.HIDException as e:
                    self.log.warning("Could not reconnect: %s", e)
                    return False
                except ValueError as e:
                    self.log.warning("Problem with provided values: %s", e)
                    return False
        return self.hid.interface_acquired()

    def query_id(self):
        try:
            result, msg = self.hid.send_and_read_validate(CmdHelper.compose_cmd(Cmd.GET_ID), 1000, CmdHelper.expect(Cmd.GET_ID))
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
                self.sw_version_num = [int(x) for x in self.sw_version.split(".")]
                self.hw_version = match.group("hw")
                return True, msg
            else:
                self.log.warning("Could not match version string: %s", msg)
                return False, "Could not match version string. Please update firmware."
        except Exception as e:
            self.log.warning(f"Exception matching version string '{msg}':\n{e}")
            return False, "Could not match version string. Please update firmware."

    def get_name(self):
        return self.name

    def get_sw_version(self):
        return self.sw_version

    def get_sw_version_number(self):
        """Get the software version number in as 3 ints: major, minor, patch"""
        return self.sw_version_num

    def get_hw_version(self):
        return self.hw_version

    def reset_overlays(self):
        self.log.info("Reset Overlays...")
        return self.hid.send(CmdHelper.compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x20))

    def enable_overlays(self):
        self.log.info("Enable Overlays...")
        return self.hid.send(CmdHelper.compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x01))

    def disable_overlays(self):
        self.log.info("Disable Overlays...")
        return self.hid.send(CmdHelper.compose_cmd(Cmd.OVERLAY_FLAGS_OFF, 0x01))

    def set_brightness(self, brightness):
        self.log.info("Setting Display Brightness to %d...", brightness)
        return self.hid.send(CmdHelper.compose_cmd(Cmd.SET_BRIGHTNESS, int(np.clip(brightness, 0, 50))))

    def press_and_release_key(self, keycode, duration):
        self.log.info("Pressing 0x%2x for %f sec...", keycode, duration)
        result, msg = self.hid.send(CmdHelper.compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))
        if result:
            # for now, it is fine to block this thread
            time.sleep(duration)
            return self.hid.send(CmdHelper.compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))
        else:
            return result, msg

    def press_key(self, keycode):
        self.log.info("Pressing 0x%2x...", keycode)
        return self.hid.send(CmdHelper.compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))

    def release_key(self, keycode):
        self.log.info("Releasing 0x%2x...", keycode)
        return self.hid.send(CmdHelper.compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))

    def set_idle(self, idle):
        self.log.debug("Setting idle state to %s...", "True" if idle else "False")
        return self.hid.send(CmdHelper.compose_cmd(Cmd.IDLE_STATE, 1 if idle else 0))

    def query_current_lang(self):
        """Query current keyboard language an remember language internally"""
  
        try:
            result, msg = self.hid.send_and_read_validate(CmdHelper.compose_cmd(Cmd.GET_LANG), 100, CmdHelper.expect(Cmd.GET_LANG))
            if result:
                self.current_lang = msg[3:]
                return True, self.current_lang
            else:
                return False, "Could not read reply from PolyKybd"
        except Exception as e:
            return False, f"Exception: {e}"

    def enumerate_lang(self):
        self.log.debug("Enumerate Languages...")
        result, msg = self.query_current_lang()
        if not result:
            return False, msg

        result, reply = self.hid.send_and_read_validate(CmdHelper.compose_cmd(Cmd.GET_LANG_LIST), 100, CmdHelper.expect(Cmd.GET_LANG_LIST))

        if not result:
            return False, "Could not receive language list."
        lang_str = ""
        while result and len(reply) > 3:
            assert reply.startswith(CmdHelper.expect(Cmd.GET_LANG_LIST))
            lang_str = f"{lang_str}{reply[3:]}"
            result, reply = self.hid.read(100)

        self.all_languages = CmdHelper.split_by_n_chars(lang_str, 4)
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

        result, msg = self.hid.send_and_read_validate(CmdHelper.compose_cmd_str(Cmd.CHANGE_LANG, lang), 100, CmdHelper.expect(Cmd.CHANGE_LANG))
        if not result:
            return False, f"Could not change to {lang} ({msg})"

        self.log.info("Language changed to %s (%s).", lang, msg)
        return True, lang

    def set_overlay_masking(self, flags, set):
        cmd = Cmd.OVERLAY_FLAGS_ON if set else Cmd.OVERLAY_FLAGS_OFF
        return self.hid.send(CmdHelper.compose_cmd(cmd, 0x1e))

    def send_overlays(self, filenames, allow_compressed):
        overlay_counter = 0
        hid_msg_counter = 0
        enabled = False

        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            converter = ImageConverter.ImageConverter()
            if not converter:
                return False, f"Invalid file '{filename}'."

            if not converter.open(filename):
                return False, f"Unable to read '{filename}'."

            self.log.debug(f"PLAIN_OVERLAY_BYTES_PER_MSG: {OverlayData.PLAIN_OVERLAY_BYTES_PER_MSG}, BYTES_PER_OVERLAY: {OverlayData.BYTES_PER_OVERLAY}, NUM_PLAIN_OVERLAY_MSGS: {OverlayData.NUM_PLAIN_OVERLAY_MSGS}")
            for modifier in ImageConverter.Modifier:
                overlaymap = converter.extract_overlays(modifier)
                # it is okay if there is no overlay for a modifier
                if overlaymap:
                    self.log.debug(f"Sending overlays for modifier {modifier}.")

                    # Send ESC first
                    if not enabled and modifier == ImageConverter.Modifier.NO_MOD:
                        if KeyCode.KC_ESCAPE.value in overlaymap.keys():
                            if allow_compressed:
                                #hid_msg_counter = hid_msg_counter + self.send_overlay_roi_for_keycode(KeyCode.KC_ESCAPE.value, modifier, overlaymap, False)
                                hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode_compressed(KeyCode.KC_ESCAPE.value, modifier, overlaymap)
                            else:
                                hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode(KeyCode.KC_ESCAPE.value, modifier, overlaymap)
                            overlaymap.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True

                    for keycode in overlaymap:
                        if allow_compressed:
                            #hid_msg_counter = hid_msg_counter + self.send_overlay_roi_for_keycode(keycode, modifier, overlaymap, False)
                            hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode_compressed(keycode, modifier, overlaymap)
                        else:
                            hid_msg_counter = hid_msg_counter + self.send_overlay_for_keycode(keycode, modifier, overlaymap)
                        #self.send_overlay_for_keycode(keycode, modifier, overlaymap)
                        #if modifier != ImageConverter.Modifier.NO_MOD:
                        #    time.sleep(0.1)

                    all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                    self.log.debug(f"Overlays for keycodes {all_keys} have been sent.")
                    overlay_counter = overlay_counter + 1
                    
                    #time.sleep(0.2)

        # self.log.info(f"Sum Plain: {self.stat_plain} Comp: {self.stat_comp} Roi: {self.stat_roi} CRoi: {self.stat_croi} Best: {self.stat_best}")
        self.log.info(f"{overlay_counter} overlays sent ({hid_msg_counter} hid messages).")
        #self.log.info(f"Stats: Plain:{self.stat_plain} C:{self.stat_comp} R:{self.stat_roi} CR:{self.stat_croi} --> {self.stat_best}")
        if not enabled:
            self.enable_overlays()
        return True, "Overlays sent."

    def send_overlay_roi_for_keycode(self, keycode, modifier, mapping : dict, compressed):
        overlay = mapping[keycode]
        if not overlay.roi:
            self.send_overlay_for_keycode_compressed(keycode, modifier, mapping)
            
        hdr = CmdHelper.compose_roi_header(Cmd.START_ROI_OVERLAY, keycode, modifier.value, overlay, compressed)
        lock = None
        buffer = overlay.compressed_roi_bytes if compressed else overlay.roi_bytes
        num_msgs = overlay.compressed_roi_msgs if compressed else overlay.roi_msgs
        num_bytes = len(buffer)
        start = 0
        end = OverlayData.MAX_DATA_PER_MSG - 5 # minus one for keycode, minus 4 for modifier|top|bottom|left|right|compressed
        for msg_num in range(0,num_msgs):
            #self.log.info(f"Sending roi overlay msg {msg_num + 1} of {overlay.roi_msg_msgs} with {end-start} bytes.")
            cmd = hdr if msg_num == 0 else CmdHelper.compose_cmd(Cmd.SEND_ROI_OVERLAY)
            data = cmd + buffer[start:end]
            start = end
            end = min(end + OverlayData.MAX_DATA_PER_MSG, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                return False, f"Error sending roi overlay message {msg_num + 1}/{num_msgs} ({msg})"
        if lock:
            lock.release()
        return num_msgs

    def send_overlay_for_keycode(self, keycode, modifier, mapping : dict, skip_empty=True):
        lock = None
        overlay = mapping[keycode]
        msg_cnt = 0
        max_msgs = OverlayData.NUM_PLAIN_OVERLAY_MSGS
        for msg_num in range(0, max_msgs):
            #self.log.debug("Sending msg %d of %d", msg_num + 1, max_msgs)
            cmd = CmdHelper.compose_cmd(Cmd.SEND_OVERLAY, keycode, modifier.value, msg_num)
            from_idx = msg_num * OverlayData.PLAIN_OVERLAY_BYTES_PER_MSG
            to_idx = (msg_num + 1) * OverlayData.PLAIN_OVERLAY_BYTES_PER_MSG
            data = overlay.all_bytes[from_idx:to_idx]
            if skip_empty and msg_num+1!=max_msgs and all(b == 0 for b in data):
                #self.log.debug("Skipping msg %d as all bytes are 0", msg_num + 1)
                continue
            result, msg, lock = self.hid.send_multiple(cmd + data, lock)
            if not result:
                return False, f"Error sending overlay message {msg_num + 1}/{max_msgs} ({msg})"
            msg_cnt = msg_cnt + 1
        if lock:
            lock.release()
        #self.log.info(f"Keycode {keycode}: Sent {msg_cnt} plain msgs")
        return msg_cnt
    
    def send_overlay_for_keycode_compressed(self, keycode, modifier, mapping : dict):
        lock = None
        overlay = mapping[keycode]
        hdr = CmdHelper.compose_cmd(Cmd.START_COMPRESSED_OVERLAY, keycode, modifier.value)
        num_bytes = len(overlay.compressed_bytes)
        start = 0
        end = OverlayData.MAX_DATA_PER_MSG - 2 # minus one byte for the keycode and one for the modifier -> -2
        for msg_num in range(0, overlay.compressed_msgs):
            # self.log.info(f"Sending compressed msg {msg_num + 1} of {max_msg} with {end-start} bytes.")
            cmd = hdr if msg_num == 0 else CmdHelper.compose_cmd(Cmd.SEND_COMPRESSED_OVERLAY)
            data = cmd + overlay.compressed_bytes[start:end]
            start = end
            end = min(end + OverlayData.MAX_DATA_PER_MSG, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                return False, f"Error sending overlay message {msg_num + 1}/{overlay.compressed_msgs} ({msg})"
        if lock:
            lock.release()
        #self.log.info(f"Keycode {keycode}: Sent {max_msg} compressed msgs")
        return overlay.compressed_msgs

    def execute_commands(self, command_list):
        """Execute a list of commands"""
        for cmd_str in command_list:
            cmd_str = cmd_str.strip()
            end = cmd_str.find(" ")
            cmd = cmd_str[:end] if end != -1 else cmd_str
            try:
                match cmd:
                    case "wait":
                        time.sleep(float(cmd_str[end + 1 :]))
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
                                self.send_overlays(params[end + 1:], True)
                            case "reset":
                                self.reset_overlays()
                            case _:
                                self.log.warning(f"Unknown overlay command '{cmd}' from '{cmd_str}'")
                    case _:
                        self.log.warning(f"Unknown command '{cmd_str}'")
            except Exception as e:
                self.log.error(f"Couldn't not execute '{cmd_str}': {e}")
