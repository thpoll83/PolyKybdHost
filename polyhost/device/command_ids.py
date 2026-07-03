from enum import Enum


class HidId(Enum):
    ID_GET_PROTOCOL_VERSION = 1
    ID_GET_KEYBOARD_VALUE = 2
    ID_SET_KEYBOARD_VALUE = 3
    ID_DYNAMIC_KEYMAP_GET_KEYCODE = 4
    ID_DYNAMIC_KEYMAP_SET_KEYCODE = 5
    ID_DYNAMIC_KEYMAP_RESET = 6
    ID_CUSTOM_SET_VALUE = 7
    ID_CUSTOM_GET_VALUE = 8
    ID_CUSTOM_SAVE = 9
    ID_EEPROM_RESET = 10
    ID_BOOTLOADER_JUMP = 11
    ID_DYNAMIC_KEYMAP_MACRO_GET_COUNT = 12
    ID_DYNAMIC_KEYMAP_MACRO_GET_BUFFER_SIZE = 13
    ID_DYNAMIC_KEYMAP_MACRO_GET_BUFFER = 14
    ID_DYNAMIC_KEYMAP_MACRO_SET_BUFFER = 15
    ID_DYNAMIC_KEYMAP_MACRO_RESET = 16
    ID_DYNAMIC_KEYMAP_GET_LAYER_COUNT = 17
    ID_DYNAMIC_KEYMAP_GET_BUFFER = 18
    ID_DYNAMIC_KEYMAP_SET_BUFFER = 19
    ID_DYNAMIC_KEYMAP_GET_ENCODER = 20
    ID_DYNAMIC_KEYMAP_SET_ENCODER = 21
    ID_POLYKYBD = 80


class Cmd(Enum):
    GET_ID = 6
    GET_LANG = 7
    GET_LANG_LIST = 8  # RETIRED (protocol v2): firmware NACKs it — use GET_LANG_LIST_PACKED (27)
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
    SET_UNICODE_MODE = 20
    SEND_OVERLAY_MAPPING = 21
    GET_DEFAULT_LAYER = 22
    ENTER_BOOTLOADER = 23
    DISPLAY_OFF = 24
    SET_HANDEDNESS = 25
    SAVE_MRU = 26
    GET_LANG_LIST_PACKED = 27
    IDLE_STYLE = 28  # get/set idle (anti-burn-in) display style (protocol v4+)
    SET_OS = 29  # get/set the active host-OS identity (protocol v7+)
    GLYPH_SCRIPT = 30  # get/set glyph-script override (standard / fantasy, protocol v9+)


class OsType(Enum):
    """Active host-OS identity — mirrors the firmware's enum poly_os.

    A first-class state, independent of the unicode input mode (cmd 20). The host
    pushes it over cmd 29 (host-auto) and it drives the keyboard's modifier-legend
    swap, OS icon, and semantic action keys. Values are append-only and shared on
    the wire with the firmware — never reorder.
    """
    UNKNOWN = 0
    WINDOWS = 1
    MACOS = 2
    LINUX = 3
    ANDROID = 4
    IOS = 5
    # Host-detected Linux desktop environments (from XDG_CURRENT_DESKTOP). They
    # refine the keyboard's Super-key shortcut hints (GNOME and KDE bind the
    # launcher/window-switcher differently); otherwise they behave as LINUX. Sent
    # over cmd 29 to firmware protocol >= 8. Anything else (XFCE, Cinnamon, …)
    # stays plain LINUX.
    LINUX_GNOME = 6
    LINUX_KDE = 7


class IdleStyle(Enum):
    """Idle (anti-burn-in) display style — mirrors the firmware's poly_idle_style.

    PULSE is the legacy contrast-only breathing; JITTER additionally relocates the
    key legend by a small random offset each pulse cycle so the lit pixels migrate.
    """
    PULSE = 0
    JITTER = 1


class GlyphScript(Enum):
    """Glyph-script override — mirrors the firmware's poly_glyph_script.

    STANDARD renders the normal language legends; any other value overrides the
    language-layer letter/digit legends with an alternative script (leaving overlays
    and OS-hints untouched). Values are append-only and shared on the wire with the
    firmware — never reorder. TENGWAR ships in the "fantasy" font-pack bundle.
    """
    STANDARD = 0
    TENGWAR = 1
