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

import gc
import importlib
import sys
import threading

from polyhost.services.shortcut_source.model import (
    Shortcut, TREESCOPE_SUBTREE, UIA_CONTROL_TYPES, UIA_PROP_ACCELERATOR,
    UIA_PROP_ACCESS_KEY, UIA_PROP_CONTROL_TYPE, UIA_PROP_NAME,
    UIA_PROP_PROCESS_ID, is_window_manager_chord, parse_win_accel,
    pick_win_binding)


# ⚠️ PER THREAD, never module-global. The harvest thread
# (`ShortcutIconFetcher._loop`) exits after 30 s idle and the next window change
# starts a new one. A module-global cache handed the FIRST thread's COM object to
# every later thread, and comtypes initializes COM only on the thread that first
# imports it -- so each later thread called into an object whose apartment had
# died with its thread, from a thread with COM not initialized at all. On
# Windows 11 / 1.1.7 that raised RPC_E_DISCONNECTED (0x80010108) every few
# minutes and, after 92 minutes, an access violation that took the headless
# daemon down with no log line (field, 2026-09-23). Each thread now initializes
# COM itself, builds its own IUIAutomation, and releases both through
# `release_thread()` before it exits.
_local = threading.local()

# COINIT_APARTMENTTHREADED: what comtypes itself uses at import, so the first
# thread and every later one land in the same kind of apartment.
_COINIT_APARTMENTTHREADED = 0x2


def _comtypes_loaded() -> bool:
    """Whether comtypes has been imported (its import initializes COM)."""
    return "comtypes" in sys.modules


def _co_initialize() -> bool:
    """CoInitializeEx on this thread; True if the call must be balanced.

    S_OK and S_FALSE both take a reference that CoUninitialize must drop.
    Anything else (RPC_E_CHANGED_MODE: the thread is already in another
    apartment) took none, so there is nothing to undo.
    """
    import ctypes
    hr = ctypes.windll.ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED)
    return hr in (0, 1)


def _co_uninitialize() -> None:
    import ctypes
    ctypes.windll.ole32.CoUninitialize()


def _enter_apartment() -> None:
    """Initialize COM on this thread, once, and remember whether we own it.

    ⚠️ The FIRST import of comtypes calls CoInitializeEx on the importing thread
    itself. Calling it again there would take a second reference that nothing
    drops, leaving the dead thread's apartment counted as live. So on the
    importing thread the import IS the initialization, and we own it.
    """
    if getattr(_local, "com_entered", False):
        return
    if _comtypes_loaded():
        owned = _co_initialize()
    else:
        # Imported for its side effect: it initializes COM on this thread.
        importlib.import_module("comtypes")
        owned = True
    _local.com_entered = True
    _local.com_owned = owned


def _uia():
    """This thread's IUIAutomation instance, created once per thread.

    Cached because watch mode polls the focused element every interval, and
    building the COM object per poll is pure overhead.
    """
    cached = getattr(_local, "uia", None)
    if cached is not None:
        return cached
    _enter_apartment()
    import comtypes.client
    module = comtypes.client.GetModule("UIAutomationCore.dll")
    iuia = comtypes.client.CreateObject(
        "{ff48dba4-60ef-4201-aa87-54103eef594e}",  # CLSID_CUIAutomation
        interface=module.IUIAutomation,
    )
    _local.uia = (module, iuia)
    return _local.uia


def release_thread() -> None:
    """Drop this thread's COM objects, then leave its apartment.

    Call it on the thread that used the backend, before that thread exits.
    The order matters: a COM pointer released AFTER CoUninitialize calls into a
    torn-down apartment, which is the crash this exists to prevent. Hence the
    `gc.collect()` between the two, for any pointer a reference cycle still
    holds. Never raises.
    """
    try:
        if getattr(_local, "uia", None) is not None:
            _local.uia = None
            gc.collect()
        if getattr(_local, "com_owned", False):
            _co_uninitialize()
    except Exception:
        # Runs on a thread's way out, for a cosmetic feature: a failure here
        # must not become a thread exception in crash_log.txt.
        pass
    finally:
        _local.com_entered = False
        _local.com_owned = False


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


def shortcuts_for_app(name: str = "", reason: dict | None = None,
                      pid: int | None = None) -> list[Shortcut]:
    """Every shortcut the FOCUSED top-level window exposes.

    ⚠️ `name` is accepted and ignored, so the two backends share one signature.
    UIA answers "what has focus" directly and far more cheaply than it answers
    "find the window called X" -- and the caller only ever asks about the app it
    already believes is focused, so resolving by name would be a second, slower
    opinion about the same thing.

    Returns [] on any failure, for the reason the AT-SPI side does.

    `reason` and `pid` are accepted and unused -- see the note on the AT-SPI
    side for why all three backends carry them regardless.
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
