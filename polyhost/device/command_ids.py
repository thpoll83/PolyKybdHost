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
    REPLAY_ANIM = 31  # replay the one-time startup ("Eden") animation on demand
    # Overlay mapping with a host-chosen value width (protocol v12+). Same
    # packed from/to stream as SEND_OVERLAY_MAPPING, but data[2] carries the
    # bit width, so each group of pairs travels at the narrowest width it
    # fits in (8 bits = 30 pairs/report, 9 = 27, 10 = 24, 11 = 22).
    SEND_OVERLAY_MAPPING_W = 33
    GLYPH_SIZE = 34  # get/set the keycap legend size (protocol v13+)
    # Read-only: count byte + that many NUL-terminated ASCII layer names of at
    # most 8 chars. The count matches ID_DYNAMIC_KEYMAP_GET_LAYER_COUNT.
    GET_LAYER_NAMES = 35  # (protocol v14+)
    # --- dynamic macros (protocol v15+) -------------------------------------
    # Split three ways because they answer different questions at different rates:
    # INFO is a cheap header the editor needs before it can lay anything out, BODY is
    # streamed in report-sized windows (the buffer is ~2 KB and a report holds 64), and
    # LABEL is the one field the keycap renders, so it round-trips on its own.
    MACRO_INFO = 36   # count, label stride, capacity, bytes in use
    MACRO_BODY = 37   # windowed read/write of the shared body buffer
    MACRO_LABEL = 38  # get/set one macro's whole keycap look (caption+style+icon)



class MacroStyle(Enum):
    """How a macro keycap composes itself. Byte-identical to `poly_macro_style`.

    A macro owns its whole cell -- it cannot ride a modifier, because QMK carries the
    wrapped key in the low byte and a macro keycode is 0x7700+ -- so the cell is free to
    be more than a legend.

    Append-only, and a value the keyboard does not know is stored as INDEX rather than
    refused (the open-ended glyph-script rule, not the closed glyph-size one): INDEX is
    the one style that needs neither a font pack nor a chosen icon, so it always draws
    something. `PolyKybd.get_macro_info()["styles"]` reports how many the firmware can
    actually render.
    """

    INDEX = 0   # "M3" above the caption -- the default
    ICON = 1    # a chosen glyph above the caption
    TEXT = 2    # the caption alone, at the largest face that fits

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
    IDDQD runs the doom easter egg's attract demo as a screensaver instead of the
    pulse (dismissed by the first key press); firmware without the doom build (or
    older than the feature) falls back to / NACKs it — surfaced as a plain error.
    (Named for the cheat code, matching the tray/CLI label; the firmware calls the
    same value IDLE_STYLE_IDDQD internally — the wire value 2 is what's shared.)
    EDEN loops the "Eden" boot animation as a screensaver (split72 only), dismissed
    by the first key press; on split42 the animation is a no-op and it behaves like
    PULSE.
    """
    PULSE = 0
    JITTER = 1
    IDDQD = 2
    EDEN = 3


class GlyphScript(Enum):
    """Glyph-script override — mirrors the firmware's poly_glyph_script.

    STANDARD renders the normal language legends; any other value overrides the
    language-layer letter/digit legends with an alternative script (leaving overlays
    and OS-hints untouched). Values are append-only and shared on the wire with the
    firmware — never reorder. Every non-STANDARD script ships in the "fantasy"
    font-pack bundle (auto-flashed on connect).
    """
    STANDARD = 0
    TENGWAR = 1
    # 2026-07 expansion (firmware protocol v10). Order matches poly_glyph_script.
    RUNES = 2
    AUREBESH = 3
    SGA = 4
    CIRTH = 5
    IBMVGA = 6
    C64 = 7
    AMIGA = 8
    APL = 9
    BRAILLE = 10


class GlyphSize(Enum):
    """Keycap legend size — mirrors the firmware's poly_glyph_size.

    Selects how large a key's MAIN legend is drawn — the single glyph the key
    produces. The shift / AltGr previews and every other kind of chrome are
    deliberately unaffected: a keycap has room for one big thing. Values are
    append-only and shared on the wire with the firmware — never reorder.

    ⚠️ Unlike GlyphScript, this range is CLOSED: the firmware NACKs a value it does
    not know, because a size names a rendering tier rather than a catalogue entry,
    and an unknown one would persist as a setting that silently renders as SMALL.
    So do NOT send a value that is not in this enum, and do not expect a newer
    keyboard to accept one that is.

    The bigger faces are latin only and ship in the `latinbig` font-pack bundle
    (auto-flashed on connect). Without it — or for a legend outside the latin
    repertoire, e.g. a CJK or Arabic keycap — the keyboard falls back to SMALL for
    that key, so selecting a size is always safe.
    """
    SMALL = 0    # the original 27 px face, and the default
    MEDIUM = 1   # 33 px em
    LARGE = 2    # 39 px em
