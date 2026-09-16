#!/usr/bin/env python3
"""Check what the OS hands us as the focused application's own icon.

The Windows PE resource parse and the macOS bundle walk in
`polyhost/services/os_app_icon.py` have never run against a live application,
and a claim nobody can check is worth less than a command anybody can run:

    python tools/os_icon_probe.py                      # this process
    python tools/os_icon_probe.py 1234                 # a pid
    python tools/os_icon_probe.py "C:\\...\\WINWORD.EXE"
    python tools/os_icon_probe.py 1234 --save out.png

It names the file it found, every display name the OS offers for it, the
conversion that won, the score and whether that clears MIN_SCORE, then prints the
keycap as text.

⚠️ **The display names are the point on Windows and macOS.** `kebab("Microsoft
Word")` is mdi's own `microsoft-word`, which the executable name `winword` can
never reach -- but that only works if `RT_VERSION` / `CFBundleDisplayName`
actually hold a usable name on a real install, which no machine has checked.
Run this against WINWORD.EXE and read the `names:` line before trusting
`docs/generic-icons-plan.md` B.2.

⚠️ This lives in `tools/` rather than in the module it exercises because the
module must not import `app_icons` -- that is the direction of the cycle CodeQL
reported. `os_app_icon` is a pure lookup: it finds bytes and converts nothing,
so rendering belongs on this side of the boundary. `shortcut_probe.py` beside it
is the same shape for the shortcut harvest.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polyhost.services import app_icons, icon_binarise, os_app_icon  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", default=None,
                        help="a pid, or a path to an executable/bundle/icon")
    parser.add_argument("--app", default="",
                        help="the app name the window tracker reports")
    parser.add_argument("--save", default="", help="write the keycap to this PNG")
    args = parser.parse_args(argv)

    if args.target and not str(args.target).isdigit():
        path = str(args.target)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            print("cannot read %s: %s" % (path, exc))
            return 2
        if path.lower().endswith(".exe") or raw[:2] == b"MZ":
            # Report the version strings even when there is no icon: a PE with a
            # usable ProductName and no RT_GROUP_ICON still resolves a mark.
            for key, value in sorted(os_app_icon.version_strings(raw).items()):
                print("  %-18s %s" % (key + ":", value))
            names = os_app_icon.names_from_pe(raw)
            blob = os_app_icon.icon_from_pe(raw)
            if not blob:
                print("no RT_GROUP_ICON resource in %s" % path)
                print("names: %s" % (", ".join(names) or "(none)"))
                return 1
            found, source = blob, path
        else:
            found, source, names = raw, path, ()
    else:
        pid = int(args.target) if args.target else os.getpid()
        identity = os_app_icon.app_identity(pid, args.app)
        found, source, names = identity.icon, identity.icon_path, identity.names
        if not found:
            print("platform %s: no OS icon for pid %d (app %r)"
                  % (os_app_icon.platform_key(), pid, args.app))
            print("names: %s" % (", ".join(names) or "(none)"))
            return 1

    data = found
    print("source: %s (%d bytes)" % (source, len(data)))
    print("names:  %s" % (", ".join(names) or "(none)"))
    # ⚠️ ONE call, with the names in the NAMES slot -- not one call per name with
    # each in the app-name slot. That is how `app_icon_fetcher` calls it, and it
    # is the only form that produces the bare `mdi:microsoft-word`: the hyphen
    # rule admits a bare mdi name for a DISPLAY name and refuses it for an
    # executable, so probing name-by-name would silently hide the exact
    # mechanism this tool exists to verify.
    tried = app_icons.candidates(args.app or os.path.basename(source), names)
    print("catalog order:")
    for name in tried:
        print("    %s" % name)
    if not tried:
        print("    (nothing -- no catalog name could be derived)")
    mask, conversion, score = app_icons.render_os_overlay(data)
    if mask is None:
        print("no 1-bit reading survived")
        return 1
    verdict = "DRAWN" if score >= icon_binarise.MIN_SCORE else "REJECTED (too low)"
    print("conversion: %s   score: %.2f   %s (gate %.2f)"
          % (conversion, score, verdict, icon_binarise.MIN_SCORE))
    # What the running app would actually do, which is the question E6 asks.
    # The OS icon goes FIRST since E2, so a REJECTED reading here is not a
    # failure -- it is the gate working, and the catalog gets its turn.
    if score >= icon_binarise.MIN_SCORE:
        print("=> the keycap would show THIS, the app's own icon")
    elif tried:
        print("=> the keycap would fall through to the catalog: %s" % tried[0])
    else:
        print("=> the keycap would show NOTHING (no OS reading, no catalog name)")
    for row in mask:
        print("".join("#" if value else "." for value in row))
    if args.save:
        try:
            from PIL import Image
            Image.fromarray(((~mask) * 255).astype("uint8")).save(args.save)
            print("wrote %s" % args.save)
        except Exception as exc:    # noqa: BLE001 - a convenience, not the check
            print("could not write %s: %s" % (args.save, exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
