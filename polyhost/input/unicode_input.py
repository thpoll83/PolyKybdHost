import sys
import subprocess
from enum import Enum


class InputMethod(Enum):
    Linux = 0
    Mac = 1
    Windows = 2
    WinCompose = 3
    BSD = 4
    Unknown = 5

def process_exists(process_name):
    call = 'TASKLIST', '/FI', 'imagename eq %s' % process_name
    output = str(subprocess.check_output(call))
    return process_name in output

def get_input_method():
    os = sys.platform
    if os == "linux":
        return InputMethod.Linux
    elif os == "darwin":
        return InputMethod.Mac
    elif os == "win32":
        return InputMethod.WinCompose if process_exists("wincompose.exe") else InputMethod.Windows
    elif os.startswith('freebsd'):
        return InputMethod.BSD
    return InputMethod.Unknown


def get_host_os():
    """The OS identity to push to the keyboard (cmd 29), independent of the unicode
    input mode. BSD maps to Linux for shortcut purposes (the firmware has no BSD OS;
    its Ctrl-based chords match). Android/iOS never originate here — the host app
    doesn't run on them — so they only ever come from firmware detection or a manual
    pin on the keyboard."""
    from polyhost.device.command_ids import OsType
    os = sys.platform
    if os == "win32":
        return OsType.WINDOWS
    elif os == "darwin":
        return OsType.MACOS
    elif os.startswith("linux") or os.startswith("freebsd"):
        # BSD with a KDE/GNOME desktop shares those Super-key shortcuts; falls back
        # to plain LINUX otherwise (the firmware has no separate BSD OS).
        return _linux_de_os()
    return OsType.UNKNOWN


def _linux_de_os():
    """Refine a Linux host into a desktop-environment-specific OsType so the
    keyboard can show DE-correct Super-key hints. Only GNOME and KDE differ enough
    to model (GNOME: Super+Tab switches apps, no Super+D; KDE: Alt+Tab + Super+D);
    everything else (XFCE, Cinnamon, MATE, …) is Windows-like and stays plain LINUX.
    Reads $XDG_CURRENT_DESKTOP (colon-separated, e.g. "ubuntu:GNOME")."""
    from polyhost.device.command_ids import OsType
    import os as _os
    desktop = (_os.environ.get("XDG_CURRENT_DESKTOP")
               or _os.environ.get("XDG_SESSION_DESKTOP")
               or _os.environ.get("DESKTOP_SESSION") or "").lower()
    if "kde" in desktop or "plasma" in desktop:
        return OsType.LINUX_KDE
    if "gnome" in desktop:
        return OsType.LINUX_GNOME
    return OsType.LINUX