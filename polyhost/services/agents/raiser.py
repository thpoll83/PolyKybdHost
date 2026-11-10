"""Bring an agent's window to the front.

Order of attempts: the window the title scanner saw; a window owned by the
agent's process or one of its ancestors (a CLI runs inside a terminal, whose
process is an ancestor, on Linux); a window whose title contains the headline; a
window whose title is this vendor's own title format (titles.parse_title).

The last one exists because the ancestor walk does not reach the window on
Windows and macOS: Windows Terminal and Terminal.app are not ancestors of the
shell. Claude Code, Gemini CLI and Codex write their own title, so the window is
found by that title instead. With several such windows the one whose title names
the headline is taken first.

Limits (docs/agent-registry-plan.md): a terminal tab or an IDE panel is not a
window, so the raise brings the window forward and stops there. Native Wayland
offers no window activation to clients.
"""
from __future__ import annotations

import os
import sys


def _ancestors(pid: int, depth: int = 8) -> list[int]:
    """pid and its parents, on Linux from /proc. Elsewhere only pid itself."""
    chain = []
    while pid and pid > 1 and len(chain) < depth:
        chain.append(pid)
        if not sys.platform.startswith("linux"):
            break
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
                # The command name may contain spaces; the ppid follows the last ')'.
                pid = int(fh.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return chain


def _win32_force_foreground(hwnd: int) -> bool:
    """Bring `hwnd` to the front on Windows, and say whether it got there.

    ⚠️ Windows refuses SetForegroundWindow from a process that did not receive the
    last input event, and the host daemon is such a process: pywinctl's activate()
    then only flashes the taskbar button. The usual way round it: restore a minimized
    window, attach to the foreground thread's input queue for the call, and if that
    is not enough, send a lone Alt press, which makes this process the last input.
    """
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    SW_RESTORE, VK_MENU, KEYEVENTF_KEYUP = 9, 0x12, 0x0002
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    me = kernel32.GetCurrentThreadId()
    attached = bool(fg_thread and fg_thread != me
                    and user32.AttachThreadInput(me, fg_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, fg_thread, False)
    if user32.GetForegroundWindow() == hwnd:
        return True
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)
    return user32.GetForegroundWindow() == hwnd


def raise_agent(agent, windows=None):
    """True when a window was brought to the front; False when none was found; a
    text when one was found but the system kept the focus elsewhere. `windows` is
    for tests: an iterable of objects with getHandle(), getPID(), title and
    activate()."""
    if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
        return False
    windows_from_system = windows is None
    if windows is None:
        import pywinctl
        windows = pywinctl.getAllWindows()
    windows = list(windows)

    def handle(w):
        try:
            return str(w.getHandle())
        except Exception:   # noqa: BLE001
            return ""

    def pid_of(w):
        try:
            return int(w.getPID() or 0)
        except Exception:   # noqa: BLE001
            return 0

    target = None
    if agent.window:
        target = next((w for w in windows if handle(w) == agent.window), None)
    if target is None and agent.pid:
        chain = _ancestors(agent.pid)
        for pid in chain:
            target = next((w for w in windows if pid_of(w) == pid), None)
            if target is not None:
                break
    if target is None and agent.display_headline:
        text = agent.display_headline.lower()
        target = next((w for w in windows if text in (w.title or "").lower()), None)
    if target is None:
        from polyhost.services.agents.titles import parse_title
        own = []
        for w in windows:
            parsed = parse_title(w.title or "")
            if parsed is not None and parsed[0] == agent.vendor:
                own.append((w, parsed[2]))
        text = (agent.display_headline or "").lower()
        target = next((w for w, topic in own if text and text in (topic or "").lower()),
                      own[0][0] if own else None)
    if target is None:
        return False
    if sys.platform == "win32" and windows_from_system:
        try:
            if _win32_force_foreground(int(target.getHandle())):
                return True
            return f"Windows kept the focus elsewhere (window '{target.title}')"
        except Exception:   # noqa: BLE001 - fall back to pywinctl below
            pass
    target.activate()
    return True
