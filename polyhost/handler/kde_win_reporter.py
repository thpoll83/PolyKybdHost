import logging
import os
import pathlib
import subprocess
from datetime import datetime

_log = logging.getLogger("PolyHost")


def getActiveWindow():
    script = os.path.join(pathlib.Path(__file__).parent.resolve(), "active_win.js")

    output = (
        subprocess.run(
            "dbus-send --print-reply --dest=org.kde.KWin \
                        /Scripting org.kde.kwin.Scripting.loadScript \
                        string:" + script,
            capture_output=True,
            shell=True,
        )
        .stdout.decode()
        .split("\n")
    )
    reg_script_number = None
    for line in reversed(output):
        if "int32" in line:
            reg_script_number = line.split()[-1]
            break

    if reg_script_number is None:
        _log.warning("KWin: could not find script number in dbus output (transient)")
        return None
    try:
        reg_script_number = str(int(reg_script_number))
    except ValueError:
        _log.warning("KWin: unexpected script number format '%s' (transient)", reg_script_number)
        return None
    
    datetime_now = datetime.now()
    subprocess.run(
        "dbus-send --print-reply --dest=org.kde.KWin /Scripting/Script"
        + reg_script_number
        + " org.kde.kwin.Script.run",
        shell=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        "dbus-send --print-reply --dest=org.kde.KWin /Scripting/Script"
        + reg_script_number
        + " org.kde.kwin.Script.stop",
        shell=True,
        stdout=subprocess.DEVNULL,
    )

    since = str(datetime_now)

    msg = (
        subprocess.run(
            'journalctl _COMM=kwin_wayland -o cat --since "' + since + '"',
            capture_output=True,
            shell=True,
        )
        .stdout.decode()
        .rstrip()
        .split("\n")
    )
    result = [elem.removeprefix("js: ") for elem in msg]
    if not result or not result[0]:
        return None  # transient: KWin script produced no output this cycle
    try:
        return KWin(result)
    except ValueError as e:
        _log.warning("KWin: malformed window response (transient): %s", e)
        return None


class KWin:
    def __init__(self, msg):
        elems = msg[0].split(";")
        if len(elems) != 3:
            raise ValueError(f"Unexpected format reported by KWin Script: '{msg}'")

        self.name = elems[0]
        self.title = elems[1]
        self.handle = int(elems[2]) if len(elems[2])>0 else hash(self.name)
        # log = logging.getLogger("PolyHost")
        # log.info("KWin %s", msg)
    
    def getHandle(self):
        return self.handle
    
    def getAppName(self):
        return self.name

    def __eq__(self, other):
        if not other:
            return False
        return self.handle == other.getHandle()


# reporter = KdeWindowReporter()
# win = reporter.getActiveWindow()
# print(f"Title: {win.title} Handle: {win.getHandle()} Name: {win.getAppName()}")
