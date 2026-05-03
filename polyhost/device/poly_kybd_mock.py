import logging
import time
from typing import Any

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
from polyhost.input.unicode_input import InputMethod
from polyhost.util.dict_util import split_by_n_chars


class PolyKybdMock:
    """
    Software stub for PolyKybd — complete interface without physical hardware.

    Mirrors every public method of PolyKybd, maintains simulated device state,
    and records all calls in ``self.calls`` as (method_name, args, kwargs) tuples
    so tests can assert on what was invoked and in what order.
    """

    def __init__(self, device_settings: DeviceSettings, poly_settings=None, *,
                 version: str = "1.0.0",
                 lang: str = "enUS",
                 langs: str = "enUSdeATkoKRfrFRitITesES",
                 num_layers: int = 4):
        self.device_settings = device_settings
        self.poly_settings = poly_settings
        self.log = logging.getLogger('PolyHost')

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
        return self._name

    def get_sw_version(self) -> str:
        return self._sw_version

    def get_sw_version_number(self) -> list[int]:
        """Return [major, minor, patch] version integers."""
        return self._sw_version_num

    def get_hw_version(self) -> str:
        return self._hw_version

    # -------------------------------------------------------------------------
    # Overlay flags / reset
    # -------------------------------------------------------------------------

    def reset_overlay_mapping(self) -> tuple[bool, str]:
        self._log_call("reset_overlay_mapping")
        self._overlay_mapping = {}
        self.log.info("Reset Overlay Mapping...")
        return True, ""

    def reset_overlays_and_usage(self) -> tuple[bool, str]:
        self._log_call("reset_overlays_and_usage")
        self._sent_overlays = []
        self.log.info("Reset Overlays AND Usage...")
        return True, ""

    def reset_overlay_usage(self) -> tuple[bool, str]:
        self._log_call("reset_overlay_usage")
        self.log.info("Reset Overlay Usage...")
        return True, ""

    def reset_overlays(self) -> tuple[bool, str]:
        self._log_call("reset_overlays")
        self._sent_overlays = []
        self.log.info("Reset Overlays...")
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

    def set_brightness(self, brightness: int) -> tuple[bool, str]:
        self._log_call("set_brightness", brightness)
        self._brightness = max(0, min(brightness, 50))
        return True, ""

    def set_idle(self, idle: bool) -> tuple[bool, str]:
        self._log_call("set_idle", idle)
        self._idle = idle
        return True, ""

    def set_unicode_mode(self, mode: InputMethod) -> tuple[bool, str]:
        self._log_call("set_unicode_mode", mode)
        self._unicode_mode = mode
        self.log.info("Setting unicode mode to %d", mode.value)
        return True, ""

    # -------------------------------------------------------------------------
    # Key press / release
    # -------------------------------------------------------------------------

    def press_and_release_key(self, keycode: int, duration: int) -> tuple[bool, str]:
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
        return self._all_languages

    def get_current_lang(self) -> str:
        return self._current_lang

    def change_language(self, lang: str) -> tuple[bool, str]:
        self._log_call("change_language", lang)
        if lang not in self._all_languages:
            return False, f"Language '{lang}' not present on PolyKybd"
        self._current_lang = lang
        return True, lang

    # -------------------------------------------------------------------------
    # Overlay transmission
    # -------------------------------------------------------------------------

    def send_overlay_mapping(self, from_to: dict) -> tuple[bool, str]:
        self._log_call("send_overlay_mapping", from_to)
        self._overlay_mapping.update(from_to)
        return True, "Mapping sent"

    def send_overlays(self, filenames: list) -> bool:
        self._log_call("send_overlays", filenames)
        overlay_counter = 0
        hid_msg_counter = 0
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
                        if KeyCode.KC_ESCAPE.value in overlay_map:
                            hid_msg_counter += self.send_smallest_overlay(
                                KeyCode.KC_ESCAPE.value, modifier, overlay_map)
                            overlay_map.pop(KeyCode.KC_ESCAPE.value)
                            self.enable_overlays()
                            enabled = True

                    for keycode in overlay_map:
                        hid_msg_counter += self.send_smallest_overlay(
                            keycode, modifier, overlay_map)
                    overlay_counter += 1

        self.log.info("%d overlays sent (%d simulated HID messages).",
                      overlay_counter, hid_msg_counter)
        if not enabled:
            self.enable_overlays()
        self._sent_overlays.extend(filenames)
        return True

    def send_smallest_overlay(self, keycode: int, modifier: Modifier, mapping: dict) -> int:
        ov = mapping[keycode]
        return min(ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs)

    # -------------------------------------------------------------------------
    # Serial / console
    # -------------------------------------------------------------------------

    def read_serial(self):
        return None

    def get_console_output(self, flush_and_return: bool = True) -> str | None:
        return "" if flush_and_return else None

    # -------------------------------------------------------------------------
    # Command execution
    # -------------------------------------------------------------------------

    def execute_commands(self, command_list: list) -> None:
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

    # -------------------------------------------------------------------------
    # Dynamic keymap
    # -------------------------------------------------------------------------

    def get_default_layer(self) -> tuple[bool, int]:
        self._log_call("get_default_layer")
        return True, 0

    def get_dynamic_layer_count(self) -> tuple[bool, int]:
        self._log_call("get_dynamic_layer_count")
        return True, self._num_layers

    def get_dynamic_keycode(self, layer: int, row: int, col: int) -> tuple[bool, int | bytearray]:
        self._log_call("get_dynamic_keycode", layer, row, col)
        if layer >= self._num_layers:
            return False, bytearray()
        return True, self._keymap[layer][row][col]

    def set_dynamic_keycode(self, layer: int, row: int, col: int, keycode: int) -> tuple[bool, Any]:
        self._log_call("set_dynamic_keycode", layer, row, col, keycode)
        self.log.info("set_dynamic_keycode layer=%d row=%d col=%d keycode=0x%04x",
                      layer, row, col, keycode)
        if layer >= self._num_layers:
            return False, f"Layer {layer} out of range"
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
