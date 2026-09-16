"""AT-SPI2 discovery — the Linux backend.

Extracted from `tools/shortcut_probe.py` unchanged; see `model.py` for why the
probe imports this rather than carrying its own copy.

⚠️ MEASURED CEILING: this finds shortcuts for CLASSIC-MENUBAR apps only. An app
whose menu lives in a hamburger popover exposes no accelerator at all -- gedit's
real Ctrl+S is simply absent from its accessible tree, and GTK4 answers
"<VoidSymbol>" for every keybinding it has. That is not a bug to fix here; it is
the reason `services/shortcut_overlays.py` must degrade to drawing nothing.
"""

from __future__ import annotations

from polyhost.services.shortcut_source.model import (
    Shortcut, parse_accel, pick_binding)


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


DEFAULT_NODE_BUDGET = 4000


def available() -> bool:
    """Is the accessibility bridge reachable at all?

    A plain import check: `Atspi` imports fine without a session bus and only
    fails when asked for the desktop, so the desktop is what is asked for.
    """
    try:
        atspi = _atspi()
        atspi.get_desktop(0).get_child_count()
        return True
    except Exception:
        return False


def shortcuts_for_app(name: str, budget: int = DEFAULT_NODE_BUDGET) -> list[Shortcut]:
    """Every shortcut the named application exposes, or [] for anything at all.

    Matched on a substring of the desktop child's name, the same rule the probe's
    `--app` uses, because the accessible name ("gedit") and the window-manager
    class the host tracks ("org.gnome.gedit") agree only loosely.

    ⚠️ Returns [] rather than raising on ANY failure. This runs on a background
    thread for a cosmetic feature; an app that died mid-walk, a bridge that is
    not running, or a D-Bus timeout must all cost nothing.
    """
    if not name:
        return []
    needle = name.lower()
    try:
        atspi = _atspi()
        desktop = atspi.get_desktop(0)
        counter = [budget]
        for i in range(desktop.get_child_count()):
            child = _safe(lambda i=i: desktop.get_child_at_index(i))
            if child is None:
                continue
            child_name = (_safe(child.get_name, "") or "").lower()
            if not child_name or needle not in child_name and child_name not in needle:
                continue
            return shortcuts_for(child, atspi, counter)
    except Exception:
        return []
    return []
