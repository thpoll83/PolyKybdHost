#!/usr/bin/env python3
"""Listen to one application's AT-SPI events and say which ones a re-harvest could use.

The harvest caches each app's shortcuts for the life of the process, so Kate
first seen on its welcome page never gains Save/Undo/Copy once a document opens
(those items come from the editor component and exist only with a document).
Re-harvesting needs a trigger. This measures the two candidates on a live app:

  * object:property-change:accessible-name on the FRAME -- the window title;
  * object:children-changed on a MENU -- the menus announcing their own rebuild.

and window:activate for context. It prints each event as it arrives, then a
summary of how many events of each kind came from which role. Read the summary
for two things: do menu children-changed events arrive when a document opens
(the precise trigger), and how many events per second a busy app produces (the
cost of listening at all).

    QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 kate -n &      # or any app on the bus
    python3 tools/atspi_event_probe.py kate --seconds 60
    # meanwhile: open a file, switch tabs, edit, save, close the document

Ctrl+C stops early and still prints the summary. --quiet prints only the summary.

MEASURED on Kate, Plasma, 2026-10-09 (65 s: new document, close, new
document, type nine characters, save):

  * object:children-changed: NONE, not even when the first document opened
    and the menus gained Save/Undo/Copy. Qt does not announce a menu rebuild
    over AT-SPI, so an event listener has no precise trigger to offer;
  * frame title: changed exactly on welcome -> document (and back), but ALSO
    on every keystroke in an unsaved document (Kate previews its first words
    in the title): nine changes in 0.6 s;
  * the rest is noise: ~20 name changes on status-bar widgets per view
    switch, a busy "popup menu 'Kate'", window:activate in duplicate pairs.

So the harvest re-runs on the window title the core already has, behind a
one-in-flight guard, a 3 s floor and a backoff on unchanged results
(`services/shortcut_fetcher.py`). Re-run this before building on events for
another toolkit -- GTK may behave differently.
"""

import argparse
import collections
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from polyhost.services.shortcut_source import atspi as A  # noqa: E402

EVENT_TYPES = (
    "object:children-changed",
    "object:property-change:accessible-name",
    "window:activate",
)

MENU_ROLES = ("menu", "menu bar", "popup menu", "menu item")


def is_menu_role(role: str) -> bool:
    return role in MENU_ROLES


def summarise(records):
    """Counts per (event type, source role), plus the two answers that matter.

    `records` are (t, type, role, name, detail1, child_role) tuples, `t` in
    seconds since the probe started. Pure, so it is testable without a bus.
    """
    by_kind = collections.Counter((r[1], r[2]) for r in records)
    menu_changes = [r for r in records
                    if r[1].startswith("object:children-changed")
                    and (is_menu_role(r[2]) or is_menu_role(r[5]))]
    title_changes = [r for r in records
                     if r[1].startswith("object:property-change:accessible-name")
                     and r[2] == "frame"]
    span = (records[-1][0] - records[0][0]) if len(records) > 1 else 0.0
    return {
        "by_kind": by_kind,
        "menu_changes": len(menu_changes),
        "title_changes": len(title_changes),
        "total": len(records),
        "span": span,
    }


def print_summary(s, out=sys.stdout):
    print("\n=== summary", file=out)
    print(f"  {s['total']} event(s) over {s['span']:.1f} s", file=out)
    for (etype, role), n in s["by_kind"].most_common():
        print(f"  {n:6d}  {etype}  [{role or '?'}]", file=out)
    print(f"  menu children-changed: {s['menu_changes']}", file=out)
    print(f"  window title changes:  {s['title_changes']}", file=out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("app", help="application name, substring match as in --list")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args(argv)

    Atspi = A._atspi()
    if not A._bus_ok(Atspi):
        print("accessibility bus unreachable")
        return 1
    from gi.repository import GLib   # gi is loaded by A._atspi() above

    want = args.app.lower()
    start = time.monotonic()
    records = []

    def on_event(event):
        try:
            source = event.source
            app = A._safe(source.get_application)
            app_name = (A._safe(app.get_name, "") or "") if app else ""
            if want not in app_name.lower():
                return
            role = A._safe(source.get_role_name, "") or ""
            name = A._safe(source.get_name, "") or ""
            child_role = ""
            if event.type.startswith("object:children-changed"):
                child = event.any_data
                child_role = (A._safe(child.get_role_name, "") or "") if child else ""
            t = time.monotonic() - start
            records.append((t, event.type, role, name, event.detail1, child_role))
            if not args.quiet:
                # repr(): names are app-supplied text, never raw to a terminal.
                print(f"{t:8.2f}  {event.type:45s} [{role}] {name[:60]!r}"
                      + (f" child=[{child_role}]" if child_role else ""))
        except Exception as exc:
            print(f"  (event dropped: {type(exc).__name__}: {exc})")

    listener = Atspi.EventListener.new(on_event)
    for etype in EVENT_TYPES:
        listener.register(etype)

    def stop(*_):
        Atspi.event_quit()
        return False

    GLib.timeout_add(int(args.seconds * 1000), stop)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, stop)
    print(f"listening to {args.app!r} for {args.seconds:.0f} s (Ctrl+C stops)")
    Atspi.event_main()
    for etype in EVENT_TYPES:
        listener.deregister(etype)
    print_summary(summarise(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
