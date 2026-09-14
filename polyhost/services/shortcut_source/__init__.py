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
    Accel, Shortcut, displayable_hid, parse_accel, parse_win_accel,
    pick_binding, pick_win_binding)

__all__ = ["Accel", "Shortcut", "displayable_hid", "parse_accel",
           "parse_win_accel", "pick_binding", "pick_win_binding",
           "backend_name", "pick", "harvest"]


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


def harvest(app: str) -> list:
    """Shortcuts for the focused app, or [] — the one call the core makes."""
    backend = pick()
    if backend is None:
        return []
    try:
        return backend.shortcuts_for_app(app)
    except Exception:
        return []
