from enum import IntEnum, IntFlag
import pathlib
import re
from pathlib import Path
from typing import Tuple

HEADER_FILE = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "keycodes.h"


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

        # Match: KC_A = 0x0004,
        m = re.match(
            r'([A-Z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+)',
            line
        )

        if m:
            entries[m.group(1)] = int(m.group(2), 16)

    return entries


def parse_qmk_keycodes(header_path: Path) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    return parse_qmk_keycode_header(header_path, "qk_keycode_defines")


def parse_qmk_ranges(header_path: Path) -> list:
    ranges = parse_qmk_keycode_header(header_path, "qk_keycode_ranges")
    range_pairs = []
    sorted_items = sorted(ranges.items(), key=lambda x: x[1])
    
    i = 0
    while i < len(sorted_items):
        name, value = sorted_items[i]
        
        # Look for corresponding _MAX
        if not name.endswith('_MAX'):
            # Find the next _MAX or the item before next range start
            range_start = value
            range_name = name
            
            # Look ahead for _MAX
            max_name = name + '_MAX'
            if max_name in self.ranges:
                range_end = self.ranges[max_name]
                range_pairs.append((range_name, range_start, range_end))
            else:
                # Single value range
                range_pairs.append((range_name, range_start, range_start))
        
        i += 1
    
    return range_pairs


def match_qmk_range(range_pairs: list, keycode: int) -> Tuple[str, int, int] | None:
    """
    Find which range a keycode belongs to.
    Returns (range_name, range_start, range_end) or None
    """
    
    for name, start, end in range_pairs:
        if start <= keycode <= end:
            return (name, start, end)
    
    return None

def categorize(key_name: str) -> str:
    """Categorize a key_name into a functional group (Modifiers, Media, RGB, etc.)."""
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


def create_nice_name(key_name) -> str:
    """Convert key_name to a display-friendly name with abbreviated terms and line breaks."""
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


# IntEnum for key types (top bits)
class KeyType(IntEnum):
    KC_BASE = 0   # plain key
    MO = 1        # momentary layer
    TG = 2        # toggle layer
    TO = 3        # set default layer
    LT = 4        # layer-tap (layer + key)
    MT = 5        # mod-tap (modifiers + key)
    # Add more types as needed

# IntFlag for modifiers (useful for MT)
class Mod(IntFlag):
    NONE = 0
    LCTL = 1 << 0
    LSFT = 1 << 1
    LALT = 1 << 2
    LGUI = 1 << 3
    RCTL = 1 << 4
    RSFT = 1 << 5
    RALT = 1 << 6
    RGUI = 1 << 7

# Config describing a hypothetical 16-bit layout:
# [type (4 bits)] [layer (4 bits)] [key (8 bits)]
CONFIG = {
    "total_bits": 16,
    "key_bits": 8,
    "layer_bits": 4,
    "type_bits": 4,
    "mt_mod_bits": 4,  # if MT uses the layer_bits as modifier bitmask in your encoding
}

def decompose_keycode(value, keycode_to_name, cfg=CONFIG):
    key_mask = (1 << cfg["key_bits"]) - 1
    layer_mask = (1 << cfg["layer_bits"]) - 1
    type_mask = (1 << cfg["type_bits"]) - 1

    key = value & key_mask
    layer = (value >> cfg["key_bits"]) & layer_mask
    typ_val = (value >> (cfg["key_bits"] + cfg["layer_bits"])) & type_mask

    # Safely convert to KeyType
    try:
        typ = KeyType(typ_val)
    except ValueError:
        typ = None

    if key in keycode_to_name:
        base_kc = keycode_to_name[key]
    else:
        base_kc = f"0x{key:02X}"

    if typ is KeyType.KC_BASE or typ is None:
        return base_kc
    elif typ is KeyType.MO:
        return f"MO({layer})"
    elif typ is KeyType.TG:
        return f"TG({layer})"
    elif typ is KeyType.TO:
        return f"TO({layer})"
    elif typ is KeyType.LT:
        return f"LT({layer}, {base_kc})"
    elif typ is KeyType.MT:
        # Interpret 'layer' bits as a mod bitmask for this example.
        mod_mask = layer  # adapt if mods live elsewhere
        mods = Mod(mod_mask)
        # Build human-readable mod string (e.g., "LCTL|LSFT")
        if mods == Mod.NONE:
            mod_str = "MOD_NONE"
        else:
            mod_str = "|".join([m.name for m in Mod if m in mods and m != Mod.NONE])
        return f"MT({mod_str}, {base_kc})"
    else:
        return f"TYPE_{typ_val}({layer},{base_kc})"

def compose_keycode(typ: KeyType, layer: int, key: int, cfg=CONFIG):
    return (int(typ) << (cfg["key_bits"] + cfg["layer_bits"])) | (layer << cfg["key_bits"]) | key
