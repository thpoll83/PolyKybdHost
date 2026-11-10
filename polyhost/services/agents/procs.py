"""Process helpers for the agent registry: find the agent's own process from a hook,
and tell whether a process still runs.

A hook command's parent is often a shell the agent started just for that hook
(bash, cmd, PowerShell), which exits right after. On Windows polyctl itself is two
or three processes too: pip's `polyctl.exe` launcher, the venv's `python.exe` stub
and the real Python. `agent_pid()` first walks up past that launcher chain, then
past the shells, to the agent's own process (claude, node, codex, copilot), whose
life is the session's. The registry removes an entry once that process is gone, but only
after it has seen it alive once, so a wrong pid cannot remove a live agent.
"""
from __future__ import annotations

import os
import subprocess
import sys

# Programs that run a hook for the agent and are not the agent itself.
SHELLS = frozenset({
    "sh", "bash", "dash", "zsh", "fish", "ksh", "env", "sudo", "timeout", "nohup",
    "cmd.exe", "powershell.exe", "pwsh.exe", "pwsh", "bash.exe", "sh.exe",
    "conhost.exe", "wsl.exe", "git-bash.exe",
})
# polyctl's own launcher chain on Windows (pip console script, venv stub, py
# launcher). Skipped only directly above this process, before the first shell, so
# an agent that is itself a Python program (aider) is still found.
LAUNCHERS = frozenset({
    "polyctl", "polyctl.exe", "python", "python3", "python.exe", "python3.exe",
    "pythonw.exe", "py.exe",
})
MAX_DEPTH = 10


def _is_launcher(name: str) -> bool:
    """`name` (lower case) is in LAUNCHERS or is a versioned Python, such as
    `python3.13` on Linux or `python3.13.exe`."""
    if name in LAUNCHERS:
        return True
    stem = name[:-4] if name.endswith(".exe") else name
    return stem.startswith("python") and all(c.isdigit() or c in ".w" for c in stem[6:])


def _linux_parent(pid: int):
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
            head, tail = fh.read().rsplit(")", 1)
        name = head.split("(", 1)[1]
        return int(tail.split()[1]), name
    except (OSError, ValueError, IndexError):
        return None


def _windows_table():
    """{pid: (ppid, exe name)} from one Toolhelp snapshot."""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)   # TH32CS_SNAPPROCESS
    if snapshot in (0, -1):
        return {}
    table = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            table[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return table


def _ps_parent(pid: int):
    try:
        out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)],   # nosemgrep
                             capture_output=True, text=True, timeout=2).stdout.strip()
        ppid, name = out.split(None, 1)
        return int(ppid), os.path.basename(name)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _parent_lookup():
    """A function pid -> (ppid, name) or None, for this platform. On Windows it
    reads one Toolhelp snapshot up front, so a walk costs one system call."""
    if sys.platform == "win32":
        table = _windows_table()
        return lambda p: table.get(p)
    if sys.platform.startswith("linux"):
        return _linux_parent
    return _ps_parent


def ancestors(pid: int, depth: int = MAX_DEPTH) -> list[int]:
    """`pid` and its parents, nearest first, at most `depth` long."""
    parent = _parent_lookup()
    chain = []
    while pid and pid > 1 and len(chain) < depth:
        chain.append(pid)
        info = parent(pid)
        if info is None:
            break
        pid = info[0]
    return chain


def agent_pid(start: int | None = None) -> int:
    """The agent's process for a hook running in process `start` (default: this
    process). Walks up past polyctl's own launcher chain (LAUNCHERS, only before
    the first shell), then past the shells (SHELLS), and returns the first other
    process. Returns 0 when the walk finds none: no pid is better than the pid of
    a process that exits with the hook, because the registry removes an agent
    once its pid is gone."""
    pid = start or os.getpid()
    parent = _parent_lookup()
    in_launchers = True
    for _ in range(MAX_DEPTH):
        info = parent(pid)
        if info is None:
            return 0
        ppid, name = info
        name = name.lower()
        if in_launchers and _is_launcher(name):
            pass
        elif name in SHELLS:
            in_launchers = False
        else:
            return pid
        if ppid <= 1:
            return 0
        pid = ppid
    return 0


def is_alive(pid: int) -> bool:
    """Whether process `pid` runs (a zombie on Linux counts as gone)."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259                         # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
                return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False
    return True
