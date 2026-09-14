"""Resolve the process name behind a window handle on Windows, without WMI.

pywinctl's ``Win32Window.getAppName()`` answers "which app owns this window?"
the expensive way (``_pywinctl_win.py``)::

    WMI = GetObject('winmgmts:')
    return [(p.Properties_("ProcessID").Value, p.Properties_("Name").Value)
            for p in WMI.InstancesOf('Win32_Process')]

So every window change opens a WMI connection and wraps EVERY process on the
machine through ``win32com``'s ``_get_good_object_`` -> ``Dispatch`` to read one
name. ⚠️ **That walk killed the daemon twice on 2026-09-14** (0.19.5, Python
3.13): a COM proxy in the enumeration went away mid-walk (``RPC_E_DISCONNECTED``,
0x80010108) and pywin32 dereferenced it, raising a Windows **access violation**
inside ``__WrapDispatch``. An access violation is not a Python exception, so the
``try/except Exception`` around the call site cannot catch it — the whole
headless daemon vanished with no log line, taking the HID device with it while
the keyboard kept running. The tray survived as a client with a dead pipe.

``QueryFullProcessImageNameW`` answers the same question from the PID the window
already carries: no COM, no WMI, one process instead of all of them.

Windows only. Every other backend is cheap or free already — macOS returns a
cached attribute, the Linux/KDE/GNOME reporters have the name in hand — so they
keep calling ``getAppName()``.
"""

import ctypes
import logging
import os
import sys

_log = logging.getLogger("polyhost")

# Vista+. Deliberately NOT PROCESS_QUERY_INFORMATION: the LIMITED right is the
# one granted across integrity levels for exactly this query, so an elevated
# app's window still resolves from an unelevated daemon.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
# QueryFullProcessImageNameW takes the \\?\-capable ceiling, not MAX_PATH.
_MAX_PATH_W = 32768

_win32 = None


def _load_win32():
    """Bind the three calls once, with explicit arg/restypes.

    ⚠️ ``OpenProcess`` returns a HANDLE. Without an explicit ``restype`` ctypes
    defaults to ``c_int`` and TRUNCATES it on 64-bit, so the handle closes the
    wrong thing (or nothing) — the classic way this lookup goes subtly wrong.
    """
    global _win32
    if _win32 is not None:
        return _win32
    from ctypes import wintypes  # fails to import off Windows

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    _win32 = (user32, kernel32, wintypes)
    return _win32


def win32_process_name(hwnd):
    """``"chrome.exe"`` for a window handle, or ``""`` when it can't be read."""
    user32, kernel32, wintypes = _load_win32()

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(_MAX_PATH_W)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return os.path.basename(buf.value)
    finally:
        kernel32.CloseHandle(handle)


def app_name_for(win):
    """The owning app's name for `win`, the cheap way on Windows.

    Off Windows this is ``win.getAppName()`` unchanged. On Windows a failed
    lookup falls back to the window TITLE, which is what pywinctl's own
    implementation returns when the PID is missing from its process list — so
    the caller's normalisation sees exactly what it saw before.
    """
    if sys.platform != "win32":
        return win.getAppName()
    try:
        name = win32_process_name(win.getHandle())
    except Exception:
        # Never let this kill a tick: the window may have closed between
        # getActiveWindow() and here.
        _log.debug("Process-name lookup failed for the focused window", exc_info=True)
        name = ""
    return name or win.title
