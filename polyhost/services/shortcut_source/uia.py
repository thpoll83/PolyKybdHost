"""UI Automation discovery — the Windows backend.

Extracted from `tools/shortcut_probe.py` unchanged; see `model.py`.

⚠️ UNMEASURED ON REAL HARDWARE. It was written without a Windows machine, so the
PURE parsers it leans on are selftested (54 cases, real localized strings) while
the COM code below has never run against a live application. Expect to debug it
on first contact, and read a first success as one sample rather than as coverage.

Two reasons to expect it to beat the Linux ceiling, both expectations rather than
measurements: classic menubars are far more common, and UIA exposes
AcceleratorKey on toolbar and ribbon controls, not only on menus.
"""

from __future__ import annotations

from polyhost.services.shortcut_source.model import (
    Shortcut, TREESCOPE_SUBTREE, UIA_CONTROL_TYPES, UIA_PROP_ACCELERATOR,
    UIA_PROP_ACCESS_KEY, UIA_PROP_CONTROL_TYPE, UIA_PROP_NAME,
    UIA_PROP_PROCESS_ID, is_window_manager_chord, parse_win_accel,
    pick_win_binding)


_UIA_CACHE = None


def _uia():
    """The IUIAutomation instance, created once.

    Cached because watch mode polls the focused element every interval, and
    building the COM object per poll is pure overhead.
    """
    global _UIA_CACHE
    if _UIA_CACHE is not None:
        return _UIA_CACHE
    import comtypes.client
    module = comtypes.client.GetModule("UIAutomationCore.dll")
    iuia = comtypes.client.CreateObject(
        "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CLSID_CUIAutomation
        interface=module.IUIAutomation,
    )
    _UIA_CACHE = (module, iuia)
    return _UIA_CACHE


def _cached(element, prop_id, default=""):
    try:
        value = element.GetCachedPropertyValue(prop_id)
    except Exception:
        return default
    return default if value is None else value


def uia_shortcuts(iuia, root, cache_request) -> tuple[list[Shortcut], int]:
    """Fetch the whole subtree in ONE cross-process call, then read the cache."""
    found: list[Shortcut] = []
    seen: set[tuple[int, str]] = set()
    elements = root.FindAllBuildCache(
        TREESCOPE_SUBTREE, iuia.CreateTrueCondition(), cache_request)
    count = elements.Length
    for i in range(count):
        el = elements.GetElement(i)
        accel_raw = str(_cached(el, UIA_PROP_ACCELERATOR))
        access_raw = str(_cached(el, UIA_PROP_ACCESS_KEY))
        if not accel_raw.strip() and not access_raw.strip():
            continue
        ctype = int(_cached(el, UIA_PROP_CONTROL_TYPE, 0) or 0)
        text, kind = pick_win_binding(accel_raw, access_raw, ctype)
        if not text:
            continue
        accel = parse_win_accel(text)
        if accel is None:
            continue
        # A menu AccessKey carrying no modifier is the mnemonic used once the menu
        # is already open -- Word's System menu reports "Space" that way while its
        # real binding is Alt+Space. Same rule as the AT-SPI role gate: only a
        # chord is a one-press binding.
        if kind == "menu" and accel.mods == 0:
            continue
        # Alt+Space / Alt+F4 belong to Windows, not to the app — see
        # WINDOW_MANAGER_CHORDS. Dropped here rather than left to the icon
        # matcher so the harvest COUNT is honest.
        if is_window_manager_chord(accel.mods, accel.keysym):
            continue
        key = (accel.mods, accel.keysym.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(Shortcut(
            label=str(_cached(el, UIA_PROP_NAME)).strip(),
            role=UIA_CONTROL_TYPES.get(ctype, f"type {ctype}"),
            accel=accel.pretty(), mods=accel.mods, keysym=accel.keysym,
            hid=accel.hid, displayable=accel.displayable, kind=kind,
            raw=accel_raw or access_raw,
        ))
    return found, count



CACHED_PROPERTIES = (UIA_PROP_NAME, UIA_PROP_CONTROL_TYPE, UIA_PROP_ACCELERATOR,
                     UIA_PROP_ACCESS_KEY, UIA_PROP_PROCESS_ID)


def available() -> bool:
    try:
        _uia()
        return True
    except Exception:
        return False


def shortcuts_for_app(name: str = "") -> list[Shortcut]:
    """Every shortcut the FOCUSED top-level window exposes.

    ⚠️ `name` is accepted and ignored, so the two backends share one signature.
    UIA answers "what has focus" directly and far more cheaply than it answers
    "find the window called X" -- and the caller only ever asks about the app it
    already believes is focused, so resolving by name would be a second, slower
    opinion about the same thing.

    Returns [] on any failure, for the reason the AT-SPI side does.
    """
    try:
        _, iuia = _uia()
        cache_request = iuia.CreateCacheRequest()
        for prop in CACHED_PROPERTIES:
            cache_request.AddProperty(prop)
        desktop = iuia.GetRootElement()
        walker = iuia.ControlViewWalker
        top = iuia.GetFocusedElement()
        if top is None:
            return []
        while True:
            parent = walker.GetParentElement(top)
            if parent is None or iuia.CompareElements(parent, desktop):
                break
            top = parent
        found, _count = uia_shortcuts(iuia, top, cache_request)
        return found
    except Exception:
        return []
