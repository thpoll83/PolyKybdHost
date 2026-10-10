#!/usr/bin/env python3
"""Dump the RAW AT-SPI keybinding strings one application exposes.

shortcut_probe.py reports only what pick_binding() accepts, so a zero there
cannot tell "the app exposes nothing" from "the app exposes a format we
reject". This prints the role histogram and every non-empty GetKeyBinding
string, unfiltered, so the two cases separate.

    python3 tools/atspi_raw_dump.py kate
    python3 tools/atspi_raw_dump.py kate --all-nodes | grep -i save

--all-nodes also lists every menu item WITHOUT a binding, which is how to tell
"the item is in the tree but carries no shortcut" from "the item is absent".
"""

import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from polyhost.services.shortcut_source import atspi as A  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    all_nodes = "--all-nodes" in sys.argv
    want = (args[0] if args else "").lower()
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
            is_menu_item = "menu item" in role
            name = A._safe(node.get_name, "") or ""
            action = A._safe(node.get_action_iface)
            n = (A._safe(action.get_n_actions, 0) or 0) if action is not None else 0
            if n == 0:
                # A menu item with no action interface, or none of its own,
                # is still PRESENT -- dropping it would read as "absent from
                # the tree", the exact question --all-nodes exists to answer.
                if all_nodes and is_menu_item:
                    raws.append((role, name, "-",
                                 "<no action interface>" if action is None
                                 else "<no actions>", True))
                continue
            for i in range(n):
                # None, not "": a lookup that RAISED is not an empty binding.
                raw = A._safe(lambda i=i: action.get_key_binding(i), None)
                if raw is None:
                    raws.append((role, name, i, "<lookup failed>", True))
                elif raw or (all_nodes and is_menu_item):
                    raws.append((role, name, i, raw, False))
        print(f"=== {app.get_name()} ({sum(roles.values())} nodes)")
        for role, n in roles.most_common():
            print(f"  {n:5d}  {role}")
        print(f"--- {len(raws)} keybinding string(s)"
              + (" (menu items without one included)" if all_nodes else ""))
        # ⚠️ The marker is a FLAG, never read off the text: a real GTK binding
        # starts with "<" too ('<Control>s'), and an app-supplied string must
        # always go through repr() so a newline or a control character in it
        # cannot rewrite the terminal (Greptile, #337).
        for role, name, i, raw, is_marker in raws:
            shown = raw if is_marker else repr(raw)
            print(f"  [{role}] {name!r} action{i}: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
