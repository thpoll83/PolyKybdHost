"""Discover the keyboard shortcuts the focused application exposes.

One model, three platforms, two backends built:

    Linux    AT-SPI2 over D-Bus, `org.a11y.atspi.Action.GetKeyBinding`  built
    Windows  UI Automation, AcceleratorKey (30006) / AccessKey (30007)  built
    macOS    Accessibility API, AXMenuItemCmdChar & friends             NOT built

⚠️ macOS therefore harvests NOTHING and the shortcut fall-back never fires there.
That is a gap, not a failure: `pick()` returns None, the caller draws no icons,
and nothing misbehaves. It is also the platform most worth doing eventually --
every Mac app has a real menu bar with real key equivalents, where the modern
Linux toolkits yield literally zero.

⚠️ NOTHING HERE RAISES. It runs on a background thread for a cosmetic feature, so
a missing bridge, a dead app or a D-Bus timeout must each cost an empty list.
"""

from __future__ import annotations

import sys

from polyhost.services.shortcut_source.model import (  # noqa: F401  (re-export)
    Accel, MOD_ALT, MOD_CTRL, MOD_GUI, MOD_SHIFT, Shortcut,
    WINDOW_MANAGER_CHORDS, displayable_hid, is_window_manager_chord,
    parse_accel, parse_win_accel, pick_binding, pick_win_binding)

__all__ = ["Accel", "MOD_ALT", "MOD_CTRL", "MOD_GUI", "MOD_SHIFT", "Shortcut",
           "WINDOW_MANAGER_CHORDS", "displayable_hid", "is_window_manager_chord",
           "parse_accel", "parse_win_accel", "pick_binding", "pick_win_binding",
           "backend_name", "pick", "harvest", "unavailable_reason"]


def backend_name() -> str:
    """Which backend THIS PLATFORM would use, whether or not it is usable."""
    if sys.platform.startswith("win"):
        return "uia"
    if sys.platform.startswith("darwin"):
        return ""                       # see the module docstring
    return "atspi"


def pick():
    """The backend module, or None when this platform has none that works.

    The availability probe is deliberately part of the pick: on Linux the import
    succeeds on a machine with no accessibility bus at all, and an unusable
    backend that answers [] is indistinguishable from an app with no shortcuts --
    which is exactly the distinction the caller's log line needs to draw.
    """
    name = backend_name()
    if not name:
        return None
    try:
        if name == "uia":
            from polyhost.services.shortcut_source import uia as backend
        else:
            from polyhost.services.shortcut_source import atspi as backend
    except Exception:
        return None
    return backend if backend.available() else None


def unavailable_reason() -> str | None:
    """WHY no backend is usable here, or None when one is.

    ⚠️ The caller's log line used to be a flat *"no accessibility backend on
    this platform"*, which is right for macOS and wrong for every other cause --
    and the commonest cause, an interpreter that cannot see the system
    PyGObject, is the one that sentence explicitly denies. The three need
    opposite fixes, so they are told apart here rather than flattened.
    """
    name = backend_name()
    if not name:
        return "this platform has no accessibility backend (macOS is not built)"
    try:
        if name == "uia":
            from polyhost.services.shortcut_source import uia as backend
        else:
            from polyhost.services.shortcut_source import atspi as backend
    except Exception as exc:
        return "the %s backend could not be imported: %s" % (name, exc)
    reason = getattr(backend, "unavailable_reason", None)
    if reason is None:
        # A backend that predates the reason API: fall back to the yes/no it
        # does have, rather than reporting it as working.
        return None if backend.available() else "the %s backend is unusable" % name
    return reason()


def harvest(app: str) -> list:
    """Shortcuts for the focused app, or [] — the one call the core makes."""
    backend = pick()
    if backend is None:
        return []
    try:
        return backend.shortcuts_for_app(app)
    except Exception:
        return []
