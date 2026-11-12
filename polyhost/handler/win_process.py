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
    # Lazy and submodule-qualified: `ctypes.wintypes` raises on import off
    # Windows, so it cannot sit at module scope — this module has to stay
    # importable everywhere for the `sys.platform` branch in app_name_for to
    # be reachable at all. Spelled `import ctypes.wintypes` rather than
    # `from ctypes import wintypes` so the module is imported one way only
    # (CodeQL py/import-and-import-from).
    import ctypes.wintypes
    wintypes = ctypes.wintypes

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


def _win32_image_path(pid):
    """The full path of process `pid`'s executable, or ``""``."""
    _user32, kernel32, wintypes = _load_win32()
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(_MAX_PATH_W)
        buf = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value
    finally:
        kernel32.CloseHandle(handle)


def win32_process_name(hwnd):
    """``"chrome.exe"`` for a window handle, or ``""`` when it can't be read."""
    user32, _kernel32, wintypes = _load_win32()

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    if not pid.value:
        return ""
    return os.path.basename(_win32_image_path(pid.value))


#: The Wine and Proton loaders. A Windows game under Proton runs as one of
#: these, so /proc/<pid>/exe names the loader and not the game.
_WINE_LOADERS = frozenset({"wine", "wine64", "wine-preloader", "wine64-preloader"})


def process_dir(pid):
    """The folder of process `pid`'s executable, or None when it can't be read.

    Under Wine or Proton the executable is the loader, so this returns the
    process's working folder instead: Proton starts a game in its install
    folder (not checked for every game). macOS answers None.
    """
    if not pid:
        return None
    try:
        if sys.platform == "win32":
            path = _win32_image_path(int(pid))
            return os.path.dirname(path) or None
        if sys.platform.startswith("linux"):
            exe = os.readlink(f"/proc/{pid}/exe").removesuffix(" (deleted)")
            if os.path.basename(exe) in _WINE_LOADERS:
                return os.readlink(f"/proc/{pid}/cwd")
            return os.path.dirname(exe) or None
    except (OSError, ValueError, AttributeError):
        # The process may have exited; a missing hint only costs the search.
        _log.debug("No folder for process %s", pid, exc_info=True)
    return None


#: What pywinctl's Linux ``getAppName()`` (``ps -o comm=``) reports when the
#: name says nothing about which app owns the window (measured under X11,
#: 2026-10-22):
#:
#: - ``main``: MuseScore Studio 4 and Audacity 4 rename their main thread to it
#:   (the 4.7.5 and 4.0.1 AppImages).
#: - ``AppRun``: an AppImage whose ``AppRun`` is a symlink to the binary runs
#:   under that name (the OpenSCAD 2026.10.18 nightly). ``comm`` is the name of
#:   the path that was executed, not of the file it points to.
_UNINFORMATIVE_NAMES = frozenset({"main", "AppRun"})

#: The kernel keeps 15 BYTES of a process name (``TASK_COMM_LEN`` 16 with the
#: terminating NUL), and ``ps -o comm=`` prints that copy. A name of exactly
#: this length may be cut short: GNOME Terminal's ``gnome-terminal-server`` is
#: reported as ``gnome-terminal-``, so neither of the terminal entry's keys
#: matched and no editor overlay (nano, vim) was shown in it (Ubuntu GNOME on
#: X11 through the forwarder, ``Active App: 'nano' gnome-terminal-``,
#: 2026-11-05).
_COMM_LEN = 15


def _linux_exe_name(win):
    """Basename of ``/proc/<pid>/exe`` for `win`, or ``""`` when unreadable.

    The executable's file name, which a thread rename does not change:
    ``mscore4portable`` where ``comm`` says ``main``, ``openscad`` where it
    says ``AppRun``.
    """
    # Imported here: own_process is the one place that knows every way a
    # backend exposes the pid (PyWinCtl 0.3 has no getPID() on Linux).
    from polyhost.handler.own_process import window_pid
    try:
        pid = window_pid(win)
        if not pid:
            return ""
        path = os.readlink(f"/proc/{pid}/exe")
    except Exception:
        return ""
    # The kernel appends this when the file was replaced while running.
    return os.path.basename(path.removesuffix(" (deleted)"))


def app_name_for(win):
    """The owning app's name for `win`, the cheap way on Windows.

    Off Windows this is ``win.getAppName()``, except that on Linux a name in
    ``_UNINFORMATIVE_NAMES`` becomes the executable's name, and so does a name
    the kernel cut to ``_COMM_LEN`` bytes when the executable's name starts
    with it. A renamed process (``comm`` set by the program, a different file
    name) keeps its own name. On Windows a failed
    lookup falls back to the window TITLE, which is what pywinctl's own
    implementation returns when the PID is missing from its process list — so
    the caller's normalisation sees exactly what it saw before.
    """
    if sys.platform != "win32":
        name = win.getAppName()
        if not sys.platform.startswith("linux"):
            return name
        if name in _UNINFORMATIVE_NAMES:
            return _linux_exe_name(win) or name
        if isinstance(name, str) and len(os.fsencode(name)) == _COMM_LEN:
            exe = _linux_exe_name(win)
            # Bytes, not characters: the kernel limit counts bytes, so a
            # name with a multi-byte character is cut at fewer than 15.
            if len(os.fsencode(exe)) > _COMM_LEN and exe.startswith(name):
                return exe
        return name
    try:
        name = win32_process_name(win.getHandle())
    except Exception:
        # Never let this kill a tick: the window may have closed between
        # getActiveWindow() and here.
        _log.debug("Process-name lookup failed for the focused window", exc_info=True)
        name = ""
    return name or win.title
