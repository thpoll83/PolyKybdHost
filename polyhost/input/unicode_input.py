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
    elif os.startswith("linux"):
        return OsType.LINUX
    elif os.startswith("freebsd"):
        return OsType.LINUX
    return OsType.UNKNOWN