"""Is the focused window one of PolyHost's own?

PolyHost runs as a bare interpreter (`python -m polyhost`), so the window
tracker reports its windows as `python3` / `pythonw` / `Python`. Everything
keyed on that name then describes the interpreter rather than the app: the
generic mark on ESC resolved to the Python logo, from the executable's own
icon and from the catalog alike.

The executable cannot tell the two apart, so this reads the process's COMMAND
LINE. Every launcher we ship (autostart, the post-update relaunch, the daemon
spawn) starts `-m polyhost`, which is what `argv_is_polyhost` looks for.

`own_app_name()` is the one entry point. It renames a PolyHost window to
`POLYHOST_APP` and leaves every other name alone, so the window handler and the
forwarder cannot disagree about which windows are ours.

⚠️ The command line is read only when the name is a Python runtime, so a
non-Python window never pays for it. The handler asks once per window change;
the forwarder asks on each report tick, which is one `/proc` read or one
`NtQueryInformationProcess` call.

⚠️ The Windows and macOS readers are ctypes calls this suite cannot execute.
Their parsing is unit-tested; the calls themselves need a hardware round.
"""

from __future__ import annotations

import logging
import os
import re
import sys

# The name a PolyHost window is reported under. `app_icons.program_overlay`
# draws the built-in PolyKybd mark for it.
POLYHOST_APP = "polyhost"

_log = logging.getLogger("PolyHost")

# `python3`, `python3.11`, `pythonw`, `Python` (macOS reports the bundle name),
# with or without `.exe`.
_RUNTIME_RE = re.compile(r"^pythonw?(\d+(\.\d+)*)?(\.exe)?$", re.IGNORECASE)

# Interpreter options that consume the NEXT argument (`-X utf8`, `-W ignore`).
_OPTS_WITH_ARG = frozenset(("-X", "-W", "-Q"))


def is_python_runtime(app_name) -> bool:
    return bool(app_name) and bool(_RUNTIME_RE.match(app_name.strip()))


def argv_is_polyhost(argv) -> bool:
    """Whether an interpreter command line runs the `polyhost` package.

    Walks the options the way the interpreter does, so `python -X utf8 -m
    polyhost` counts and `python tool.py -m polyhost` does not. A script path
    counts when it is the package's own `__main__.py` (an IDE launch).
    """
    args = list(argv or ())[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-m":
            module = args[i + 1] if i + 1 < len(args) else ""
            return module == "polyhost" or module.startswith("polyhost.")
        if arg.startswith("-m"):
            module = arg[2:]
            return module == "polyhost" or module.startswith("polyhost.")
        if arg in _OPTS_WITH_ARG:
            i += 2
            continue
        if arg == "-c" or arg == "-":
            return False
        if arg.startswith("-"):
            i += 1
            continue
        # The first non-option is the script, and nothing after it is ours.
        parts = re.split(r"[\\/]", arg)
        return len(parts) >= 2 and parts[-1] == "__main__.py" \
            and parts[-2] == "polyhost"
    return False


def parse_procargs2(raw: bytes):
    """argv out of a macOS `KERN_PROCARGS2` buffer, or None.

    Layout: a native int argc, the executable path, NUL padding, then argc
    NUL-terminated strings (the environment follows and is ignored).
    """
    if len(raw) < 4:
        return None
    argc = int.from_bytes(raw[:4], sys.byteorder)
    rest = raw[4:]
    end = rest.find(b"\0")
    if end < 0:
        return None
    pos = end
    while pos < len(rest) and rest[pos] == 0:
        pos += 1
    argv = []
    for _ in range(argc):
        end = rest.find(b"\0", pos)
        if end < 0:
            return None
        argv.append(rest[pos:end].decode("utf-8", "replace"))
        pos = end + 1
    return argv


def _linux_argv(pid):
    with open("/proc/%d/cmdline" % int(pid), "rb") as fh:
        raw = fh.read()
    return [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]


def _macos_argv(pid):
    import ctypes
    import ctypes.util

    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    ctl_kern, kern_argmax, kern_procargs2 = 1, 8, 49
    argmax = ctypes.c_int(0)
    size = ctypes.c_size_t(ctypes.sizeof(argmax))
    mib = (ctypes.c_int * 2)(ctl_kern, kern_argmax)
    if libc.sysctl(mib, 2, ctypes.byref(argmax), ctypes.byref(size), None, 0):
        return None
    buf = ctypes.create_string_buffer(argmax.value)
    size = ctypes.c_size_t(argmax.value)
    mib = (ctypes.c_int * 3)(ctl_kern, kern_procargs2, int(pid))
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0):
        return None
    # Only the filled bytes: `buf.raw` would copy the whole argmax buffer first.
    return parse_procargs2(ctypes.string_at(buf, size.value))


def _windows_argv(pid):
    """argv via NtQueryInformationProcess(ProcessCommandLineInformation).

    That info class (60, Windows 8.1+) needs only QUERY_LIMITED_INFORMATION,
    the same right `win_process` already opens with. The PEB walk it replaces
    needs VM_READ and fails across integrity levels.

    ⚠️ Every restype is explicit: a HANDLE or a pointer left at ctypes' default
    `c_int` is truncated on 64-bit (see `win_process._load_win32`).
    """
    import ctypes
    import ctypes.wintypes
    wintypes = ctypes.wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    ntdll.NtQueryInformationProcess.argtypes = [
        wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong)]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR,
                                           ctypes.POINTER(ctypes.c_int)]
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)

    class UnicodeString(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort),
                    ("MaximumLength", ctypes.c_ushort),
                    ("Buffer", ctypes.c_void_p)]

    process_query_limited_information = 0x1000
    process_command_line_information = 60
    handle = kernel32.OpenProcess(process_query_limited_information, False,
                                  int(pid))
    if not handle:
        return None
    try:
        needed = ctypes.c_ulong(0)
        # The first call only sizes the buffer; its status is the expected
        # STATUS_INFO_LENGTH_MISMATCH.
        ntdll.NtQueryInformationProcess(handle, process_command_line_information,
                                        None, 0, ctypes.byref(needed))
        if not needed.value:
            return None
        buf = ctypes.create_string_buffer(needed.value)
        status = ntdll.NtQueryInformationProcess(
            handle, process_command_line_information, buf, needed,
            ctypes.byref(needed))
        if status != 0:
            return None
        text = UnicodeString.from_buffer(buf)
        if not text.Buffer:
            return None
        command_line = ctypes.wstring_at(text.Buffer, text.Length // 2)
    finally:
        kernel32.CloseHandle(handle)
    argc = ctypes.c_int(0)
    argv_ptr = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not argv_ptr:
        return None
    try:
        return [argv_ptr[i] for i in range(argc.value)]
    finally:
        kernel32.LocalFree(argv_ptr)


def process_argv(pid):
    """The command line of process `pid` as a list, or None if unreadable."""
    try:
        if sys.platform.startswith("linux"):
            return _linux_argv(pid)
        if sys.platform == "darwin":
            return _macos_argv(pid)
        if sys.platform == "win32":
            return _windows_argv(pid)
    except Exception:
        # A process that exited between the focus change and here, or one we
        # may not inspect. Either way the window keeps its runtime name.
        _log.debug("Could not read the command line of pid %s", pid,
                   exc_info=True)
    return None


def is_polyhost_process(pid) -> bool:
    if pid is None:
        return False
    try:
        if int(pid) == os.getpid():
            return True
    except (TypeError, ValueError):
        return False
    return argv_is_polyhost(process_argv(pid) or ())


def window_pid(win):
    """`win.getPID()`, or None for a backend that has none or fails.

    pywinctl's windows implement it; the KDE and GNOME Wayland reporters do not.
    """
    try:
        return win.getPID() if win is not None else None
    except Exception:
        return None


def _macos_top_window():
    """`(owner pid, owner name)` of the topmost normal window, or None.

    From the window server: in-process and fresh on any thread, unlike
    `NSWorkspace`'s KVO properties (see `active_window.frontmost_app`).
    """
    import Quartz
    options = (Quartz.kCGWindowListOptionOnScreenOnly
               | Quartz.kCGWindowListExcludeDesktopElements)
    for info in Quartz.CGWindowListCopyWindowInfo(
            options, Quartz.kCGNullWindowID) or ():
        if info.get("kCGWindowLayer") == 0:
            return (int(info.get("kCGWindowOwnerPID")),
                    info.get("kCGWindowOwnerName") or "")
    return None


def parse_lsappinfo_pid(text):
    """The pid out of `lsappinfo info -only pid` output (`"pid"=35938`)."""
    match = re.search(r'"pid"\s*=\s*(\d+)', text or "")
    return int(match.group(1)) if match else None


def _macos_launchservices_front_pid():
    """The front application's pid, as LaunchServices (the menu bar) sees it."""
    import subprocess
    # Audit: fixed argv, no shell, no user input; `lsappinfo` is a system
    # binary. The second call takes the ASN the first one printed.
    front = subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        ["lsappinfo", "front"], capture_output=True, text=True, timeout=2)
    asn = (front.stdout or "").strip()
    if not asn:
        return None
    info = subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        ["lsappinfo", "info", "-only", "pid", asn],
        capture_output=True, text=True, timeout=2)
    return parse_lsappinfo_pid(info.stdout)


def own_front_app():
    """`(POLYHOST_APP, pid)` when a PolyHost window is in front on macOS.

    ⚠️ pywinctl cannot answer this on macOS. It asks System Events for the
    process "whose frontmost is true", and with a PolyHost window focused
    System Events answered Terminal, or failed outright ("Can't get
    {loginwindow, 156} whose frontmost = true"), while LaunchServices and
    the window server both named our Python process (measured 2026-09-23).

    The window server is asked first because it is one in-process call per
    tick. LaunchServices is asked only when the top window is ours, and it
    must agree: a PolyHost window stays topmost when the user activates an
    app that has no window of its own.

    None everywhere else, and on any failure: the caller falls back to
    pywinctl, which is today's behaviour.
    """
    if sys.platform != "darwin":
        return None
    try:
        top = _macos_top_window()
        if top is None:
            return None
        pid, owner = top
        # ⚠️ The owner NAME gates the command-line read, as it does in
        # `own_app_name`: this runs every tick, and each macOS read allocates
        # a `kern.argmax`-sized buffer (about 1 MiB). Only a Python runtime
        # can be PolyHost; our own pid is accepted whatever it is called.
        if pid != os.getpid() and not is_python_runtime(owner):
            return None
        if not is_polyhost_process(pid):
            return None
        front = _macos_launchservices_front_pid()
        if front is not None and front != pid:
            return None
        return POLYHOST_APP, pid
    except Exception:
        _log.debug("Could not read the macOS front window", exc_info=True)
        return None


def own_app_name(app_name, pid, own_window_active=False):
    """`POLYHOST_APP` for a PolyHost window, `app_name` unchanged otherwise.

    ⚠️ The GNOME Wayland and KDE reporters have no pid and name a window by its
    WM class, which `main_app` sets to `PolyHost`. That name is ours alone, so
    it is accepted without a command-line read.

    `own_window_active` is the calling process's own answer: Qt's
    `activeWindow()` is set exactly while one of its windows has focus. It
    needs no pid, and it is the check that caught the forwarder's Log Viewer,
    which a GNOME forwarder reported as `python` with a pid that was neither
    its own nor a `-m polyhost` command line (field, 2026-09-23). It is
    honoured only for a name that could be ours, so a focus change caught
    between the backend's read and Qt's cannot relabel another application.
    """
    if app_name and app_name.strip().lower() == POLYHOST_APP:
        return POLYHOST_APP
    if own_window_active and (not app_name or is_python_runtime(app_name)):
        return POLYHOST_APP
    if is_python_runtime(app_name) and is_polyhost_process(pid):
        return POLYHOST_APP
    return app_name


def describe_python_owner(pid) -> str:
    """Why a Python window was not taken for ours, for a one-off log line."""
    return "pid %s, this process %s, argv %s" % (
        pid, os.getpid(), process_argv(pid) if pid is not None else None)
