"""Is the focused `explorer.exe` window the Windows SHELL rather than File Explorer?

The taskbar, the desktop and File Explorer are one process, so the tracker names
all three `explorer` and the taskbar used to get File Explorer's keycaps (new
window, rename, …), none of which do anything there (hardware round,
2026-09-29). The taskbar's own keys (arrows, Enter, Shift+F10) are not drawn by
any template, and the Win-key shortcuts that work there are global and already
hinted by the firmware while Win is held. So the shell should draw nothing.

`shell_app_name()` renames a shell window to `SHELL_APP`. No mapping entry
carries that name, the shortcut harvest finds nothing on the taskbar, and the
ESC mark is never sent on its own -- so nothing is drawn. The name also gives a
future shell template a key of its own.

⚠️ It goes by the Win32 window CLASS, not the title. A title gate cannot do it:
`find_matching_entry` skips a `title:` regex when the title is empty, on
purpose, because macOS without screen-recording permission and some Wayland
setups report no titles at all -- and the taskbar's title IS empty.

⚠️ `window_class()` is a ctypes call this suite cannot execute. The decision is
unit-tested with an injected reader; the call itself needs a hardware round.
"""

from __future__ import annotations

import sys

SHELL_APP = "windows-shell"

# The taskbar on the primary monitor, the taskbar on any other monitor, and the
# desktop (Progman, or the WorkerW that hosts the icons behind a wallpaper).
SHELL_CLASSES = frozenset({"Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                           "Progman", "WorkerW"})


def window_class(handle) -> str | None:
    """The Win32 class name of `handle`, or None off Windows or on any failure."""
    if sys.platform != "win32" or not isinstance(handle, int):
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        if ctypes.windll.user32.GetClassNameW(handle, buf, len(buf)):
            return buf.value
    except Exception:       # noqa: BLE001 - a cosmetic lookup must not break tracking
        pass
    return None


def shell_app_name(app_name, handle, class_of=window_class):
    """`SHELL_APP` for the taskbar or desktop, `app_name` unchanged otherwise.

    Takes the name with or without `.exe` and in any case, since the handler
    strips it and the forwarder does not. The class is read only for
    `explorer`, so no other window pays for the call.
    """
    if not app_name:
        return app_name
    stem = app_name.strip().lower()
    if stem.endswith(".exe"):
        stem = stem[:-4]
    if stem != "explorer":
        return app_name
    return SHELL_APP if class_of(handle) in SHELL_CLASSES else app_name
