#!/usr/bin/env python3
"""Enumerate the keyboard shortcuts a running application exposes over AT-SPI2.

This is a MEASUREMENT tool, not a feature. It answers the one question that
decides whether the keyboard can show app shortcuts without overlay pixmaps:
how many of an application's shortcuts can be discovered automatically, and how
many of those land on a key the keycap displays can actually draw.

Why AT-SPI and not the GTK menu model: GLib documents the D-Bus interface behind
g_dbus_connection_export_menu_model() as a private implementation detail, and the
standard GMenuModel attributes (label/action/target/icon) carry no accelerator --
GTK4 sets accels through gtk_application_set_accels_for_action(), which never
leaves the process. AT-SPI's org.a11y.atspi.Action.GetKeyBinding() carries the
binding explicitly, works under X11 and Wayland, and covers Qt/LibreOffice/
Electron as well as GTK.

There are two backends behind one model: AT-SPI on Linux, UI Automation on
Windows. Only discovery and the accelerator STRING FORMAT differ -- Accel,
displayable_hid(), the HID tables and the report are shared.

    # Linux
    python3 tools/shortcut_probe.py --list
    python3 tools/shortcut_probe.py --app mousepad --json /tmp/mousepad.json

    # Windows (pip install comtypes)
    python tools/shortcut_probe.py --list
    python tools/shortcut_probe.py --focused --json shortcuts.json

    python tools/shortcut_probe.py --selftest      # pure parsers, runs anywhere

Needs the accessibility bus up (org.a11y.Bus) and the app running with its
toolkit bridge active; GTK3 needs libatk-adaptor installed.

MEASURED 2026-09-09, Ubuntu 24.04 under Xvfb + at-spi-bus-launcher:

    mousepad 0.6      (GTK3, classic GtkMenuBar)   26 accelerators, 32/32 displayable
    gedit 46          (GTK3, GMenu + headerbar)     0
    gnome-text-editor (GTK4)                        0

The cliff is NOT GTK3 vs GTK4 -- it is a classic menubar vs everything modern.
An app with a real GtkMenuBar exposes its whole accelerator set, and every one
of them landed on a keycap slot. An app whose menu lives in a hamburger popover
exposes nothing: gedit's tree has no accelerator at all (its real Ctrl+S/Ctrl+O
are absent), and GTK4 answers "<VoidSymbol>" -- X11's "no key" -- for all 84
keybindings across 61 of its 65 nodes, with no menu-role node anywhere.

So on Linux this discovers shortcuts for legacy-menubar apps only. Treat that
as the ceiling when deciding whether it is worth a HID command.

WINDOWS IS UNMEASURED AND THE UIA BACKEND IS UNRUN. It was written without a
Windows machine to test on, so the pure parsers below are selftested (46 cases,
including real localized strings) but uia_shortcuts()/main_uia() have never
executed. Expect to debug them on first contact. There are two reasons to think
Windows scores better than the Linux numbers above -- classic menubars are far
more common, and UIA exposes AcceleratorKey on toolbar and ribbon controls
rather than only on menus -- but that is an expectation, not a measurement, and
Windows is the platform that decides this feature.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field

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
    icon_concept: str = ""
    icon_rule: str = ""
    icon_confidence: float = 0.0
    path: list[str] = field(default_factory=list)
    raw: str = ""


# ---------------------------------------------------------------------------
# Self-test of the pure half
# ---------------------------------------------------------------------------

def selftest() -> int:
    cases: list[tuple[str, object, object]] = []

    def check(name, got, want):
        cases.append((name, got, want))

    # Fixtures below are REAL AT-SPI strings captured from mousepad 0.6, not
    # invented -- the traversal case is what a hand-written fixture missed.
    check("direct shortcut wins", pick_binding("n;<Alt>f:n;<Primary>n"),
          ("<Primary>n", "accelerator"))
    check("menu traversal is not a shortcut", pick_binding("m;<Alt>f:m;"), (None, ""))
    check("deep traversal is not a shortcut", pick_binding("h;<Alt>f:e:h;"), (None, ""))
    check("top-level menu post kept", pick_binding("<Alt>f;<Alt>f;", "menu"),
          ("<Alt>f", "menu"))
    # Real gedit string: same shape, but a popover button, so it is a mnemonic.
    check("popover mnemonic rejected", pick_binding("<Alt>s;<Alt>s;", "push button"),
          (None, ""))
    check("popover checkbox rejected", pick_binding("<Alt>f;<Alt>f;", "check box"),
          (None, ""))
    check("accelerator ignores role", pick_binding("s;;<Primary>s", "push button"),
          ("<Primary>s", "accelerator"))
    check("bare mnemonic dropped", pick_binding("S;;", "menu item"), (None, ""))
    check("empty string", pick_binding("", "menu"), (None, ""))

    a = parse_accel("<Control><Shift>s")
    check("ctrl+shift mods", a.mods, MOD_CTRL | MOD_SHIFT)
    check("ctrl+shift key", a.hid, 0x16)
    check("primary is ctrl", parse_accel("<Primary>c").mods, MOD_CTRL)
    check("super is gui", parse_accel("<Super>l").mods, MOD_GUI)
    check("named key", parse_accel("<Control>Page_Up").hid, 0x4B)
    check("function key", parse_accel("F5").hid, 0x3E)
    check("bare modifier is not an accel", parse_accel("<Control>"), None)
    check("unknown token refused", parse_accel("<Frobnicate>x"), None)
    check("uppercase letter folds", parse_accel("<Control>S").hid, 0x16)
    check("unknown keysym has no hid", parse_accel("<Control>Ediacaran").hid, None)
    check("pretty", parse_accel("<Control><Alt>Delete").pretty(), "Ctrl+Alt+Delete")

    # --- Windows / UIA parser -------------------------------------------------
    w = parse_win_accel("Ctrl+Shift+S")
    check("win ctrl+shift", w.mods, MOD_CTRL | MOD_SHIFT)
    check("win ctrl+shift key", w.hid, 0x16)
    check("win function key", parse_win_accel("F5").hid, 0x3E)
    check("win alt+f4", parse_win_accel("Alt+F4").mods, MOD_ALT)
    # The case that rules out splitting on "+": zoom-in is genuinely Ctrl++.
    check("win ctrl++ key", parse_win_accel("Ctrl++").keysym, "+")
    check("win ctrl++ mods", parse_win_accel("Ctrl++").mods, MOD_CTRL)
    check("win ctrl++ hid", parse_win_accel("Ctrl++").hid, 0x2E)
    check("win german", parse_win_accel("Strg+Umschalt+S").mods, MOD_CTRL | MOD_SHIFT)
    check("win french", parse_win_accel("Ctrl+Maj+S").mods, MOD_CTRL | MOD_SHIFT)
    check("win german key name", parse_win_accel("Strg+Entf").hid, 0x4C)
    check("win altgr is ctrl+alt", parse_win_accel("AltGr+E").mods, MOD_CTRL | MOD_ALT)
    check("win pgup", parse_win_accel("Ctrl+PgUp").hid, 0x4B)
    check("win win key", parse_win_accel("Win+V").mods, MOD_GUI)
    check("win bare modifier refused", parse_win_accel("Ctrl+Alt"), None)
    check("win trailing separator refused", parse_win_accel("Ctrl+"), None)
    check("win unknown localization refused", parse_win_accel("Ctrl+Grupp+S"), None)
    check("win empty", parse_win_accel(""), None)
    check("win unknown key has no hid", parse_win_accel("Ctrl+Ediacaran").hid, None)

    # Real strings captured from Word and Excel on Windows.
    check("keytip sequence refused", parse_win_accel("Alt, H, Z N"), None)
    check("short keytip refused", parse_win_accel("Alt, Q"), None)
    check("alternate accelerators take the first",
          parse_win_accel("Ctrl+Alt+C, Alt+Ctrl+V").keysym, "C")
    check("alternate accelerators mods",
          parse_win_accel("Ctrl+Alt+C, Alt+Ctrl+V").mods, MOD_CTRL | MOD_ALT)
    check("shrink font punctuation", parse_win_accel("Ctrl+Shift+<").hid, 0x36)
    check("grow font punctuation", parse_win_accel("Ctrl+Shift+>").hid, 0x37)
    check("word superscript", parse_win_accel("Ctrl+Shift++").hid, 0x2E)
    check("word subscript", parse_win_accel("Ctrl+Shift+_").hid, 0x2D)

    check("uia accelerator wins", pick_win_binding("Ctrl+S", "Alt+F", 50000),
          ("Ctrl+S", "accelerator"))
    check("uia menubar access key kept", pick_win_binding("", "Alt+F", 50011),
          ("Alt+F", "menu"))
    # The gedit lesson, on the other platform: a button mnemonic is not a shortcut.
    check("uia button mnemonic dropped", pick_win_binding("", "Alt+S", 50000),
          (None, ""))
    check("uia nothing", pick_win_binding("", "", 50011), (None, ""))

    check("letter displayable", displayable_hid(0x04), True)
    check("gap not displayable", displayable_hid(0x60), False)
    check("modifier slot displayable", displayable_hid(0xE3), True)
    check("None not displayable", displayable_hid(None), False)

    failed = [(n, g, w) for n, g, w in cases if g != w]
    for name, got, want in failed:
        print(f"FAIL {name}: got {got!r}, want {want!r}")
    print(f"selftest: {len(cases) - len(failed)}/{len(cases)} passed")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# AT-SPI traversal
# ---------------------------------------------------------------------------

def _atspi():
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    return Atspi


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def walk(node, atspi, budget: list[int], depth: int = 0, path: tuple[str, ...] = ()):
    """Yield (accessible, role_name, path) over the subtree, bounded by `budget`.

    The budget is a shared mutable counter rather than a depth limit: an app's
    accessible tree can be tens of thousands of nodes and every child access is a
    D-Bus round trip, so the cost has to be capped globally, not per branch.
    """
    if budget[0] <= 0 or depth > 24:
        return
    budget[0] -= 1
    role = _safe(node.get_role_name, "") or ""
    name = _safe(node.get_name, "") or ""
    yield node, role, path
    count = _safe(node.get_child_count, 0) or 0
    here = path + (name or f"<{role}>",)
    for i in range(count):
        child = _safe(lambda i=i: node.get_child_at_index(i))
        if child is None:
            continue
        yield from walk(child, atspi, budget, depth + 1, here)


def shortcuts_for(app, atspi, budget: list[int]) -> list[Shortcut]:
    found: list[Shortcut] = []
    seen: set[tuple[int, str]] = set()
    for node, role, path in walk(app, atspi, budget):
        action = _safe(node.get_action_iface)
        if action is None:
            continue
        n = _safe(action.get_n_actions, 0) or 0
        for i in range(n):
            raw = _safe(lambda i=i: action.get_key_binding(i), "") or ""
            accel_text, kind = pick_binding(raw, role)
            if not accel_text:
                continue
            accel = parse_accel(accel_text)
            if accel is None:
                continue
            label = (_safe(node.get_name, "") or "").strip()
            key = (accel.mods, accel.keysym)
            if key in seen:
                continue
            seen.add(key)
            found.append(Shortcut(
                label=label, role=role, accel=accel.pretty(), mods=accel.mods,
                keysym=accel.keysym, hid=accel.hid, displayable=accel.displayable,
                kind=kind, path=list(path), raw=raw,
            ))
    return found


def list_apps(atspi) -> list[tuple[int, str]]:
    desktop = atspi.get_desktop(0)
    out = []
    for i in range(desktop.get_child_count()):
        child = _safe(lambda i=i: desktop.get_child_at_index(i))
        if child is None:
            continue
        out.append((i, _safe(child.get_name, "") or "<unnamed>"))
    return out


def _icon_matcher():
    """polyhost.services.shortcut_icons, if this checkout has it."""
    try:
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root not in sys.path:
            sys.path.insert(0, root)
        from polyhost.services import shortcut_icons
        return shortcut_icons
    except Exception:
        return None


def report(name: str, shortcuts: list[Shortcut], nodes_used: int,
           icons=None) -> dict:
    usable = [s for s in shortcuts if s.displayable]
    accels = [s for s in shortcuts if s.kind == "accelerator"]
    menus = [s for s in shortcuts if s.kind == "menu"]
    ok_accels = [s for s in accels if s.displayable]
    print(f"\n=== {name} ===")
    print(f"{len(accels)} accelerator(s) + {len(menus)} menu post(s) "
          f"= {len(shortcuts)} total; {len(usable)} displayable "
          f"({len(ok_accels)} of them real accelerators)  [{nodes_used} nodes]")
    matched = 0
    unmatched: list[dict] = []
    if shortcuts:
        width = max(len(s.accel) for s in shortcuts)
        print()
        for s in sorted(shortcuts, key=lambda s: (not s.displayable, s.accel)):
            mark = " " if s.displayable else "x"
            hid = f"0x{s.hid:02X}" if s.hid is not None else "  -- "
            icon = ""
            if icons is not None:
                m = icons.match(s.label)
                if m is None and not icons.suppressed(s.label):
                    unmatched.append({"label": s.label.strip(), "accel": s.accel})
                if m is not None:
                    matched += 1
                    s.icon = m.codepoint
                    s.icon_concept = m.concept
                    s.icon_rule = m.rule
                    s.icon_confidence = m.confidence
                    icon = f"  {m.char} U+{m.codepoint:04X} {m.concept}/{m.rule}"
                else:
                    icon = "  -"
            print(f" {mark} {s.accel:<{width}}  {hid}  "
                  f"{s.label[:34]:<34} [{s.role}]{icon}")
        undisplayable = [s for s in shortcuts if not s.displayable]
        if undisplayable:
            print(f"\n  x = no keycap slot: {', '.join(sorted({s.keysym for s in undisplayable}))}")
    return {
        "app": name,
        "total": len(shortcuts),
        "accelerators": len(accels),
        "menu_posts": len(menus),
        "displayable_accelerators": len(ok_accels),
        "icon_matches": matched,
        "unmatched_labels": unmatched,
        "displayable": len(usable),
        "nodes_walked": nodes_used,
        "shortcuts": [asdict(s) for s in shortcuts],
    }


def main_atspi(args) -> list[dict] | None:
    try:
        atspi = _atspi()
    except Exception as exc:
        print(f"AT-SPI unavailable: {exc}", file=sys.stderr)
        print("Needs python3-gi + gir1.2-atspi-2.0, and the a11y bus running.",
              file=sys.stderr)
        return None

    atspi.init()
    apps = list_apps(atspi)
    if args.list or (not args.app and not args.all):
        print(f"{len(apps)} application(s) on the accessibility bus:")
        for i, name in apps:
            print(f"  [{i}] {name}")
        if not args.list:
            print("\nPass --app NAME or --all to probe.")
        return []

    desktop = atspi.get_desktop(0)
    targets = []
    for i, name in apps:
        if args.all or (args.app and args.app.lower() in name.lower()):
            targets.append((i, name))
    if not targets:
        print(f"no application matching {args.app!r}; try --list", file=sys.stderr)
        return None

    results = []
    for i, name in targets:
        app = desktop.get_child_at_index(i)
        budget = [args.max_nodes]
        found = shortcuts_for(app, atspi, budget)
        results.append(report(name, found, args.max_nodes - budget[0],
                              icons=_icon_matcher() if args.icons else None))
    return results

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


def _uia():
    import comtypes.client
    module = comtypes.client.GetModule("UIAutomationCore.dll")
    iuia = comtypes.client.CreateObject(
        "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CLSID_CUIAutomation
        interface=module.IUIAutomation,
    )
    return module, iuia


def _cached(element, prop_id, default=""):
    try:
        value = element.GetCachedPropertyValue(prop_id)
    except Exception:
        return default
    return default if value is None else value


def uia_shortcuts(iuia, root, cache_request) -> tuple[list[Shortcut], int]:
    """Fetch the whole subtree in ONE cross-process call, then read the cache."""
    found: list[Shortcut] = []
    seen: set[tuple[int, str]] = set()
    elements = root.FindAllBuildCache(
        TREESCOPE_SUBTREE, iuia.CreateTrueCondition(), cache_request)
    count = elements.Length
    for i in range(count):
        el = elements.GetElement(i)
        accel_raw = str(_cached(el, UIA_PROP_ACCELERATOR))
        access_raw = str(_cached(el, UIA_PROP_ACCESS_KEY))
        if not accel_raw.strip() and not access_raw.strip():
            continue
        ctype = int(_cached(el, UIA_PROP_CONTROL_TYPE, 0) or 0)
        text, kind = pick_win_binding(accel_raw, access_raw, ctype)
        if not text:
            continue
        accel = parse_win_accel(text)
        if accel is None:
            continue
        # A menu AccessKey carrying no modifier is the mnemonic used once the menu
        # is already open -- Word's System menu reports "Space" that way while its
        # real binding is Alt+Space. Same rule as the AT-SPI role gate: only a
        # chord is a one-press binding.
        if kind == "menu" and accel.mods == 0:
            continue
        key = (accel.mods, accel.keysym.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(Shortcut(
            label=str(_cached(el, UIA_PROP_NAME)).strip(),
            role=UIA_CONTROL_TYPES.get(ctype, f"type {ctype}"),
            accel=accel.pretty(), mods=accel.mods, keysym=accel.keysym,
            hid=accel.hid, displayable=accel.displayable, kind=kind,
            raw=accel_raw or access_raw,
        ))
    return found, count


def main_uia(args) -> list[dict] | None:
    try:
        module, iuia = _uia()
    except Exception as exc:
        print(f"UI Automation unavailable: {exc}", file=sys.stderr)
        print("Needs Windows and `pip install comtypes`.", file=sys.stderr)
        return None

    cache_request = iuia.CreateCacheRequest()
    for prop in (UIA_PROP_NAME, UIA_PROP_CONTROL_TYPE, UIA_PROP_ACCELERATOR,
                 UIA_PROP_ACCESS_KEY, UIA_PROP_PROCESS_ID):
        cache_request.AddProperty(prop)

    desktop = iuia.GetRootElement()
    walker = iuia.ControlViewWalker
    windows = []
    child = walker.GetFirstChildElement(desktop)
    while child:
        name = ""
        try:
            name = child.CurrentName or ""
        except Exception:
            pass
        if name.strip():
            windows.append((name, child))
        child = walker.GetNextSiblingElement(child)

    if args.list or (not args.app and not args.all and not args.focused):
        print(f"{len(windows)} top-level window(s):")
        for i, (name, _) in enumerate(windows):
            print(f"  [{i}] {name}")
        if not args.list:
            print("\nPass --app NAME, --focused or --all to probe.")
        return []

    if args.focused:
        try:
            el = iuia.GetFocusedElement()
        except Exception as exc:
            print(f"cannot read the focused element: {exc}", file=sys.stderr)
            return None
        # Walk up to the top-level window that owns the focus.
        top = el
        while True:
            parent = walker.GetParentElement(top)
            if parent is None or iuia.CompareElements(parent, desktop):
                break
            top = parent
        targets = [(str(getattr(top, "CurrentName", "") or "<focused>"), top)]
    else:
        targets = [(n, e) for n, e in windows
                   if args.all or (args.app and args.app.lower() in n.lower())]

    if not targets:
        print(f"no window matching {args.app!r}; try --list", file=sys.stderr)
        return None

    results = []
    for name, element in targets:
        try:
            found, count = uia_shortcuts(iuia, element, cache_request)
        except Exception as exc:
            print(f"  {name}: subtree fetch failed ({exc})", file=sys.stderr)
            continue
        results.append(report(name, found, count,
                              icons=_icon_matcher() if args.icons else None))
    return results


# ---------------------------------------------------------------------------
# Entry point -- picks the backend for the platform
# ---------------------------------------------------------------------------

def merge_unmatched(path: str, results: list[dict]) -> int:
    """Accumulate the labels that produced no icon, across runs and applications.

    A running tally rather than a snapshot: the value of the log is knowing which
    label is worth a hint, and that is a question about FREQUENCY across the apps
    you actually use, not about any single probe.
    """
    log = {"labels": {}}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                log = json.load(fh) or log
        except (OSError, ValueError):
            pass          # a corrupt log must not cost the run
    labels = log.setdefault("labels", {})
    added = 0
    for result in results:
        app = result.get("app", "?")
        for item in result.get("unmatched_labels", []):
            key = item["label"].strip().lower()
            if not key:
                continue
            entry = labels.setdefault(key, {"count": 0, "apps": [],
                                            "raw": [], "accels": []})
            entry["count"] += 1
            added += 1
            for field_name, value in (("apps", app), ("raw", item["label"]),
                                      ("accels", item["accel"])):
                if value and value not in entry[field_name]:
                    entry[field_name].append(value)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2, sort_keys=True)
    return added


def review_unmatched(path: str) -> int:
    """Print the accumulated log by frequency, with a stub for the hint file."""
    try:
        with open(path, encoding="utf-8") as fh:
            labels = (json.load(fh) or {}).get("labels", {})
    except (OSError, ValueError) as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1
    if not labels:
        print(f"{path}: nothing to review")
        return 0
    ranked = sorted(labels.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    width = min(34, max(len(k) for k in labels))
    print(f"{len(ranked)} label(s) with no icon, most frequent first:\n")
    for key, entry in ranked:
        apps = ", ".join(entry["apps"][:3])
        accels = ", ".join(entry["accels"][:2])
        print(f"  {entry['count']:>3}x  {key[:width]:<{width}}  {accels:<20} [{apps}]")
    print("\nPaste into polyhost/res/shortcut_hints.yaml under `hints:`,")
    print("giving each a concept name, a U+XXXX codepoint, or `text`:\n")
    for key, _ in ranked:
        print(f'  "{key}": text')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app", help="application/window name to probe (substring match)")
    ap.add_argument("--all", action="store_true", help="probe every application")
    ap.add_argument("--focused", action="store_true",
                    help="probe the focused window (Windows backend only)")
    ap.add_argument("--list", action="store_true", help="list targets and exit")
    ap.add_argument("--json", help="write the full result to this path")
    ap.add_argument("--max-nodes", type=int, default=20000,
                    help="AT-SPI node budget per application (default 20000)")
    ap.add_argument("--backend", choices=("auto", "atspi", "uia"), default="auto",
                    help="force a backend instead of choosing by platform")
    ap.add_argument("--icons", action="store_true",
                    help="map each label to a keycap glyph via shortcut_icons")
    ap.add_argument("--unmatched", metavar="PATH",
                    help="accumulate labels that produced no icon into this JSON log")
    ap.add_argument("--review", metavar="PATH",
                    help="print an accumulated --unmatched log by frequency and exit")
    ap.add_argument("--selftest", action="store_true", help="run the pure-parser tests")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.review:
        return review_unmatched(args.review)
    if args.unmatched:
        args.icons = True          # nothing to collect without the matcher

    backend = args.backend
    if backend == "auto":
        backend = "uia" if sys.platform == "win32" else "atspi"
    if args.focused and backend != "uia":
        print("--focused is only implemented for the UIA backend", file=sys.stderr)
        return 2

    results = main_uia(args) if backend == "uia" else main_atspi(args)
    if results is None:
        return 1
    if not results:
        return 0

    total = sum(r["total"] for r in results)
    usable = sum(r["displayable"] for r in results)
    accels = sum(r["accelerators"] for r in results)
    print(f"\nTOTAL: {total} shortcut(s) ({accels} real accelerators), "
          f"{usable} displayable on the keycaps  [backend: {backend}]")
    if args.icons:
        icons_hit = sum(r.get("icon_matches", 0) for r in results)
        pct = (100.0 * icons_hit / total) if total else 0.0
        print(f"ICONS: {icons_hit}/{total} labels mapped to a glyph ({pct:.0f}%); "
              f"the rest would draw their label text")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        print(f"wrote {args.json}")
    if args.unmatched:
        added = merge_unmatched(args.unmatched, results)
        print(f"logged {added} unmatched label(s) to {args.unmatched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
