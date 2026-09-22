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

⚠️ **Which makes SIX ways of answering [], and the caller cannot tell them
apart from the list.** They need entirely different responses -- grant a
permission, do nothing, or ask again in a moment -- so `shortcuts_for_app`
takes a `reason` out-parameter that names the one that fired. Without it the
log says *"the app exposes no accelerators"* for all six, which is a lie about
five of them: measured in the field, four macOS apps reported exactly that on a
machine where Chrome harvested 65 in the same session, so both the causes that
sentence implies were provably absent (2026-09-21).
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


def _frontmost_name(workspace) -> str:
    """The frontmost application's localized name, or "" when unreadable.

    ⚠️ **STALE ON A WORKER THREAD — do not use this to decide which app to
    harvest.** Measured in the field (macOS 22.6, 2026-09-21): across a 3-minute
    session it returned `Safari` for every single harvest, including one issued
    six seconds BEFORE Safari was ever focused and one three minutes after focus
    had left it. Nine apps in a row, one answer. The consequence was total: the
    name check refused every app but the one it was stuck on, so exactly one
    application on the machine could ever produce shortcuts.

    The likely mechanism is that `frontmostApplication` is updated by workspace
    notifications delivered to the MAIN thread's run loop, which a worker thread
    does not pump — but that is unverified, and the fix does not rest on it.
    What is measured is that the value does not change here.

    `_running_name` is the per-pid lookup to use instead; this one is kept for
    the probe, which runs on the main thread and has no pid to work from.
    """
    try:
        app = workspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return ""
        return str(app.localizedName() or "")
    except Exception:
        return ""


def _running_name(pid: int) -> str:
    """The localized name of the process `pid`, or "" when unreadable.

    A DIRECT lookup rather than an observed property, which is the whole point:
    it answers about one process instead of about "which app is in front", so
    there is no notification to have missed. See `_frontmost_name`.
    """
    try:
        from AppKit import NSRunningApplication
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
        if app is None:
            return ""
        return str(app.localizedName() or "")
    except Exception:
        return ""


def names_agree(requested: str, frontmost: str) -> bool:
    """Is `frontmost` plausibly the app the caller asked about?

    ⚠️ **FAILS OPEN, and that is the whole design.** The caller's name comes
    from the window handler and the frontmost name comes from AppKit, so the two
    spellings are not guaranteed to match even when they denote the same
    application ("Code" vs "Visual Studio Code", "Safari" vs "Safari.app"). A
    strict comparison would therefore refuse a correct harvest on an unfamiliar
    naming convention and turn a RARE mislabel into a TOTAL failure -- strictly
    worse than the race it closes. So a substring match either way is enough,
    and anything unreadable or empty is accepted.

    What it does catch is the case that matters: the user switched from Mail to
    Xcode while the harvest was queued, and the two names have nothing in
    common. Greptile, #248.
    """
    a = (requested or "").strip().lower()
    b = (frontmost or "").strip().lower()
    if not a or not b:
        return True
    return a in b or b in a


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
                      budget: int = DEFAULT_NODE_BUDGET,
                      reason: dict | None = None,
                      pid: int | None = None) -> list[Shortcut]:
    """Every key equivalent an application's menu bar exposes.

    ⚠️ **PASS `pid` WHENEVER THE CALLER HAS ONE.** With it this harvests the
    named PROCESS; without it, whatever `NSWorkspace` calls frontmost — and on
    the worker thread this runs on, that value is STALE and never changes (see
    `_frontmost_name`). Measured in the field: without a pid, exactly one
    application on the machine could ever harvest, because the name check
    refused all the others against a frozen answer. `PolyCore` already has the
    pid — the OS-icon route two lines above takes the same one — so the app
    path always supplies it and only the probe falls back.

    ⚠️ `name` still does not SELECT the application. With a pid it names the
    process; without one it is checked against the frontmost app through
    `names_agree`. Either way it VERIFIES rather than searches, because the AX
    API answers "this pid" and "what is frontmost" directly and answers "find
    the one called X" not at all.

    ⚠️ **The Apple menu is skipped.** It is the first menu bar item on every
    application and it is not the application's — its items are the system's
    (Sleep, Log Out, Force Quit), so harvesting them would put an icon for a
    system action on a keycap in every app on the machine, which is the same
    defect `WINDOW_MANAGER_CHORDS` exists to prevent on Windows.

    Returns [] on any failure, for the reason the other two backends do.

    ⚠️ **`reason` is what tells the SIX ways of returning [] apart**, and they
    need entirely different responses: grant a permission, do nothing (the app
    really has no key equivalents), or ask again in a moment. Flattened into
    the caller's one sentence -- *"the app exposes no accelerators"* -- five of
    the six are a lie, and the field log that prompted this had four macOS apps
    reporting exactly that while Chrome harvested 65 on the same machine, so
    the permission and the import were provably fine and the sentence narrowed
    nothing (2026-09-21).

    It is an out-parameter rather than a return value because the empty list is
    the contract every caller already codes against; `_say(app, reason["why"])`
    is the whole consumer. `reason["retry"]` is the machine-readable half: true
    means THIS HARVEST did not look, so the answer must not be cached.
    """
    def why(text, retry=False):
        if reason is not None:
            reason["why"] = text
            reason["retry"] = retry
        return []

    try:
        create_app, copy_attr, _is_trusted, workspace = _api()
        if not _trusted():
            # Normally unreachable: the fetcher consults `unavailable_reason()`
            # first. Reachable if the grant is revoked mid-session, and then the
            # cached answer is stale rather than wrong -- so say the same thing
            # that function does rather than inventing a second sentence.
            return why(unavailable_reason() or "this process has no "
                       "Accessibility permission")
        # ⚠️ Two different questions, and the pid decides which is asked. With
        # one we verify that THAT PROCESS is still the app the caller meant,
        # which is a live per-pid lookup; without one we fall back to the
        # frontmost app, whose name is frozen here.
        if pid is None:
            pid = _frontmost_pid(workspace)
            if pid is None:
                return why("macOS reports no frontmost application -- the "
                           "harvest landed between two apps", retry=True)
            observed = _frontmost_name(workspace)
        else:
            observed = _running_name(pid)
            if not observed:
                return why("the process this app was running as (pid %d) is "
                           "gone" % pid, retry=True)
        # ⚠️ The harvest runs on a WORKER THREAD, queued by the window tick, so
        # focus can move between the two -- and the fetcher caches the result
        # under the name it ASKED about. Without this check app B's shortcuts
        # are stored under app A's key and drawn every time A is focused until
        # the cache clears (Greptile, #248).
        #
        # ⚠️ The UIA backend has the SAME race and cannot close it as cheaply:
        # it resolves the focused ELEMENT, whose owning application name costs
        # another cross-process call. This backend is deliberately the stricter
        # of the two rather than both being left equally loose.
        if not names_agree(name, observed):
            return why("the app at that pid is now '%s', not '%s' -- focus "
                       "moved before the harvest ran, so this never looked"
                       % (observed or "?", name), retry=True)
        app = create_app(pid)
        menu_bar = _attr(copy_attr, app, AX_MENU_BAR)
        if menu_bar is None:
            return why("it exposes no AXMenuBar at all -- a non-AppKit app, or "
                       "one whose menu bar is not readable by this process")
        found: list[Shortcut] = []
        seen: set[tuple[int, str]] = set()
        remaining = [int(budget)]
        bar_items = _attr(copy_attr, menu_bar, AX_CHILDREN, []) or []
        for bar_item in list(bar_items)[1:]:        # [1:] drops the Apple menu
            title = str(_attr(copy_attr, bar_item, AX_TITLE, "") or "").strip()
            for menu in _attr(copy_attr, bar_item, AX_CHILDREN, []) or []:
                _menu_shortcuts(copy_attr, menu, [title], found, seen, remaining)
        if not found:
            # ⚠️ The one empty answer that is CORRECT, and the counts are what
            # separate its two causes. A bar the walk never entered -- 0 menus
            # past the Apple menu -- is not the same as a full menu bar with no
            # key equivalents in it, and per the module docstring a toolkit that
            # populates a submenu only when it is first SHOWN looks like the
            # second while being the first.
            return why("its menu bar has %d menu(s) past the Apple menu and "
                       "not one key equivalent in them (%d node(s) walked)"
                       % (len(list(bar_items)[1:]),
                          int(budget) - max(remaining[0], 0)))
        return found
    except Exception as exc:
        return why("the Accessibility API failed: %s: %s"
                   % (type(exc).__name__, exc), retry=True)
