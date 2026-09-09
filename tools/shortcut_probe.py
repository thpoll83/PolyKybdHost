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

Run it against a running app:

    python3.12 tools/shortcut_probe.py --list
    python3.12 tools/shortcut_probe.py --app mousepad --json /tmp/mousepad.json
    python3.12 tools/shortcut_probe.py --all

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

So this discovers shortcuts for legacy-menubar apps only. Treat that as the
ceiling when deciding whether it is worth a HID command.
"""

from __future__ import annotations

import argparse
import json
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


def report(name: str, shortcuts: list[Shortcut], nodes_used: int) -> dict:
    usable = [s for s in shortcuts if s.displayable]
    accels = [s for s in shortcuts if s.kind == "accelerator"]
    menus = [s for s in shortcuts if s.kind == "menu"]
    ok_accels = [s for s in accels if s.displayable]
    print(f"\n=== {name} ===")
    print(f"{len(accels)} accelerator(s) + {len(menus)} menu post(s) "
          f"= {len(shortcuts)} total; {len(usable)} displayable "
          f"({len(ok_accels)} of them real accelerators)  [{nodes_used} nodes]")
    if shortcuts:
        width = max(len(s.accel) for s in shortcuts)
        print()
        for s in sorted(shortcuts, key=lambda s: (not s.displayable, s.accel)):
            mark = " " if s.displayable else "x"
            hid = f"0x{s.hid:02X}" if s.hid is not None else "  -- "
            print(f" {mark} {s.accel:<{width}}  {hid}  {s.label[:40]:<40} [{s.role}]")
        undisplayable = [s for s in shortcuts if not s.displayable]
        if undisplayable:
            print(f"\n  x = no keycap slot: {', '.join(sorted({s.keysym for s in undisplayable}))}")
    return {
        "app": name,
        "total": len(shortcuts),
        "accelerators": len(accels),
        "menu_posts": len(menus),
        "displayable_accelerators": len(ok_accels),
        "displayable": len(usable),
        "nodes_walked": nodes_used,
        "shortcuts": [asdict(s) for s in shortcuts],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--app", help="application name to probe (substring match)")
    ap.add_argument("--all", action="store_true", help="probe every application")
    ap.add_argument("--list", action="store_true", help="list applications and exit")
    ap.add_argument("--json", help="write the full result to this path")
    ap.add_argument("--max-nodes", type=int, default=20000,
                    help="node budget per application (default 20000)")
    ap.add_argument("--selftest", action="store_true", help="run the pure-parser tests")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    try:
        atspi = _atspi()
    except Exception as exc:
        print(f"AT-SPI unavailable: {exc}", file=sys.stderr)
        print("Needs python3-gi + gir1.2-atspi-2.0, and the a11y bus running.",
              file=sys.stderr)
        return 2

    atspi.init()
    apps = list_apps(atspi)
    if args.list or (not args.app and not args.all):
        print(f"{len(apps)} application(s) on the accessibility bus:")
        for i, name in apps:
            print(f"  [{i}] {name}")
        if not args.list:
            print("\nPass --app NAME or --all to probe.")
        return 0

    desktop = atspi.get_desktop(0)
    targets = []
    for i, name in apps:
        if args.all or (args.app and args.app.lower() in name.lower()):
            targets.append((i, name))
    if not targets:
        print(f"no application matching {args.app!r}; try --list", file=sys.stderr)
        return 1

    results = []
    for i, name in targets:
        app = desktop.get_child_at_index(i)
        budget = [args.max_nodes]
        found = shortcuts_for(app, atspi, budget)
        results.append(report(name, found, args.max_nodes - budget[0]))

    total = sum(r["total"] for r in results)
    usable = sum(r["displayable"] for r in results)
    print(f"\nTOTAL: {total} shortcut(s), {usable} displayable on the keycaps")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
