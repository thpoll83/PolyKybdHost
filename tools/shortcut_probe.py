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

Watch mode runs unattended for as long as you leave it, probing whichever window
has focus and logging the labels that got no icon. That log is what grows
res/shortcut_hints.yaml: which labels deserve a glyph is a question about the
apps you actually use, and a day of ordinary work answers it better than a guess.
A label counts once per window VISIT, not once per probe, so the ranking reflects
how often you meet it rather than how long a window sat in the foreground.

    python tools/shortcut_probe.py --watch --unmatched unmatched.json
    ...work all day, then Ctrl+C...
    python tools/shortcut_probe.py --review unmatched.json

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
Windows machine to test on, so the pure parsers below are selftested (54 cases,
including real localized strings) but uia_shortcuts()/main_uia() have never
executed. Expect to debug them on first contact. There are two reasons to think
Windows scores better than the Linux numbers above -- classic menubars are far
more common, and UIA exposes AcceleratorKey on toolbar and ribbon controls
rather than only on menus -- but that is an expectation, not a measurement, and
Windows is the platform that decides this feature.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import time
import sys
from dataclasses import dataclass, asdict, field


# ---------------------------------------------------------------------------
# The model and both backends now live in the APP, not here
# ---------------------------------------------------------------------------
#
# ⚠️ This file is a CLI over polyhost/services/shortcut_source/, not a second
# implementation of it. The probe is the only way to measure what an application
# really exposes, and a measurement taken against a copy of the parser measures
# the copy -- so when Phase 2 wired the harvest into the app, the code moved and
# the probe started importing it. Everything below (the report, the watch loop,
# the curation review) is probe-only and stayed.

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost.services.shortcut_source.atspi import (  # noqa: E402
    _atspi, _safe, list_apps, shortcuts_for, walk)
from polyhost.services.shortcut_source.model import (  # noqa: E402,F401
    Accel, MOD_ALT, MOD_CTRL, MOD_GUI, MOD_NAMES, MOD_SHIFT, MOD_TOKENS,
    KEYSYM_TO_HID, Shortcut, TREESCOPE_SUBTREE, UIA_CONTROL_TYPES,
    UIA_MENU_TYPES, UIA_PROP_ACCELERATOR, UIA_PROP_ACCESS_KEY,
    UIA_PROP_CLASS_NAME, UIA_PROP_CONTROL_TYPE, UIA_PROP_NAME,
    UIA_PROP_PROCESS_ID, WINKEY_TO_HID, WIN_MOD_TOKENS, WIN_SEPARATORS,
    displayable_hid, parse_accel, parse_win_accel, pick_binding,
    pick_win_binding)
from polyhost.services.shortcut_source.uia import (  # noqa: E402
    _cached, _uia, uia_shortcuts)



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
           icons=None, quiet: bool = False) -> dict:
    usable = [s for s in shortcuts if s.displayable]
    accels = [s for s in shortcuts if s.kind == "accelerator"]
    menus = [s for s in shortcuts if s.kind == "menu"]
    ok_accels = [s for s in accels if s.displayable]
    if not quiet:
        print(f"\n=== {name} ===")
        print(f"{len(accels)} accelerator(s) + {len(menus)} menu post(s) "
              f"= {len(shortcuts)} total; {len(usable)} displayable "
              f"({len(ok_accels)} of them real accelerators)  [{nodes_used} nodes]")
    matched = 0
    unmatched: list[dict] = []
    if shortcuts:
        width = max(len(s.accel) for s in shortcuts)
        if not quiet:
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
                    s.icon_name = m.icon
                    s.icon_concept = m.concept
                    s.icon_rule = m.rule
                    s.icon_confidence = m.confidence
                    # ⚠️ A catalog-only concept has NO codepoint -- Bold, Italic
                    # and the rest have no bundle glyph and never will. Formatting
                    # it unconditionally crashed the probe on the first such match.
                    if m.codepoint is not None:
                        where = f"{m.char} U+{m.codepoint:04X}"
                    else:
                        where = f"[{m.icon}]"
                    icon = f"  {where} {m.concept}/{m.rule}"
                else:
                    icon = "  -"
            if not quiet:
                print(f" {mark} {s.accel:<{width}}  {hid}  "
                      f"{s.label[:34]:<34} [{s.role}]{icon}")
        undisplayable = [s for s in shortcuts if not s.displayable]
        if undisplayable and not quiet:
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
                              icons=_icon_matcher() if args.icons else None,
                              quiet=getattr(args, "quiet", False)))
    return results


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
                              icons=_icon_matcher() if args.icons else None,
                              quiet=getattr(args, "quiet", False)))
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
    except FileNotFoundError:
        # Nothing was ever logged -- a clean outcome for a watch session where
        # every label matched, not an error to fail the run on.
        print(f"{path}: nothing logged yet")
        return 0
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



def _focus_key(backend):
    """Cheap identity of the window that currently has focus, or None.

    Process id plus class name, deliberately NOT the title: a title changes as you
    type (Word appends a modified marker), which would read as a new window every
    few seconds and re-probe the whole subtree each time. Class name is stable per
    application window ("OpusApp" for Word), so switching document inside one app
    does not re-probe -- the reprobe timer covers that.
    """
    if backend != "uia":
        return "atspi"          # no focus tracking on AT-SPI; the timer drives it
    try:
        _, iuia = _uia()
        el = iuia.GetFocusedElement()
        if el is None:
            return None
        return (int(el.CurrentProcessId or 0), str(el.CurrentClassName or ""))
    except Exception:
        return None


def _focus_title(backend):
    if backend != "uia":
        return "all applications"
    try:
        _, iuia = _uia()
        el = iuia.GetFocusedElement()
        walker = iuia.ControlViewWalker
        desktop = iuia.GetRootElement()
        top = el
        while top is not None:
            parent = walker.GetParentElement(top)
            if parent is None or iuia.CompareElements(parent, desktop):
                break
            top = parent
        return str(getattr(top, "CurrentName", "") or "?")
    except Exception:
        return "?"


def watch(args, backend) -> int:
    """Probe the focused window as you work, until Ctrl+C.

    ⚠️ A label is counted ONCE PER VISIT, not once per probe. The log exists to
    rank labels by how often you meet them, and re-probing one window all day
    would give Word's "Bold" several hundred counts against mousepad's
    "Transpose" one -- destroying exactly the ranking the log is for. A visit is
    focus arriving at a window; a periodic re-probe of the same window can add
    NEW labels (a ribbon tab changed) but never re-counts one already seen.
    """
    probe = main_uia if backend == "uia" else main_atspi
    args.quiet = True
    args.icons = True
    if backend == "uia":
        args.focused, args.all, args.app = True, False, None
    elif not args.app:
        args.all = True

    started = time.time()
    visits, total_logged = 0, 0
    apps_seen: set[str] = set()
    current_key, visit_labels, last_probe = object(), set(), 0.0

    # flush= on every line: a watch session is routinely redirected to a file,
    # and Python block-buffers a non-tty stream, so without this the log stays
    # empty for hours and reads as a hung process.
    say = functools.partial(print, flush=True)
    say(f"watching the focused window every {args.interval}s "
        f"(re-probe after {args.reprobe}s) -- Ctrl+C to stop")
    say(f"logging unmatched labels to {args.unmatched}\n")
    try:
        while True:
            key = _focus_key(backend)
            now = time.time()
            changed = key is not None and key != current_key
            due = args.reprobe > 0 and (now - last_probe) >= args.reprobe
            if key is not None and (changed or due):
                if changed:
                    current_key, visit_labels = key, set()
                    visits += 1
                try:
                    results = probe(args) or []
                except Exception as exc:
                    # A window can close mid-probe. One bad window must not end a
                    # session that is meant to run all day.
                    say(f"  [{time.strftime('%H:%M:%S')}] probe failed: {exc}")
                    results = []
                last_probe = now

                fresh, shortcuts, icons = [], 0, 0
                for result in results:
                    apps_seen.add(result.get("app", "?"))
                    shortcuts += result.get("total", 0)
                    icons += result.get("icon_matches", 0)
                    new = [u for u in result.get("unmatched_labels", [])
                           if u["label"].strip().lower() not in visit_labels]
                    for item in new:
                        visit_labels.add(item["label"].strip().lower())
                    if new:
                        fresh.append({**result, "unmatched_labels": new})
                added = merge_unmatched(args.unmatched, fresh) if fresh else 0
                total_logged += added
                if changed or added:
                    name = _focus_title(backend)[:44]
                    say(f"  [{time.strftime('%H:%M:%S')}] {name:<44} "
                        f"{shortcuts:>3} shortcuts, {icons:>2} icons, "
                        f"{added:>2} new label(s)")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        elapsed = int(time.time() - started)
        say(f"\n\nstopped after {elapsed // 3600}h{elapsed % 3600 // 60:02d}m -- "
            f"{visits} window visit(s) across {len(apps_seen)} application(s)")
        say(f"logged {total_logged} unmatched label sighting(s) to {args.unmatched}\n")
        return review_unmatched(args.unmatched)


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
    ap.add_argument("--watch", action="store_true",
                    help="probe the focused window as you work, until Ctrl+C")
    ap.add_argument("--interval", type=float, default=2.0,
                    help="watch: seconds between focus polls (default 2)")
    ap.add_argument("--reprobe", type=float, default=300.0,
                    help="watch: re-probe the same window after this many seconds, "
                         "to catch a ribbon/tab change (0 disables)")
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
    if args.watch:
        if not args.unmatched:
            print("--watch needs --unmatched PATH to log into", file=sys.stderr)
            return 2
        return watch(args, backend)
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
