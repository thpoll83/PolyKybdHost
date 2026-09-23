"""Discover the keyboard shortcuts the focused application exposes.

One model, three platforms, three backends:

    Linux    AT-SPI2 over D-Bus, `org.a11y.atspi.Action.GetKeyBinding`
    Windows  UI Automation, AcceleratorKey (30006) / AccessKey (30007)
    macOS    Accessibility API, AXMenuItemCmdChar & friends

⚠️ **"Built" is not "measured", and the three are at different stages.** Only
the Linux one has run against real applications (mousepad 26/26, gedit 0,
gnome-text-editor 0 -- the classic-menubar ceiling). Windows and macOS were
both written without the machine, so their PURE parsers are selftested and
their platform calls have never executed. Expect to debug each on first
contact and read a first success as one sample.

macOS is the one with the highest ceiling and the lowest confidence: every Mac
app has a real menu bar exposing a STRUCTURED binding, so there is nothing to
parse heuristically -- but it is also the only backend gated on a permission
the user must grant by hand, and a denied grant looks exactly like an app with
no shortcuts unless the reason is named. See `macos.unavailable_reason()`.

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
           "backend_name", "pick", "harvest", "release_thread",
           "unavailable_reason"]


def backend_name() -> str:
    """Which backend THIS PLATFORM would use, whether or not it is usable."""
    if sys.platform.startswith("win"):
        return "uia"
    if sys.platform.startswith("darwin"):
        return "macos"
    return "atspi"


def _backend_module(name: str):
    """Import the named backend.

    ⚠️ One import site, shared by `pick()` and `unavailable_reason()`, because
    the two must agree about which module they are talking about -- a second
    copy of this mapping is a place for the two to disagree, and the symptom
    would be a reason that describes a backend the app is not using. It was two
    copies while there were two backends and one `else`; adding a third made the
    `else` a wrong answer for macOS rather than merely an untidy one.
    """
    if name == "uia":
        from polyhost.services.shortcut_source import uia as backend
    elif name == "macos":
        from polyhost.services.shortcut_source import macos as backend
    else:
        from polyhost.services.shortcut_source import atspi as backend
    return backend


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
        backend = _backend_module(name)
    except Exception:
        return None
    return backend if backend.available() else None


def release_thread() -> None:
    """Let the backend free what THIS thread holds, before the thread exits.

    Only the Windows backend has anything to free (its COM apartment and the
    IUIAutomation object built in it -- see `uia.release_thread`). A backend
    that was never imported is not imported here: nothing on this thread can
    be holding its objects. Never raises.
    """
    module = sys.modules.get(f"{__name__}.{backend_name()}")
    release = getattr(module, "release_thread", None)
    if release is None:
        return
    try:
        release()
    except Exception:
        # The module docstring's rule: nothing here raises. This runs in the
        # harvest thread's `finally`, where an escape would reach
        # threading.excepthook and read as a crash.
        pass


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
        # Unreachable on the three platforms this app supports; kept because
        # `backend_name()` answers for whatever `sys.platform` says, and a new
        # platform must degrade to a sentence rather than an AttributeError.
        return "this platform has no accessibility backend"
    try:
        backend = _backend_module(name)
    except Exception as exc:
        return "the %s backend could not be imported: %s" % (name, exc)
    reason = getattr(backend, "unavailable_reason", None)
    if reason is None:
        # A backend that predates the reason API: fall back to the yes/no it
        # does have, rather than reporting it as working.
        return None if backend.available() else "the %s backend is unusable" % name
    return reason()


def harvest(app: str, reason: dict | None = None,
            pid: int | None = None) -> list:
    """Shortcuts for the focused app, or [] — the one call the core makes.

    ⚠️ **An empty list has six different meanings on macOS and the caller
    cannot tell them apart.** Pass a dict as `reason` and the backend fills
    `reason["why"]` with a sentence and `reason["retry"]` with whether THIS
    harvest looked at all -- a focus race and an app with genuinely no key
    equivalents both return [] and need opposite handling, and the second must
    never be cached as the first.

    Every backend takes the parameter so this needs no branch; only `macos`
    fills it today.

    ⚠️ `pid` is the process the caller means, and on macOS it is the difference
    between harvesting that app and harvesting whatever `NSWorkspace` last
    called frontmost -- a value that is frozen on the worker thread, so without
    a pid exactly one app on the machine can ever harvest. Pass it whenever the
    caller has one; only `macos` uses it today.
    """
    backend = pick()
    if backend is None:
        return []
    try:
        return backend.shortcuts_for_app(app, reason=reason, pid=pid)
    except Exception as exc:
        if reason is not None:
            # The backend's own guard should have caught this, so reaching here
            # is itself the finding -- say so rather than letting it read as
            # "the app has no shortcuts".
            reason["why"] = ("the %s backend raised past its own guard: %s: %s"
                             % (backend_name(), type(exc).__name__, exc))
            reason["retry"] = True
        return []
