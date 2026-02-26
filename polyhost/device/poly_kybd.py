import logging
import math
import re
import time
from enum import Enum
from typing import Any

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.serial_helper import SerialHelper
from polyhost.input.unicode_input import InputMethod
from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.bit_packing import pack_dict_10_bit
from polyhost.device.cmd_composer import compose_cmd, compose_request, expect, compose_cmd_str, compose_roi_header, expectReq
from polyhost.device.command_ids import Cmd, HidId
from polyhost.device.hid_helper import HidHelper
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier

import hid

from polyhost.util.dict_util import split_dict


class MaskFlag(Enum):
    LEFT_TOP = 2
    LEFT_BOTTOM = 4
    RIGHT_TOP = 8
    RIGHT_BOTTOM = 16


class PolyKybd:
    """
    Communication to PolyKybd
    """

    def __init__(self, settings: DeviceSettings):
        self.log = logging.getLogger('PolyHost')
        self.console_buffer = ""
        self.all_languages = list()
        self.current_lang = None
        self.hid = None
        self.serial = None
        self.name = None
        self.sw_version = None
        self.sw_version_num = None
        self.hw_version = None
        self.settings = settings
        self.num_layers = None

        # Statistics
        self.stat_plain = 0
        self.stat_comp = 0
        self.stat_roi = 0  # region of interest
        self.stat_croi = 0  # compressed region of interest
        self.stat_best = 0

    def connect(self):
        """Connect to PolyKybd"""
        # Connect to Keeb
        if not self.hid:
            self.hid = HidHelper(self.settings)
            self.serial = SerialHelper(self.settings)
        else:
            result, msg = self.query_id()
            if not result:
                self.log.debug("Reconnecting to PolyKybd... (%s)", msg)
                try:
                    self.hid = HidHelper(self.settings)
                except hid.HIDException as e:
                    self.log.warning("Could not reconnect: %s", e)
                    return False
                except ValueError as e:
                    self.log.warning("Problem with provided values: %s", e)
                    return False
        return self.hid.interface_acquired()

    def read_serial(self):
        if self.serial:
            return self.serial.read_all()
        return None

    def get_console_output(self, flush_and_return=True) -> str | None:
        try:
            last_line = self.hid.get_console_output()
            while len(last_line) > 0:
                self.console_buffer += last_line.decode().strip('\x00')
                last_line = self.hid.get_console_output()
        except Exception as e:
            return str(e)

        if flush_and_return:
            console_out = self.console_buffer
            self.console_buffer = ""
            return console_out
        return None

    def query_id(self) -> tuple[bool, str]:
        try:
            result, msg = self.hid.send_and_read_validate(
                compose_cmd(Cmd.GET_ID), 15, expect(Cmd.GET_ID))
            msg = msg.decode().strip('\x00')
            return result, msg if not result else msg[3:]
        except Exception as e:
            return False, f"Exception: {e}"

    def query_version_info(self) -> tuple[bool, str]:
        result, msg = self.query_id()
        if not result:
            return False, msg
        try:
            match = re.search(
                r"(?P<name>.+)\W(?P<sw>\d\.\d\.\d)\WHW(?P<hw>\w*)", msg)
            if match:
                self.name = match.group("name")
                self.sw_version = match.group("sw")
                self.sw_version_num = [int(x)
                                       for x in self.sw_version.split(".")]
                self.hw_version = match.group("hw")
                return True, msg
            else:
                self.log.warning("Could not match version string: %s", msg)
                return False, "Could not match version string. Please update firmware."
        except Exception as e:
            self.log.warning(
                "Exception matching version string '%s':\n%s", msg, e)
            return False, "Could not match version string. Please update firmware."

    def get_name(self) -> str:
        return self.name

    def get_sw_version(self) -> str:
        return self.sw_version

    def get_sw_version_number(self) -> str:
        """Get the software version number in as 3 ints: major, minor, patch"""
        return self.sw_version_num

    def get_hw_version(self) -> str:
        return self.hw_version

    def reset_overlay_mapping(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlay Mapping...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x80))

    def reset_overlays_and_usage(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlays AND Usage...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x60))

    def reset_overlay_usage(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlay Usage...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x40))

    def reset_overlays(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x20))

    def enable_overlays(self) -> tuple[bool, Any]:
        self.log.info("Enable Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x01))

    def disable_overlays(self) -> tuple[bool, Any]:
        self.log.info("Disable Overlays...")
        return self.hid.send(compose_cmd(Cmd.OVERLAY_FLAGS_OFF, 0x01))

    def set_unicode_mode(self, mode: InputMethod) -> tuple[bool, Any]:
        self.log.info("Setting unicode mode to %d", mode.value)
        return self.hid.send(compose_cmd(Cmd.SET_UNICODE_MODE, mode.value))

    def set_brightness(self, brightness: int) -> tuple[bool, Any]:
        self.log.info("Setting Display Brightness to %d...", brightness)
        return self.hid.send(compose_cmd(Cmd.SET_BRIGHTNESS, int(np.clip(brightness, 0, 50))))

    def press_and_release_key(self, keycode: int, duration: int) -> tuple[bool, Any]:
        self.log.info("Pressing 0x%2x for %f sec...", keycode, duration)
        result, reply = self.hid.send(compose_cmd(
            Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))
        if result:
            # for now, it is fine to block this thread
            time.sleep(duration)
            return self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))
        else:
            return result, reply

    def press_key(self, keycode: int) -> tuple[bool, Any]:
        self.log.info("Pressing 0x%2x...", keycode)
        return self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))

    def release_key(self, keycode: int) -> tuple[bool, Any]:
        self.log.info("Releasing 0x%2x...", keycode)
        return self.hid.send(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))

    def set_idle(self, idle: bool) -> tuple[bool, Any]:
        self.log.debug("Setting idle state to %s...",
                       "True" if idle else "False")
        return self.hid.send(compose_cmd(Cmd.IDLE_STATE, 1 if idle else 0))

    def query_current_lang(self) -> tuple[bool, str]:
        """Query current keyboard language"""

        try:
            result, msg = self.hid.send_and_read_validate(
                compose_cmd(Cmd.GET_LANG), 15, expect(Cmd.GET_LANG))
            if result:
                msg = msg.decode().strip('\x00')
                self.current_lang = msg[3:]
                return True, self.current_lang
            else:
                return False, "Could not read reply from PolyKybd"
        except Exception as e:
            return False, f"Exception: {e}"

    def enumerate_lang(self) -> tuple[bool, str]:
        self.log.debug("Enumerate Languages...")
        result, msg = self.query_current_lang()
        if not result:
            return False, msg

        lock = None
        result, reply, lock = self.hid.send_and_read_validate_with_lock(
            compose_cmd(Cmd.GET_LANG_LIST), 15, expect(Cmd.GET_LANG_LIST), lock)

        if not result:
            return False, "Could not receive language list."
        lang_str = ""

        reply = reply.decode().strip('\x00')
        while result and len(reply) > 3:
            assert reply.startswith(expect(Cmd.GET_LANG_LIST).decode())
            lang_str = f"{lang_str}{reply[3:]}"
            result, reply, lock = self.hid.read_with_lock(15, lock)
            reply = reply.decode().strip('\x00')

        if lock:
            lock.release()

        self.all_languages = split_by_n_chars(lang_str, 4)
        return True, lang_str

    def get_lang_list(self) -> list:
        return self.all_languages

    def get_current_lang(self) -> str:
        return self.current_lang

    def change_language(self, lang: str) -> tuple[bool, str]:
        """
        Send command to change the language to the specified index
        :param lang: 4 letter str which must be in the list of languages.
        :return:
            - result (:py:class:`bool`) True on successful language change.
            - lang_code (:py:class:`str`) The 4 letter language code as str in use.
        """
        if lang not in self.all_languages:
            return False, f"Language '{lang}' not present on PolyKybd"

        result, msg = self.hid.send_and_read_validate(
            compose_cmd_str(Cmd.CHANGE_LANG, lang), 15, expect(Cmd.CHANGE_LANG))
        msg = msg.decode().strip('\x00')
        if not result:
            return False, f"Could not change to {lang} ({msg})"

        self.log.info("Language changed to %s (%s).", lang, msg)
        return True, lang

    def set_overlay_masking(self, set_all: bool) -> tuple[bool, Any]:
        cmd = Cmd.OVERLAY_FLAGS_ON if set_all else Cmd.OVERLAY_FLAGS_OFF
        return self.hid.send(compose_cmd(cmd, 0x1e))

    def send_overlay_mapping(self, from_to: dict) -> tuple[bool, str]:
        split_per_msg = split_dict(
            from_to, self.settings.OVERLAY_MAPPING_INDICES_PER_REPORT/2)

        cmd = compose_cmd(Cmd.SEND_OVERLAY_MAPPING)
        lock = None
        num_msgs = 0
        for dict_part in split_per_msg:
            msg = cmd + pack_dict_10_bit(dict_part)
            result, msg, lock = self.hid.send_multiple(msg, lock)
            num_msgs += 1
            if not result:
                return False, f"Error sending overlay mapping: {msg}"
            self.log.debug("send_overlay_mapping: Sent %s", dict_part)

        # _, drained, _, lock = self.hid.drain_read_buffer(num_msgs, lock)
        # self.log.debug_detailed(
        #     "send_overlay_mapping: Drained %d HID reports", drained)

        if lock:
            lock.release()
        return True, "Mapping sent"

    def send_overlays(self, filenames: list) -> bool:
        overlay_counter = 0
        hid_msg_counter = 0
        enabled = False

        all_keys = ""
        num_keys = 0
        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            delta = time.perf_counter()
            converter = ImageConverter(self.settings)
            if self.log.isEnabledFor(logging.DEBUG):
                delta = time.perf_counter() - delta
                self.log.debug("Converted in '%f' msec", delta*1000)
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
                    self.log.debug_detailed(
                        "Sending overlays for modifier %s.", modifier)
                    all_keys += f"\n(Mod: {modifier}/{modifier.value} {overlay_map.keys()})"
                    num_keys += len(overlay_map)

                    # Send ESC first
                    if not enabled and modifier == Modifier.NO_MOD:
                        if KeyCode.KC_ESCAPE.value in overlay_map.keys():
                            hid_msg_counter += self.send_smallest_overlay(
                                KeyCode.KC_ESCAPE.value, modifier, overlay_map)
                            overlay_map.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True
                            self.log.debug_detailed("Sending ESC first")

                    for keycode in overlay_map:
                        hid_msg_counter += self.send_smallest_overlay(
                            keycode, modifier, overlay_map)

                    self.log.debug_detailed(
                        "Overlays for keycodes %s have been sent", overlay_map.keys())
                    overlay_counter += 1
                    self.get_console_output(False)
                    
                    time.sleep(0.2)

        self.log.info("%d overlays sent, %d hid messages for %d keys:%s",
                      overlay_counter, hid_msg_counter, num_keys, all_keys)
        if not enabled:
            self.enable_overlays()
        return True

    def send_smallest_overlay(self, keycode: int, modifier: Modifier, mapping: dict) -> int:
        ov = mapping[keycode]
        smallest = min(ov.all_msgs, ov.compressed_msgs,
                       ov.roi_msgs, ov.compressed_roi_msgs)

        if smallest == ov.roi_msgs:
            self.log.debug_detailed(
                "send_smallest_overlay: Sending keycode 0x%x (mod 0x%x) as uncompressed ROI", keycode, modifier.value)
            return self.send_overlay_roi_for_keycode(keycode, modifier, mapping, False)
        elif smallest == ov.compressed_msgs:
            self.log.debug_detailed(
                "send_smallest_overlay: Sending keycode 0x%x (mod 0x%x) as compressed overlay", keycode, modifier.value)
            return self.send_overlay_for_keycode_compressed(keycode, modifier, mapping)
        elif smallest == ov.compressed_roi_msgs:
            self.log.debug_detailed(
                "send_smallest_overlay: Sending keycode 0x%x (mod 0x%x) as compressed ROI", keycode, modifier.value)
            return self.send_overlay_roi_for_keycode(keycode, modifier, mapping, True)
        else:
            self.log.debug_detailed(
                "send_smallest_overlay: Sending keycode 0x%x (mod 0x%x) as plain overlay", keycode, modifier.value)
            return self.send_overlay_for_keycode(keycode, modifier, mapping)

    def send_overlay_roi_for_keycode(self, keycode: int, modifier: Modifier, mapping: dict, compressed: bool) -> int:
        overlay = mapping[keycode]
        if not overlay.roi:
            return self.send_overlay_for_keycode_compressed(keycode, modifier, mapping)

        hdr = compose_roi_header(
            Cmd.START_ROI_OVERLAY, keycode, modifier, overlay, compressed)
        lock = None
        buffer = overlay.compressed_roi_bytes if compressed else overlay.roi_bytes
        num_msgs = overlay.compressed_roi_msgs if compressed else overlay.roi_msgs
        num_bytes = len(buffer)
        start = 0
        end = self.settings.MAX_PAYLOAD_BYTES_PER_REPORT - \
            self.settings.OVERLAY_CMD_BYTES_ROI_ONCE
        for msg_num in range(0, num_msgs):
            # self.log.info(f"Sending roi overlay msg {msg_num + 1} of {overlay.roi_msg_msgs} with {end-start} bytes.")
            cmd = hdr if msg_num == 0 else compose_cmd(Cmd.SEND_ROI_OVERLAY)
            data = cmd + buffer[start:end]
            start = end
            end = min(end + self.settings.MAX_PAYLOAD_BYTES_PER_REPORT, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                self.log.error(
                    "Error sending roi overlay message %d/%d (%s)", msg_num+1, msg_num, msg)
                return num_msgs

        # _, drained, _, lock = self.hid.drain_read_buffer(num_msgs, lock)
        # self.log.debug_detailed(
        #     "send_overlay_roi_for_keycode: Drained %d of %d HID reports (compressed %s)", drained, num_msgs, str(compressed))

        if lock:
            lock.release()
        return num_msgs

    def send_overlay_for_keycode(self, keycode: int, modifier: Modifier, mapping: dict, skip_empty: bool = True) -> int:
        lock = None
        overlay = mapping[keycode]
        msg_cnt = 0
        max_msgs = self.settings.OVERLAY_PLAIN_DATA_REPORT_COUNT
        for msg_num in range(0, max_msgs):
            # self.log.debug("Sending msg %d of %d", msg_num + 1, max_msgs)
            cmd = compose_cmd(Cmd.SEND_OVERLAY, keycode,
                              modifier.value, msg_num)
            from_idx = msg_num * self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            to_idx = from_idx + self.settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            data = overlay.all_bytes[from_idx:to_idx]
            if skip_empty and msg_num+1 != max_msgs and all(b == 0 for b in data):
                # self.log.debug("Skipping msg %d as all bytes are 0", msg_num + 1)
                continue
            result, msg, lock = self.hid.send_multiple(cmd + data, lock)
            if not result:
                self.log.error(
                    "Error sending plain overlay message %d/%d (%s)", msg_num + 1, msg_num, msg)
                return msg_cnt
            msg_cnt += 1

        # _, drained, _, lock = self.hid.drain_read_buffer(max_msgs, lock)
        # self.log.debug_detailed(
        #     "send_overlay_for_keycode: Drained %d of %d HID reports", drained, max_msgs)

        if lock:
            lock.release()
        # self.log.info(f"Keycode {keycode}: Sent {msg_cnt} plain msgs")
        return msg_cnt

    def send_overlay_for_keycode_compressed(self, keycode: int, modifier: Modifier, mapping: dict) -> int:
        lock = None
        overlay = mapping[keycode]
        hdr = compose_cmd(Cmd.START_COMPRESSED_OVERLAY,
                          keycode, modifier.value)
        num_bytes = len(overlay.compressed_bytes)
        start = 0
        end = self.settings.MAX_PAYLOAD_BYTES_PER_REPORT - \
            self.settings.OVERLAY_CMD_BYTES_COMPRESSED_ONCE
        for msg_num in range(0, overlay.compressed_msgs):
            # self.log.info(f"Sending compressed msg {msg_num + 1} of {max_msg} with {end-start} bytes.")
            cmd = hdr if msg_num == 0 else compose_cmd(
                Cmd.SEND_COMPRESSED_OVERLAY)
            data = cmd + overlay.compressed_bytes[start:end]
            start = end
            end = min(end + self.settings.MAX_PAYLOAD_BYTES_PER_REPORT, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                self.log.error(
                    "Error sending compressed overlay message %d/%d (%s)", msg_num + 1, msg_num, msg)
                return msg_num

        # _, drained, _, lock = self.hid.drain_read_buffer(
        #     overlay.compressed_msgs, lock)
        # self.log.debug_detailed(
        #     "send_overlay_for_keycode_compressed: Drained %d of %d HID reports", drained, overlay.compressed_msgs)

        if lock:
            lock.release()
        # self.log.info(f"Keycode {keycode}: Sent {max_msg} compressed msgs")
        return overlay.compressed_msgs

    def execute_commands(self, command_list: list) -> None:
        """Execute a list of commands"""
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
                                self.send_overlays(params[end + 1:])
                            case "reset":
                                self.reset_overlays()
                            case "reset-usage":
                                self.reset_overlay_usage()
                            case "reset-mapping":
                                self.reset_overlay_mapping()
                            case _:
                                self.log.warning(
                                    "Unknown overlay command '%s' from '%s'", cmd, cmd_str)
                    case _:
                        self.log.warning("Unknown command '%s'", cmd_str)
            except Exception as e:
                self.log.error("Couldn't not execute '%s': %s", cmd_str, e)

    def get_dynamic_keycode(self, layer: int, row: int, col: int) -> tuple[bool, int | bytearray]:
        req = HidId.ID_DYNAMIC_KEYMAP_GET_KEYCODE
        result, reply = self.hid.send_and_read_validate(
            compose_request(req, layer, row, col), 50, expectReq(req))
        if result:
            return True, int.from_bytes(reply[4:6])
        else:
            return False, reply

    def get_dynamic_layer_count(self) -> tuple[bool, int | bytearray]:
        if self.num_layers is not None:
            return True, self.num_layers

        req = HidId.ID_DYNAMIC_KEYMAP_GET_LAYER_COUNT
        result, reply = self.hid.send_and_read_validate(
            compose_request(req), 50, expectReq(req))
        if result:
            self.num_layers = int.from_bytes(reply[1:2])
            return True, self.num_layers
        else:
            return False, reply

    def reset_dynamic_keymap(self) -> tuple[bool, Any]:
        return self.hid.send(compose_request(HidId.ID_DYNAMIC_KEYMAP_RESET))

    def get_dynamic_buffer(self) -> tuple[bool, bytearray | None]:
        if self.num_layers is None:
            success, _ = self.get_dynamic_layer_count()
            if not success:
                return False, None

        size = self.settings.HID_REPORT_SIZE - 4  # compose request adds 4 bytes
        req = HidId.ID_DYNAMIC_KEYMAP_GET_BUFFER
        max_bytes = self.settings.MATRIX_COLUMNS * self.settings.MATRIX_ROWS * \
            self.num_layers * 2  # 2 bytes per keycode
        if max_bytes % size != 0:
            max_bytes = math.ceil(max_bytes/size)*size

        buffer = bytearray(max_bytes)
        for offset in range(0, max_bytes, size):
            success, reply = self.hid.send_and_read_validate(
                compose_request(req, offset >> 8, offset & 0xff, size), 50, expectReq(req))
            if not success:
                return False, buffer
            buffer.extend(reply[4:4+size])

        return True, buffer

    # class HidId(Enum):
    # ID_GET_PROTOCOL_VERSION = 1
    # ID_GET_KEYBOARD_VALUE = 2
    # ID_SET_KEYBOARD_VALUE = 3
    # ID_DYNAMIC_KEYMAP_GET_KEYCODE = 4
    # ID_DYNAMIC_KEYMAP_SET_KEYCODE = 5
    # ID_DYNAMIC_KEYMAP_RESET = 6
    # ID_CUSTOM_SET_VALUE = 7
    # ID_CUSTOM_GET_VALUE = 8
    # ID_CUSTOM_SAVE = 9
    # ID_EEPROM_RESET = 10
    # ID_BOOTLOADER_JUMP = 11
    # ID_DYNAMIC_KEYMAP_MACRO_GET_COUNT = 12
    # ID_DYNAMIC_KEYMAP_MACRO_GET_BUFFER_SIZE = 13
    # ID_DYNAMIC_KEYMAP_MACRO_GET_BUFFER = 14
    # ID_DYNAMIC_KEYMAP_MACRO_SET_BUFFER = 15
    # ID_DYNAMIC_KEYMAP_MACRO_RESET = 16
    # ID_DYNAMIC_KEYMAP_GET_LAYER_COUNT = 17
    # ID_DYNAMIC_KEYMAP_GET_BUFFER = 18
    # ID_DYNAMIC_KEYMAP_SET_BUFFER = 19
    # ID_DYNAMIC_KEYMAP_GET_ENCODER = 20
    # ID_DYNAMIC_KEYMAP_SET_ENCODER = 21
