"""Accessibility-API discovery — the macOS backend.

⚠️ **UNMEASURED ON REAL HARDWARE**, exactly as the Windows backend was when it
landed. The PURE half it leans on (`parse_mac_accel` and its three tables) is
selftested offline; the AX calls below have never run against a live
application. Read a first success as one sample, not as coverage.

Why it is worth building even so: **macOS is the platform where this feature
should work best, and it is the only one where it does nothing at all.** Every
Mac app has a real menu bar with real key equivalents, exposed as a STRUCTURED
binding — a character plus a modifier mask — where Linux's modern toolkits hand
back literally zero and Windows hands back a localized display string that has
to be parsed heuristically. The ceiling here is the height of the menu, not the
shape of the toolkit.

✅ **It needs NO new dependency.** `PyWinCtl` is a hard requirement of this app
and its own metadata declares `pyobjc >=8.1 ; sys_platform == "darwin"`, so the
umbrella pyobjc package — `ApplicationServices` and `AppKit` included — is
already installed on every Mac that runs PolyKybdHost. Measured from the
installed metadata rather than assumed (`importlib.metadata.requires("PyWinCtl")`).
The practical consequence is that `_api()` failing means a BROKEN install, not a
normal state, so the permission below is the failure to expect.

Three things decide whether it works on a given machine, and only the first is
about code:

- ⚠️ **TCC.** The AX API answers nothing until the user grants the *host
  process* Accessibility permission in System Settings → Privacy & Security →
  Accessibility. Without it every read returns `kAXErrorAPIDisabled` and the
  tree looks empty — which is indistinguishable from an app with no shortcuts
  unless the failure is named, so `unavailable_reason()` names it. That is the
  E13 lesson applied before the report arrives rather than after.
- ⚠️ **The permission is granted to the BINARY, not to this file.** A user
  running `python -m polyhost` from a terminal grants it to their terminal or
  to the Python interpreter, and a packaged `.app` is a different subject that
  has to be granted separately. So "I already allowed it" and "this process is
  allowed" are different statements, and only the second one matters.
- ⚠️ **Menu population is LAZY in some toolkits.** AppKit builds the whole menu
  tree up front, so a native app's items are readable without opening anything;
  an Electron or Java app may populate a submenu only when it is first shown.
  Unverified here, and it is the likeliest reason a real harvest comes back
  smaller than the menu looks.

⚠️ NOTHING HERE RAISES — same contract as the other two backends. It runs on a
background thread for a cosmetic feature, so a missing bridge, a denied
permission or an app that quit mid-walk each cost an empty list.
"""

from __future__ import annotations

from polyhost.services.shortcut_source.model import Shortcut, parse_mac_accel

# A menu tree is deeper but far narrower than an AT-SPI or UIA subtree, so the
# budget is a guard against a pathological app rather than a routine ceiling --
# a large native app's whole menu bar is a few hundred items.
DEFAULT_NODE_BUDGET = 3000

# AX attribute names. Spelled out rather than imported so that a typo fails a
# unit test here instead of quietly reading nothing on a Mac.
AX_MENU_BAR = "AXMenuBar"
AX_CHILDREN = "AXChildren"
AX_TITLE = "AXTitle"
AX_ROLE = "AXRole"
AX_CMD_CHAR = "AXMenuItemCmdChar"
AX_CMD_VIRTUAL_KEY = "AXMenuItemCmdVirtualKey"
AX_CMD_MODIFIERS = "AXMenuItemCmdModifiers"
AX_CMD_GLYPH = "AXMenuItemCmdGlyph"

AX_ERROR_SUCCESS = 0
AX_ERROR_API_DISABLED = -25211

_TRUST_CACHE: bool | None = None


def _api():
    """The pyobjc symbols this backend needs, imported late.

    Late for the reason the other two backends import late: this module is
    reachable from a platform check on every OS, and pyobjc is a heavy import
    that must not land on a Linux or Windows host that will never call it.
    """
    from ApplicationServices import (  # noqa: F401  (re-exported below)
        AXIsProcessTrusted, AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication)
    from AppKit import NSWorkspace
    return (AXUIElementCreateApplication, AXUIElementCopyAttributeValue,
            AXIsProcessTrusted, NSWorkspace)


def _attr(copy_attr, element, name, default=None):
    """One AX attribute, or `default`.

    ⚠️ pyobjc returns `(error, value)` rather than raising, and an unsupported
    attribute is the NORMAL answer for most of these — a menu item with no key
    equivalent simply has no `AXMenuItemCmdChar`. So a non-zero error is not an
    event worth logging; it is the shape of the data.
    """
    try:
        err, value = copy_attr(element, name, None)
    except Exception:
        return default
    if err != AX_ERROR_SUCCESS or value is None:
        return default
    return value


def _trusted() -> bool:
    """Has this process been granted Accessibility permission?

    Cached per process: the answer cannot change without the user restarting
    the app (macOS kills a process whose AX grant is revoked), and this is asked
    on the harvest path.

    ⚠️ Deliberately `AXIsProcessTrusted()` and NOT the `WithOptions` form that
    can raise the system prompt. A cosmetic keycap feature must not throw a
    permission dialog at a user who never asked for it, and the prompt is shown
    once per subject ever — spending it from a background thread at an arbitrary
    moment is the worst possible time to spend it.
    """
    global _TRUST_CACHE
    if _TRUST_CACHE is None:
        try:
            _, _, is_trusted, _ = _api()
            _TRUST_CACHE = bool(is_trusted())
        except Exception:
            _TRUST_CACHE = False
    return _TRUST_CACHE


def available() -> bool:
    return unavailable_reason() is None


def unavailable_reason() -> str | None:
    """WHY the AX API is unusable here, or None when it works.

    Two causes, needing opposite fixes: a missing pyobjc (a pip install) and a
    missing TCC grant (a trip to System Settings, then a restart of this app).
    Collapsing them into one sentence is the defect the AT-SPI side already
    records — a user told "install pyobjc" when the package is present goes and
    installs it again.

    ⚠️ **The permission is the one to expect**; pyobjc ships with PyWinCtl on
    this platform (see the module docstring), so a missing one means the install
    is broken rather than incomplete — which is why that sentence names the
    packages instead of just saying "install pyobjc".
    """
    try:
        _api()
    except Exception as exc:
        return ("pyobjc is not installed (pip install pyobjc-framework-Cocoa "
                "pyobjc-framework-ApplicationServices): %s" % exc)
    if not _trusted():
        return ("this process has no Accessibility permission — grant it in "
                "System Settings > Privacy & Security > Accessibility and "
                "restart PolyKybdHost (the grant is per BINARY, so a terminal "
                "and a packaged app are separate entries)")
    return None


def _frontmost_pid(workspace) -> int | None:
    app = workspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None
    return int(app.processIdentifier())


def _menu_shortcuts(copy_attr, menu, path, found, seen, budget):
    """Walk one AXMenu, depth first, appending every real key equivalent."""
    for item in _attr(copy_attr, menu, AX_CHILDREN, []) or []:
        if budget[0] <= 0:
            return
        budget[0] -= 1
        title = str(_attr(copy_attr, item, AX_TITLE, "") or "").strip()
        char = _attr(copy_attr, item, AX_CMD_CHAR, "")
        vkey = _attr(copy_attr, item, AX_CMD_VIRTUAL_KEY)
        mods = _attr(copy_attr, item, AX_CMD_MODIFIERS)
        accel = parse_mac_accel(str(char or ""),
                                None if vkey is None else int(vkey),
                                None if mods is None else int(mods),
                                _attr(copy_attr, item, AX_CMD_GLYPH))
        # ⚠️ `is_window_manager_chord` is deliberately NOT consulted here. Its
        # set is Windows' (Alt+Space, Alt+F4), and on macOS `MOD_ALT + space` is
        # ⌥Space -- a chord an application may legitimately bind, so borrowing
        # that denylist would silently drop a real shortcut. The system chords
        # that matter here (Force Quit, Sleep, Log Out) all live in the Apple
        # menu, which `shortcuts_for_app` skips wholesale; ⌘Tab and ⌘Space are
        # in no menu at all and so can never be harvested.
        if accel is not None and title:
            key = (accel.mods, accel.keysym.lower())
            if key not in seen:
                seen.add(key)
                found.append(Shortcut(
                    label=title, role="menu item", accel=accel.pretty(),
                    mods=accel.mods, keysym=accel.keysym, hid=accel.hid,
                    displayable=accel.displayable, kind="accelerator",
                    path=list(path), raw=str(char or "")))
        for submenu in _attr(copy_attr, item, AX_CHILDREN, []) or []:
            _menu_shortcuts(copy_attr, submenu, path + [title],
                            found, seen, budget)


def shortcuts_for_app(name: str = "",
                      budget: int = DEFAULT_NODE_BUDGET) -> list[Shortcut]:
    """Every key equivalent the FRONTMOST application's menu bar exposes.

    ⚠️ `name` is accepted and ignored, for the reason the Windows backend gives:
    the AX API answers "which app is frontmost" directly and cheaply, the caller
    only ever asks about the app it already believes is focused, and resolving
    by name would be a second and slower opinion about the same thing.

    ⚠️ **The Apple menu is skipped.** It is the first menu bar item on every
    application and it is not the application's — its items are the system's
    (Sleep, Log Out, Force Quit), so harvesting them would put an icon for a
    system action on a keycap in every app on the machine, which is the same
    defect `WINDOW_MANAGER_CHORDS` exists to prevent on Windows.

    Returns [] on any failure, for the reason the other two backends do.
    """
    try:
        create_app, copy_attr, _is_trusted, workspace = _api()
        if not _trusted():
            return []
        pid = _frontmost_pid(workspace)
        if pid is None:
            return []
        app = create_app(pid)
        menu_bar = _attr(copy_attr, app, AX_MENU_BAR)
        if menu_bar is None:
            return []
        found: list[Shortcut] = []
        seen: set[tuple[int, str]] = set()
        remaining = [int(budget)]
        bar_items = _attr(copy_attr, menu_bar, AX_CHILDREN, []) or []
        for bar_item in list(bar_items)[1:]:        # [1:] drops the Apple menu
            title = str(_attr(copy_attr, bar_item, AX_TITLE, "") or "").strip()
            for menu in _attr(copy_attr, bar_item, AX_CHILDREN, []) or []:
                _menu_shortcuts(copy_attr, menu, [title], found, seen, remaining)
        return found
    except Exception:
        return []
