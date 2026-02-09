import pathlib
import re
from pathlib import Path

HEADER_FILE = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "keycodes.h"


def parse_qmk_keycodes(header_path: Path) -> dict[str, int]:
    """Parse QMK keycode enum from the qmk header file and return dict of keycode names to hex values."""
    text = header_path.read_text(encoding="utf-8", errors="ignore")

    enum_match = re.search(
        r'enum\s+qk_keycode_defines\s*\{(.*?)\};',
        text,
        re.S,
    )
    if not enum_match:
        raise RuntimeError("qk_keycode_defines enum not found")

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


def categorize(keycode: str) -> str:
    """Categorize a keycode into a functional group (Modifiers, Media, RGB, etc.)."""
    name = keycode[3:] if keycode.startswith("KC_") else keycode

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


def create_nice_name(keycode) -> str:
    """Convert keycode to a display-friendly name with abbreviated terms and line breaks."""
    caption = keycode[3:] if keycode[2] == '_' else keycode
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
    if caption.startswith("MIDI") and len(keycode) > 11:
        caption = caption[5:]
    if caption.startswith("MAGIC") and len(keycode) > 11:
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