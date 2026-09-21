"""The pure half of shortcut discovery: accelerator strings in, HID keys out.

Extracted VERBATIM from `tools/shortcut_probe.py`, which now imports it, so the
probe stays a CLI over exactly the code the app runs. That direction matters:
the probe is the only way to measure what an application really exposes, and a
measurement taken against a copy of the parser measures the copy.

Nothing here imports AT-SPI, comtypes or PyQt, so it runs on any platform and is
unit-testable offline -- which is also what lets `shortcut_probe --selftest`
cover both backends' string formats from a machine that has neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pure parsing -- no AT-SPI import needed, so --selftest runs anywhere.
# ---------------------------------------------------------------------------

# GTK accelerator modifier tokens -> QMK modifier bit.
# The keyboard folds right modifiers onto left (fill_overlay.c overlay_mod_variant:
# `mods |= mods >> 4; return mods & 0x0f`), so one nibble is the whole variant:
#   bit0 Ctrl, bit1 Shift, bit2 Alt, bit3 GUI.
MOD_CTRL, MOD_SHIFT, MOD_ALT, MOD_GUI = 0x01, 0x02, 0x04, 0x08

MOD_TOKENS = {
    "control": MOD_CTRL, "ctrl": MOD_CTRL, "primary": MOD_CTRL, "ctl": MOD_CTRL,
    "shift": MOD_SHIFT, "shft": MOD_SHIFT,
    "alt": MOD_ALT, "mod1": MOD_ALT,
    "super": MOD_GUI, "meta": MOD_GUI, "hyper": MOD_GUI, "mod4": MOD_GUI, "win": MOD_GUI,
    # Deliberately mapped to nothing -- present in accel strings, not a PolyKybd variant.
    "mod2": 0, "mod3": 0, "mod5": 0, "lock": 0, "release": 0,
}

MOD_NAMES = ((MOD_CTRL, "Ctrl"), (MOD_SHIFT, "Shift"), (MOD_ALT, "Alt"), (MOD_GUI, "GUI"))

# X11 keysym name -> USB HID usage id, restricted to what the keycaps can draw.
# The displayable set is copy_overlay_to_buffer()'s: 0x04..0x53, 0x64..0x65,
# 0xE0..0xE7 -- letters, digits, punctuation, F1-F12, nav cluster, keypad.
KEYSYM_TO_HID: dict[str, int] = {}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEYSYM_TO_HID[_c] = 0x04 + _i
for _i, _c in enumerate("1234567890"):
    KEYSYM_TO_HID[_c] = 0x1E + _i
KEYSYM_TO_HID.update({
    "Return": 0x28, "Escape": 0x29, "BackSpace": 0x2A, "Tab": 0x2B, "space": 0x2C,
    "minus": 0x2D, "equal": 0x2E, "bracketleft": 0x2F, "bracketright": 0x30,
    "backslash": 0x31, "semicolon": 0x33, "apostrophe": 0x34, "grave": 0x35,
    "comma": 0x36, "period": 0x37, "slash": 0x38,
    "Print": 0x46, "Scroll_Lock": 0x47, "Pause": 0x48,
    "Insert": 0x49, "Home": 0x4A, "Prior": 0x4B, "Page_Up": 0x4B,
    "Delete": 0x4C, "End": 0x4D, "Next": 0x4E, "Page_Down": 0x4E,
    "Right": 0x4F, "Left": 0x50, "Down": 0x51, "Up": 0x52, "Num_Lock": 0x53,
    "less": 0x64, "Menu": 0x65,
})
for _i in range(1, 13):
    KEYSYM_TO_HID[f"F{_i}"] = 0x3A + _i - 1
# Shifted punctuation names: an accel string may spell the produced character.
KEYSYM_TO_HID.update({
    "plus": 0x2E, "underscore": 0x2D, "braceleft": 0x2F, "braceright": 0x30,
    "bar": 0x31, "colon": 0x33, "quotedbl": 0x34, "asciitilde": 0x35,
    "question": 0x38, "exclam": 0x1E, "at": 0x1F, "numbersign": 0x20,
    "dollar": 0x21, "percent": 0x22, "asciicircum": 0x23, "ampersand": 0x24,
    "asterisk": 0x25, "parenleft": 0x26, "parenright": 0x27,
})


def displayable_hid(usage: int | None) -> bool:
    """True when the keyboard has an overlay slot for this HID usage.

    Mirrors copy_overlay_to_buffer() (poly_keymap.c): 0x04..0x53 -> slots 0..79,
    0x64..0x65 -> 80..81, 0xE0..0xE7 -> 82..89.
    """
    if usage is None:
        return False
    return 0x04 <= usage <= 0x53 or 0x64 <= usage <= 0x65 or 0xE0 <= usage <= 0xE7


def pick_binding(raw: str, role: str = "") -> tuple[str | None, str]:
    """Choose the usable accelerator out of an AT-SPI keybinding string.

    AT-SPI returns up to three ';'-delimited parts:
      1. the binding usable only while the object is posted (a menu mnemonic),
      2. the full sequence that posts the menu AND activates the item,
      3. the direct shortcut, which invokes the action with no menu posted.

    Part 3 is what a keycap should advertise, so it wins. When it is empty the
    item has no accelerator at all and only a menu path -- measured on mousepad,
    that is 35 of 67 items, shaped 'm;<Alt>f:m;'. Falling back to part 2 there
    reports a *traversal* ("Alt+F then M") as though it were a shortcut, which no
    keycap can show; a ':' in a candidate is what rules it out.

    The one fallback worth taking is a single chord with no ':' on a `menu` role
    -- a top-level menubar item posts as '<Alt>f;<Alt>f;' and really is one press.

    ROLE IS LOAD-BEARING HERE. A GtkPopover's buttons carry the identical string
    shape ('<Alt>s' on a `push button`), but that is a MNEMONIC that only works
    while the popover is already open -- not something a keycap can advertise.
    Measured on gedit: without the role gate it reports 13 "shortcuts" that are
    all popover mnemonics, while every real accelerator it has (Ctrl+S, Ctrl+O)
    is absent from the tree entirely. Reporting those 13 would turn a true zero
    into a plausible-looking number, which is the worst available outcome.

    Returns (accel_text, kind) where kind is "accelerator" or "menu".
    """
    if not raw:
        return None, ""
    parts = [p.strip() for p in raw.split(";")]
    if len(parts) >= 3 and parts[2]:
        return parts[2], "accelerator"
    if role == "menu":
        for part in parts[:2]:
            if part and "<" in part and ":" not in part:
                return part, "menu"
    return None, ""


@dataclass
class Accel:
    mods: int
    keysym: str
    hid: int | None

    @property
    def displayable(self) -> bool:
        return displayable_hid(self.hid)

    def pretty(self) -> str:
        names = [n for bit, n in MOD_NAMES if self.mods & bit]
        return "+".join(names + [self.keysym])


def parse_accel(text: str) -> Accel | None:
    """Parse a GTK accelerator string such as '<Control><Shift>s' into (mods, key).

    Returns None when there is no key left after the modifiers, which is what a
    bare modifier press or an empty binding looks like.
    """
    if not text:
        return None
    mods = 0
    rest = text.strip()
    while rest.startswith("<"):
        close = rest.find(">")
        if close < 0:
            return None
        token = rest[1:close].strip().lower()
        if token not in MOD_TOKENS:
            return None
        mods |= MOD_TOKENS[token]
        rest = rest[close + 1:].strip()
    if not rest:
        return None
    # A single letter arrives upper- or lower-case depending on toolkit; the HID
    # usage is the same key either way, and Shift is already carried in `mods`.
    keysym = rest
    hid = KEYSYM_TO_HID.get(keysym)
    if hid is None and len(keysym) == 1:
        hid = KEYSYM_TO_HID.get(keysym.lower())
    return Accel(mods=mods, keysym=keysym, hid=hid)


@dataclass
class Shortcut:
    label: str
    role: str
    accel: str
    mods: int
    keysym: str
    hid: int | None
    displayable: bool
    kind: str = "accelerator"
    icon: int | None = None
    icon_name: str = ""
    icon_concept: str = ""
    icon_rule: str = ""
    icon_confidence: float = 0.0
    path: list[str] = field(default_factory=list)
    raw: str = ""

# ---------------------------------------------------------------------------
# Windows backend (UI Automation)
# ---------------------------------------------------------------------------
#
# UIA differs from AT-SPI in three ways that matter here:
#
#  1. AcceleratorKey is a DISPLAY STRING the app authored, not a structured
#     binding -- "Ctrl+Shift+S", and localized ("Strg+Umschalt+S" on a German
#     Windows). So parsing is a heuristic, where the AT-SPI side was exact.
#  2. It is NOT restricted to menus. Toolbar buttons, split buttons and ribbon
#     controls carry it too, so Windows may well beat the Linux menubar ceiling.
#  3. Every property read is a cross-process call. Reading them one at a time
#     over a few thousand elements is seconds of latency, so the whole subtree is
#     fetched with ONE FindAllBuildCache() and read back out of the cache.

# Property ids from UIAutomationClient.h. Read via GetCachedPropertyValue rather
# than the generated Cached* accessors, whose availability depends on the typelib
# comtypes happens to generate on the machine.
UIA_PROP_PROCESS_ID = 30002
UIA_PROP_CONTROL_TYPE = 30003
UIA_PROP_NAME = 30005
UIA_PROP_ACCELERATOR = 30006
UIA_PROP_ACCESS_KEY = 30007
UIA_PROP_CLASS_NAME = 30012

TREESCOPE_SUBTREE = 7

UIA_CONTROL_TYPES = {
    50000: "button", 50001: "calendar", 50002: "check box", 50003: "combo box",
    50004: "edit", 50005: "hyperlink", 50006: "image", 50007: "list item",
    50008: "list", 50009: "menu", 50010: "menu bar", 50011: "menu item",
    50012: "progress bar", 50013: "radio button", 50014: "scroll bar",
    50015: "slider", 50016: "spinner", 50017: "status bar", 50018: "tab",
    50019: "tab item", 50020: "text", 50021: "tool bar", 50022: "tool tip",
    50023: "tree", 50024: "tree item", 50025: "custom", 50026: "group",
    50027: "thumb", 50028: "data grid", 50029: "data item", 50030: "document",
    50031: "split button", 50032: "window", 50033: "pane", 50034: "header",
    50035: "header item", 50036: "table", 50037: "title bar", 50038: "separator",
}

# Control types whose AccessKey is a real one-press binding rather than a
# mnemonic that needs its container already open. Same gate as the AT-SPI
# `role == "menu"` rule, and for the same reason -- see pick_binding().
UIA_MENU_TYPES = {50009, 50010, 50011}

# Modifier names as Windows applications spell them, lower-cased. Longest match
# wins, so "alt gr" is tried before "alt".
WIN_MOD_TOKENS = {
    "ctrl": MOD_CTRL, "control": MOD_CTRL, "ctl": MOD_CTRL,
    "strg": MOD_CTRL,            # de
    "ctrl droite": MOD_CTRL,     # fr
    "shift": MOD_SHIFT, "shft": MOD_SHIFT,
    "umschalt": MOD_SHIFT,       # de
    "maj": MOD_SHIFT,            # fr
    "mayus": MOD_SHIFT, "mayús": MOD_SHIFT,   # es
    "maiusc": MOD_SHIFT,         # it
    "skift": MOD_SHIFT,          # da/no/sv
    "alt": MOD_ALT,
    "win": MOD_GUI, "windows": MOD_GUI, "super": MOD_GUI, "meta": MOD_GUI,
    # AltGr IS Ctrl+Alt on Windows, so it decodes to both bits.
    "alt gr": MOD_CTRL | MOD_ALT, "altgr": MOD_CTRL | MOD_ALT,
    "alt graph": MOD_CTRL | MOD_ALT,
}

WIN_SEPARATORS = "+-"

# Windows key display names -> HID usage. Localized spellings are included where
# they are common; an unknown name simply yields no HID id and is reported as
# undisplayable rather than guessed at.
WINKEY_TO_HID: dict[str, int] = {}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    WINKEY_TO_HID[_c] = 0x04 + _i
for _i, _c in enumerate("1234567890"):
    WINKEY_TO_HID[_c] = 0x1E + _i
for _i in range(1, 13):
    WINKEY_TO_HID[f"f{_i}"] = 0x3A + _i - 1
WINKEY_TO_HID.update({
    "enter": 0x28, "return": 0x28, "eingabe": 0x28, "entrar": 0x28,
    "esc": 0x29, "escape": 0x29, "echap": 0x29,
    "backspace": 0x2A, "bksp": 0x2A, "back": 0x2A, "rücktaste": 0x2A,
    "tab": 0x2B, "tabulator": 0x2B,
    "space": 0x2C, "spacebar": 0x2C, "leertaste": 0x2C, "espace": 0x2C,
    "-": 0x2D, "minus": 0x2D, "_": 0x2D,
    "=": 0x2E, "+": 0x2E, "plus": 0x2E,
    "[": 0x2F, "]": 0x30, "\\": 0x31, ";": 0x33, "'": 0x34, "`": 0x35,
    ",": 0x36, "comma": 0x36, ".": 0x37, "period": 0x37,
    "/": 0x38, "slash": 0x38,
    "prtscn": 0x46, "print screen": 0x46, "printscreen": 0x46, "druck": 0x46,
    "scroll lock": 0x47, "rollen": 0x47,
    "pause": 0x48, "break": 0x48,
    "ins": 0x49, "insert": 0x49, "einfg": 0x49,
    "home": 0x4A, "pos1": 0x4A,
    "pgup": 0x4B, "page up": 0x4B, "pageup": 0x4B, "bild auf": 0x4B,
    "del": 0x4C, "delete": 0x4C, "entf": 0x4C, "suppr": 0x4C,
    "end": 0x4D, "ende": 0x4D, "fin": 0x4D,
    "pgdn": 0x4E, "page down": 0x4E, "pagedown": 0x4E, "bild ab": 0x4E,
    "right": 0x4F, "→": 0x4F, "rechts": 0x4F,
    "left": 0x50, "←": 0x50, "links": 0x50,
    "down": 0x51, "↓": 0x51, "unten": 0x51,
    "up": 0x52, "↑": 0x52, "oben": 0x52,
    "num lock": 0x53, "numlock": 0x53,
    "menu": 0x65, "apps": 0x65,
    # Shifted punctuation, spelled as the produced character. Word's Shrink/Grow
    # Font are Ctrl+Shift+< and Ctrl+Shift+>, which land on the comma/period keys.
    "<": 0x36, ">": 0x37, "?": 0x38, ":": 0x33, '"': 0x34, "~": 0x35,
    "{": 0x2F, "}": 0x30, "|": 0x31, "!": 0x1E, "@": 0x1F, "#": 0x20,
    "$": 0x21, "%": 0x22, "^": 0x23, "&": 0x24, "*": 0x25, "(": 0x26, ")": 0x27,
})

_WIN_MODS_BY_LEN = sorted(WIN_MOD_TOKENS, key=len, reverse=True)


def parse_win_accel(text: str) -> Accel | None:
    """Parse a Windows UIA AcceleratorKey display string such as 'Ctrl+Shift+S'.

    Consumes known modifier tokens from the left, each followed by a separator;
    whatever is left is the key. Doing it that way rather than splitting on '+'
    is what makes 'Ctrl++' work -- split() would hand back an empty final field
    and lose the key, and '+' is a real accelerator (zoom in) in a lot of apps.

    Unlike the AT-SPI side this is a HEURISTIC: the string is authored by the
    application and localized by it, so an unrecognised modifier means the whole
    string is refused rather than silently parsed as a bare key. Reporting
    'Strg+S' as the single key "Strg+S" would be worse than reporting nothing.
    """
    if not text:
        return None
    # A comma separates either an Office KEYTIP SEQUENCE ("Alt, H, Z N" = press
    # Alt, then H, then Z, then N) or a list of ALTERNATE accelerators
    # ("Ctrl+Alt+C, Alt+Ctrl+V"). Taking the first segment handles both: an
    # alternate list yields its first real chord, and a KeyTip yields the bare
    # "Alt", which the bare-modifier guard below already refuses. This is the same
    # distinction the AT-SPI backend draws for "<Alt>f:n" -- a traversal is not a
    # shortcut and no keycap can show one. Measured on Word and Excel, KeyTips
    # were 19 of 32 and 22 of 30 reported bindings.
    rest = text.split(",")[0].strip()
    if not rest:
        return None
    mods = 0
    matched_any = True
    while matched_any and rest:
        matched_any = False
        low = rest.lower()
        for token in _WIN_MODS_BY_LEN:
            if not low.startswith(token):
                continue
            after = rest[len(token):]
            if after[:1] in WIN_SEPARATORS and len(after) > 1:
                mods |= WIN_MOD_TOKENS[token]
                rest = after[1:].strip()
                matched_any = True
                break
    if not rest:
        return None
    key = rest.strip()
    # "Ctrl+Alt" -- the leftover is itself a modifier, so there is no key.
    if key.lower() in WIN_MOD_TOKENS:
        return None
    # "Ctrl+" -- trailing separator, nothing after it. Length guards the case
    # where the key IS the separator, which "Ctrl++" (zoom in) really is.
    if len(key) > 1 and key[-1] in WIN_SEPARATORS:
        return None
    # A leftover that still looks like "Word+Word" carries a modifier this table
    # does not know -- most likely a localization. Refuse it.
    if len(key) > 1 and any(sep in key[:-1] for sep in WIN_SEPARATORS) and " " not in key:
        head = key.split("+")[0].split("-")[0]
        if head and head.lower() not in WINKEY_TO_HID:
            return None
    low = key.lower()
    hid = WINKEY_TO_HID.get(low)
    return Accel(mods=mods, keysym=key, hid=hid)


# Chords the WINDOW MANAGER owns, on every window, in every app. They arrive
# through UIA looking exactly like an application shortcut -- a control with a
# real AcceleratorKey and a real label -- because from the app's point of view
# they ARE controls: the system menu is a menu the app hosts and Windows fills.
#
# Measured on a field daemon_log.txt (2026-09-14): Calculator and Photos each
# reported `Alt+Space 'System'` as their ONLY harvested shortcut, so the
# diagnostic read "1 shortcut(s) harvested" for two apps that expose none. No
# icon was ever drawn for it (no concept matches "System"), so this changes no
# pixels -- it makes the count TRUE, which is what that line is read for.
#
# ⚠️ Keyed on the CHORD, never on the label. "System" is localized -- German
# reports "Systemmenü" -- so a label test would drop these on an English desktop
# and let them through everywhere else, which is the worst of both.
#
# ⚠️ Safe to drop outright rather than merely leave unmatched: Windows
# INTERCEPTS both of these before the focused app sees them, so an application
# cannot usefully bind either one, and a keycap promising otherwise would lie.
# `pick_win_binding`'s existing menu-mnemonic rule catches the OTHER form of the
# same thing (the bare "Space" a system menu reports once it is already open).
WINDOW_MANAGER_CHORDS = frozenset({
    (MOD_ALT, "space"),   # the system menu
    (MOD_ALT, "f4"),      # close window
})


def is_window_manager_chord(mods: int, keysym: str) -> bool:
    """True for a chord the OS owns on every window — see WINDOW_MANAGER_CHORDS."""
    return (mods, (keysym or "").lower()) in WINDOW_MANAGER_CHORDS


def pick_win_binding(accelerator: str, access_key: str,
                     control_type: int) -> tuple[str | None, str]:
    """Choose between an element's AcceleratorKey and its AccessKey.

    AcceleratorKey is the real shortcut and always wins. AccessKey is the
    mnemonic, and is only a one-press binding on a menu-ish control -- exactly
    the distinction the AT-SPI backend draws by role, and the one that stopped
    gedit reporting 13 popover mnemonics as shortcuts.
    """
    if accelerator and accelerator.strip():
        return accelerator.strip(), "accelerator"
    if access_key and access_key.strip() and control_type in UIA_MENU_TYPES:
        return access_key.strip(), "menu"
    return None, ""
