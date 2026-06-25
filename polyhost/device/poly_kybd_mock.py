import logging
import os
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np  # for the get_display_image return annotation only

from polyhost.device.device_settings import DeviceSettings
from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_sim import OverlayFirmwareSim, display_flat_idx
from polyhost.input.unicode_input import InputMethod


class PolyKybdMock:
    """
    Software stub for PolyKybd — complete interface without physical hardware.

    Mirrors every public method of PolyKybd and maintains simulated device state.
    Every public method appends an entry to ``self.calls`` as a
    (method_name, args, kwargs) tuple so tests can assert on what was invoked
    and in what order.
    """

    def __init__(self, device_settings: DeviceSettings, poly_settings=None, *,
                 version: str = "1.0.0",
                 lang: str = "enUS",
                 langs: str = "enUSdeATkoKRfrFRitITesES",
                 num_layers: int = 4):
        self.device_settings = device_settings
        self.poly_settings = poly_settings
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

        # Version / identity
        self._name = "PolyKybdMock"
        self._sw_version = version
        self._sw_version_num = [int(x) for x in version.split(".")]
        self._hw_version = version

        # Language state
        self._current_lang = lang
        self._lang_str = langs
        self._all_languages = split_by_n_chars(langs, 4)

        # Device state
        self._brightness: int = 0
        self._overlays_enabled: bool = False
        self._idle: bool = False
        self._unicode_mode: InputMethod | None = None
        self._overlay_masking: bool = False
        self._overlay_mapping: dict = {}
        self._sent_overlays: list[str] = []

        # Dynamic keymap: _keymap[layer][row][col] = keycode (int)
        self._num_layers: int = num_layers
        rows = device_settings.MATRIX_ROWS
        cols = device_settings.MATRIX_COLUMNS
        self._keymap: list[list[list[int]]] = [
            [[0] * cols for _ in range(rows)] for _ in range(num_layers)
        ]

        # Call log for test assertions
        self.calls: list[tuple[str, tuple, dict]] = []

    def _log_call(self, name: str, *args, **kwargs) -> None:
        self.calls.append((name, args, kwargs))

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    def connect(self) -> bool:
        self._log_call("connect")
        return True

    def pop_fresh_boot(self) -> bool:
        self._log_call("pop_fresh_boot")
        return False

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------

    def query_id(self) -> tuple[bool, str]:
        self._log_call("query_id")
        return True, f"{self._name} {self._sw_version} HW0"

    def query_version_info(self) -> tuple[bool, str]:
        self._log_call("query_version_info")
        return True, self._sw_version

    def get_name(self) -> str:
        self._log_call("get_name")
        return self._name

    def get_sw_version(self):
        return self.version

    def get_sw_version_number(self) -> list[int]:
        """Software version as 3 ints: major, minor, patch."""
        self._log_call("get_sw_version_number")
        return self._sw_version_num

    def get_hw_version(self) -> str:
        self._log_call("get_hw_version")
        return self._hw_version

    # -------------------------------------------------------------------------
    # Overlay flags / reset
    # -------------------------------------------------------------------------

    def reset_overlay_mapping(self) -> tuple[bool, str]:
        self._log_call("reset_overlay_mapping")
        self._overlay_mapping = {}
        self.log.info("Reset Overlay Mapping...")
        self._sim.reset_mapping()
        return True, ""

    def set_all_overlay_usage(self):
        self.log.info("Set All Overlay Mapping Usage...")
        self._sim.set_all_usage()
        return True, ""

    def set_mirror_overlays(self, enable):
        # The mock simulator doesn't model split-side storage, so the flag is
        # a no-op functionally — we just log it for parity with the real device.
        self.log.info("Mirror Overlays: %s", enable)
        return True, ""

    def reset_overlays_and_usage(self) -> tuple[bool, str]:
        self._log_call("reset_overlays_and_usage")
        self._sent_overlays = []
        self.log.info("Reset Overlays AND Usage...")
        self._sim.reset_all()
        return True, ""

    def reset_overlay_mapping_and_usage(self):
        self.log.info("Reset Overlay Mapping AND Usage...")
        self._sim.reset_mapping()
        self._sim.reset_usage()
        return True, ""

    def prepare_for_mru_send(self):
        # The simulator doesn't model MIRROR_OVERLAYS at all — its uploads are
        # already side-agnostic — so the mirror part is a logged no-op.
        self.log.info("Prepare for MRU send (mock)...")
        self._sim.reset_mapping()
        self._sim.reset_usage()
        return True, ""

    def reset_overlay_usage(self):
        self._log_call("reset_overlay_usage")
        self.log.info("Clear Overlay Mapping Usage...")
        self._sim.reset_usage()
        return True, ""

    def reset_overlays(self) -> tuple[bool, str]:
        self._log_call("reset_overlays")
        self._sent_overlays = []
        self.log.info("Reset Overlays...")
        self._sim._store.clear()
        return True, ""

    def enable_overlays(self) -> tuple[bool, str]:
        self._log_call("enable_overlays")
        self._overlays_enabled = True
        return True, ""

    def disable_overlays(self) -> tuple[bool, str]:
        self._log_call("disable_overlays")
        self._overlays_enabled = False
        return True, ""

    def set_overlay_masking(self, set_all: bool) -> tuple[bool, str]:
        self._log_call("set_overlay_masking", set_all)
        self._overlay_masking = set_all
        return True, f"{set_all}"

    # -------------------------------------------------------------------------
    # Device settings
    # -------------------------------------------------------------------------

    def set_brightness(self, brightness: int, flags: int = 0) -> tuple[bool, str]:
        self._log_call("set_brightness", brightness, flags)
        max_brightness = getattr(self.device_settings, "MAX_BRIGHTNESS", 50)
        self._brightness = max(0, min(brightness, max_brightness))
        return True, ""

    def set_idle(self, idle: bool) -> tuple[bool, str]:
        self._log_call("set_idle", idle)
        self._idle = idle
        return True, ""

    def set_idle_style(self, style) -> tuple[bool, str]:
        value = getattr(style, "value", style)
        self._log_call("set_idle_style", value)
        self._idle_style = int(value)
        return True, ""

    def get_idle_style(self) -> tuple[bool, int]:
        self._log_call("get_idle_style")
        return True, getattr(self, "_idle_style", 0)

    def set_unicode_mode(self, mode: InputMethod) -> tuple[bool, str]:
        self._log_call("set_unicode_mode", mode)
        self._unicode_mode = mode
        self.log.info("Setting unicode mode to %d", mode.value)
        return True, ""

    def set_os(self, os, pin: bool = False) -> tuple[bool, str]:
        self._log_call("set_os", os, pin)
        self._os = getattr(os, "value", os)
        self._os_pin = pin
        return True, ""

    def get_os(self) -> tuple[bool, int]:
        self._log_call("get_os")
        return True, getattr(self, "_os", 0)

    # -------------------------------------------------------------------------
    # Key press / release
    # -------------------------------------------------------------------------

    def press_and_release_key(self, keycode: int, duration: int,
                              cancel=None) -> tuple[bool, str]:
        self._log_call("press_and_release_key", keycode, duration)
        return True, ""

    def press_key(self, keycode: int) -> tuple[bool, str]:
        self._log_call("press_key", keycode)
        return True, ""

    def release_key(self, keycode: int) -> tuple[bool, str]:
        self._log_call("release_key", keycode)
        return True, ""

    # -------------------------------------------------------------------------
    # Language
    # -------------------------------------------------------------------------

    def query_current_lang(self) -> tuple[bool, str]:
        self._log_call("query_current_lang")
        return True, self._current_lang

    def enumerate_lang(self) -> tuple[bool, str]:
        self._log_call("enumerate_lang")
        return True, self._lang_str

    def get_lang_list(self) -> list[str]:
        self._log_call("get_lang_list")
        return self._all_languages

    def get_current_lang(self) -> str:
        self._log_call("get_current_lang")
        return self._current_lang

    def change_language(self, lang: str) -> tuple[bool, str]:
        self._log_call("change_language", lang)
        if lang not in self._all_languages:
            return False, f"Language '{lang}' not present on PolyKybd"
        self._current_lang = lang
        return True, lang

    def send_overlay_mapping(self, from_to: dict) -> tuple[bool, str]:
        self.hid_mapping_sends += 1
        self.last_mapping = from_to
        self._overlay_mapping.update(from_to)
        self._sim.apply_mapping(from_to)
        return True, "Mapping sent"

    def send_overlay(self, filename, on_off=True):
        self.log.info("Send Overlay '%s'...", filename)
        converter = ImageConverter(self.device_settings)
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

    def send_overlays(self, filenames: list, cancel=None) -> bool:
        self._log_call("send_overlays", filenames)
        if cancel is not None and cancel.is_set():
            return False
        overlay_counter = 0
        hid_msg_counter = 0
        key_counter = 0
        enabled = False

        for filename in filenames:
            self.log.info("Send Overlay '%s'...", filename)
            converter = ImageConverter(self.device_settings)
            if not converter.open(filename):
                self.log.warning("Unable to read %s", filename)
                return False

            for modifier in Modifier:
                overlay_map = converter.extract_overlays(modifier)
                if overlay_map:
                    self.log.info("Sending overlays for modifier %s.", modifier)
                    if not enabled and modifier == Modifier.NO_MOD:
                        if KeyCode.KC_ESCAPE.value in overlay_map.keys():
                            hid_msg_counter += self.send_smallest_overlay(
                                KeyCode.KC_ESCAPE.value, modifier, overlay_map)
                            overlay_map.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True

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
        self._sent_overlays.extend(filenames)
        return True

    def send_overlays_mru(self, filenames: list, cache, cancel=None) -> bool:
        if cancel is not None and cancel.is_set():
            return False
        display_to_pool: dict[int, int] = {}

        # Parity with the real device path; see PolyKybd.send_overlays_mru.
        self.prepare_for_mru_send()

        with cache.batch():
            for filename in filenames:
                self.log.info("Send Overlay MRU (mock) '%s'...", filename)
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
                            self.hid_image_sends += self.send_smallest_overlay(
                                pool_kc, pool_mod, {pool_kc: overlay_data})

                        disp_idx = cache.display_flat_idx(keycode, modifier)
                        display_to_pool[disp_idx] = pool_slot

        # Parity with PolyKybd.send_overlays_mru — clears any upload-time
        # use_overlay contamination before the mapping send establishes the
        # legitimate from-index bits.
        # self.reset_overlay_usage()
        self.send_overlay_mapping(display_to_pool)
        cache.record_transferred_mapping(display_to_pool)
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
        """Return the 72x40 bool numpy array shown at (keycode, modifier), or None."""
        return self._sim.get_display_image(keycode, modifier)

    def save_overlay_as_png(self, keycode: int, modifier: Modifier, path: str) -> bool:
        """Save the overlay at (keycode, modifier) as a PNG file for visual inspection."""
        return self._sim.save_as_png(keycode, modifier, path)

    def read_serial(self):
        self._log_call("read_serial")
        return None

    def get_console_output(self, flush_and_return=True):
        return "" if flush_and_return else None

    def execute_commands(self, command_list, cancel=None):
        for cmd_str in command_list:
            if cancel is not None and cancel.is_set():
                return
            cmd_str = cmd_str.strip()
            end = cmd_str.find(" ")
            cmd = cmd_str[:end] if end != -1 else cmd_str
            try:
                match cmd:
                    case "wait":
                        duration = float(cmd_str[end + 1:])
                        if cancel is not None:
                            cancel.wait(duration)
                        else:
                            time.sleep(duration)
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
                                if cancel is not None:
                                    self.send_overlays([params[end + 1:]], cancel)
                                else:
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

    # -------------------------------------------------------------------------
    # Dynamic keymap
    # -------------------------------------------------------------------------

    def get_default_layer(self) -> tuple[bool, int]:
        self._log_call("get_default_layer")
        return True, 0

    def get_dynamic_layer_count(self) -> tuple[bool, int]:
        self._log_call("get_dynamic_layer_count")
        return True, self._num_layers

    def get_dynamic_keycode(self, layer: int, row: int, col: int) -> tuple[bool, int | None]:
        self._log_call("get_dynamic_keycode", layer, row, col)
        if (layer >= self._num_layers
                or row >= self.device_settings.MATRIX_ROWS
                or col >= self.device_settings.MATRIX_COLUMNS):
            return False, None
        return True, self._keymap[layer][row][col]

    def set_dynamic_keycode(self, layer: int, row: int, col: int, keycode: int) -> tuple[bool, Any]:
        self._log_call("set_dynamic_keycode", layer, row, col, keycode)
        self.log.info("set_dynamic_keycode layer=%d row=%d col=%d keycode=0x%04x",
                      layer, row, col, keycode)
        if (layer >= self._num_layers
                or row >= self.device_settings.MATRIX_ROWS
                or col >= self.device_settings.MATRIX_COLUMNS):
            return False, f"Coordinates ({layer},{row},{col}) out of range"
        self._keymap[layer][row][col] = keycode
        return True, ""

    def reset_dynamic_keymap(self) -> tuple[bool, Any]:
        self._log_call("reset_dynamic_keymap")
        rows = self.device_settings.MATRIX_ROWS
        cols = self.device_settings.MATRIX_COLUMNS
        self._keymap = [
            [[0] * cols for _ in range(rows)] for _ in range(self._num_layers)
        ]
        return True, ""

    def get_dynamic_buffer(self) -> tuple[bool, list[int] | None]:
        self._log_call("get_dynamic_buffer")
        flat: list[int] = []
        for layer in range(self._num_layers):
            for row in range(self.device_settings.MATRIX_ROWS):
                for col in range(self.device_settings.MATRIX_COLUMNS):
                    flat.append(self._keymap[layer][row][col])
        return True, flat
