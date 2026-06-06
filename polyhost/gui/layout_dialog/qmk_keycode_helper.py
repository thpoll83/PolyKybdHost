import pathlib
import re
from pathlib import Path

HEADER_FILE = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "keycodes.h"
LAYER_NAMES_FILE = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "layer_names.yaml"


def parse_qmk_keycode_header(header_path: Path, enum_to_parse: str) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    text = header_path.read_text(encoding="utf-8", errors="ignore")

    enum_match = re.search(
        rf'enum\s+{enum_to_parse}\s*\{{(.*?)\}};',
        text,
        re.S,
    )
    if not enum_match:
        raise RuntimeError(f"{enum_to_parse} enum not found")

    body = enum_match.group(1)

    entries = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        m = re.match(r'([A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+)', line)
        if m:
            entries[m.group(1)] = int(m.group(2), 16)

    return entries


def parse_qmk_keycodes(header_path: Path) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    return parse_qmk_keycode_header(header_path, "qk_keycode_defines")


def parse_layer_names(layer_names_path: Path = None) -> dict[int, str]:
    """Load layer names from the pre-generated YAML in res/layer_names.yaml.

    Generate or update the file with:
        python scripts/generate_layer_names.py
    """
    import yaml
    if layer_names_path is None:
        layer_names_path = LAYER_NAMES_FILE
    try:
        data = yaml.safe_load(layer_names_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {int(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def categorize(key_name: str) -> str:
    """Categorize a key_name into a functional group."""
    name = key_name[3:] if key_name.startswith("KC_") else key_name

    if name.startswith(("LEFT", "RIGHT")):
        return "Modifiers"
    if name.startswith(("MEDIA", "VOL", "MUTE", "PLAY", "STOP", "SYSTEM", "WWW")) or "MUSIC" in name or "AUDIO" in name or "BLUETOOTH" in name or "OUTPUT" in name:
        return "Media / System"
    if "MIDI" in name:
        return "Midi"
    if "HAPTIC" in name:
        return "Haptic"
    if "UNICODE" in name or "INTERNATIONAL" in name:
        return "Unicode / International"
    if "LED" in name or "RGB" in name or "BACKLIGHT" in name or "UNDERGLOW" in name:
        return "RGB"
    if "MOUSE" in name or "JOYSTICK" in name:
        return "Mouse / Joystick"
    if "MAGIC" in name:
        return "Magic"
    if "MACRO" in name or "USER" in name or name.startswith("QK_KB_"):
        return "User / Macro"
    if "PROGRAMMABLE" in name:
        return "Programmable"
    if name.startswith("QK_SPACE_CADET"):
        return "Space Cadet"
    if name.startswith("QK"):
        return "Quantum"

    return "Additional"


def create_nice_name(key_name: str) -> str:
    """Convert key_name to a display-friendly name with abbreviated terms and line breaks."""
    # Pass through special decoded keycode strings (MO, TG, LT, MT, etc.)
    # These don't start with "KC_" or "QK_" so they fall through cleanly.
    if len(key_name) < 3:
        return key_name
    caption = key_name[3:] if key_name[2] == '_' else key_name
    caption = caption.replace("UNDERGLOW_", "UNDERGL\n")
    caption = caption.replace("TRANSPARENT", "TRANSP")
    caption = caption.replace("CONTINUOUS", "CONT")
    caption = caption.replace("DYNAMIC_MACRO", "DYNMACRO")
    caption = caption.replace("PARENTHESIS", "PAREN")
    caption = caption.replace("BOOTLOADER", "BOOTLDR")
    caption = caption.replace("BRIGHTNESS", "BRIGHTN")
    caption = caption.replace("SPACE_CADET_", "")
    caption = caption.replace("INTERNATIONAL", "INTL")
    caption = caption.replace("PROGRAMMABLE", "PROG")
    caption = caption.replace("MODULATION", "MODUL")
    caption = caption.replace("CAPS_LOCK", "CAPSLOCK")
    caption = caption.replace("SATURATION", "SAT")
    caption = caption.replace("PORTAMENTO", "PORTAM")
    caption = caption.replace("AUTOCORRECT", "AUTO\nCORRECT")
    caption = caption.replace("APPLICATION", "APPLI\nCATION")
    caption = caption.replace("_", "\n")
    if caption.startswith("MIDI") and len(key_name) > 11:
        caption = caption[5:]
    if caption.startswith("MAGIC") and len(key_name) > 11:
        caption = caption[6:]
    return caption


def standard_category() -> str:
    return "Standard"


def last_key_in_standard_category() -> str:
    return "KC_KP_EQUAL"


def category_order() -> list[str]:
    return ["Standard", "Additional", "Modifiers", "Media / System", "RGB", "Unicode / International",
            "Mouse / Joystick",
            "Midi", "Haptic", "Magic", "User / Macro", "Programmable", "Space Cadet", "Quantum"]


def _mod_str(mods: int) -> str:
    """Convert 5-bit QMK modifier mask to a human-readable string."""
    right = (mods >> 4) & 1
    prefix = "R" if right else "L"
    parts = []
    if mods & 0x01:
        parts.append(f"{prefix}CTL")
    if mods & 0x02:
        parts.append(f"{prefix}SFT")
    if mods & 0x04:
        parts.append(f"{prefix}ALT")
    if mods & 0x08:
        parts.append(f"{prefix}GUI")
    return "+".join(parts) if parts else "MOD0"


def decompose_keycode(value: int, keycode_to_name: dict) -> str:
    """Decode a 16-bit QMK keycode to a human-readable string using the actual QMK encoding."""

    def basic_name(kc: int) -> str:
        n = keycode_to_name.get(kc, f"0x{kc:02X}")
        return n[3:] if n.startswith("KC_") else n

    # KC_NO
    if value == 0x0000:
        return "KC_NO"
    # KC_TRANSPARENT (_______)
    if value == 0x0001:
        return "KC_TRANSPARENT"
    # Basic keycodes (QK_BASIC range 0x0002–0x00FF)
    if 0x0002 <= value <= 0x00FF:
        return keycode_to_name.get(value, f"0x{value:02X}")
    # QK_MODS: modifier+key combos (Ctrl+A, Shift+B, …) — 0x0100–0x1FFF
    if 0x0100 <= value <= 0x1FFF:
        mods = (value >> 8) & 0x1F
        key = value & 0xFF
        return f"{_mod_str(mods)}({basic_name(key)})"
    # QK_MOD_TAP: MT() — 0x2000–0x3FFF
    if 0x2000 <= value <= 0x3FFF:
        mods = (value >> 8) & 0x1F
        key = value & 0xFF
        return f"MT({_mod_str(mods)},{basic_name(key)})"
    # QK_LAYER_TAP: LT() — 0x4000–0x4FFF
    if 0x4000 <= value <= 0x4FFF:
        layer = (value >> 8) & 0x0F
        key = value & 0xFF
        return f"LT({layer},{basic_name(key)})"
    # QK_LAYER_MOD: LM() — 0x5000–0x51FF (layer<<5 | 5-bit mod)
    if 0x5000 <= value <= 0x51FF:
        layer = (value >> 5) & 0x0F
        mods = value & 0x1F
        return f"LM({layer},{_mod_str(mods)})"
    # QK_TO: TO() — 0x5200–0x521F
    if 0x5200 <= value <= 0x521F:
        return f"TO({value & 0x1F})"
    # QK_MOMENTARY: MO() — 0x5220–0x523F
    if 0x5220 <= value <= 0x523F:
        return f"MO({value & 0x1F})"
    # QK_DEF_LAYER: DF() — 0x5240–0x525F
    if 0x5240 <= value <= 0x525F:
        return f"DF({value & 0x1F})"
    # QK_TOGGLE_LAYER: TG() — 0x5260–0x527F
    if 0x5260 <= value <= 0x527F:
        return f"TG({value & 0x1F})"
    # QK_ONE_SHOT_LAYER: OSL() — 0x5280–0x529F
    if 0x5280 <= value <= 0x529F:
        return f"OSL({value & 0x1F})"
    # QK_ONE_SHOT_MOD: OSM() — 0x52A0–0x52BF
    if 0x52A0 <= value <= 0x52BF:
        return f"OSM({_mod_str(value & 0x1F)})"
    # QK_LAYER_TAP_TOGGLE: TT() — 0x52C0–0x52DF
    if 0x52C0 <= value <= 0x52DF:
        return f"TT({value & 0x1F})"
    # QK_PERSISTENT_DEF_LAYER: PDF() — 0x52E0–0x52FF
    if 0x52E0 <= value <= 0x52FF:
        return f"PDF({value & 0x1F})"
    # QK_SWAP_HANDS: SH_T(kc) tap-hold — 0x5600–0x56EF (0x56F0+ are named actions)
    if 0x5600 <= value <= 0x56EF:
        return f"SH_T({basic_name(value & 0xFF)})"
    # QK_TAP_DANCE: TD(n) — 0x5700–0x57FF (firmware-defined dance index)
    if 0x5700 <= value <= 0x57FF:
        return f"TD({value & 0xFF})"

    # A named constant (parsed from keycodes.h) wins for everything else.
    name = keycode_to_name.get(value)
    if name is not None:
        return name
    # Firmware-defined parametric keycodes — index encoded in the low bits.
    if 0x7440 <= value <= 0x747F:
        return f"PB({value - 0x7440})"          # programmable button
    if 0x7700 <= value <= 0x777F:
        return f"MACRO({value - 0x7700})"
    if 0x7E00 <= value <= 0x7E3F:
        return f"KB({value - 0x7E00})"           # keyboard-specific custom
    if 0x7E40 <= value <= 0x7FFF:
        return f"USER({value - 0x7E40})"         # user custom (QK_USER)
    return f"0x{value:04X}"


# ---------------------------------------------------------------------------
# Keycode composition (encode) — the inverse of decompose_keycode().
#
# These build the 16-bit QMK keycode for the "special" behaviours from their
# parameters (layer / modifier mask / inner basic keycode), matching the exact
# encoding documented in quantum/keycodes.h. Keep these and decompose_keycode()
# in sync — they are two halves of the same single source of truth.
# ---------------------------------------------------------------------------

# QK_* range bases (low edge of each range).
QK_MODS = 0x0000          # modified keycode = (mods << 8) | basic_kc
QK_MOD_TAP = 0x2000
QK_LAYER_TAP = 0x4000
QK_LAYER_MOD = 0x5000
QK_TO = 0x5200
QK_MOMENTARY = 0x5220
QK_DEF_LAYER = 0x5240
QK_TOGGLE_LAYER = 0x5260
QK_ONE_SHOT_LAYER = 0x5280
QK_ONE_SHOT_MOD = 0x52A0
QK_LAYER_TAP_TOGGLE = 0x52C0
QK_PERSISTENT_DEF_LAYER = 0x52E0
QK_SWAP_HANDS = 0x5600

# 5-bit modifier mask bits (modifiers.h). Bit 4 selects right-hand mods.
MOD_CTRL = 0x01
MOD_SHIFT = 0x02
MOD_ALT = 0x04
MOD_GUI = 0x08
MOD_RIGHT = 0x10

# Layer-switch behaviours that take only a layer argument: name -> range base.
LAYER_BEHAVIORS = {
    "MO": QK_MOMENTARY,
    "TO": QK_TO,
    "TG": QK_TOGGLE_LAYER,
    "DF": QK_DEF_LAYER,
    "TT": QK_LAYER_TAP_TOGGLE,
    "OSL": QK_ONE_SHOT_LAYER,
}


def encode_mods(ctrl: bool = False, shift: bool = False, alt: bool = False,
                gui: bool = False, right: bool = False) -> int:
    """Build a 5-bit QMK modifier mask from individual modifier flags."""
    mods = 0
    if ctrl:
        mods |= MOD_CTRL
    if shift:
        mods |= MOD_SHIFT
    if alt:
        mods |= MOD_ALT
    if gui:
        mods |= MOD_GUI
    if right and mods:
        mods |= MOD_RIGHT
    return mods


def encode_layer_switch(behavior: str, layer: int) -> int:
    """Encode MO/TO/TG/DF/TT/OSL(layer) — layer clamped to 0..31."""
    base = LAYER_BEHAVIORS[behavior]
    return base | (layer & 0x1F)


def encode_one_shot_mod(mods: int) -> int:
    """Encode OSM(mods)."""
    return QK_ONE_SHOT_MOD | (mods & 0x1F)


def encode_mod_tap(mods: int, basic_kc: int) -> int:
    """Encode MT(mods, kc) — tap = kc, hold = mods. kc limited to 0..255."""
    return QK_MOD_TAP | ((mods & 0x1F) << 8) | (basic_kc & 0xFF)


def encode_layer_tap(layer: int, basic_kc: int) -> int:
    """Encode LT(layer, kc) — tap = kc, hold = layer. layer limited to 0..15."""
    return QK_LAYER_TAP | ((layer & 0x0F) << 8) | (basic_kc & 0xFF)


def encode_modded(mods: int, basic_kc: int) -> int:
    """Encode a modified keycode like LCTL(kc)/RSFT(kc) — sends mods+kc together."""
    return QK_MODS | ((mods & 0x1F) << 8) | (basic_kc & 0xFF)


def encode_layer_mod(layer: int, mods: int) -> int:
    """Encode LM(layer, mods) — momentary layer while holding the given mods."""
    return QK_LAYER_MOD | ((layer & 0x0F) << 5) | (mods & 0x1F)


def encode_persistent_def_layer(layer: int) -> int:
    """Encode PDF(layer) — set the default layer and persist it to EEPROM."""
    return QK_PERSISTENT_DEF_LAYER | (layer & 0x1F)


def encode_swap_hands_tap(basic_kc: int) -> int:
    """Encode SH_T(kc) — tap = kc, hold = swap hands. kc limited to 0..0xEF."""
    return QK_SWAP_HANDS | (basic_kc & 0xFF)


def decode_for_composer(value: int):
    """Decode a keycode into the composer's fields, or None if not composable.

    Returns (behavior, layer, mods, inner_kc) where behavior is one of the
    composer behaviour tags (MO/TO/TG/DF/TT/OSL/OSM/MT/LT/MOD). LM() and the
    persistent-default-layer range are intentionally not composable and yield
    None, as do plain basic keycodes.
    """
    # Modified keycode (Ctrl+C, RShift+A, …).
    if 0x0100 <= value <= 0x1FFF:
        return "MOD", 0, (value >> 8) & 0x1F, value & 0xFF
    # Mod-tap MT().
    if 0x2000 <= value <= 0x3FFF:
        return "MT", 0, (value >> 8) & 0x1F, value & 0xFF
    # Layer-tap LT().
    if 0x4000 <= value <= 0x4FFF:
        return "LT", (value >> 8) & 0x0F, 0, value & 0xFF
    # Layer-mod LM().
    if 0x5000 <= value <= 0x51FF:
        return "LM", (value >> 5) & 0x0F, value & 0x1F, 0
    # Layer switches that take only a layer argument.
    for lo, hi, tag in (
        (0x5200, 0x521F, "TO"), (0x5220, 0x523F, "MO"),
        (0x5240, 0x525F, "DF"), (0x5260, 0x527F, "TG"),
        (0x5280, 0x529F, "OSL"), (0x52C0, 0x52DF, "TT"),
    ):
        if lo <= value <= hi:
            return tag, value & 0x1F, 0, 0
    # One-shot mod OSM().
    if 0x52A0 <= value <= 0x52BF:
        return "OSM", 0, value & 0x1F, 0
    # Persistent default layer PDF().
    if 0x52E0 <= value <= 0x52FF:
        return "PDF", value & 0x1F, 0, 0
    # Swap-hands tap-hold SH_T().
    if 0x5600 <= value <= 0x56EF:
        return "SH_T", 0, 0, value & 0xFF
    return None


# ---------------------------------------------------------------------------
# Two-line display description — base label + behaviour badge.
#
# describe_keycode() turns a 16-bit keycode into (main_text, badge_text,
# badge_color) so a key tile can show the tap/base key prominently with a small
# coloured badge for the behaviour (held mod, target layer, one-shot, …).
# ---------------------------------------------------------------------------

# Badge colours by behaviour family.
BADGE_COLOR_LAYER = "#FFCC44"   # amber  — layer switches (MO/TO/TG/DF/TT/OSL) & OSM
BADGE_COLOR_TAP = "#66C2FF"     # cyan   — tap/hold duals (LT/MT/SH_T)
BADGE_COLOR_MOD = "#FF9955"     # orange — modified keycodes sent together (LCTL(kc)…)
BADGE_COLOR_FW = "#C792EA"      # violet — firmware-defined (TD/MACRO/PB/KB/USER)

# Compact modifier glyphs for badges.
_MOD_GLYPHS = [(MOD_CTRL, "⌃"), (MOD_SHIFT, "⇧"),
               (MOD_ALT, "⌥"), (MOD_GUI, "⌘")]


def _mod_symbols(mods: int) -> str:
    """Compact modifier glyph string, e.g. 0x12 -> 'R⇧' (right shift)."""
    glyphs = "".join(g for bit, g in _MOD_GLYPHS if mods & bit)
    if not glyphs:
        return "∅"
    return ("R" + glyphs) if (mods & MOD_RIGHT) else glyphs


def describe_keycode(value: int, keycode_to_name: dict):
    """Return (main_text, badge_text, badge_color) for a two-line key tile.

    badge_text is "" (and badge_color None) for plain keys.
    """
    def basic_display(kc: int) -> str:
        name = keycode_to_name.get(kc)
        if name is None:
            name = decompose_keycode(kc, keycode_to_name)
        return create_nice_name(name)

    # Modified keycode (Ctrl+C, RShift+A, …) — main = key, badge = held mods.
    if 0x0100 <= value <= 0x1FFF:
        mods = (value >> 8) & 0x1F
        return basic_display(value & 0xFF), _mod_symbols(mods), BADGE_COLOR_MOD
    # Mod-tap MT() — main = tap key, badge = held mods (cyan = tap/hold dual).
    if 0x2000 <= value <= 0x3FFF:
        mods = (value >> 8) & 0x1F
        return basic_display(value & 0xFF), _mod_symbols(mods), BADGE_COLOR_TAP
    # Layer-tap LT() — main = tap key, badge = hold target layer.
    if 0x4000 <= value <= 0x4FFF:
        layer = (value >> 8) & 0x0F
        return basic_display(value & 0xFF), f"L{layer}", BADGE_COLOR_TAP
    # Layer-mod LM() — main = target layer, badge = mods.
    if 0x5000 <= value <= 0x51FF:
        layer = (value >> 5) & 0x0F
        return f"L{layer}", "LM" + _mod_symbols(value & 0x1F), BADGE_COLOR_LAYER
    # Layer switches MO/TO/DF/TG/OSL/TT — main = target layer, badge = behaviour.
    for lo, hi, tag in (
        (0x5200, 0x521F, "TO"), (0x5220, 0x523F, "MO"),
        (0x5240, 0x525F, "DF"), (0x5260, 0x527F, "TG"),
        (0x5280, 0x529F, "OSL"), (0x52C0, 0x52DF, "TT"),
    ):
        if lo <= value <= hi:
            return f"L{value & 0x1F}", tag, BADGE_COLOR_LAYER
    # One-shot mod OSM() — main = mods, badge = OSM.
    if 0x52A0 <= value <= 0x52BF:
        return _mod_symbols(value & 0x1F), "OSM", BADGE_COLOR_LAYER
    # Persistent default layer PDF().
    if 0x52E0 <= value <= 0x52FF:
        return f"L{value & 0x1F}", "PDF", BADGE_COLOR_LAYER
    # Swap-hands tap-hold SH_T() — tap key / hold swap.
    if 0x5600 <= value <= 0x56EF:
        return basic_display(value & 0xFF), "SH", BADGE_COLOR_TAP
    # Tap dance TD() — firmware-defined dance index.
    if 0x5700 <= value <= 0x57FF:
        return "TD", str(value & 0xFF), BADGE_COLOR_FW

    # Plain key (or anything else) — single line, no badge.
    name = keycode_to_name.get(value)
    if name is None:
        name = decompose_keycode(value, keycode_to_name)
    return create_nice_name(name), "", None
