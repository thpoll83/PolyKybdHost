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
    # QK_LAYER_MOD: LM() — 0x5000–0x51FF
    if 0x5000 <= value <= 0x51FF:
        layer = (value >> 4) & 0x0F
        mods = value & 0x0F
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
    # QK_PERSISTENT_DEF_LAYER — 0x52E0–0x52FF
    if 0x52E0 <= value <= 0x52FF:
        return f"DF*({value & 0x1F})"
    # Fall through: look up in full mapping or show hex
    return keycode_to_name.get(value, f"0x{value:04X}")
