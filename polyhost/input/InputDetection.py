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