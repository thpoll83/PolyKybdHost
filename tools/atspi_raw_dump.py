#!/usr/bin/env python3
"""Dump the RAW AT-SPI keybinding strings one application exposes.

shortcut_probe.py reports only what pick_binding() accepts, so a zero there
cannot tell "the app exposes nothing" from "the app exposes a format we
reject". This prints the role histogram and every non-empty GetKeyBinding
string, unfiltered, so the two cases separate.

    python3 tools/atspi_raw_dump.py kate
"""

import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from polyhost.services.shortcut_source import atspi as A  # noqa: E402


def main() -> int:
    want = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    Atspi = A._atspi()
    if not A._bus_ok(Atspi):
        print("accessibility bus unreachable")
        return 1
    desktop = Atspi.get_desktop(0)
    apps = [desktop.get_child_at_index(i) for i in range(desktop.get_child_count())]
    apps = [a for a in apps if a is not None and want in (a.get_name() or "").lower()]
    if not apps:
        print(f"no application matching {want!r}")
        return 1
    for app in apps:
        roles = collections.Counter()
        raws = []
        for node, role, path in A.walk(app, Atspi, [20000]):
            roles[role] += 1
            action = A._safe(node.get_action_iface)
            if action is None:
                continue
            for i in range(A._safe(action.get_n_actions, 0) or 0):
                raw = A._safe(lambda i=i: action.get_key_binding(i), "") or ""
                if raw:
                    raws.append((role, A._safe(node.get_name, "") or "", i, raw))
        print(f"=== {app.get_name()} ({sum(roles.values())} nodes)")
        for role, n in roles.most_common():
            print(f"  {n:5d}  {role}")
        print(f"--- {len(raws)} non-empty keybinding string(s)")
        for role, name, i, raw in raws[:80]:
            print(f"  [{role}] {name!r} action{i}: {raw!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
