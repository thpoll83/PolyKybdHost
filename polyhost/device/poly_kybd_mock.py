import functools
import inspect
import logging
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np  # for the get_display_image return annotation only

from polyhost.device.command_ids import IdleTimeout
from polyhost.device.device_settings import DeviceSettings
from polyhost.util.dict_util import split_by_n_chars
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import Modifier
from polyhost.device.mock_firmware import FaultPlan, MockFirmware, MockHidHelper
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_sim import OverlayFirmwareSim
from polyhost.input.unicode_input import InputMethod


class _MockLog(logging.LoggerAdapter):
    """The PolyHost logger with "(mock) " in front, so the mock's half of a
    send is never mistaken for the keyboard's in a log bundle."""

    def process(self, msg, kwargs):
        return f"(mock) {msg}", kwargs

    def debug_detailed(self, msg, *args, **kwargs):
        from polyhost.util.log_util import DEBUG_DETAILED
        self.log(DEBUG_DETAILED, msg, *args, **kwargs)


class _NoPauseSettings:
    """PolySettings for the mock's wire: no rate-limit pauses. The pause keeps a
    real keyboard responsive to typing during a burst; the emulator has nothing
    to protect, and as a secondary device it would double every cold switch."""

    def __init__(self, inner):
        self._inner = inner

    def get(self, name):
        if name == "max_hid_message_before_delay":
            return 1 << 30
        if name == "delay_time_after_max_hid_messages":
            return 0
        return self._inner.get(name) if self._inner is not None else None


def _shipped_bundle_versions() -> dict[int, int]:
    """{bundle index: content_version} of the font pack this host ships, so a
    mock keyboard reads as up to date and the autocheck flashes nothing."""
    try:
        from polyhost.services.fontpack_bundle import load_bundle_manifest
        manifest = load_bundle_manifest() or {}
    except Exception:   # noqa: BLE001 -- a missing manifest just means "empty"
        return {}
    return {b["index"]: b["content_version"] for b in manifest.get("bundles", [])}


class PolyKybdMock:
    """
    Software stub for PolyKybd — complete interface without physical hardware.

    Mirrors every public method of PolyKybd and maintains simulated device state.
    Every public method appends an entry to ``self.calls`` as a
    (method_name, args, kwargs) tuple so tests can assert on what was invoked
    and in what order.

    Three layers, and which one a method uses is deliberate:

    * Settings, macros, language and keymap keep their own state here; their
      semantics are what the tests pin.
    * Overlays and the device commands (bootloader, handedness, crash record,
      MRU save) go through a REAL ``PolyKybd`` over ``self.firmware``, a
      ``MockFirmware``. The keycaps therefore hold what the wire carried -- the
      encoding choice, PRC, icon fills and the v21 mapping flags are the real
      code, decoded the way the firmware decodes them.
    * ``self.hid`` is a ``MockHidHelper`` over the same firmware, so the
      font-pack and firmware-update modules, which talk to ``keeb.hid``
      directly, work against the mock too.

    ``protocol`` makes it any firmware generation: ``supports()`` and
    ``capabilities()`` answer for it, gated accessors refuse the way the real
    ones do, and the wire carries that protocol's encodings. ``faults`` is a
    ``FaultPlan``; see mock_firmware.py.
    """

    def __init__(self, device_settings: DeviceSettings, poly_settings=None, *,
                 version: str = "1.0.0",
                 lang: str = "enUS",
                 langs: str = "enUSdeATkoKRfrFRitITesES",
                 num_layers: int = 4,
                 protocol: int | None = None,
                 faults: FaultPlan | None = None,
                 fontpack: str = "current",
                 keymap: str = "empty"):
        if isinstance(poly_settings, str):
            # `version` is keyword-only. A version string passed positionally
            # lands here and the mock silently reports the default "1.0.0".
            raise TypeError("poly_settings must be a settings object; "
                            "pass the version as version=...")
        self.device_settings = device_settings
        self.poly_settings = poly_settings
        self.log = logging.getLogger('PolyHost')
        self.all_languages = list()
        self.version = version
        self.sw_version_num = [int(x) for x in version.split(".")]
        self.lang = lang
        self.langs = langs
        self.last_mapping: dict = {}
        self.last_mapping_flags = (False, False)
        self._sim = OverlayFirmwareSim()
        from polyhost._version import __protocol__
        self.protocol_version: int = __protocol__ if protocol is None else int(protocol)
        self.faults = faults or FaultPlan()

        # Version / identity
        self._name = "PolyKybdMock"
        self._sw_version = version
        self._sw_version_num = [int(x) for x in version.split(".")]
        self._hw_version = version

        # Language state
        self._current_lang = lang
        self._lang_str = langs
        self._all_languages = split_by_n_chars(langs, 4)

        # The keyboard behind the wire. "current" = every shipped bundle already
        # flashed (a quiet autocheck); "empty" = nothing flashed yet.
        self.firmware = MockFirmware(
            self.protocol_version, settings=device_settings, sim=self._sim,
            faults=self.faults, name=self._name, version=version,
            languages=list(self._all_languages), lang=lang,
            bundle_versions=_shipped_bundle_versions() if fontpack == "current" else {})
        self.hid = MockHidHelper(self.firmware, device_settings)
        from polyhost.device.poly_kybd import PolyKybd
        self._wire = PolyKybd(device_settings, _NoPauseSettings(poly_settings))
        self._wire.hid = self.hid
        self._wire.protocol_version = self.protocol_version
        self._wire.log = _MockLog(self.log, {})

        # Device state
        self._brightness: int = 0
        self._idle: bool = False
        self._unicode_mode: InputMethod | None = None
        self._overlay_masking: bool = False
        self._sent_overlays: list[str] = []

        # Dynamic keymap: _keymap[layer][row][col] = keycode (int)
        self._num_layers: int = num_layers
        # "board" starts layer 0 as the firmware's default keymap (exported to
        # res/preview/board.json), so the layout editor and the board view show a
        # real keyboard; "empty" is all KC_NO, which is what the tests pin.
        self._default_keys = {}
        if keymap == "board":
            from polyhost.services.board_layout import base_keycodes
            self._default_keys = base_keycodes()
        self._keymap: list[list[list[int]]] = self._fresh_keymap()

        # Call log for test assertions
        self.calls: list[tuple[str, tuple, dict]] = []

    def _log_call(self, name: str, *args, **kwargs) -> None:
        self.calls.append((name, args, kwargs))

    def _forward(self, name: str, *args) -> None:
        """Send the same command over the wire too, so the emulated keyboard
        sees everything a caller sends -- that is what lets a protocol sweep of
        the CORE catch a command its caller should have gated. The mock's own
        state stays the answer; the wire's reply is not consulted."""
        try:
            getattr(self._wire, name)(*args)
        except Exception as e:   # noqa: BLE001 -- the mock must not fail on its mirror
            self.log.debug("(mock) forwarding %s failed: %s", name, e)

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    def connect(self) -> bool:
        self._log_call("connect")
        if self.firmware.faults.disconnected or self.firmware.deaf():
            return False
        self.hid.reattach()          # a failed transfer may have closed it
        return True

    def pop_fresh_boot(self) -> bool:
        self._log_call("pop_fresh_boot")
        return self.firmware.pop_fresh_boot()

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------

    def query_id(self) -> tuple[bool, str]:
        self._log_call("query_id")
        if self.firmware.deaf():
            return False, "EMPTY REPLY"
        return True, f"{self._name} {self._sw_version} P{self.protocol_version} HW0"

    def query_version_info(self) -> tuple[bool, str]:
        self._log_call("query_version_info")
        return True, self._sw_version

    # -------------------------------------------------------------------------
    # Protocol
    # -------------------------------------------------------------------------

    def get_protocol_version(self) -> int:
        return self.protocol_version

    def supports(self, feature: str) -> bool:
        from polyhost.device.poly_kybd import protocol_supports
        return protocol_supports(self.protocol_version, feature)

    def capabilities(self) -> dict:
        from polyhost.device.poly_kybd import FEATURE_MIN_PROTOCOL, protocol_supports
        return {f: protocol_supports(self.protocol_version, f) for f in FEATURE_MIN_PROTOCOL}

    def _too_old(self, feature: str) -> str | None:
        """The refusal text when this protocol lacks ``feature``, else None."""
        if self.supports(feature):
            return None
        from polyhost.device.poly_kybd import FEATURE_MIN_PROTOCOL
        return (f"Firmware protocol {self.protocol_version} is too old for {feature} "
                f"(need v{FEATURE_MIN_PROTOCOL[feature]}+).")

    @property
    def fontpack_bundle_versions(self) -> dict:
        return self.firmware.reported_bundle_versions()

    @property
    def state_generation(self):
        if self.protocol_version < 16:
            return None
        return self.firmware.state_generation

    # -- the counters the tests read, from what the firmware received ------

    @property
    def hid_image_sends(self) -> int:
        return self.firmware.image_reports + self.firmware.fill_reports

    @property
    def hid_mapping_sends(self) -> int:
        return self.firmware.mapping_reports

    @property
    def prc_reports(self) -> list[bytes]:
        return self.firmware.prc_records

    @property
    def _overlays_enabled(self) -> bool:
        return self.firmware.overlays_enabled

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

    def reset_overlay_mapping(self) -> tuple[bool, Any]:
        self._log_call("reset_overlay_mapping")
        self._sent_overlays = []
        return self._wire.reset_overlay_mapping()

    def set_all_overlay_usage(self):
        self._log_call("set_all_overlay_usage")
        return self._wire.set_all_overlay_usage()

    def set_mirror_overlays(self, enable):
        self._log_call("set_mirror_overlays", enable)
        return self._wire.set_mirror_overlays(enable)

    def reset_overlays_and_usage(self) -> tuple[bool, Any]:
        self._log_call("reset_overlays_and_usage")
        self._sent_overlays = []
        return self._wire.reset_overlays_and_usage()

    def reset_overlay_mapping_and_usage(self):
        self._log_call("reset_overlay_mapping_and_usage")
        return self._wire.reset_overlay_mapping_and_usage()

    def prepare_for_mru_send(self):
        self._log_call("prepare_for_mru_send")
        return self._wire.prepare_for_mru_send()

    def reset_overlay_usage(self):
        self._log_call("reset_overlay_usage")
        return self._wire.reset_overlay_usage()

    def reset_overlays(self) -> tuple[bool, Any]:
        self._log_call("reset_overlays")
        self._sent_overlays = []
        return self._wire.reset_overlays()

    def enable_overlays(self) -> tuple[bool, Any]:
        self._log_call("enable_overlays")
        return self._wire.enable_overlays()

    def disable_overlays(self) -> tuple[bool, Any]:
        self._log_call("disable_overlays")
        return self._wire.disable_overlays()

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
        self._forward("set_brightness", brightness, flags)
        return True, ""

    def set_idle(self, idle: bool) -> tuple[bool, str]:
        self._log_call("set_idle", idle)
        self._idle = idle
        self._forward("set_idle", idle)
        return True, ""

    def set_idle_style(self, style) -> tuple[bool, str]:
        value = getattr(style, "value", style)
        self._log_call("set_idle_style", value)
        if (refusal := self._too_old("idle_style")):
            return False, refusal
        self._forward("set_idle_style", style)
        self._idle_style = int(value)
        return True, ""

    def get_idle_style(self) -> tuple[bool, int]:
        self._log_call("get_idle_style")
        if self._too_old("idle_style"):
            return False, 0
        return True, getattr(self, "_idle_style", 0)

    def set_idle_timeout(self, value) -> tuple[bool, str]:
        # Refuses what the firmware refuses: the preset range is CLOSED, so a mock
        # that banked any integer would let a caller "succeed" against a value the
        # real board NACKs.
        v = getattr(value, "value", value)
        self._log_call("set_idle_timeout", v)
        if (refusal := self._too_old("idle_timeout")):
            return False, refusal
        try:
            v = IdleTimeout(int(v)).value
        except (ValueError, TypeError):
            return False, f"{value!r} is not an idle-timeout preset"
        self._forward("set_idle_timeout", v)
        self._idle_timeout = v
        return True, ""

    def get_idle_timeout(self) -> tuple[bool, tuple[int, int]]:
        self._log_call("get_idle_timeout")
        if self._too_old("idle_timeout"):
            return False, (0, 0)
        value = getattr(self, "_idle_timeout", IdleTimeout.MIN_2.value)
        try:
            seconds = IdleTimeout(value).seconds
        except ValueError:
            seconds = 0
        return True, (value, seconds)

    def set_glyph_script(self, script) -> tuple[bool, str]:
        value = getattr(script, "value", script)
        self._log_call("set_glyph_script", value)
        if (refusal := self._too_old("glyph_script")):
            return False, refusal
        self._forward("set_glyph_script", int(value))
        self._glyph_script = int(value)
        return True, ""

    def get_glyph_script(self) -> tuple[bool, int]:
        self._log_call("get_glyph_script")
        if self._too_old("glyph_script"):
            return False, 0
        return True, getattr(self, "_glyph_script", 0)

    def set_glyph_size(self, size) -> tuple[bool, str]:
        value = size.value if hasattr(size, "value") else int(size)
        self._log_call("set_glyph_size", value)
        if (refusal := self._too_old("glyph_size")):
            return False, refusal
        self._forward("set_glyph_size", int(value))
        self._glyph_size = int(value)
        return True, "ok"

    def get_glyph_size(self) -> tuple[bool, int]:
        self._log_call("get_glyph_size")
        if self._too_old("glyph_size"):
            return False, 0
        return True, getattr(self, "_glyph_size", 0)

    # --- dynamic macros ---------------------------------------------------
    # Backed by a real byte buffer, not a dict of strings: the whole point of the
    # host-side encoding is the NUL-delimited packing, and a mock that stored macros
    # as separate strings would let a packing bug through untouched.
    MACRO_COUNT = 16
    MACRO_LABEL_LEN = 12
    MACRO_CAPACITY = 2267

    MACRO_STYLES = 4

    def _macro_buf(self) -> bytearray:
        if not hasattr(self, "_macros"):
            self._macros = bytearray(self.MACRO_CAPACITY)
            self._macro_looks = [{"label": "", "style": 0, "icon": 0}
                                 for _ in range(self.MACRO_COUNT)]
        return self._macros

    def get_macro_info(self) -> tuple[bool, dict]:
        self._log_call("get_macro_info")
        if (refusal := self._too_old("macros")):
            return False, refusal
        buf = self._macro_buf()
        used = 0
        for i, b in enumerate(buf):
            if b:
                used = i + 2
        return True, {
            "count": self.MACRO_COUNT,
            "label_len": self.MACRO_LABEL_LEN,
            "capacity": self.MACRO_CAPACITY,
            "used": min(used, self.MACRO_CAPACITY),
            "styles": self.MACRO_STYLES,
        }

    def read_macro_buffer(self, capacity: int) -> tuple[bool, bytes]:
        self._log_call("read_macro_buffer", capacity)
        if (refusal := self._too_old("macros")):
            return False, refusal
        return True, bytes(self._macro_buf()[:capacity])

    def write_macro_buffer(self, data: bytes) -> tuple[bool, int]:
        self._log_call("write_macro_buffer", len(data))
        if (refusal := self._too_old("macros")):
            return False, refusal
        buf = self._macro_buf()
        buf[:len(data)] = data
        return True, len(data)

    def get_macro_look(self, macro_id: int) -> tuple[bool, dict]:
        self._log_call("get_macro_look", macro_id)
        if (refusal := self._too_old("macros")):
            return False, refusal
        self._macro_buf()
        if not 0 <= macro_id < self.MACRO_COUNT:
            return False, "out of range"
        return True, dict(self._macro_looks[macro_id])

    def set_macro_look(self, macro_id: int, text: str,
                       style: int = 0, icon: int = 0) -> tuple[bool, dict]:
        self._log_call("set_macro_look", macro_id, text, style, icon)
        if (refusal := self._too_old("macros")):
            return False, refusal
        self._macro_buf()
        if not 0 <= macro_id < self.MACRO_COUNT:
            return False, "out of range"
        # Mirror the firmware: ASCII only, cut to the stride, and an unknown style
        # stored as INDEX rather than refused.
        clean = "".join(c for c in text if 0x20 <= ord(c) <= 0x7E)[:self.MACRO_LABEL_LEN]
        look = {"label": clean,
                "style": style if 0 <= style < self.MACRO_STYLES else 0,
                "icon": icon & 0xFFFFFFFF}
        self._macro_looks[macro_id] = look
        return True, dict(look)

    def replay_startup_anim(self) -> tuple[bool, Any]:
        self._log_call("replay_startup_anim")
        return self._wire.replay_startup_anim()

    def set_unicode_mode(self, mode: InputMethod,
                         persist: bool = True) -> tuple[bool, str]:
        self._log_call("set_unicode_mode", mode, persist)
        if not persist and (refusal := self._too_old("unicode_mode_volatile")):
            return False, refusal
        self._forward("set_unicode_mode", mode, persist)
        self._unicode_mode = mode
        self.log.info("Setting unicode mode to %d", mode.value)
        return True, ""

    def set_os(self, os, pin: bool = False) -> tuple[bool, str]:
        self._log_call("set_os", os, pin)
        if (refusal := self._too_old("os")):
            return False, refusal
        self._forward("set_os", os, pin)
        self._os = getattr(os, "value", os)
        self._os_pin = pin
        return True, ""

    def get_os(self) -> tuple[bool, int]:
        self._log_call("get_os")
        if self._too_old("os"):
            return False, 0
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
        if self.firmware.faults.disconnected or self.firmware.deaf():
            return False, "Could not read reply from PolyKybd"
        return True, self._current_lang

    def enumerate_lang(self) -> tuple[bool, str]:
        self._log_call("enumerate_lang")
        if (refusal := self._too_old("packed_lang_list")):
            return False, refusal
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

    def send_overlay_mapping(self, from_to: dict, reset: bool = False,
                             show: bool = False) -> tuple[bool, str]:
        self._log_call("send_overlay_mapping", from_to, reset, show)
        self.last_mapping = from_to
        self.last_mapping_flags = (reset, show)
        return self._wire.send_overlay_mapping(from_to, reset, show)

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
        """Parity with PolyKybd.send_overlays — a no-reuse send is an MRU send
        with a throwaway cache. There is no separate direct path any more."""
        self._log_call("send_overlays", filenames)
        ok = self.send_overlays_mru(
            filenames, OverlayMRUCache(self.device_settings.OVERLAY_MAPPING_CAPACITY), cancel)
        if ok:
            self._sent_overlays.extend(filenames)
        return ok

    def send_overlays_mru(self, filenames: list, cache, cancel=None,
                          synthetic: dict | None = None) -> bool:
        """The real PolyKybd.send_overlays_mru, over the emulated keyboard: the
        same cache decisions, encodings, cancellation and rollback, so the mock
        cannot fall behind the device's signature or behaviour again."""
        self._log_call("send_overlays_mru", filenames)
        self._wire.fontpack_bundle_versions = self.firmware.reported_bundle_versions()
        return self._wire.send_overlays_mru(filenames, cache, cancel, synthetic=synthetic)

    def send_smallest_overlay(self, keycode: int, modifier: Modifier, mapping: dict,
                              clean_slot: bool = True) -> int:
        return self._wire.send_smallest_overlay(keycode, modifier, mapping, clean_slot=clean_slot)

    # -------------------------------------------------------------------------
    # Device commands -- the real PolyKybd over the emulated keyboard
    # -------------------------------------------------------------------------

    def activate_bootloader(self) -> tuple[bool, Any]:
        self._log_call("activate_bootloader")
        return self._wire.activate_bootloader()

    def set_handedness(self, master_is_left: bool) -> tuple[bool, Any]:
        self._log_call("set_handedness", master_is_left)
        return self._wire.set_handedness(master_is_left)

    def save_mru(self) -> tuple[bool, Any]:
        self._log_call("save_mru")
        return self._wire.save_mru()

    def get_crash_record(self, which: int = 0) -> tuple[bool, Any]:
        self._log_call("get_crash_record", which)
        return self._wire.get_crash_record(which)

    def clear_crash_record(self) -> tuple[bool, Any]:
        self._log_call("clear_crash_record")
        return self._wire.clear_crash_record()

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

    def get_layer_names(self) -> tuple[bool, list[str]]:
        self._log_call("get_layer_names")
        if self._too_old("layer_names"):
            return False, []
        names = ["Qwerty", "Stag!", "ColemkDH", "Neo", "Workman", "Fn", "Numpad", "Utility"]
        return True, names[:self._num_layers]

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
        self._keymap = self._fresh_keymap()
        return True, ""

    def _fresh_keymap(self) -> list[list[list[int]]]:
        """What a keymap reset leaves: the default layer 0, empty above it --
        the firmware restores its compiled keymap, not zeros."""
        rows = self.device_settings.MATRIX_ROWS
        cols = self.device_settings.MATRIX_COLUMNS
        keymap = [[[0] * cols for _ in range(rows)] for _ in range(self._num_layers)]
        for (row, col), keycode in self._default_keys.items():
            if row < rows and col < cols and self._num_layers:
                keymap[0][row][col] = keycode
        return keymap

    def base_layer(self) -> dict[str, int]:
        """{"row,col": keycode} of layer 0 as it stands now -- edits through the
        layout editor included -- for the board view."""
        if not self._keymap:
            return {}
        return {f"{r},{c}": kc for r, row in enumerate(self._keymap[0])
                for c, kc in enumerate(row) if kc}

    def get_dynamic_buffer(self) -> tuple[bool, list[int] | None]:
        self._log_call("get_dynamic_buffer")
        flat: list[int] = []
        for layer in range(self._num_layers):
            for row in range(self.device_settings.MATRIX_ROWS):
                for col in range(self.device_settings.MATRIX_COLUMNS):
                    flat.append(self._keymap[layer][row][col])
        return True, flat


# Inspection helpers stay outside the fault plan: they read the simulated
# keyboard rather than talk to it.
_NOT_FAULTABLE = {"get_display_bitmap", "get_display_image", "save_overlay_as_png",
                  "supports", "capabilities", "get_protocol_version"}


def _faultable(fn):
    """Let a FaultPlan fail or raise in ``fn`` by name, the way a device call
    fails: a bool method returns False, a tuple method (False, message)."""
    returns_bool = inspect.signature(fn).return_annotation is bool
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if FaultPlan.take(self.faults.raises, name):
            raise OSError(f"{name}: injected fault")
        if FaultPlan.take(self.faults.fail, name):
            self._log_call(name, *args, **kwargs)
            return False if returns_bool else (False, f"{name}: injected fault")
        return fn(self, *args, **kwargs)
    return wrapper


for _name, _fn in list(vars(PolyKybdMock).items()):
    if (inspect.isfunction(_fn) and not _name.startswith("_")
            and _name not in _NOT_FAULTABLE):
        setattr(PolyKybdMock, _name, _faultable(_fn))
del _name, _fn
