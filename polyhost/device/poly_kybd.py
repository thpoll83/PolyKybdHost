import array
import logging
import math
import re
import time
from typing import Any

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.serial_helper import SerialHelper
from polyhost.input.unicode_input import InputMethod
from polyhost.settings import PolySettings
from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.bit_packing import pack_dict_10_bit
from polyhost.device.cmd_composer import compose_cmd, compose_request, expect, compose_cmd_str, compose_roi_header, expectReq
from polyhost.device.command_ids import Cmd, HidId
from polyhost.device.hid_helper import HidHelper
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.services import iso_lang_country

# Firmware PROTOCOL_VERSION at which GET_LANG_LIST_PACKED (the compact 2-byte
# index encoding of the language list) became available. Older firmware (or
# firmware that reports no protocol version) only understands the ASCII
# GET_LANG_LIST, so the host stays on that path and never probes the new command.
PACKED_LANG_LIST_MIN_PROTOCOL = 2

import hid

from polyhost.util.dict_util import split_dict


class PolyKybd:
    """
    Communication to PolyKybd
    """

    def __init__(self, settings: DeviceSettings, poly_settings: PolySettings):
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
        self.protocol_version = None
        self.device_settings = settings
        self.poly_settings = poly_settings
        self.num_layers = None

        self._fresh_boot = False

        # Statistics
        self.stat_plain = 0
        self.stat_comp = 0
        self.stat_roi = 0  # region of interest
        self.stat_croi = 0  # compressed region of interest
        self.stat_best = 0

    def _open_interfaces(self) -> bool:
        """(Re-)open the HID and serial interfaces.

        Returns True on success. On failure both handles are reset to None so
        the device is left in a clean, fully-disconnected state and the next
        reconnect attempt starts from scratch. HidHelper re-raises
        hid.HIDException when the device shows up in enumeration but can't be
        opened yet — a race that happens while the firmware comes back up after
        a flash — so this must never propagate out of connect()."""
        try:
            self.hid = HidHelper(self.device_settings)
            self.serial = SerialHelper(self.device_settings)
            return True
        except Exception as e:
            self.log.warning("Failed to open HID device: %s", e)
            self.hid = None
            self.serial = None
            return False

    def connect(self):
        """Connect to PolyKybd"""
        if not self.hid:
            self.log.debug("Connecting to PolyKybd for the first time...")
            return self._open_interfaces()
        else:
            retries = self.poly_settings.get("hid_reconnect_retries")
            for attempt in range(retries):
                result, msg = self.query_id()
                if result:
                    return True
                self.log.warning("ID query failed (attempt %d/%d): %s", attempt + 1, retries, msg if msg else "EMPTY REPLY")
            # All retries exhausted — HID handle is stale after a reset/reflash;
            # re-enumerate so the new USB path is picked up.
            self.log.warning("Re-enumerating HID after %d failed attempts...", retries)
            if not self._open_interfaces():
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
                compose_cmd(Cmd.GET_ID), 50, expect(Cmd.GET_ID))
            msg = msg.decode().strip('\x00')
            if not result:
                return False, msg
            if len(msg) > 2 and msg[2] == '*':
                self._fresh_boot = True
            return True, msg[3:]
        except Exception as e:
            return False, f"Exception: {e}"

    def pop_fresh_boot(self) -> bool:
        """Returns True (and clears the flag) if firmware signalled a fresh boot via GET_ID."""
        result = self._fresh_boot
        self._fresh_boot = False
        return result

    def query_version_info(self) -> tuple[bool, str]:
        result, msg = self.query_id()
        if not result:
            return False, msg
        try:
            match = re.search(
                r"(?P<name>.+)\W(?P<sw>\d+\.\d+\.\d+)\W(P(?P<proto>\d+)\W)?HW(?P<hw>\w*)", msg)
            if match:
                self.name = match.group("name")
                self.sw_version = match.group("sw")
                self.sw_version_num = [int(x)
                                       for x in self.sw_version.split(".")]
                self.protocol_version = int(match.group("proto")) if match.group("proto") else None
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

    def get_protocol_version(self) -> int | None:
        """Return the protocol version reported by the firmware, or None for old firmware."""
        return self.protocol_version

    def reset_overlay_mapping(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlay Mapping...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x80))

    def set_all_overlay_usage(self) -> tuple[bool, Any]:
        self.log.info("Set All Overlay Usage...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x02))

    def set_mirror_overlays(self, enable: bool) -> tuple[bool, Any]:
        """Toggle the firmware's MIRROR_OVERLAYS state flag (bit 2 = 0x04).

        With it on, every overlay upload is stored on both halves regardless
        of the upload's keycode side — required for MRU mappings that can
        redirect a display position on either half to any pool slot. With it
        off, uploads use the legacy side-conditional storage path (image goes
        only to the half whose matrix the upload's keycode resides on).
        """
        cmd = Cmd.OVERLAY_FLAGS_ON if enable else Cmd.OVERLAY_FLAGS_OFF
        self.log.info("Mirror Overlays: %s", enable)
        return self.hid.send_and_read_validate(compose_cmd(cmd, 0x04))

    def reset_overlays_and_usage(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlays AND Usage...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x60))

    def reset_overlay_mapping_and_usage(self) -> tuple[bool, Any]:
        """Reset overlay_map[] to identity AND clear all use_overlay[] bits in
        one HID command (MAPPING_RESET | USAGE_RESET). Bitmaps in overlays[]
        are preserved — required when an MRU send needs to invalidate stale
        from→to redirects from a previous program without losing cached data."""
        self.log.info("Reset Overlay Mapping AND Usage...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x80 | 0x40))

    def prepare_for_mru_send(self) -> tuple[bool, Any]:
        """One HID command that sets MIRROR_OVERLAYS and resets the mapping
        table to identity AND clears all use_overlay[] bits — i.e. the union
        of set_mirror_overlays(True) + reset_overlay_mapping_and_usage().
        Combines two HID round-trips (and two slave force-syncs) into one,
        which is what every send_overlays_mru wants at its start."""
        self.log.info("Prepare for MRU send (mirror + reset mapping/usage)...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x04 | 0x80 | 0x40))

    def reset_overlay_usage(self) -> tuple[bool, Any]:
        self.log.info("Clear Overlay Usage...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x40))

    def reset_overlays(self) -> tuple[bool, Any]:
        self.log.info("Reset Overlays...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x20))

    def enable_overlays(self) -> tuple[bool, Any]:
        self.log.info("Enable Overlays...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_ON, 0x01))

    def disable_overlays(self) -> tuple[bool, Any]:
        self.log.info("Disable Overlays...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.OVERLAY_FLAGS_OFF, 0x01))

    def set_unicode_mode(self, mode: InputMethod) -> tuple[bool, Any]:
        self.log.info("Setting unicode mode to %d", mode.value)
        return self.hid.send_and_read_validate(compose_cmd(Cmd.SET_UNICODE_MODE, mode.value))

    def set_brightness(self, brightness: int) -> tuple[bool, Any]:
        self.log.info("Setting Display Brightness to %d...", brightness)
        return self.hid.send_and_read_validate(compose_cmd(Cmd.SET_BRIGHTNESS, int(np.clip(brightness, 0, 50))))

    def press_and_release_key(self, keycode: int, duration: int) -> tuple[bool, Any]:
        self.log.info("Pressing 0x%2x for %f sec...", keycode, duration)
        result, reply = self.hid.send(compose_cmd(
            Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))
        if result:
            # for now, it is fine to block this thread
            time.sleep(duration)
            return self.hid.send_and_read_validate(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))
        else:
            return result, reply

    def press_key(self, keycode: int) -> tuple[bool, Any]:
        self.log.info("Pressing 0x%2x...", keycode)
        return self.hid.send_and_read_validate(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 0))

    def release_key(self, keycode: int) -> tuple[bool, Any]:
        self.log.info("Releasing 0x%2x...", keycode)
        return self.hid.send_and_read_validate(compose_cmd(Cmd.KEYPRESS, keycode >> 8, keycode & 255, 1))

    def activate_bootloader(self) -> tuple[bool, Any]:
        self.log.info("Requesting bootloader mode...")
        # The keyboard jumps to its bootloader as soon as it receives this command
        # and resets without sending a reply, so we only send — there is no ACK to
        # wait for (doing so would just time out against the disconnected device).
        return self.hid.send(compose_cmd(Cmd.ENTER_BOOTLOADER))

    def set_idle(self, idle: bool) -> tuple[bool, Any]:
        self.log.debug("Setting idle state to %s...",
                       "True" if idle else "False")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.IDLE_STATE, 1 if idle else 0))

    def save_mru(self) -> tuple[bool, Any]:
        """Ask the keyboard to persist its emoji/language MRU recents to EEPROM.

        The firmware only writes when the lists actually changed, so this is
        cheap to send on system suspend/shutdown. The keyboard also saves the
        MRU autonomously on USB suspend; this is the host-driven "do both" path
        for clean shutdowns where USB suspend may not fire."""
        self.log.debug("Requesting MRU save...")
        return self.hid.send_and_read_validate(compose_cmd(Cmd.SAVE_MRU))

    def set_handedness(self, master_is_left: bool) -> tuple[bool, Any]:
        """Fix which half is the left side and which is the right side.

        Master/slave is decided by which half holds the USB cable (VBUS), and is
        independent of left/right (handedness lives in each half's EEPROM via
        EE_HANDS). A HID command only reaches the master (USB) half, so the
        assignment is expressed relative to it:

          master_is_left=True  -> the connected (master) half = LEFT,  other = RIGHT
          master_is_left=False -> the connected (master) half = RIGHT, other = LEFT

        The master persists its handedness, pushes the opposite to the slave over
        the split link, then both halves reboot onto the corrected assignment
        (about 10 s, no replug needed). The keyboard resets right after receiving
        this command and does not send a reliable reply, so we only send (like
        activate_bootloader) — there is no ACK to wait for.
        """
        self.log.info("Setting handedness: connected half = %s.",
                      "LEFT" if master_is_left else "RIGHT")
        return self.hid.send(compose_cmd(Cmd.SET_HANDEDNESS, 0 if master_is_left else 1))

    def query_current_lang(self) -> tuple[bool, str]:
        """Query current keyboard language"""

        try:
            result, msg = self.hid.send_and_read_validate(
                compose_cmd(Cmd.GET_LANG), 50, expect(Cmd.GET_LANG))
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

        # Firmware new enough for the compact 2-byte-per-language encoding sends
        # it via GET_LANG_LIST_PACKED. Fall back to the ASCII list if that fails.
        if (self.protocol_version is not None
                and self.protocol_version >= PACKED_LANG_LIST_MIN_PROTOCOL):
            ok, value = self._enumerate_lang_packed()
            if ok:
                return ok, value
            self.log.warning(
                "Packed language list failed, falling back to ASCII list.")
        return self._enumerate_lang_ascii()

    def _enumerate_lang_packed(self) -> tuple[bool, str]:
        """Read the language list as packed (lang_idx, country_idx) byte pairs.

        Wire format mirrors the ASCII list: every HID report is prefixed with the
        "P<cmd>." response header; the payload across reports is a count byte
        followed by two index bytes per language. The count makes the total length
        known after the first report, so termination is deterministic (no reliance
        on a read timeout). Payload is binary, so it must not be decoded/stripped.
        """
        lock = None
        result, reply, lock = self.hid.send_and_read_validate_with_lock(
            compose_cmd(Cmd.GET_LANG_LIST_PACKED), 15,
            expect(Cmd.GET_LANG_LIST_PACKED), lock)
        # reply[2] is the ACK ('.') / NACK ('!') marker; anything else => unsupported.
        if not result or len(reply) < 4 or reply[2] != ord('.'):
            if lock:
                lock.release()
            return False, "Could not receive packed language list."

        data = bytearray(reply[3:])
        total = 1 + 2 * data[0]  # count byte + 2 bytes per language
        while len(data) < total and result:
            result, reply, lock = self.hid.read_with_lock(15, lock)
            data += reply[3:]
        if lock:
            lock.release()

        if len(data) < total:
            return False, "Truncated packed language list."
        try:
            self.all_languages = iso_lang_country.decode_packed(data[:total])
        except (KeyError, IndexError) as e:
            return False, f"Could not decode packed language list: {e}"
        return True, "".join(self.all_languages)

    def _enumerate_lang_ascii(self) -> tuple[bool, str]:
        lock = None
        result, reply, lock = self.hid.send_and_read_validate_with_lock(
            compose_cmd(Cmd.GET_LANG_LIST), 15, expect(Cmd.GET_LANG_LIST), lock)

        if not result:
            if lock:
                lock.release()
            return False, "Could not receive language list."
        lang_str = ""

        expected = expect(Cmd.GET_LANG_LIST).decode()
        reply = reply.decode().strip('\x00')
        while result and len(reply) > 3:
            if not reply.startswith(expected):
                self.log.warning("enumerate_lang: unexpected reply prefix, stopping early")
                break
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

    def send_overlay_mapping(self, from_to: dict) -> tuple[bool, str]:
        chunk_size = int(self.device_settings.OVERLAY_MAPPING_INDICES_PER_REPORT / 2)
        split_per_msg = split_dict(from_to, chunk_size)

        cmd = compose_cmd(Cmd.SEND_OVERLAY_MAPPING)
        lock = None
        num_msgs = 0
        for dict_part in split_per_msg:
            # Pad to chunk_size so every HID message carries exactly chunk_size pairs.
            # The firmware ignores pairs where from >= OVERLAY_MAP_IDX_CNT (810),
            # preventing zero-padded bytes in the buffer from overwriting mapping[0].
            padded = dict(dict_part)
            noop_key = 810
            while len(padded) < chunk_size:
                padded[noop_key] = 810
                noop_key += 1
            msg = cmd + pack_dict_10_bit(padded)
            result, msg, lock = self.hid.send_multiple(msg, lock)
            num_msgs += 1
            if not result:
                return False, f"Error sending overlay mapping: {msg}"
            self.log.debug("send_overlay_mapping: Sent %s", dict_part)
            
        self.log.info("send_overlay_mapping: Sent %d mapping messages", num_msgs)
        # SEND_OVERLAY_MAPPING (cmd 21) is the only overlay-related command that
        # produces a firmware ACK per chunk; drain them now so they don't
        # accumulate and confuse later send_and_read_validate calls.
        _, drained, _, lock = self.hid.drain_read_buffer(num_msgs, lock, timeout=20)
        self.log.debug("send_overlay_mapping: Drained %d of %d HID ACKs", drained, num_msgs)

        if lock:
            lock.release()
        return True, "Mapping sent"

    def send_overlays(self, filenames: list) -> bool:
        overlay_counter = 0
        hid_msg_counter = 0
        hid_msg_counter_old = 0
        enabled = False
        
        MAX_MSG_BEFORE_DELAY = self.poly_settings.get("max_hid_message_before_delay")
        DELAY_TIME_AFTER_MAX_MSG = self.poly_settings.get("delay_time_after_max_hid_messages")

        all_keys = ""
        num_keys = 0
        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            delta = time.perf_counter()
            converter = ImageConverter(self.device_settings)
            if self.log.isEnabledFor(logging.DEBUG):
                delta = time.perf_counter() - delta
                self.log.debug("Converted in '%f' msec", delta*1000)
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
                    
                    if hid_msg_counter_old < hid_msg_counter-MAX_MSG_BEFORE_DELAY:
                        hid_msg_counter_old = hid_msg_counter
                        time.sleep(DELAY_TIME_AFTER_MAX_MSG)
                        self.log.debug_detailed("Waiting before sending more overlays")

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
        end = self.device_settings.MAX_PAYLOAD_BYTES_PER_REPORT - \
            self.device_settings.OVERLAY_CMD_BYTES_ROI_ONCE
        for msg_num in range(0, num_msgs):
            cmd = hdr if msg_num == 0 else compose_cmd(Cmd.SEND_ROI_OVERLAY)
            data = cmd + buffer[start:end]
            start = end
            end = min(end + self.device_settings.MAX_PAYLOAD_BYTES_PER_REPORT, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                self.log.error(
                    "Error sending roi overlay message %d/%d (%s)", msg_num+1, msg_num, msg)
                return num_msgs

        if lock:
            lock.release()
        return num_msgs

    def send_overlay_for_keycode(self, keycode: int, modifier: Modifier, mapping: dict, skip_empty: bool = True) -> int:
        lock = None
        overlay = mapping[keycode]
        msg_cnt = 0
        max_msgs = self.device_settings.OVERLAY_PLAIN_DATA_REPORT_COUNT
        for msg_num in range(0, max_msgs):
            cmd = compose_cmd(Cmd.SEND_OVERLAY, keycode,
                              modifier.value, msg_num)
            from_idx = msg_num * self.device_settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            to_idx = from_idx + self.device_settings.OVERLAY_PLAIN_DATA_BYTES_PER_REPORT
            data = overlay.all_bytes[from_idx:to_idx]
            if skip_empty and msg_num+1 != max_msgs and all(b == 0 for b in data):
                continue
            result, msg, lock = self.hid.send_multiple(cmd + data, lock)
            if not result:
                self.log.error(
                    "Error sending plain overlay message %d/%d (%s)", msg_num + 1, msg_num, msg)
                return msg_cnt
            msg_cnt += 1

        if lock:
            lock.release()
        return msg_cnt

    def send_overlay_for_keycode_compressed(self, keycode: int, modifier: Modifier, mapping: dict) -> int:
        lock = None
        overlay = mapping[keycode]
        hdr = compose_cmd(Cmd.START_COMPRESSED_OVERLAY,
                          keycode, modifier.value)
        num_bytes = len(overlay.compressed_bytes)
        start = 0
        end = self.device_settings.MAX_PAYLOAD_BYTES_PER_REPORT - \
            self.device_settings.OVERLAY_CMD_BYTES_COMPRESSED_ONCE
        for msg_num in range(0, overlay.compressed_msgs):
            cmd = hdr if msg_num == 0 else compose_cmd(
                Cmd.SEND_COMPRESSED_OVERLAY)
            data = cmd + overlay.compressed_bytes[start:end]
            start = end
            end = min(end + self.device_settings.MAX_PAYLOAD_BYTES_PER_REPORT, num_bytes)
            result, msg, lock = self.hid.send_multiple(data, lock)
            if not result:
                self.log.error(
                    "Error sending compressed overlay message %d/%d (%s)", msg_num + 1, msg_num, msg)
                return msg_num

        if lock:
            lock.release()
        return overlay.compressed_msgs

    def send_overlays_mru(self, filenames: list, cache: OverlayMRUCache) -> bool:
        """
        Send only overlay images not already in the keyboard's MRU pool, then
        update the display-position → pool-slot mapping in one command.
        Does NOT call reset_overlays_and_usage (cached images must be preserved).
        """
        import os
        hid_msg_counter = 0
        hid_msg_counter_old = 0
        MAX_MSG_BEFORE_DELAY = self.poly_settings.get("max_hid_message_before_delay")
        DELAY_TIME_AFTER_MAX_MSG = self.poly_settings.get("delay_time_after_max_hid_messages")

        display_to_pool: dict[int, int] = {}

        self.prepare_for_mru_send()

        with cache.batch():
            for filename in filenames:
                self.log.info("Send Overlay MRU '%s'...", filename)
                converter = ImageConverter(self.device_settings)
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
                            self.log.debug_detailed(
                                "MRU miss: sending 0x%x/%s to pool slot %d (addr 0x%x/%s)",
                                keycode, modifier, pool_slot, pool_kc, pool_mod)
                            hid_msg_counter += self.send_smallest_overlay(
                                pool_kc, pool_mod, {pool_kc: overlay_data})
                        else:
                            self.log.debug_detailed(
                                "MRU hit: 0x%x/%s already in pool slot %d", keycode, modifier, pool_slot)

                        display_idx = cache.display_flat_idx(keycode, modifier)
                        display_to_pool[display_idx] = pool_slot

                        if hid_msg_counter_old < hid_msg_counter - MAX_MSG_BEFORE_DELAY:
                            hid_msg_counter_old = hid_msg_counter
                            time.sleep(DELAY_TIME_AFTER_MAX_MSG)

        self.log.info("MRU: %d HID image messages, %d display positions mapped",
                      hid_msg_counter, len(display_to_pool))

        ok, msg = self.send_overlay_mapping(display_to_pool)
        if not ok:
            self.log.warning("send_overlays_mru: mapping failed: %s", msg)
            return False
        cache.record_transferred_mapping(display_to_pool)
        self.enable_overlays()
        return True

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
                                self.send_overlays([params[end + 1:]])
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

    def get_default_layer(self) -> tuple[bool, int]:
        try:
            result, reply = self.hid.send_and_read_validate(
                compose_cmd(Cmd.GET_DEFAULT_LAYER), 15, expect(Cmd.GET_DEFAULT_LAYER))
            if result and len(reply) > 3 and reply[2:3] == b'.':
                return True, reply[3]
        except Exception:
            pass
        return False, 0

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

    def set_dynamic_keycode(self, layer: int, row: int, col: int, keycode: int) -> tuple[bool, Any]:
        req = HidId.ID_DYNAMIC_KEYMAP_SET_KEYCODE
        result, reply = self.hid.send_and_read_validate(
            compose_request(req, layer, row, col, keycode >> 8, keycode & 0xFF),
            50, expectReq(req))
        return result, reply

    def get_dynamic_buffer(self) -> tuple[bool, list[int] | None]:
        if self.num_layers is None:
            success, _ = self.get_dynamic_layer_count()
            if not success:
                return False, None

        size = self.device_settings.HID_REPORT_SIZE - 4  # compose request adds 4 bytes
        req = HidId.ID_DYNAMIC_KEYMAP_GET_BUFFER
        max_bytes = self.device_settings.MATRIX_COLUMNS * self.device_settings.MATRIX_ROWS * \
            self.num_layers * 2  # 2 bytes per keycode
        if max_bytes % size != 0:
            max_bytes = math.ceil(max_bytes/size)*size

        buffer = bytearray()
        for offset in range(0, max_bytes, size):
            success, reply = self.hid.send_and_read_validate(
                compose_request(req, offset >> 8, offset & 0xff, size), 50, expectReq(req))
            if not success:
                arr = array.array('H')
                arr.frombytes(buffer)
                arr.byteswap()
                return False, arr
            buffer.extend(reply[4:4+size])

        arr = array.array('H')
        arr.frombytes(buffer)
        arr.byteswap()
        return True, arr.tolist()
